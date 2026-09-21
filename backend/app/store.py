from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .schemas import ExperimentCreate, TelemetryIn


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._init_schema()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._connection.cursor()
            try:
                yield cursor
                self._connection.commit()
            finally:
                cursor.close()

    def _init_schema(self) -> None:
        with self._cursor() as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT NOT NULL,
                  request_rate REAL NOT NULL,
                  cpu_percent REAL NOT NULL,
                  memory_mb REAL NOT NULL,
                  p95_latency_ms REAL NOT NULL,
                  error_rate REAL NOT NULL,
                  restart_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  current_replicas INTEGER NOT NULL,
                  desired_replicas INTEGER NOT NULL,
                  predicted_rps REAL NOT NULL,
                  confidence REAL NOT NULL,
                  reason TEXT NOT NULL,
                  applied INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incidents (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  severity TEXT NOT NULL,
                  action TEXT NOT NULL,
                  status TEXT NOT NULL,
                  detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL,
                  name TEXT NOT NULL,
                  scenario TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  duration_seconds INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                """
            )
            cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('scaling_mode', 'fixed')")
            cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('fixed_replicas', '1')")

    def add_telemetry(self, sample: TelemetryIn) -> None:
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO telemetry(timestamp, request_rate, cpu_percent, memory_mb,
                   p95_latency_ms, error_rate, restart_count) VALUES(?,?,?,?,?,?,?)""",
                (
                    sample.timestamp.isoformat(), sample.request_rate, sample.cpu_percent,
                    sample.memory_mb, sample.p95_latency_ms, sample.error_rate, sample.restart_count,
                ),
            )

    def telemetry(self, limit: int = 240) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            rows = cur.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def latest_telemetry(self) -> dict[str, Any] | None:
        rows = self.telemetry(1)
        return rows[-1] if rows else None

    def add_decision(self, decision: dict[str, Any]) -> None:
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO decisions(timestamp, mode, current_replicas, desired_replicas,
                   predicted_rps, confidence, reason, applied) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    decision["timestamp"], decision["mode"], decision["current_replicas"],
                    decision["desired_replicas"], decision["predicted_rps"],
                    decision["confidence"], decision["reason"], int(decision["applied"]),
                ),
            )

    def decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            rows = cur.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) | {"applied": bool(row["applied"])} for row in rows]

    def add_incident(self, kind: str, severity: str, action: str, status: str, detail: str) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO incidents(timestamp, kind, severity, action, status, detail) VALUES(?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), kind, severity, action, status, detail),
            )
            return int(cur.lastrowid)

    def incidents(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            rows = cur.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def add_experiment(self, experiment: ExperimentCreate) -> int:
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO experiments(created_at, name, scenario, mode, duration_seconds,
                   status, result_json) VALUES(?,?,?,?,?,'planned','{}')""",
                (datetime.now(timezone.utc).isoformat(), experiment.name, experiment.scenario,
                 experiment.mode, experiment.duration_seconds),
            )
            return int(cur.lastrowid)

    def experiments(self) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            rows = cur.execute("SELECT * FROM experiments ORDER BY id DESC LIMIT 100").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json"))
            result.append(item)
        return result

    def experiment(self, experiment_id: int) -> dict[str, Any] | None:
        with self._cursor() as cur:
            row = cur.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json"))
        return item

    def set_experiment_status(self, experiment_id: int, status: str, result: dict[str, Any] | None = None) -> bool:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE experiments SET status=?, result_json=COALESCE(?, result_json) WHERE id=?",
                (status, json.dumps(result) if result is not None else None, experiment_id),
            )
            return cur.rowcount == 1

    def telemetry_since(self, timestamp: str) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM telemetry WHERE timestamp >= ? ORDER BY id ASC", (timestamp,)
            ).fetchall()
        return [dict(row) for row in rows]

    def decisions_since(self, timestamp: str) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM decisions WHERE timestamp >= ? ORDER BY id ASC", (timestamp,)
            ).fetchall()
        return [dict(row) | {"applied": bool(row["applied"])} for row in rows]

    def set_setting(self, key: str, value: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def setting(self, key: str, default: str) -> str:
        with self._cursor() as cur:
            row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default
