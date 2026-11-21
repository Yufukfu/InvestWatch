import sys
from pathlib import Path

import iw_scraper
from iw_scraper.config import contracts_dir


def test_runs_on_python_312_or_newer():
    assert sys.version_info >= (3, 12)


def test_package_version_is_exposed():
    assert iw_scraper.__version__ == "0.1.0"


def test_contracts_dir_defaults_to_repo_contracts_with_document_schema():
    schema = contracts_dir() / "schemas" / "scraped-document.schema.json"

    assert schema.is_file()


def test_contracts_dir_honours_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CONTRACTS_DIR", str(tmp_path))

    assert contracts_dir() == tmp_path
