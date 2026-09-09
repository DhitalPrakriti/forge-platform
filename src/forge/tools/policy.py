from forge.tools.builtins import Definition
from forge.tools.models import Tool


def decision(tool: Tool, definition: Definition) -> str:
    """Allowlist for low/medium-risk demos. Refunds use the versioned policy service."""
    if tool.status != "ACTIVE" or tool.handler_type != "LOCAL_DEMO_V1":
        return "DENY"
    if any(getattr(tool, key) != value for key, value in definition.metadata().items()):
        return "DENY"
    if tool.risk_level not in {"LOW", "MEDIUM"}:
        return "DENY"
    if tool.risk_level == "MEDIUM" and not tool.idempotency_supported:
        return "DENY"
    return "ALLOW"
