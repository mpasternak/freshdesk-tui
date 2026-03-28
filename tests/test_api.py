"""Tests for freshdesk_tui.api."""

from __future__ import annotations

import httpx
import pytest
import respx

from freshdesk_tui.api import (
    PRIORITY_MAP,
    STATUS_MAP,
    Attachment,
    Conversation,
    FreshdeskClient,
    Ticket,
    _parse_attachments,
    _parse_ticket,
)


# --- Unit tests for parsing helpers ---


class TestParseAttachments:
    def test_empty_list(self):
        assert _parse_attachments([]) == []

    def test_parses_attachment_fields(self):
        data = [
            {
                "id": 42,
                "name": "report.pdf",
                "content_type": "application/pdf",
                "size": 12345,
                "attachment_url": "https://example.com/report.pdf",
            }
        ]
        result = _parse_attachments(data)
        assert len(result) == 1
        att = result[0]
        assert att.id == 42
        assert att.name == "report.pdf"
        assert att.content_type == "application/pdf"
        assert att.size == 12345
        assert att.attachment_url == "https://example.com/report.pdf"

    def test_missing_fields_use_defaults(self):
        result = _parse_attachments([{}])
        att = result[0]
        assert att.id == 0
        assert att.name == ""
        assert att.size == 0


class TestParseTicket:
    def test_basic_ticket(self):
        data = {
            "id": 101,
            "subject": "Test ticket",
            "status": 2,
            "priority": 3,
            "requester": {"name": "Alice"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "description_text": "plain text",
            "description": "<p>html</p>",
            "tags": ["billing", "urgent"],
        }
        ticket = _parse_ticket(data)
        assert ticket.id == 101
        assert ticket.subject == "Test ticket"
        assert ticket.status == 2
        assert ticket.priority == 3
        assert ticket.requester_name == "Alice"
        assert ticket.description_text == "plain text"
        assert ticket.description_html == "<p>html</p>"
        assert ticket.tags == ["billing", "urgent"]
        assert ticket.attachments == []

    def test_with_attachments(self):
        data = {
            "id": 102,
            "subject": "With files",
            "status": 2,
            "priority": 1,
            "attachments": [{"id": 1, "name": "file.txt", "content_type": "text/plain", "size": 100, "attachment_url": "https://x.com/f"}],
        }
        ticket = _parse_ticket(data, include_attachments=True)
        assert len(ticket.attachments) == 1
        assert ticket.attachments[0].name == "file.txt"

    def test_without_attachments_flag(self):
        data = {
            "id": 103,
            "subject": "No files parsed",
            "status": 2,
            "priority": 1,
            "attachments": [{"id": 1, "name": "file.txt"}],
        }
        ticket = _parse_ticket(data, include_attachments=False)
        assert ticket.attachments == []

    def test_missing_requester_falls_back_to_id(self):
        data = {"id": 104, "requester_id": 999}
        ticket = _parse_ticket(data)
        assert ticket.requester_name == "999"

    def test_null_requester(self):
        data = {"id": 105, "requester": None, "requester_id": 888}
        ticket = _parse_ticket(data)
        assert ticket.requester_name == "888"

    def test_no_subject_default(self):
        data = {"id": 106}
        ticket = _parse_ticket(data)
        assert ticket.subject == "(no subject)"


class TestTicketProperties:
    def test_status_label_known(self):
        t = Ticket(id=1, subject="", status=2, priority=1, requester_name="", created_at="", updated_at="")
        assert t.status_label == "Open"

    def test_status_label_unknown(self):
        t = Ticket(id=1, subject="", status=99, priority=1, requester_name="", created_at="", updated_at="")
        assert t.status_label == "#99"

    def test_priority_label_known(self):
        t = Ticket(id=1, subject="", status=2, priority=4, requester_name="", created_at="", updated_at="")
        assert t.priority_label == "Urgent"

    def test_priority_label_unknown(self):
        t = Ticket(id=1, subject="", status=2, priority=99, requester_name="", created_at="", updated_at="")
        assert t.priority_label == "#99"


# --- Integration tests for FreshdeskClient using respx ---

SAMPLE_TICKET = {
    "id": 1,
    "subject": "Help me",
    "status": 2,
    "priority": 3,
    "requester": {"name": "Bob"},
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "description_text": "I need help",
    "description": "<p>I need help</p>",
    "tags": ["support"],
    "attachments": [
        {"id": 10, "name": "log.txt", "content_type": "text/plain", "size": 500, "attachment_url": "https://x.com/log.txt"}
    ],
}

SAMPLE_CONVERSATION = {
    "id": 201,
    "body_text": "reply text",
    "body": "<p>reply html</p>",
    "from_email": "agent@example.com",
    "created_at": "2026-01-03T00:00:00Z",
    "incoming": False,
    "attachments": [],
}


@pytest.fixture
def client():
    c = FreshdeskClient(domain="test.freshdesk.com", api_key="testkey")
    yield c


@pytest.mark.asyncio
class TestFreshdeskClientListTickets:
    async def test_list_tickets(self, client):
        with respx.mock:
            respx.get("https://test.freshdesk.com/api/v2/tickets").mock(
                return_value=httpx.Response(200, json=[SAMPLE_TICKET])
            )
            tickets = await client.list_tickets()

        assert len(tickets) == 1
        assert tickets[0].id == 1
        assert tickets[0].subject == "Help me"
        assert tickets[0].requester_name == "Bob"

    async def test_list_tickets_with_filter(self, client):
        with respx.mock:
            route = respx.get("https://test.freshdesk.com/api/v2/tickets").mock(
                return_value=httpx.Response(200, json=[])
            )
            await client.list_tickets(filter_str="spam")

        assert "filter" in str(route.calls[0].request.url)


@pytest.mark.asyncio
class TestFreshdeskClientGetTicket:
    async def test_get_ticket(self, client):
        with respx.mock:
            respx.get("https://test.freshdesk.com/api/v2/tickets/1").mock(
                return_value=httpx.Response(200, json=SAMPLE_TICKET)
            )
            ticket = await client.get_ticket(1)

        assert ticket.id == 1
        assert len(ticket.attachments) == 1
        assert ticket.attachments[0].name == "log.txt"


@pytest.mark.asyncio
class TestFreshdeskClientGetConversations:
    async def test_get_conversations(self, client):
        with respx.mock:
            respx.get("https://test.freshdesk.com/api/v2/tickets/1/conversations").mock(
                return_value=httpx.Response(200, json=[SAMPLE_CONVERSATION])
            )
            convs = await client.get_conversations(1)

        assert len(convs) == 1
        assert convs[0].from_email == "agent@example.com"
        assert convs[0].body_text == "reply text"
        assert convs[0].incoming is False


@pytest.mark.asyncio
class TestFreshdeskClientSearch:
    async def test_search_tickets(self, client):
        with respx.mock:
            respx.get("https://test.freshdesk.com/api/v2/search/tickets").mock(
                return_value=httpx.Response(200, json={"results": [SAMPLE_TICKET], "total": 1})
            )
            tickets = await client.search_tickets("status:2")

        assert len(tickets) == 1
        assert tickets[0].id == 1

    async def test_search_tickets_with_page(self, client):
        with respx.mock:
            route = respx.get("https://test.freshdesk.com/api/v2/search/tickets").mock(
                return_value=httpx.Response(200, json={"results": [], "total": 0})
            )
            await client.search_tickets("status:5", page=3)

        assert "page=3" in str(route.calls[0].request.url)

    async def test_search_empty_results(self, client):
        with respx.mock:
            respx.get("https://test.freshdesk.com/api/v2/search/tickets").mock(
                return_value=httpx.Response(200, json={"results": [], "total": 0})
            )
            tickets = await client.search_tickets("nonexistent")

        assert tickets == []


@pytest.mark.asyncio
class TestFreshdeskClientClose:
    async def test_close(self, client):
        await client.close()
