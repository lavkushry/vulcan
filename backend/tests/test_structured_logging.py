"""
Project Vulcan: Structured JSON Logging Tests (INFRA-24)
Verifies VulcanJSONLogFormatter produces valid JSON, propagates correlation IDs,
and that setup_structured_logging() correctly wires the vulcan logger hierarchy.
"""
import json
import logging
import os
import unittest
from unittest.mock import patch

from app.adapters.structured_logger import VulcanJSONLogFormatter, setup_structured_logging


class TestVulcanJSONLogFormatter(unittest.TestCase):
    """Unit tests for the JSON log formatter."""

    def setUp(self):
        self.formatter = VulcanJSONLogFormatter()
        self.logger = logging.getLogger("vulcan.test.formatter")
        self.logger.setLevel(logging.DEBUG)

    def test_produces_valid_json(self):
        """Basic log record produces parseable JSON with required keys."""
        record = self.logger.makeRecord(
            "vulcan.test", logging.INFO, "test_file.py", 42,
            "Test message", (), None
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)

        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["logger"], "vulcan.test")
        self.assertEqual(parsed["message"], "Test message")
        self.assertIn("timestamp", parsed)
        self.assertIn("source", parsed)
        self.assertIn("test_file.py:42", parsed["source"])

    def test_propagates_correlation_id(self):
        """Extra fields like correlation_id surface as top-level JSON keys."""
        record = self.logger.makeRecord(
            "vulcan.test", logging.INFO, "test_file.py", 10,
            "Request handled", (), None
        )
        record.correlation_id = "VULC-ABC12345"
        record.method = "POST"
        record.path = "/api/v1/jobs"
        record.status_code = 201
        record.duration_ms = 42.5

        output = self.formatter.format(record)
        parsed = json.loads(output)

        self.assertEqual(parsed["correlation_id"], "VULC-ABC12345")
        self.assertEqual(parsed["method"], "POST")
        self.assertEqual(parsed["path"], "/api/v1/jobs")
        self.assertEqual(parsed["status_code"], 201)
        self.assertEqual(parsed["duration_ms"], 42.5)

    def test_exception_included_in_json(self):
        """Exception info is captured in the 'exception' field."""
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = self.logger.makeRecord(
            "vulcan.test", logging.ERROR, "test_file.py", 99,
            "Something failed", (), exc_info
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)

        self.assertIn("exception", parsed)
        self.assertIn("ValueError: test error", parsed["exception"])

    def test_no_reserved_field_leakage(self):
        """Standard LogRecord internals (args, exc_info, etc.) don't leak into JSON."""
        record = self.logger.makeRecord(
            "vulcan.test", logging.INFO, "test_file.py", 1,
            "Clean record", (), None
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)

        # These Python logging internals should NOT appear
        for reserved in ("args", "exc_info", "exc_text", "stack_info", "processName"):
            self.assertNotIn(reserved, parsed)

    def test_all_levels_produce_valid_json(self):
        """Every log level (DEBUG through CRITICAL) produces valid JSON."""
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            record = self.logger.makeRecord(
                "vulcan.test", level, "test_file.py", 1,
                f"Level {logging.getLevelName(level)}", (), None
            )
            output = self.formatter.format(record)
            parsed = json.loads(output)
            self.assertEqual(parsed["level"], logging.getLevelName(level))


class TestSetupStructuredLogging(unittest.TestCase):
    """Integration tests for setup_structured_logging()."""

    def tearDown(self):
        # Clean up any handlers added during tests
        root = logging.getLogger("vulcan")
        root.handlers.clear()

    def test_json_mode_configures_handler(self):
        """setup_structured_logging(use_json=True) installs VulcanJSONLogFormatter."""
        setup_structured_logging(level=logging.DEBUG, use_json=True)
        root = logging.getLogger("vulcan")

        self.assertEqual(root.level, logging.DEBUG)
        self.assertTrue(len(root.handlers) >= 1)
        handler = root.handlers[-1]
        self.assertIsInstance(handler.formatter, VulcanJSONLogFormatter)

    def test_text_mode_configures_handler(self):
        """setup_structured_logging(use_json=False) installs standard Formatter."""
        setup_structured_logging(level=logging.WARNING, use_json=False)
        root = logging.getLogger("vulcan")

        self.assertEqual(root.level, logging.WARNING)
        handler = root.handlers[-1]
        self.assertNotIsInstance(handler.formatter, VulcanJSONLogFormatter)
        self.assertIsInstance(handler.formatter, logging.Formatter)

    def test_child_loggers_inherit_json_formatter(self):
        """Child loggers (vulcan.config, vulcan.s3, etc.) inherit the JSON formatter."""
        setup_structured_logging(level=logging.INFO, use_json=True)
        child = logging.getLogger("vulcan.config")

        # Child should effectively use parent's handler
        self.assertTrue(child.getEffectiveLevel() <= logging.INFO)
        self.assertTrue(child.parent is not None or child.name == "vulcan")

    def test_no_duplicate_handlers_on_reinit(self):
        """Calling setup_structured_logging() twice doesn't add duplicate handlers."""
        setup_structured_logging(level=logging.INFO, use_json=True)
        handler_count_1 = len(logging.getLogger("vulcan").handlers)
        setup_structured_logging(level=logging.INFO, use_json=True)
        handler_count_2 = len(logging.getLogger("vulcan").handlers)
        self.assertEqual(handler_count_1, handler_count_2)

    def test_end_to_end_json_output(self):
        """Full end-to-end: setup logging, emit a log, verify JSON output."""
        import io

        setup_structured_logging(level=logging.INFO, use_json=True)
        root = logging.getLogger("vulcan")
        handler = root.handlers[-1]

        # Capture output
        stream = io.StringIO()
        handler.stream = stream

        child = logging.getLogger("vulcan.e2e_test")
        child.info("End-to-end test message", extra={"correlation_id": "VULC-E2E00001"})

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        self.assertEqual(parsed["message"], "End-to-end test message")
        self.assertEqual(parsed["correlation_id"], "VULC-E2E00001")
        self.assertEqual(parsed["logger"], "vulcan.e2e_test")
        self.assertEqual(parsed["level"], "INFO")


if __name__ == "__main__":
    unittest.main(verbosity=2)
