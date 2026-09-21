import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    const body = path.includes("timeseries") || path.includes("decisions") || path.includes("incidents") || path.includes("experiments")
      ? { items: [] }
      : {
          service: "CloudPilot", cluster_mode: "simulation", scaling_mode: "fixed",
          current_replicas: 1, desired_replicas: 1, workload_healthy: true,
          latest: null, latest_decision: null, active_anomalies: [],
        };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
});

test("renders the control center and scaling modes", async () => {
  render(<App />);
  expect(await screen.findByText("Forecast demand. Explain decisions. Recover safely.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Kubernetes HPA/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Predictive/i })).toBeInTheDocument();
});
