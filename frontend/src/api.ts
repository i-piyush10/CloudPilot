import type { Decision, Experiment, Incident, ScalingMode, Status, Telemetry } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail ?? "CloudPilot request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<Status>("/api/status"),
  telemetry: () => request<{ items: Telemetry[] }>("/api/timeseries?limit=80"),
  decisions: () => request<{ items: Decision[] }>("/api/decisions?limit=8"),
  incidents: () => request<{ items: Incident[] }>("/api/incidents?limit=8"),
  experiments: () => request<{ items: Experiment[] }>("/api/experiments"),
  setMode: (mode: ScalingMode, fixedReplicas?: number) =>
    request<{ mode: ScalingMode }>("/api/mode", {
      method: "POST",
      body: JSON.stringify({ mode, fixed_replicas: fixedReplicas }),
    }),
  tick: () => request<Decision>("/api/control/tick", { method: "POST" }),
  recordFault: (kind: "latency" | "errors" | "pod_restart") =>
    request<{ incident_id: number }>(`/api/faults/${kind}`, { method: "POST" }),
  createExperiment: (scenario: Experiment["scenario"], mode: ScalingMode) =>
    request<{ id: number }>("/api/experiments", {
      method: "POST",
      body: JSON.stringify({ name: `${scenario}-${mode}-${new Date().toISOString()}`, scenario, mode, duration_seconds: 300 }),
    }),
  startExperiment: (id: number) => request(`/api/experiments/${id}/start`, { method: "POST" }),
  completeExperiment: (id: number) => request(`/api/experiments/${id}/complete`, { method: "POST" }),
};
