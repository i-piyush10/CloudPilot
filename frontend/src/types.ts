export type ScalingMode = "fixed" | "hpa" | "predictive";

export interface Telemetry {
  timestamp: string;
  request_rate: number;
  cpu_percent: number;
  memory_mb: number;
  p95_latency_ms: number;
  error_rate: number;
  restart_count: number;
}

export interface Decision {
  timestamp: string;
  mode: ScalingMode;
  current_replicas: number;
  desired_replicas: number;
  predicted_rps: number;
  confidence: number;
  reason: string;
  applied: boolean;
}

export interface Status {
  service: string;
  cluster_mode: string;
  scaling_mode: ScalingMode;
  current_replicas: number;
  desired_replicas: number;
  workload_healthy: boolean;
  latest: Telemetry | null;
  latest_decision: Decision | null;
  active_anomalies: string[];
}

export interface Incident {
  id: number;
  timestamp: string;
  kind: string;
  severity: string;
  action: string;
  status: string;
  detail: string;
}

export interface Experiment {
  id: number;
  created_at: string;
  name: string;
  scenario: "constant" | "ramp" | "spike" | "periodic" | "failure";
  mode: ScalingMode;
  duration_seconds: number;
  status: "planned" | "running" | "completed";
  result: Record<string, number>;
}
