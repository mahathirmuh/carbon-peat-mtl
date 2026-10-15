import subprocess
import sys

import yaml

from src.config import DEFAULT_CONFIG, ROOT, load_config


def test_auth_check_stops_while_project_is_todo(tmp_path):
    cfg = load_config(DEFAULT_CONFIG)
    cfg["gee_project"] = "TODO"
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "gee" / "auth_check.py"), "--config", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "TODO" in result.stderr
