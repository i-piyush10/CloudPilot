from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt


@dataclass(frozen=True)
class Forecast:
    predicted_rps: float
    confidence: float
    slope_rps_per_second: float
    sample_count: int
    rmse: float


class LinearTrendPredictor:
    """Small CPU-only least-squares predictor suitable for a student laptop."""

    minimum_samples = 5

    def predict(self, rows: list[dict], horizon_seconds: int) -> Forecast:
        usable = rows[-20:]
        if not usable:
            return Forecast(0.0, 0.0, 0.0, 0, 0.0)
        values = [max(0.0, float(row["request_rate"])) for row in usable]
        if len(values) < self.minimum_samples:
            return Forecast(values[-1], min(0.45, len(values) / self.minimum_samples * 0.4), 0.0, len(values), 0.0)

        timestamps = [datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00")).timestamp() for row in usable]
        origin = timestamps[0]
        xs = [value - origin for value in timestamps]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(values) / len(values)
        denominator = sum((x - mean_x) ** 2 for x in xs)
        slope = 0.0 if denominator == 0 else sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denominator
        intercept = mean_y - slope * mean_x
        fitted = [intercept + slope * x for x in xs]
        rmse = sqrt(sum((actual - estimate) ** 2 for actual, estimate in zip(values, fitted)) / len(values))
        target_x = xs[-1] + horizon_seconds
        raw_prediction = max(0.0, intercept + slope * target_x)

        # Guard against a single noisy window producing an unsafe extrapolation.
        observed_max = max(values)
        upper_bound = max(observed_max * 2.0, values[-1] + 1.0)
        prediction = min(raw_prediction, upper_bound)
        normalized_error = rmse / max(1.0, mean_y)
        confidence = max(0.05, min(0.98, 1.0 - normalized_error))
        return Forecast(round(prediction, 3), round(confidence, 3), round(slope, 5), len(values), round(rmse, 3))

