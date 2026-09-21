import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api";
import type { Decision, Experiment, Incident, ScalingMode, Status, Telemetry } from "./types";

const EMPTY_STATUS: Status = {
  service: "CloudPilot",
  cluster_mode: "connecting",
  scaling_mode: "fixed",
  current_replicas: 0,
  desired_replicas: 0,
  workload_healthy: false,
  latest: null,
  latest_decision: null,
  active_anomalies: [],
};

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function MetricCard({ label, value, detail, tone = "blue" }: { label: string; value: string; detail: string; tone?: string }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function App() {
  const grafanaEnabled = import.meta.env.VITE_ENABLE_GRAFANA_LINK === "true";
  const grafanaUrl = import.meta.env.VITE_GRAFANA_URL || "http://localhost:3000/d/cloudpilot-main";
  const [status, setStatus] = useState<Status>(EMPTY_STATUS);
  const [telemetry, setTelemetry] = useState<Telemetry[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [scenario, setScenario] = useState<Experiment["scenario"]>("spike");
  const [fixedReplicas, setFixedReplicas] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextTelemetry, nextDecisions, nextIncidents, nextExperiments] = await Promise.all([
        api.status(), api.telemetry(), api.decisions(), api.incidents(), api.experiments(),
      ]);
      setStatus(nextStatus);
      setTelemetry(nextTelemetry.items);
      setDecisions(nextDecisions.items);
      setIncidents(nextIncidents.items);
      setExperiments(nextExperiments.items);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to reach CloudPilot");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function selectMode(mode: ScalingMode) {
    setLoading(true);
    try {
      await api.setMode(mode, mode === "fixed" ? fixedReplicas : undefined);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Mode change failed");
      setLoading(false);
    }
  }

  async function runTick() {
    setLoading(true);
    try {
      await api.tick();
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Control tick failed");
      setLoading(false);
    }
  }

  async function startExperiment() {
    setLoading(true);
    try {
      const created = await api.createExperiment(scenario, status.scaling_mode);
      await api.startExperiment(created.id);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Experiment could not start");
      setLoading(false);
    }
  }

  async function completeExperiment(id: number) {
    setLoading(true);
    try {
      await api.completeExperiment(id);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Experiment could not complete");
      setLoading(false);
    }
  }

  const chartData = telemetry.map((item) => ({
    ...item,
    time: formatTime(item.timestamp),
    error_percent: item.error_rate * 100,
  }));
  const latest = status.latest;
  const confidence = status.latest_decision?.confidence ?? 0;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-mark">CP</div>
        <div>
          <p className="eyebrow">KUBERNETES OPERATIONS LAB</p>
          <h1>CloudPilot <span>Control Center</span></h1>
        </div>
        <div className={`health-chip ${status.workload_healthy ? "healthy" : "warning"}`}>
          <i /> {status.workload_healthy ? "Workload healthy" : "Needs attention"}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">LIVE EXPERIMENT ENVIRONMENT</p>
          <h2>Forecast demand. Explain decisions. Recover safely.</h2>
          <p>Compare fixed replicas, Kubernetes HPA and predictive scaling against the same measured workload.</p>
        </div>
        <div className="hero-status">
          <span>Cluster mode</span><strong>{status.cluster_mode}</strong>
          <span>Last refresh</span><strong>{new Date().toLocaleTimeString()}</strong>
        </div>
      </section>

      {error && <div className="alert" role="alert"><strong>Connection issue</strong><span>{error}</span></div>}

      <section className="metric-grid" aria-label="Current metrics">
        <MetricCard label="Current replicas" value={String(status.current_replicas)} detail={`Desired ${status.desired_replicas}`} tone="cyan" />
        <MetricCard label="Request rate" value={`${latest?.request_rate.toFixed(1) ?? "0.0"} rps`} detail="Observed workload" />
        <MetricCard label="p95 latency" value={`${latest?.p95_latency_ms.toFixed(0) ?? "0"} ms`} detail="Service objective signal" tone="violet" />
        <MetricCard label="CPU utilization" value={`${latest?.cpu_percent.toFixed(0) ?? "0"}%`} detail={`${latest?.memory_mb.toFixed(0) ?? "0"} MB memory`} tone="green" />
        <MetricCard label="Forecast" value={`${status.latest_decision?.predicted_rps.toFixed(1) ?? "0.0"} rps`} detail={`${(confidence * 100).toFixed(0)}% confidence`} tone="amber" />
      </section>

      <section className="control-grid">
        <article className="panel mode-panel">
          <div className="panel-heading"><div><p className="eyebrow">CONTROL OWNERSHIP</p><h3>Scaling mode</h3></div><span className="live-dot">LIVE</span></div>
          <div className="mode-options">
            {(["fixed", "hpa", "predictive"] as ScalingMode[]).map((mode) => (
              <button key={mode} className={status.scaling_mode === mode ? "active" : ""} onClick={() => void selectMode(mode)} disabled={loading}>
                <strong>{mode === "hpa" ? "Kubernetes HPA" : mode[0].toUpperCase() + mode.slice(1)}</strong>
                <small>{mode === "fixed" ? "Stable baseline" : mode === "hpa" ? "Reactive threshold" : "ML forecast + policy"}</small>
              </button>
            ))}
          </div>
          <div className="fixed-control">
            <label htmlFor="replicas">Fixed replicas <strong>{fixedReplicas}</strong></label>
            <input id="replicas" type="range" min="1" max="8" value={fixedReplicas} onChange={(event) => setFixedReplicas(Number(event.target.value))} />
          </div>
          <button className="primary-button" onClick={() => void runTick()} disabled={loading}>{loading ? "Synchronizing..." : "Run control decision"}</button>
        </article>

        <article className="panel decision-panel">
          <div className="panel-heading"><div><p className="eyebrow">LATEST DECISION</p><h3>Why CloudPilot acted</h3></div></div>
          <div className="decision-number"><strong>{status.current_replicas}</strong><span>→</span><strong>{status.desired_replicas}</strong><small>replicas</small></div>
          <p>{status.latest_decision?.reason ?? "Waiting for the first control decision."}</p>
          <div className="confidence"><span style={{ width: `${confidence * 100}%` }} /></div>
          <dl><div><dt>Applied</dt><dd>{status.latest_decision?.applied ? "Yes" : "No"}</dd></div><div><dt>Mode</dt><dd>{status.scaling_mode}</dd></div><div><dt>Anomalies</dt><dd>{status.active_anomalies.length}</dd></div></dl>
        </article>
      </section>

      <section className="chart-grid">
        <article className="panel chart-panel">
          <div className="panel-heading"><div><p className="eyebrow">TRAFFIC + FORECAST</p><h3>Workload history</h3></div></div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData} margin={{ top: 12, right: 16, left: -15, bottom: 0 }}>
              <defs><linearGradient id="traffic" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#45d6d0" stopOpacity={0.55}/><stop offset="95%" stopColor="#45d6d0" stopOpacity={0}/></linearGradient></defs>
              <CartesianGrid stroke="#1d3346" vertical={false} />
              <XAxis dataKey="time" stroke="#6f8799" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis stroke="#6f8799" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#102335", border: "1px solid #29465e", borderRadius: 10 }} />
              <Area type="monotone" dataKey="request_rate" stroke="#45d6d0" fill="url(#traffic)" strokeWidth={2.5} name="Request rate" />
            </AreaChart>
          </ResponsiveContainer>
        </article>
        <article className="panel chart-panel">
          <div className="panel-heading"><div><p className="eyebrow">SERVICE QUALITY</p><h3>Latency and errors</h3></div></div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 12, right: 16, left: -15, bottom: 0 }}>
              <CartesianGrid stroke="#1d3346" vertical={false} />
              <XAxis dataKey="time" stroke="#6f8799" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis stroke="#6f8799" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#102335", border: "1px solid #29465e", borderRadius: 10 }} />
              <Line type="monotone" dataKey="p95_latency_ms" stroke="#a78bfa" dot={false} strokeWidth={2.5} name="p95 latency" />
              <Line type="monotone" dataKey="error_percent" stroke="#fb7185" dot={false} strokeWidth={2} name="Error %" />
            </LineChart>
          </ResponsiveContainer>
        </article>
      </section>

      <section className="bottom-grid">
        <article className="panel">
          <div className="panel-heading"><div><p className="eyebrow">AUDIT LOG</p><h3>Recent decisions</h3></div></div>
          <div className="list">
            {decisions.length === 0 && <p className="empty">No decisions recorded yet.</p>}
            {decisions.map((decision, index) => <div className="list-row" key={`${decision.timestamp}-${index}`}><i className={decision.applied ? "applied" : "held"}/><span><strong>{decision.mode}</strong><small>{decision.reason}</small></span><time>{formatTime(decision.timestamp)}</time></div>)}
          </div>
        </article>
        <article className="panel">
          <div className="panel-heading"><div><p className="eyebrow">CONTROLLED RECOVERY</p><h3>Incidents</h3></div></div>
          <div className="fault-buttons"><button onClick={() => void api.recordFault("latency").then(refresh)}>Inject latency fault</button><button onClick={() => void api.recordFault("errors").then(refresh)}>Inject error fault</button><button onClick={() => void api.recordFault("pod_restart").then(refresh)}>Restart workload</button></div>
          <div className="list compact">
            {incidents.length === 0 && <p className="empty">No incidents recorded.</p>}
            {incidents.map((incident) => <div className="list-row" key={incident.id}><i className="incident"/><span><strong>{incident.kind}</strong><small>{incident.detail}</small></span><time>{formatTime(incident.timestamp)}</time></div>)}
          </div>
        </article>
      </section>

      <section className="panel experiment-panel">
        <div className="panel-heading"><div><p className="eyebrow">REPEATABLE EVALUATION</p><h3>Experiment notebook</h3></div></div>
        <div className="experiment-controls">
          <label>Scenario<select value={scenario} onChange={(event) => setScenario(event.target.value as Experiment["scenario"])}>
            <option value="constant">Constant</option><option value="ramp">Ramp</option><option value="spike">Spike</option><option value="periodic">Periodic</option><option value="failure">Failure</option>
          </select></label>
          <button className="primary-button" onClick={() => void startExperiment()} disabled={loading}>Start {status.scaling_mode} experiment</button>
        </div>
        <div className="experiment-list">
          {experiments.length === 0 && <p className="empty">No experiments yet. Select a mode and scenario, then start one.</p>}
          {experiments.slice(0, 6).map((experiment) => <div key={experiment.id} className="experiment-row">
            <span><strong>{experiment.scenario} · {experiment.mode}</strong><small>{experiment.status} · {experiment.duration_seconds}s plan</small></span>
            {experiment.status === "running" ? <button onClick={() => void completeExperiment(experiment.id)} disabled={loading}>Complete & calculate</button> : <code>{experiment.result.mean_p95_latency_ms != null ? `${experiment.result.mean_p95_latency_ms} ms mean p95` : "awaiting run"}</code>}
          </div>)}
        </div>
      </section>

      <footer>
        <span>CloudPilot v1.0 · educational prototype</span>
        {grafanaEnabled
          ? <a href={grafanaUrl} target="_blank" rel="noreferrer">Open Grafana ↗</a>
          : <span className="grafana-unavailable" title="Run the Docker Compose or Kubernetes stack to enable Grafana">Grafana · full stack only</span>}
      </footer>
    </main>
  );
}

export default App;
