"""
Project Vulcan: Maker-Checker Approval Use Case
Author: Uncle Bob & Alex Xu
Coordinates the Maker-Checker sign-off lifecycle, 15-minute fail-closed timeout, and state promotion.
"""
from datetime import datetime, timezone
from typing import Optional

from app.domain.entities import ApprovalDecision, ExecutionJob, JobStatus
from app.domain.exceptions import ApprovalTimeoutError, MakerCheckerViolationError


class ApproveJobUseCase:
    """
    Coordinates human checker sign-off on pending jobs.
    Enforces Maker != Checker inequality and 15m expiration.
    """

    def __init__(self, timeout_seconds: int = 900):
        self.timeout_seconds = timeout_seconds

    def execute(
        self,
        job: ExecutionJob,
        approver_id: str,
        decision_str: str,  # "APPROVE" | "REJECT"
        reason: str,
        chg_number: Optional[str] = None
    ) -> ExecutionJob:
        now = datetime.now(timezone.utc)
        decision = ApprovalDecision(
            decision=decision_str.upper(),
            approver_id=approver_id,
            decided_at=now,
            reason=reason,
            chg_number=chg_number
        )

        job.apply_approval_decision(
            decision=decision,
            evaluated_at=now,
            timeout_seconds=self.timeout_seconds
        )
        return job
