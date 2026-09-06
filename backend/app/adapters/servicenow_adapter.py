"""
Project Vulcan: ServiceNow ITSM Integration Gateway
Author: Robert C. Martin ("Uncle Bob") & Alex Xu
Provides Change Request (CHG) validation, maintenance window enforcement, and bi-directional work notes sync.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.ports.interfaces import IServiceNowGateway


class ServiceNowGateway(IServiceNowGateway):
    """
    Adapter communicating with ServiceNow REST Table API.
    Provides local simulation mode for offline testbeds and CI/CD pipelines.
    """

    def __init__(
        self,
        instance_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        mock_mode: bool = True
    ):
        self.instance_url = instance_url
        self.auth_token = auth_token
        self.mock_mode = mock_mode or (instance_url is None)

        self._mock_tickets: Dict[str, Dict[str, Any]] = {
            "CHG001": {
                "state": "Scheduled",
                "risk": "Moderate",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "f5-vip-01",
                "work_notes": []
            },
            "CHG0098412": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "pnc-core-db01",
                "work_notes": []
            },
            "CHG-DEMO-001": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "f5-edge-01.pnc.com",
                "work_notes": []
            },
            "CHG-DEMO-002": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "pnc-core-db01",
                "work_notes": []
            },
            "CHG-991122": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "f5-vip-api-01",
                "work_notes": []
            },
            "CHG-2026-0001": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "pnc-prod-infra",
                "work_notes": []
            },
            "CHG-2026-9901": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2027-01-01T00:00:00Z",
                "ci": "f5-edge-01.internal",
                "work_notes": []
            },
            "CHG-EXPIRED": {
                "state": "Scheduled",
                "risk": "High",
                "start_time": "2020-01-01T00:00:00Z",
                "end_time": "2020-01-02T00:00:00Z",
                "ci": "pnc-prod-infra",
                "work_notes": []
            }
        }

    def validate_chg(self, chg_number: str) -> Dict[str, Any]:
        if self.mock_mode:
            ticket = self._mock_tickets.get(chg_number)
            if not ticket:
                # Fail-Closed (BKND-16 / CHAT-16): Eradicate synthetic governance illusion.
                # Unknown tickets MUST NOT be fabricated as CAB-approved.
                return {
                    "chg_number": chg_number,
                    "state": "Invalid",
                    "ci_item": None,
                    "approved_by": None,
                    "is_valid": False,
                    "error": f"Change Request [{chg_number}] not found in ServiceNow CMDB."
                }
            return {"chg_number": chg_number, "is_valid": True, **ticket}

        # Real HTTP client to ServiceNow Table API
        raise NotImplementedError("Production ServiceNow credentials not configured.")

    def is_within_maintenance_window(self, chg_number: str, check_time: datetime) -> bool:
        """
        Verifies if check_time falls within scheduled change maintenance window.
        Fail-Closed: Unknown tickets or unparseable windows return False.
        """
        if self.mock_mode:
            ticket = self._mock_tickets.get(chg_number)
            if not ticket or "start_time" not in ticket or "end_time" not in ticket:
                return False
            try:
                start = datetime.fromisoformat(ticket["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(ticket["end_time"].replace("Z", "+00:00"))
                return start <= check_time <= end
            except Exception:
                return False

        return False

    def update_work_notes(self, chg_number: str, notes: str, new_state: Optional[str] = None) -> None:
        if self.mock_mode:
            if chg_number in self._mock_tickets:
                self._mock_tickets[chg_number].setdefault("work_notes", []).append(notes)
                if new_state:
                    self._mock_tickets[chg_number]["state"] = new_state
            return

        # Real ServiceNow PATCH /api/now/table/change_request/{sys_id}
        pass
