from datetime import datetime, timedelta, timezone

from app.predictor import LinearTrendPredictor


def rows(values):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {"timestamp": (start + timedelta(seconds=i * 15)).isoformat(), "request_rate": value}
        for i, value in enumerate(values)
    ]


def test_predictor_detects_upward_trend():
    forecast = LinearTrendPredictor().predict(rows([10, 20, 30, 40, 50]), 30)
    assert forecast.predicted_rps > 50
    assert forecast.confidence > 0.9
    assert forecast.slope_rps_per_second > 0


def test_predictor_is_safe_with_too_few_samples():
    forecast = LinearTrendPredictor().predict(rows([4, 8]), 60)
    assert forecast.predicted_rps == 8
    assert forecast.confidence < 0.35


def test_predictor_clamps_extreme_extrapolation():
    forecast = LinearTrendPredictor().predict(rows([1, 1, 1, 1, 100]), 600)
    assert forecast.predicted_rps <= 200

