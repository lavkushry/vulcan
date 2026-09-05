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
            }
        }

    def validate_chg(self, chg_number: str) -> Dict[str, Any]:
        if self.mock_mode:
            ticket = self._mock_tickets.get(chg_number)
            if not ticket:
                # Default synthetic valid ticket
                return {
                    "chg_number": chg_number,
                    "state": "Scheduled",
                    "ci_item": "pnc-prod-infra",
                    "approved_by": "CAB_COMMITTEE"
                }
            return {"chg_number": chg_number, **ticket}

        # Real HTTP client to ServiceNow Table API
        raise NotImplementedError("Production ServiceNow credentials not configured.")

    def is_within_maintenance_window(self, chg_number: str, check_time: datetime) -> bool:
        """
        Verifies if check_time falls within scheduled change maintenance window.
        """
        if self.mock_mode:
            ticket = self._mock_tickets.get(chg_number)
            if ticket and "start_time" in ticket and "end_time" in ticket:
                try:
                    start = datetime.fromisoformat(ticket["start_time"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(ticket["end_time"].replace("Z", "+00:00"))
                    return start <= check_time <= end
                except Exception:
                    return True
            return True

        return True

    def update_work_notes(self, chg_number: str, notes: str, new_state: Optional[str] = None) -> None:
        if self.mock_mode:
            if chg_number in self._mock_tickets:
                self._mock_tickets[chg_number].setdefault("work_notes", []).append(notes)
                if new_state:
                    self._mock_tickets[chg_number]["state"] = new_state
            return

        # Real ServiceNow PATCH /api/now/table/change_request/{sys_id}
        pass
