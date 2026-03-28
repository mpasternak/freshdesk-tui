"""Tests for pure functions in freshdesk_tui.app."""

from __future__ import annotations

import pytest

from freshdesk_tui.app import (
    _format_size,
    format_dt,
    html_to_markdown,
    priority_style,
    status_style,
)


class TestFormatDt:
    def test_iso_datetime(self):
        assert format_dt("2026-03-15T14:30:00Z") == "2026-03-15 14:30"

    def test_iso_with_timezone(self):
        result = format_dt("2026-03-15T14:30:00+02:00")
        assert result == "2026-03-15 14:30"

    def test_empty_string(self):
        assert format_dt("") == ""

    def test_invalid_date_returns_truncated(self):
        assert format_dt("not-a-date-at-all") == "not-a-date-at-al"

    def test_short_invalid_string(self):
        result = format_dt("short")
        # Falls through to iso[:16]
        assert result == "short"


class TestPriorityStyle:
    def test_urgent(self):
        assert "Urgent" in priority_style(4)
        assert "red" in priority_style(4)

    def test_high(self):
        assert "High" in priority_style(3)
        assert "yellow" in priority_style(3)

    def test_medium(self):
        assert priority_style(2) == "Medium"

    def test_low(self):
        assert "Low" in priority_style(1)
        assert "dim" in priority_style(1)


class TestStatusStyle:
    def test_open(self):
        assert "Open" in status_style(2)
        assert "green" in status_style(2)

    def test_pending(self):
        assert "Pending" in status_style(3)

    def test_resolved(self):
        assert "Resolved" in status_style(4)

    def test_closed(self):
        assert "Closed" in status_style(5)

    def test_unknown(self):
        assert status_style(99) == "99"


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(500) == "500 B"

    def test_kilobytes(self):
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert _format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_zero(self):
        assert _format_size(0) == "0 B"

    def test_boundary_kb(self):
        assert _format_size(1024) == "1.0 KB"

    def test_boundary_mb(self):
        assert _format_size(1024 * 1024) == "1.0 MB"


class TestHtmlToMarkdown:
    def test_empty_string(self):
        assert html_to_markdown("") == ""

    def test_simple_html(self):
        result = html_to_markdown("<p>Hello world</p>")
        assert "Hello world" in result

    def test_strips_script_tags(self):
        result = html_to_markdown("<p>Safe</p><script>alert('xss')</script>")
        assert "Safe" in result
        # Script tags are stripped (no <script> in output)
        assert "<script>" not in result

    def test_img_converted_to_link(self):
        html = '<img src="https://example.com/pic.png" alt="Photo">'
        result = html_to_markdown(html)
        assert "Photo" in result
        assert "example.com/pic.png" in result

    def test_inline_images_collected(self):
        html = '<p>Text</p><img src="https://example.com/a.png"><img src="https://example.com/b.jpg">'
        images: list[str] = []
        html_to_markdown(html, inline_images=images)
        assert len(images) == 2
        assert "https://example.com/a.png" in images
        assert "https://example.com/b.jpg" in images

    def test_inline_images_none_does_not_crash(self):
        html = '<img src="https://example.com/pic.png">'
        result = html_to_markdown(html, inline_images=None)
        assert result  # Should not crash
