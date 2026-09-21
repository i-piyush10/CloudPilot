from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings


class ClusterError(RuntimeError):
    pass


class ClusterAdapter:
    def replicas(self) -> int:
        raise NotImplementedError

    def scale(self, replicas: int) -> None:
        raise NotImplementedError

    def restart(self) -> None:
        raise NotImplementedError

    def ensure_hpa(self, enabled: bool) -> None:
        raise NotImplementedError


class SimulatedCluster(ClusterAdapter):
    def __init__(self, replicas: int = 1):
        self._replicas = replicas
        self._hpa = False
        self._lock = threading.Lock()

    def replicas(self) -> int:
        with self._lock:
            return self._replicas

    def scale(self, replicas: int) -> None:
        with self._lock:
            self._replicas = replicas

    def restart(self) -> None:
        return None

    def ensure_hpa(self, enabled: bool) -> None:
        with self._lock:
            self._hpa = enabled


@dataclass
class KubernetesApiCluster(ClusterAdapter):
    settings: Settings

    def __post_init__(self) -> None:
        host = os.getenv("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
        port = os.getenv("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        self.base_url = f"https://{host}:{port}"
        token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        if not token_path.exists():
            raise ClusterError("Kubernetes service-account token is unavailable")
        self.token = token_path.read_text().strip()
        import ssl
        self.ssl_context = ssl.create_default_context(cafile=ca_path)

    @property
    def deployment_path(self) -> str:
        return f"/apis/apps/v1/namespaces/{self.settings.namespace}/deployments/{self.settings.deployment}"

    @property
    def hpa_path(self) -> str:
        return f"/apis/autoscaling/v2/namespaces/{self.settings.namespace}/horizontalpodautoscalers/{self.settings.deployment}"

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/merge-patch+json" if method == "PATCH" else "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10, context=self.ssl_context) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise ClusterError(f"Kubernetes API returned {exc.code}: {detail[:240]}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ClusterError(f"Kubernetes API operation failed: {exc}") from exc

    def replicas(self) -> int:
        deployment = self._request("GET", self.deployment_path)
        return int(deployment.get("spec", {}).get("replicas", 1))

    def scale(self, replicas: int) -> None:
        self._request("PATCH", self.deployment_path, {"spec": {"replicas": replicas}})

    def restart(self) -> None:
        self._request(
            "PATCH",
            self.deployment_path,
            {"spec": {"template": {"metadata": {"annotations": {
                "cloudpilot.io/restartedAt": datetime.now(timezone.utc).isoformat()
            }}}}},
        )

    def ensure_hpa(self, enabled: bool) -> None:
        if enabled:
            manifest = {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {"name": self.settings.deployment, "namespace": self.settings.namespace},
                "spec": {
                    "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": self.settings.deployment},
                    "minReplicas": self.settings.min_replicas,
                    "maxReplicas": self.settings.max_replicas,
                    "metrics": [{"type": "Resource", "resource": {
                        "name": "cpu", "target": {"type": "Utilization", "averageUtilization": 65}
                    }}],
                },
            }
            try:
                self._request("GET", self.hpa_path)
                self._request("PATCH", self.hpa_path, {"spec": manifest["spec"]})
            except ClusterError as exc:
                if "returned 404" not in str(exc):
                    raise
                collection = f"/apis/autoscaling/v2/namespaces/{self.settings.namespace}/horizontalpodautoscalers"
                self._request("POST", collection, manifest)
        else:
            try:
                self._request("DELETE", self.hpa_path)
            except ClusterError as exc:
                if "returned 404" not in str(exc):
                    raise


def create_cluster(settings: Settings) -> ClusterAdapter:
    if settings.mode == "kubernetes":
        return KubernetesApiCluster(settings)
    return SimulatedCluster(settings.min_replicas)
