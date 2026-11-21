"""Start the server the way people will (`python -m iw_mock_server`) and call it."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

SRC = Path(__file__).resolve().parents[1] / "src"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_server(extra_env: dict[str, str]) -> subprocess.Popen:
    env = {**os.environ, "PYTHONPATH": str(SRC), "MOCK_HOST": "127.0.0.1", "MOCK_REPLAY_INTERVAL_S": "0",
           **extra_env}
    return subprocess.Popen([sys.executable, "-m", "iw_mock_server"], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)


def test_module_entry_point_serves_health():
    port = free_port()
    proc = run_server({"MOCK_PORT": str(port)})
    try:
        deadline = time.time() + 20
        while True:
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except httpx.TransportError:
                if proc.poll() is not None or time.time() > deadline:
                    raise AssertionError(f"server did not start: {proc.stdout.read() if proc.stdout else ''}")
                time.sleep(0.2)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_broken_mock_data_exits_non_zero_and_names_the_file(contracts_copy):
    (contracts_copy / "mocks" / "findings.json").write_text("[]", encoding="utf-8")

    proc = run_server({"MOCK_PORT": str(free_port()), "CONTRACTS_DIR": str(contracts_copy)})
    output, _ = proc.communicate(timeout=30)

    assert proc.returncode != 0
    assert "findings.json" in output
