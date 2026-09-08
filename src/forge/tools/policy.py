from forge.tools.builtins import Definition
from forge.tools.models import Tool


def decision(tool: Tool, definition: Definition) -> str:
    """Phase 4 boundary: only installed local demos; no model-provided authorization.

    Versioned business policies and REQUIRE_APPROVAL arrive in Phase 5.
    """
    if tool.status != "ACTIVE" or tool.handler_type != "LOCAL_DEMO_V1":
        return "DENY"
    if any(getattr(tool, key) != value for key, value in definition.metadata().items()):
        return "DENY"
    if tool.risk_level not in {"LOW", "MEDIUM"}:
        return "DENY"
    if tool.risk_level == "MEDIUM" and not tool.idempotency_supported:
        return "DENY"
    return "ALLOW"
