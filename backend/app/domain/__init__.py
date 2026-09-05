"""
Project Vulcan: Domain Layer
"""
from app.domain.exceptions import (
    DomainError,
    MakerCheckerViolationError,
    ApprovalTimeoutError,
    MaintenanceWindowClosedError,
    ParameterValidationError,
    SecretLintError,
    ResourceLockedError,
    StateTransitionError,
    AuditIntegrityError,
    HealthProbeDegradedError,
)

__all__ = [
    "DomainError",
    "MakerCheckerViolationError",
    "ApprovalTimeoutError",
    "MaintenanceWindowClosedError",
    "ParameterValidationError",
    "SecretLintError",
    "ResourceLockedError",
    "StateTransitionError",
    "AuditIntegrityError",
    "HealthProbeDegradedError",
]
