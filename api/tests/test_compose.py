"""Pins issue #157: each API service builds its own tag, so a targeted `up --build` rebuilds it."""

from pathlib import Path

import yaml

SERVICES = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "compose.yaml").read_text(encoding="utf-8")
)["services"]


def test_api_and_migrate_each_build_the_api_dockerfile():
    # `up -d --build --no-deps api` builds nothing for a service without `build:` (issue #157), and a stack that
    # starts api-migrate without api (scraper/tests/stack.sh) would pull a tag no registry has.
    for name in ("api", "api-migrate"):
        svc = SERVICES[name]
        assert svc["build"] == {"context": "..", "dockerfile": "api/Dockerfile"}, name
        assert svc["pull_policy"] == "build", name


def test_api_services_never_share_a_tag():
    # Two services building one tag race on the containerd image store ("image ... already exists").
    assert SERVICES["api"]["image"] != SERVICES["api-migrate"]["image"]
    assert SERVICES["api"]["image"].startswith("investwatch/api:")
