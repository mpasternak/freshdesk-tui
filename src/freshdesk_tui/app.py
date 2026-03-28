"""Freshdesk TUI - Terminal ticket browser."""

from __future__ import annotations

import argparse
import re
import sys
import webbrowser
from datetime import datetime

import markdownify
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
)

from .api import Attachment, Conversation, FreshdeskClient, Ticket
from .config import Config, ConfigError

# Status filter definitions: (label, type, value)
# type="api_filter" uses /tickets?filter=value
# type="search" uses /search/tickets?query="status:value"
STATUS_FILTERS = [
    ("Open & Pending", "api_filter", None),
    ("Open", "search", "status:2"),
    ("Pending", "search", "status:3"),
    ("Resolved", "search", "status:4"),
    ("Closed", "search", "status:5"),
    ("All", "search", "status:2 OR status:3 OR status:4 OR status:5"),
]

FILTER_NAMES = [f[0] for f in STATUS_FILTERS]


def format_dt(iso: str) -> str:
    """Format ISO datetime to a compact form."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso[:16]


def priority_style(priority: int) -> str:
    if priority == 4:
        return "[bold red]Urgent[/]"
    if priority == 3:
        return "[yellow]High[/]"
    if priority == 2:
        return "Medium"
    return "[dim]Low[/]"


def status_style(status: int) -> str:
    if status == 2:
        return "[bold green]Open[/]"
    if status == 3:
        return "[yellow]Pending[/]"
    if status == 4:
        return "[blue]Resolved[/]"
    if status == 5:
        return "[dim]Closed[/]"
    return str(status)


MAIN_CSS = """\
#search-bar {
    dock: top;
    height: 3;
    display: none;
    padding: 0 1;
}

#search-bar.visible {
    display: block;
}

#search-input {
    width: 100%;
}

#ticket-list {
    height: 1fr;
}

#ticket-detail {
    display: none;
    height: 1fr;
}

#ticket-detail.visible {
    display: block;
}

#detail-header {
    height: auto;
    max-height: 8;
    padding: 1 2;
    background: $surface;
    border-bottom: solid $primary;
}

#detail-header Label {
    margin-bottom: 1;
}

#detail-body {
    padding: 1 2;
}

#detail-body > Label {
    height: auto;
}

#detail-body > Markdown {
    height: auto;
    margin-bottom: 1;
}

.conversation-block {
    margin: 1 0;
    padding: 1 2;
    border: solid $accent;
    height: auto;
}

.conversation-block Markdown {
    height: auto;
}

.conversation-incoming {
    border: solid $success;
}

.conversation-outgoing {
    border: solid $primary;
}

.conversation-meta {
    color: $text-muted;
    height: auto;
    margin-bottom: 1;
}

#status-bar {
    dock: bottom;
    height: 1;
    padding: 0 1;
    background: $surface;
    color: $text-muted;
}

DataTable {
    height: 1fr;
}

DataTable > .datatable--cursor {
    background: $accent;
    color: $text;
}

#attachment-picker {
    display: none;
    height: auto;
    max-height: 50%;
    border: solid $warning;
    padding: 1;
    margin: 1 0;
}

#attachment-picker.visible {
    display: block;
}

#attachment-picker ListView {
    height: auto;
    max-height: 20;
}
"""


class FreshdeskTUI(App):
    TITLE = "Freshdesk TUI"
    CSS = MAIN_CSS

    BINDINGS = [
        Binding("slash", "search", "Search", show=True),
        Binding("s", "cycle_status", "Status Filter", show=True),
        Binding("escape", "back", "Back", show=True),
        Binding("o", "open_browser", "Open in Browser", show=True),
        Binding("a", "open_attachment", "Open Attachment", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("n", "next_page", "Next Page", show=True),
        Binding("p", "prev_page", "Prev Page", show=True),
    ]

    current_page: reactive[int] = reactive(1)
    total_loaded: reactive[int] = reactive(0)
    view_mode: reactive[str] = reactive("list")  # "list" or "detail"
    status_filter_index: reactive[int] = reactive(0)
    selected_ticket: Ticket | None = None
    detail_attachments: list[tuple[str, str]] = []  # [(name, url), ...]

    def __init__(self, initial_filter: str | None = None) -> None:
        super().__init__()
        self.config = Config.load()
        self.client = FreshdeskClient(self.config.domain, self.config.api_key)
        self.all_tickets: list[Ticket] = []
        self.filtered_tickets: list[Ticket] = []
        if initial_filter:
            # Match filter name case-insensitively
            for i, (name, _, _) in enumerate(STATUS_FILTERS):
                if name.lower() == initial_filter.lower():
                    self._default_filter_index = i
                    break
            else:
                self._default_filter_index = 0
        else:
            self._default_filter_index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal(id="search-bar"):
                yield Input(
                    placeholder="Search tickets (title, #number, requester)...",
                    id="search-input",
                )
            yield DataTable(id="ticket-list")
            with Vertical(id="ticket-detail"):
                yield Static(id="detail-header")
                with Vertical(id="attachment-picker"):
                    yield Static("[bold]Attachments[/] — Enter to open, Esc to close", id="attachment-picker-label")
                    yield ListView(id="attachment-list")
                yield VerticalScroll(id="detail-body")
        yield Static("Loading tickets...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#ticket-list", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Subject", "Status", "Priority", "Requester", "Updated")
        self.status_filter_index = self._default_filter_index
        table.focus()
        self.load_tickets()

    @property
    def current_filter(self) -> tuple[str, str, str | None]:
        return STATUS_FILTERS[self.status_filter_index]

    @work(exclusive=True, group="load")
    async def load_tickets(self) -> None:
        filter_label, filter_type, filter_value = self.current_filter
        self.update_status(f"Loading [{filter_label}] tickets...")
        try:
            if filter_type == "search" and filter_value:
                tickets = await self.client.search_tickets(
                    filter_value, page=self.current_page
                )
            else:
                tickets = await self.client.list_tickets(
                    page=self.current_page, per_page=100
                )
            self.all_tickets = tickets
            self.filtered_tickets = tickets
            self.total_loaded = len(tickets)
            self.populate_table(tickets)
            self.update_status(
                f"[{filter_label}] {len(tickets)} tickets | Page {self.current_page} | "
                f"s Filter | / Search | Enter View | o Browser | r Refresh"
            )
        except Exception as e:
            self.update_status(f"Error: {e}")
            self.notify(f"Failed to load tickets: {e}", severity="error")

    def populate_table(self, tickets: list[Ticket]) -> None:
        table = self.query_one("#ticket-list", DataTable)
        table.clear()
        for t in tickets:
            table.add_row(
                str(t.id),
                t.subject[:80],
                t.status_label,
                t.priority_label,
                t.requester_name[:25],
                format_dt(t.updated_at),
                key=str(t.id),
            )

    def update_status(self, text: str) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            bar.update(text)
        except NoMatches:
            pass

    # --- Search ---

    def action_search(self) -> None:
        if self.view_mode == "detail":
            return
        search_bar = self.query_one("#search-bar")
        search_bar.add_class("visible")
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        search_input.focus()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        if not query:
            self.filtered_tickets = self.all_tickets
        else:
            self.filtered_tickets = [
                t
                for t in self.all_tickets
                if query in t.subject.lower()
                or query in str(t.id)
                or query in t.requester_name.lower()
                or any(query in tag.lower() for tag in t.tags)
            ]
        self.populate_table(self.filtered_tickets)
        self.update_status(
            f"{len(self.filtered_tickets)}/{len(self.all_tickets)} tickets | "
            f"Filtering: '{event.value}'"
        )

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self) -> None:
        search_bar = self.query_one("#search-bar")
        search_bar.remove_class("visible")
        table = self.query_one("#ticket-list", DataTable)
        table.focus()

    # --- Navigation ---

    def action_back(self) -> None:
        # Close attachment picker if visible
        picker = self.query_one("#attachment-picker")
        if picker.has_class("visible"):
            self._close_attachment_picker()
            return

        # Close search bar if visible
        search_bar = self.query_one("#search-bar")
        if search_bar.has_class("visible"):
            search_bar.remove_class("visible")
            self.query_one("#ticket-list", DataTable).focus()
            return

        if self.view_mode == "detail":
            self.view_mode = "list"
            self.query_one("#ticket-detail").remove_class("visible")
            table = self.query_one("#ticket-list", DataTable)
            table.display = True
            table.focus()
            filter_label = self.current_filter[0]
            self.update_status(
                f"[{filter_label}] {len(self.filtered_tickets)} tickets | Page {self.current_page} | "
                f"s Filter | / Search | Enter View | o Browser | r Refresh"
            )

    @on(DataTable.RowSelected, "#ticket-list")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            ticket_id = int(event.row_key.value)
            self.show_ticket_detail(ticket_id)

    @work(exclusive=True, group="detail")
    async def show_ticket_detail(self, ticket_id: int) -> None:
        self.update_status(f"Loading ticket #{ticket_id}...")
        try:
            ticket = await self.client.get_ticket(ticket_id)
            conversations = await self.client.get_conversations(ticket_id)
            self.selected_ticket = ticket
            self.render_detail(ticket, conversations)
            self.view_mode = "detail"
            self.query_one("#ticket-list", DataTable).display = False
            detail = self.query_one("#ticket-detail")
            detail.add_class("visible")
            self.query_one("#detail-body", VerticalScroll).focus()
            self.update_status(
                f"Ticket #{ticket.id} | Esc Back | o Browser | a Attachments | q Quit"
            )
        except Exception as e:
            self.update_status(f"Error loading ticket: {e}")
            self.notify(f"Failed to load ticket: {e}", severity="error")

    def render_detail(self, ticket: Ticket, conversations: list[Conversation]) -> None:
        # Header
        header = self.query_one("#detail-header", Static)
        header_text = (
            f"[bold]#{ticket.id}[/] {ticket.subject}\n"
            f"[dim]Status:[/] {status_style(ticket.status)}  "
            f"[dim]Priority:[/] {priority_style(ticket.priority)}  "
            f"[dim]Requester:[/] {ticket.requester_name}\n"
            f"[dim]Created:[/] {format_dt(ticket.created_at)}  "
            f"[dim]Updated:[/] {format_dt(ticket.updated_at)}"
        )
        if ticket.tags:
            header_text += f"\n[dim]Tags:[/] {', '.join(ticket.tags)}"
        header.update(header_text)

        # Body
        body = self.query_one("#detail-body", VerticalScroll)
        body.remove_children()

        # Collect all attachments globally numbered
        self.detail_attachments = []

        def collect_attachments(attachments: list[Attachment]) -> None:
            for att in attachments:
                self.detail_attachments.append((att.name, att.attachment_url))

        def render_attachment_list(
            attachments: list[Attachment], container: Vertical | VerticalScroll
        ) -> None:
            if not attachments:
                return
            start_idx = len(self.detail_attachments) - len(attachments)
            lines = []
            for i, att in enumerate(attachments):
                num = start_idx + i + 1
                size = _format_size(att.size)
                lines.append(f"  [{num}] {att.name} ({size})")
            container.mount(
                Static("[dim]Attachments (press [bold]a[/bold] to open):[/]\n" + "\n".join(lines))
            )

        # Main ticket description
        inline_images: list[str] = []
        desc_md = html_to_markdown(ticket.description_html, inline_images)
        body.mount(Label("[bold underline]Description[/]"))
        body.mount(Markdown(desc_md))

        # Ticket attachments
        collect_attachments(ticket.attachments)
        render_attachment_list(ticket.attachments, body)

        # Inline images as openable items
        for img_url in inline_images:
            name = img_url.rsplit("/", 1)[-1][:60] or "image"
            self.detail_attachments.append((name, img_url))

        # Conversations
        if conversations:
            body.mount(Label(f"\n[bold underline]Conversations ({len(conversations)})[/]"))
            for conv in conversations:
                direction = "incoming" if conv.incoming else "outgoing"
                arrow = "<<" if conv.incoming else ">>"
                meta = f"[dim]{arrow} {conv.from_email} | {format_dt(conv.created_at)}[/]"
                conv_md = html_to_markdown(conv.body_html)

                block = Vertical(classes=f"conversation-block conversation-{direction}")
                body.mount(block)
                block.mount(Static(meta, classes="conversation-meta"))
                block.mount(Markdown(conv_md))

                # Conversation attachments
                collect_attachments(conv.attachments)
                render_attachment_list(conv.attachments, block)

        # Summary at the bottom
        if self.detail_attachments:
            body.mount(
                Static(
                    f"\n[bold]{len(self.detail_attachments)} attachment(s)[/] "
                    f"— press [bold]a[/] to browse"
                )
            )

    # --- Actions ---

    def action_open_attachment(self) -> None:
        if self.view_mode != "detail" or not self.detail_attachments:
            self.notify("No attachments to open", severity="warning")
            return
        # Populate and show the attachment picker ListView
        picker = self.query_one("#attachment-picker")
        lv = self.query_one("#attachment-list", ListView)
        lv.clear()
        for i, (name, _url) in enumerate(self.detail_attachments):
            lv.append(ListItem(Label(f"[{i + 1}] {name}"), id=f"att-{i}"))
        picker.add_class("visible")
        lv.focus()

    def _close_attachment_picker(self) -> None:
        picker = self.query_one("#attachment-picker")
        picker.remove_class("visible")
        self.query_one("#detail-body", VerticalScroll).focus()

    @on(ListView.Selected, "#attachment-list")
    def on_attachment_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("att-"):
            idx = int(item_id.removeprefix("att-"))
            if 0 <= idx < len(self.detail_attachments):
                name, url = self.detail_attachments[idx]
                webbrowser.open(url)
                self.notify(f"Opening: {name}")
        self._close_attachment_picker()

    def action_cycle_status(self) -> None:
        if self.view_mode != "list":
            return
        self.status_filter_index = (self.status_filter_index + 1) % len(STATUS_FILTERS)
        self.current_page = 1
        self.notify(f"Filter: {self.current_filter[0]}")
        self.load_tickets()

    def action_open_browser(self) -> None:
        if self.view_mode == "detail" and self.selected_ticket:
            url = f"https://{self.config.domain}/a/tickets/{self.selected_ticket.id}"
            webbrowser.open(url)
            self.notify(f"Opened ticket #{self.selected_ticket.id} in browser")
        elif self.view_mode == "list":
            # Open the ticket under cursor
            table = self.query_one("#ticket-list", DataTable)
            if table.cursor_row is not None:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                if row_key.value:
                    url = f"https://{self.config.domain}/a/tickets/{row_key.value}"
                    webbrowser.open(url)
                    self.notify(f"Opened ticket #{row_key.value} in browser")

    def action_refresh(self) -> None:
        if self.view_mode == "list":
            self.load_tickets()

    def action_next_page(self) -> None:
        if self.view_mode == "list" and self.total_loaded >= 100:
            self.current_page += 1
            self.load_tickets()

    def action_prev_page(self) -> None:
        if self.view_mode == "list" and self.current_page > 1:
            self.current_page -= 1
            self.load_tickets()

    async def on_unmount(self) -> None:
        await self.client.close()


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def html_to_markdown(html: str, inline_images: list[str] | None = None) -> str:
    """Convert HTML to markdown for display.

    Collects inline image URLs into inline_images list if provided.
    """
    if not html:
        return ""
    try:
        # Extract inline images before markdownify strips them
        if inline_images is not None:
            for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html):
                inline_images.append(match.group(1))

        # Convert <img> tags to markdown image syntax so they show as links
        def img_to_link(m: re.Match) -> str:
            src = ""
            alt = ""
            src_match = re.search(r'src=["\']([^"\']+)["\']', m.group(0))
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', m.group(0))
            if src_match:
                src = src_match.group(1)
            if alt_match:
                alt = alt_match.group(1)
            name = alt or src.rsplit("/", 1)[-1][:40] or "image"
            return f'<a href="{src}">[Image: {name}]</a>'

        html = re.sub(r"<img[^>]*>", img_to_link, html)
        return markdownify.markdownify(html, strip=["script", "style"])
    except Exception:
        return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Freshdesk TUI - Terminal ticket browser")
    parser.add_argument(
        "--filter",
        "-f",
        choices=[n.lower() for n in FILTER_NAMES],
        default=None,
        help="Initial status filter: " + ", ".join(FILTER_NAMES),
    )
    args = parser.parse_args()
    try:
        app = FreshdeskTUI(initial_filter=args.filter)
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    app.run()


if __name__ == "__main__":
    main()
