from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.tools.models import DemoTicket


class ToolFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ToolSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


CustomerID = Annotated[str, StringConstraints(pattern=r"^cust_[0-9]{3}$")]


class CustomerInput(ToolSchema):
    customer_id: CustomerID


class CustomerOutput(CustomerInput):
    display_name: str
    plan: str
    demo: Literal[True]


class Transaction(ToolSchema):
    transaction_id: str
    amount_usd: str
    status: str


class TransactionsOutput(CustomerInput):
    transactions: list[Transaction]
    demo: Literal[True]


class TicketInput(CustomerInput):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    details: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class TicketOutput(ToolSchema):
    ticket_id: str
    customer_id: str
    status: Literal["OPEN"]
    demo: Literal[True]


@dataclass(frozen=True)
class Definition:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    risk_level: str = "LOW"
    version: str = "1.0.0"
    timeout_seconds: int = 5
    retry_safe: bool = True
    idempotency_supported: bool = True
    handler_type: str = "LOCAL_DEMO_V1"

    def metadata(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
            "risk_level": self.risk_level,
            "timeout_seconds": self.timeout_seconds,
            "retry_safe": self.retry_safe,
            "idempotency_supported": self.idempotency_supported,
            "handler_type": self.handler_type,
        }


DEFINITIONS = {
    item.name: item
    for item in [
        Definition(
            "lookup_customer",
            "Look up synthetic demo customer cust_001 or cust_002. No real customer data.",
            CustomerInput,
            CustomerOutput,
        ),
        Definition(
            "lookup_transactions",
            "Read synthetic transactions for demo customer cust_001 or cust_002.",
            CustomerInput,
            TransactionsOutput,
        ),
        Definition(
            "create_ticket",
            "Create a local demo ticket for cust_001 or cust_002. "
            "Does not contact a helpdesk or send messages.",
            TicketInput,
            TicketOutput,
            risk_level="MEDIUM",
        ),
    ]
}

CUSTOMERS = {
    "cust_001": {"display_name": "Alex Demo", "plan": "Pro"},
    "cust_002": {"display_name": "Sam Example", "plan": "Starter"},
}


async def execute_builtin(
    name: str,
    arguments: dict,
    session: AsyncSession,
    organization_id: UUID,
    tool_call_id: UUID,
    idempotency_key: str,
) -> dict:
    customer = CUSTOMERS.get(arguments["customer_id"])
    if customer is None:
        raise ToolFailure("DEMO_CUSTOMER_NOT_FOUND")
    if name == "lookup_customer":
        return {"customer_id": arguments["customer_id"], **customer, "demo": True}
    if name == "lookup_transactions":
        return {
            "customer_id": arguments["customer_id"],
            "transactions": [
                {
                    "transaction_id": f"txn_{arguments['customer_id']}_001",
                    "amount_usd": "29.00",
                    "status": "SETTLED",
                },
            ],
            "demo": True,
        }
    if name != "create_ticket":
        raise ToolFailure("TOOL_HANDLER_UNAVAILABLE")
    ticket = await session.scalar(
        select(DemoTicket).where(
            DemoTicket.organization_id == organization_id,
            DemoTicket.idempotency_key == idempotency_key,
        )
    )
    if ticket is None:
        ticket = DemoTicket(
            organization_id=organization_id,
            tool_call_id=tool_call_id,
            idempotency_key=idempotency_key,
            **arguments,
        )
        session.add(ticket)
        await session.flush()
    return {
        "ticket_id": str(ticket.id),
        "customer_id": ticket.customer_id,
        "status": "OPEN",
        "demo": True,
    }
