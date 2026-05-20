# tests/test_config.py
import os
import tempfile
from pathlib import Path
from src.config import load_config


def test_load_config_from_file():
    yaml_content = """
settings:
  language: de
  daily_model: claude-sonnet-4-20250514
  weekly_model: claude-opus-4-6
  max_articles_per_source: 10
  max_age_hours: 26
  request_timeout: 30
  max_retries: 3
  log_level: INFO
  cleanup_days: 90

ntfy:
  enabled: true
  server: https://ntfy.sh
  topic: test-topic

sources:
  anthropic:
    - name: Anthropic Blog
      type: rss
      url: https://www.anthropic.com/rss.xml
      priority: high

output:
  daily_dir: output/daily
  weekly_dir: output/weekly
  data_dir: data
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = load_config(f.name)

    assert config["settings"]["daily_model"] == "claude-sonnet-4-20250514"
    assert config["ntfy"]["topic"] == "test-topic"
    assert len(config["sources"]["anthropic"]) == 1
    assert config["output"]["daily_dir"] == "output/daily"
    os.unlink(f.name)


def test_load_config_default_path(monkeypatch):
    """load_config() without args should look for config.yaml in project root."""
    monkeypatch.chdir(Path(__file__).parent.parent)
    config = load_config()
    assert "settings" in config
    assert "subscriptions" in config
    assert "output" in config


def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")
