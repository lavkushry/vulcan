"""
Project Vulcan: Enterprise ServiceNow & CMDB Integration Test Suite (CHAT-14 / BKND-16)
Author: Robert C. Martin ("Uncle Bob") & Alex Xu
Validates:
1. ServiceNow Table API change request validation and CAB approval checks
2. Maintenance window temporal checks and fail-closed behavior
3. CMDB Configuration Item (CI) lookup and parameter hydration
4. Unified ticket + CMDB hydration latency (< 200ms) and provenance attribution
5. Table API HTTP responses (HTTP 200, 401/403, 404, timeouts)
6. Bi-directional work notes sync via Table API PATCH
7. Intent resolution end-to-end integration and parameter extraction
8. REST API endpoints (/api/v1/integrations/servicenow/tickets, /cmdb)
"""
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import requests

from app.adapters.servicenow_adapter import ServiceNowGateway, parse_service_now_date
from app.api.server import app
from app.config import container
from app.use_cases.resolve_intent import IntentResolver


class TestServiceNowAdapter(unittest.TestCase):
    """Unit tests for ServiceNowGateway in both hermetic mock and simulated Table API modes."""

    def setUp(self):
        self.gateway = ServiceNowGateway(mock_mode=True)

    def test_validate_chg_known_valid_tickets(self):
        """Valid scheduled tickets in mock database must return is_valid=True with metadata."""
        tickets = ["CHG001", "CHG-98412", "CHG-DEMO-001", "CHG-2026-0001"]
        for chg in tickets:
            res = self.gateway.validate_chg(chg)
            self.assertTrue(res["is_valid"], f"Expected {chg} to be valid")
            self.assertEqual(res["chg_number"], chg)
            self.assertEqual(res["state"], "Scheduled")
            self.assertIsNotNone(res["ci"])
            self.assertIsNone(res.get("error"))

    def test_validate_chg_unknown_ticket_fails_closed(self):
        """BKND-16 / CHAT-14: Unknown tickets must never be synthesized as valid."""
        res = self.gateway.validate_chg("CHG-FAKE-999999")
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["state"], "Invalid")
        self.assertIn("not found in ITSM CMDB", res["error"])

    def test_validate_chg_unapproved_ticket_fails_closed(self):
        """Tickets not yet approved by CAB must return is_valid=False."""
        res = self.gateway.validate_chg("CHG-UNAPPROVED")
        self.assertFalse(res["is_valid"])
        self.assertIn("Approval", res["error"])

    def test_is_within_maintenance_window_active(self):
        """Current time within scheduled start and end returns True."""
        now = datetime.now(timezone.utc)
        self.assertTrue(self.gateway.is_within_maintenance_window("CHG001", now))
        self.assertTrue(self.gateway.is_within_maintenance_window("CHG-DEMO-001", now))

    def test_is_within_maintenance_window_expired(self):
        """Expired maintenance windows return False."""
        now = datetime.now(timezone.utc)
        self.assertFalse(self.gateway.is_within_maintenance_window("CHG-EXPIRED", now))

    def test_is_within_maintenance_window_unknown_ticket(self):
        """Unknown change tickets fail-closed for maintenance windows."""
        now = datetime.now(timezone.utc)
        self.assertFalse(self.gateway.is_within_maintenance_window("CHG-NONEXISTENT", now))

    def test_date_parser_formats(self):
        """Ensures support for ISO-8601 and ServiceNow standard timestamps."""
        d1 = parse_service_now_date("2026-05-10T14:30:00Z")
        self.assertEqual(d1.year, 2026)
        self.assertEqual(d1.month, 5)

        d2 = parse_service_now_date("2026-05-10 14:30:00")
        self.assertEqual(d2.year, 2026)
        self.assertEqual(d2.hour, 14)

        d3 = parse_service_now_date(None)
        self.assertIsNone(d3)

    def test_lookup_cmdb_ci_known(self):
        """Known CIs in CMDB return rich infrastructure parameters."""
        ci = self.gateway.lookup_cmdb_ci("pnc-core-db01")
        self.assertIsNotNone(ci)
        self.assertEqual(ci["name"], "pnc-core-db01")
        self.assertEqual(ci["ip_address"], "10.240.30.5")
        self.assertEqual(ci["environment"], "PROD")
        self.assertEqual(ci["tier"], "TIER-1")
        self.assertIn("Linux", ci["os"])
        self.assertEqual(ci["datacenter"], "us-east-1")

    def test_lookup_cmdb_ci_unknown(self):
        """Unknown CIs return None."""
        ci = self.gateway.lookup_cmdb_ci("unknown-server-xyz")
        self.assertIsNone(ci)

    def test_hydrate_ticket_and_cmdb_performance_budget(self):
        """CHAT-14: Combined hydration must complete in < 200ms and hydrate parameters."""
        res = self.gateway.hydrate_ticket_and_cmdb("CHG-DEMO-001")
        self.assertTrue(res["is_valid"])
        self.assertTrue(res["in_maintenance_window"])
        self.assertLess(res["latency_ms"], 200, "Hydration exceeded 200ms latency budget")

        params = res["parameters_hydrated"]
        self.assertEqual(params["servicenow_chg"], "CHG-DEMO-001")
        self.assertEqual(params["target_host"], "f5-edge-01.pnc.com")
        self.assertEqual(params["ip_address"], "10.240.12.11")
        self.assertEqual(params["environment"], "PROD")

        prov = res["provenance"]
        self.assertEqual(prov["servicenow_chg"], "✓ CHG")
        self.assertEqual(prov["target_host"], "🏢 CMDB")
        self.assertEqual(prov["ip_address"], "🏢 CMDB")

    def test_update_work_notes_mock(self):
        """Work notes are appended in mock ledger."""
        self.gateway.update_work_notes("CHG001", "Execution completed with 0 errors.", new_state="Implement")
        ticket = self.gateway.validate_chg("CHG001")
        self.assertEqual(ticket["state"], "Implement")


class TestServiceNowLiveTableAPI(unittest.TestCase):
    """Simulates live HTTP communication with ServiceNow REST Table API."""

    def setUp(self):
        self.gateway = ServiceNowGateway(
            instance_url="https://pnc-bank.service-now.com",
            username="vulcan_svc",
            password="fake_password_123",
            mock_mode=False
        )

    @patch("requests.Session.get")
    def test_live_table_api_success(self, mock_get):
        """Simulates successful Table API response with valid change request and CMDB CI."""
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "result": [
                {
                    "sys_id": {"value": "sys_abc123"},
                    "number": {"value": "CHG-887766"},
                    "state": {"display_value": "Scheduled"},
                    "risk": {"display_value": "High"},
                    "work_start": {"value": "2026-01-01 00:00:00"},
                    "work_end": {"value": "2027-01-01 00:00:00"},
                    "cmdb_ci": {"display_value": "pnc-core-db01"},
                    "approval": {"display_value": "Approved"},
                    "short_description": {"display_value": "Core Database Upgrade"}
                }
            ]
        }
        mock_get.return_value = mock_res

        res = self.gateway.validate_chg("CHG-887766")
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["chg_number"], "CHG-887766")
        self.assertEqual(res["state"], "Scheduled")
        self.assertEqual(res["ci"], "pnc-core-db01")

    @patch("requests.Session.get")
    def test_live_table_api_404_not_found(self, mock_get):
        """Simulates HTTP 404 response from ServiceNow Table API."""
        mock_res = MagicMock()
        mock_res.status_code = 404
        mock_get.return_value = mock_res

        res = self.gateway.validate_chg("CHG-NOTFOUND")
        self.assertFalse(res["is_valid"])
        self.assertIn("HTTP 404", res["error"])

    @patch("requests.Session.get")
    def test_live_table_api_401_unauthorized(self, mock_get):
        """Simulates HTTP 401 Unauthorized response."""
        mock_res = MagicMock()
        mock_res.status_code = 401
        mock_get.return_value = mock_res

        res = self.gateway.validate_chg("CHG-887766")
        self.assertFalse(res["is_valid"])
        self.assertIn("authentication/authorization failed", res["error"])

    @patch("requests.Session.get")
    def test_live_table_api_timeout_fails_closed(self, mock_get):
        """Simulates request timeout failing closed."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        res = self.gateway.validate_chg("CHG-887766")
        self.assertFalse(res["is_valid"])
        self.assertIn("timed out", res["error"])

    @patch("requests.Session.patch")
    @patch("requests.Session.get")
    def test_live_table_api_work_notes_patch(self, mock_get, mock_patch):
        """Simulates PATCH to update work notes in ServiceNow."""
        get_res = MagicMock()
        get_res.status_code = 200
        get_res.json.return_value = {
            "result": [{"sys_id": {"value": "sys_abc123"}, "state": {"display_value": "Scheduled"}, "approval": {"display_value": "Approved"}}]
        }
        mock_get.return_value = get_res

        patch_res = MagicMock()
        patch_res.status_code = 200
        mock_patch.return_value = patch_res

        self.gateway.update_work_notes("CHG-887766", "Proof Hash: 8fbc29...", new_state="Implement")
        mock_patch.assert_called_once()


class TestIntentResolutionHydration(unittest.TestCase):
    """Verifies that IntentResolver seamlessly extracts and hydrates parameters from ServiceNow & CMDB."""

    def setUp(self):
        self.gateway = ServiceNowGateway(mock_mode=True)
        self.resolver = container.intent_resolver
        self.resolver.servicenow_gateway = self.gateway

    def test_intent_resolver_hydrates_chg_and_cmdb(self):
        """Prompt containing CHG ticket must automatically hydrate target_host, hostname, and ip_address."""
        prompt = "renew ssl certificates under CHG-DEMO-001 on edge load balancer"
        res = self.resolver.resolve(prompt)

        self.assertIn(res.status, ("READY", "NEEDS_INPUT"))
        params = res.extracted_parameters
        self.assertEqual(params.get("servicenow_chg"), "CHG-DEMO-001")
        self.assertEqual(params.get("target_host"), "f5-edge-01.pnc.com")
        self.assertEqual(params.get("ip_address"), "10.240.12.11")

        # Verify ticket hydration data is present
        self.assertIsNotNone(res.ticket_hydration)
        self.assertEqual(res.ticket_hydration["chg_number"], "CHG-DEMO-001")
        self.assertTrue(res.ticket_hydration["in_maintenance_window"])
        self.assertIsNotNone(res.ticket_hydration["cmdb"])

    def test_intent_resolver_refuses_invalid_chg(self):
        """Prompt with unknown change ticket on valid playbook is immediately refused (fail-closed)."""
        prompt = "renew ssl certificates under CHG-UNKNOWN-12345 on edge load balancer"
        res = self.resolver.resolve(prompt)
        self.assertEqual(res.status, "REFUSED")
        self.assertIn("invalid, unapproved, outside maintenance window, or unknown", res.refusal_reason)


class TestServiceNowRESTEndpoints(unittest.TestCase):
    """Verifies the REST API endpoints for ServiceNow ticket hydration and CMDB inspection."""

    def setUp(self):
        container.snow_gateway = ServiceNowGateway(mock_mode=True)
        self.client = TestClient(app)
        self.client.headers.update({"Authorization": "Bearer vlc_test_alice"})

    def test_api_get_servicenow_ticket(self):
        """GET /api/v1/integrations/servicenow/tickets/{chg_number} returns hydrated ticket."""
        res = self.client.get("/api/v1/integrations/servicenow/tickets/CHG-DEMO-001")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_valid"])
        self.assertEqual(data["chg_number"], "CHG-DEMO-001")
        self.assertEqual(data["ci"], "f5-edge-01.pnc.com")
        self.assertIn("parameters_hydrated", data)
        self.assertEqual(data["parameters_hydrated"]["ip_address"], "10.240.12.11")

    def test_api_get_cmdb_ci(self):
        """GET /api/v1/integrations/servicenow/cmdb/{ci_name} returns CMDB metadata."""
        res = self.client.get("/api/v1/integrations/servicenow/cmdb/pnc-core-db01")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], "pnc-core-db01")
        self.assertEqual(data["ip_address"], "10.240.30.5")
        self.assertEqual(data["environment"], "PROD")
        self.assertEqual(data["tier"], "TIER-1")

    def test_api_get_cmdb_ci_404(self):
        """GET /api/v1/integrations/servicenow/cmdb/{unknown} returns HTTP 404."""
        res = self.client.get("/api/v1/integrations/servicenow/cmdb/non-existent-device-xyz")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
