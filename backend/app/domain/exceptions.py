"""
Project Vulcan: Core Domain Exceptions
Zero framework dependencies. Standard library only.
"""

class DomainError(Exception):
    """Base domain exception for Project Vulcan."""
    pass

class MakerCheckerViolationError(DomainError):
    """Raised when requester attempts to approve their own change (Separation of Duties)."""
    pass

class ApprovalTimeoutError(DomainError):
    """Raised when the 15-minute approval window expires (fail-closed)."""
    pass

class MaintenanceWindowClosedError(DomainError):
    """Raised when execution is attempted outside an authorized ServiceNow maintenance window."""
    pass

class ParameterValidationError(DomainError):
    """Raised when job input parameters fail regex, bounds, schema or type checks."""
    pass

class SecretLintError(DomainError):
    """Raised when high-entropy credentials or private keys are detected in inputs."""
    pass

class ResourceLockedError(DomainError):
    """Raised when target infrastructure resource is already locked by another active job."""
    pass

class StateTransitionError(DomainError):
    """Raised when an illegal finite state machine transition is attempted."""
    pass

class AuditIntegrityError(DomainError):
    """Raised when cryptographic audit chain is broken or pre-run audit commit fails."""
    pass

class HealthProbeDegradedError(DomainError):
    """Raised when post-flight semantic health probes fail despite exit code 0."""
    pass

class PolicyViolationError(DomainError):
    """Raised when an operation violates banking policy, such as executing uncurated candidate code (INV-1)."""
    pass
