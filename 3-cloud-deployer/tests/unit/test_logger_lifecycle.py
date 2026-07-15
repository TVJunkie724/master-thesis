"""Lifecycle tests for idempotent and redacted Deployer logging."""

import logging

import logger as logger_module


def _managed_handlers():
    return [
        handler
        for handler in logger_module.logger.handlers
        if getattr(handler, logger_module._MANAGED_HANDLER_ATTRIBUTE, False)
    ]


def test_logger_reconfiguration_updates_one_managed_handler(tmp_path):
    debug_config = tmp_path / "debug.json"
    debug_config.write_text('{"mode": "DEBUG"}', encoding="utf-8")
    info_config = tmp_path / "info.json"
    info_config.write_text('{"mode": "INFO"}', encoding="utf-8")

    try:
        logger_module.configure_logger_from_file(debug_config)
        assert logger_module.get_debug_mode() is True
        assert logger_module.logger.level == logging.DEBUG
        assert len(_managed_handlers()) == 1
        assert _managed_handlers()[0].level == logging.DEBUG
    finally:
        logger_module.configure_logger_from_file(info_config)

    assert logger_module.get_debug_mode() is False
    assert logger_module.logger.level == logging.INFO
    assert len(_managed_handlers()) == 1
    assert _managed_handlers()[0].level == logging.INFO


def test_invalid_config_fails_closed_to_info_logging(tmp_path):
    invalid_config = tmp_path / "invalid.json"
    invalid_config.write_text("{invalid", encoding="utf-8")

    logger_module.configure_logger_from_file(invalid_config)

    assert logger_module.get_debug_mode() is False
    assert logger_module.logger.level == logging.INFO


def test_non_utf8_config_fails_closed_to_info_logging(tmp_path):
    invalid_config = tmp_path / "invalid.json"
    invalid_config.write_bytes(b"\xff\xfe")

    logger_module.configure_logger_from_file(invalid_config)

    assert logger_module.get_debug_mode() is False
    assert logger_module.logger.level == logging.INFO


def test_stack_trace_is_emitted_only_in_debug_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(logger_module.logger, "error", lambda *args: calls.append(args))

    monkeypatch.setattr(logger_module, "DEBUG_MODE", False)
    logger_module.print_stack_trace()
    assert calls == []

    monkeypatch.setattr(logger_module, "DEBUG_MODE", True)
    try:
        raise RuntimeError("secret=must-not-escape-formatter")
    except RuntimeError:
        logger_module.print_stack_trace()

    assert calls and calls[0][0] == "Unhandled exception:\n%s"
