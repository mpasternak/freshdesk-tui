"""Freshdesk API client."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
STATUS_MAP = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}


@dataclass
class Ticket:
    id: int
    subject: str
    status: int
    priority: int
    requester_name: str
    created_at: str
    updated_at: str
    description_text: str = ""
    description_html: str = ""
    tags: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def status_label(self) -> str:
        return STATUS_MAP.get(self.status, f"#{self.status}")

    @property
    def priority_label(self) -> str:
        return PRIORITY_MAP.get(self.priority, f"#{self.priority}")


@dataclass
class Attachment:
    id: int
    name: str
    content_type: str
    size: int
    attachment_url: str


@dataclass
class Conversation:
    id: int
    body_text: str
    body_html: str
    from_email: str
    created_at: str
    incoming: bool
    attachments: list[Attachment] = field(default_factory=list)


def _parse_attachments(data: list[dict]) -> list[Attachment]:
    return [
        Attachment(
            id=a.get("id", 0),
            name=a.get("name", ""),
            content_type=a.get("content_type", ""),
            size=a.get("size", 0),
            attachment_url=a.get("attachment_url", ""),
        )
        for a in data
    ]


class FreshdeskClient:
    def __init__(self, domain: str, api_key: str) -> None:
        self.domain = domain
        self.base_url = f"https://{domain}/api/v2"
        auth = base64.b64encode(f"{api_key}:X".encode()).decode()
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Basic {auth}"},
            timeout=30.0,
        )

    async def list_tickets(
        self,
        page: int = 1,
        per_page: int = 100,
        order_by: str = "updated_at",
        order_type: str = "desc",
        filter_str: str | None = None,
    ) -> list[Ticket]:
        """List tickets.

        filter_str: one of Freshdesk's predefined filters:
            None (default) - new_and_my_open tickets
            "new_and_my_open", "watching", "spam", "deleted"
            For all/closed/pending, we use the search API instead.
        """
        params: dict = {
            "page": page,
            "per_page": per_page,
            "order_by": order_by,
            "order_type": order_type,
            "include": "requester",
        }
        if filter_str:
            params["filter"] = filter_str

        resp = await self.client.get("/tickets", params=params)
        resp.raise_for_status()
        data = resp.json()
        tickets = []
        for t in data:
            requester = t.get("requester", {}) or {}
            requester_name = requester.get("name", "") or t.get("requester_id", "")
            tickets.append(
                Ticket(
                    id=t["id"],
                    subject=t.get("subject", "(no subject)"),
                    status=t.get("status", 0),
                    priority=t.get("priority", 0),
                    requester_name=str(requester_name),
                    created_at=t.get("created_at", ""),
                    updated_at=t.get("updated_at", ""),
                    description_text=t.get("description_text", ""),
                    description_html=t.get("description", ""),
                    tags=t.get("tags", []),
                )
            )
        return tickets

    async def get_ticket(self, ticket_id: int) -> Ticket:
        resp = await self.client.get(
            f"/tickets/{ticket_id}", params={"include": "requester"}
        )
        resp.raise_for_status()
        t = resp.json()
        requester = t.get("requester", {}) or {}
        requester_name = requester.get("name", "") or t.get("requester_id", "")
        return Ticket(
            id=t["id"],
            subject=t.get("subject", "(no subject)"),
            status=t.get("status", 0),
            priority=t.get("priority", 0),
            requester_name=str(requester_name),
            created_at=t.get("created_at", ""),
            updated_at=t.get("updated_at", ""),
            description_text=t.get("description_text", ""),
            description_html=t.get("description", ""),
            tags=t.get("tags", []),
            attachments=_parse_attachments(t.get("attachments") or []),
        )

    async def get_conversations(self, ticket_id: int) -> list[Conversation]:
        resp = await self.client.get(f"/tickets/{ticket_id}/conversations")
        resp.raise_for_status()
        data = resp.json()
        return [
            Conversation(
                id=c["id"],
                body_text=c.get("body_text", ""),
                body_html=c.get("body", ""),
                from_email=c.get("from_email", ""),
                created_at=c.get("created_at", ""),
                incoming=c.get("incoming", False),
                attachments=_parse_attachments(c.get("attachments") or []),
            )
            for c in data
        ]

    async def search_by_filter(
        self, query: str, page: int = 1
    ) -> list[Ticket]:
        """Search tickets using Freshdesk search API with a filter query.

        query: Freshdesk search query, e.g. "status:5" for closed tickets.
        """
        resp = await self.client.get(
            "/search/tickets", params={"query": f'"{query}"', "page": page}
        )
        resp.raise_for_status()
        data = resp.json()
        tickets = []
        for t in data.get("results", []):
            tickets.append(
                Ticket(
                    id=t["id"],
                    subject=t.get("subject", "(no subject)"),
                    status=t.get("status", 0),
                    priority=t.get("priority", 0),
                    requester_name=str(t.get("requester_id", "")),
                    created_at=t.get("created_at", ""),
                    updated_at=t.get("updated_at", ""),
                    description_text=t.get("description_text", ""),
                    description_html=t.get("description", ""),
                    tags=t.get("tags", []),
                )
            )
        return tickets

    async def search_tickets(self, query: str) -> list[Ticket]:
        """Search tickets using Freshdesk search API."""
        resp = await self.client.get(
            "/search/tickets", params={"query": f'"{query}"'}
        )
        resp.raise_for_status()
        data = resp.json()
        tickets = []
        for t in data.get("results", []):
            tickets.append(
                Ticket(
                    id=t["id"],
                    subject=t.get("subject", "(no subject)"),
                    status=t.get("status", 0),
                    priority=t.get("priority", 0),
                    requester_name=str(t.get("requester_id", "")),
                    created_at=t.get("created_at", ""),
                    updated_at=t.get("updated_at", ""),
                    description_text=t.get("description_text", ""),
                    description_html=t.get("description", ""),
                    tags=t.get("tags", []),
                )
            )
        return tickets

    async def close(self) -> None:
        await self.client.aclose()
