"""gold-set-evaluation "Command line and compose service": the one-shot `analytics-eval` service and the image."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
SERVICE = COMPOSE["services"].get("analytics-eval", {})


def test_service_is_in_the_default_stack():
    assert "profiles" not in SERVICE


def test_service_uses_the_analytics_image():
    assert SERVICE["image"] == COMPOSE["services"]["analytics"]["image"]


def test_service_runs_the_evaluation_with_db_rules_only():
    assert SERVICE["command"] == ["python", "-m", "investwatch_analytics.evaluation", "--db"]
    assert not any(k.startswith("LLM_") for k in SERVICE.get("environment", {}))


def test_service_is_one_shot():
    assert SERVICE["restart"] == "no"


def test_service_waits_for_the_migration_and_postgres():
    deps = SERVICE["depends_on"]
    assert deps["api-migrate"]["condition"] == "service_completed_successfully"
    assert deps["postgres"]["condition"] == "service_healthy"
    assert "redis" not in deps


def test_service_is_on_the_data_network_only():
    assert SERVICE["networks"] == ["data"]


def test_service_is_hardened_like_the_worker():
    assert SERVICE["read_only"] is True
    assert SERVICE["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in SERVICE["security_opt"]
    assert "DATABASE_URL" in SERVICE["environment"]
    assert "healthcheck" in SERVICE and SERVICE["healthcheck"].get("disable") is True


def test_image_ships_the_gold_set():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY eval eval" in dockerfile
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert not any(p.strip("/").startswith("eval") for p in ignored)
