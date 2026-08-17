import logging

from src.app.core.logging import logger, setup_logging


def test_setup_logging_applies_application_log_level(monkeypatch):
    original_level = logger.level
    monkeypatch.setenv("APP_LOG_LEVEL", "WARNING")

    try:
        setup_logging()
        assert logger.level == logging.WARNING
    finally:
        logger.setLevel(original_level)
