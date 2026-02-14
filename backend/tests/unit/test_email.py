"""Tests for email service: templates and sending."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.email_service import (
    send_email,
    template_order_filled,
    template_agent_error,
    template_pending_approval,
    template_pnl_alert,
    _render_template,
)


class TestEmailTemplates:
    def test_order_filled_buy(self):
        subject, html = template_order_filled("005930", "buy", 10, 70000)
        assert "005930" in subject
        assert "BUY" in subject
        assert "ORDER FILLED" in html
        assert "70,000" in html
        assert "10" in html

    def test_order_filled_sell(self):
        subject, html = template_order_filled("000660", "sell", 5, 150000)
        assert "SELL" in subject
        assert "750,000" in html  # 5 * 150000

    def test_agent_error(self):
        subject, html = template_agent_error("sess-123", "Connection timeout")
        assert "Error" in subject
        assert "AGENT ERROR" in html
        assert "Connection timeout" in html
        assert "sess-123" in html

    def test_pending_approval(self):
        subject, html = template_pending_approval("sess-456", 3, 15_000_000)
        assert "3" in subject
        assert "APPROVAL REQUIRED" in html
        assert "15,000,000" in html

    def test_pnl_alert_loss(self):
        subject, html = template_pnl_alert("005930", -500000, -5.2)
        assert "-5.2%" in subject
        assert "P&L ALERT" in html
        assert "Loss" in html
        assert "500,000" in html

    def test_pnl_alert_gain(self):
        subject, html = template_pnl_alert("035420", 200000, 3.1)
        assert "+3.1%" in subject
        assert "Gain" in html

    def test_base_template_structure(self):
        html = _render_template("<p>Test</p>")
        assert "ABLE" in html
        assert "Test" in html
        assert "<!DOCTYPE html>" in html

    def test_template_with_action_button(self):
        html = _render_template("<p>Test</p>", action_url="https://example.com", action_label="Click Me")
        assert "Click Me" in html
        assert "https://example.com" in html


class TestSendEmail:
    @patch("app.services.email_service.get_settings")
    def test_skip_when_smtp_not_configured(self, mock_settings):
        mock_settings.return_value = MagicMock(smtp_host="")
        result = send_email("test@example.com", "Test", "<p>body</p>")
        assert result is False

    @patch("app.services.email_service.smtplib.SMTP")
    @patch("app.services.email_service.get_settings")
    def test_sends_when_configured(self, mock_settings, mock_smtp):
        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
            smtp_from="noreply@example.com",
            smtp_use_tls=True,
        )
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email("test@example.com", "Test Subject", "<p>body</p>")
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.send_message.assert_called_once()

    @patch("app.services.email_service.smtplib.SMTP")
    @patch("app.services.email_service.get_settings")
    def test_no_tls_when_disabled(self, mock_settings, mock_smtp):
        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            smtp_port=25,
            smtp_user="",
            smtp_password="",
            smtp_from="noreply@example.com",
            smtp_use_tls=False,
        )
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email("test@example.com", "Test", "<p>body</p>")
        assert result is True
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()

    @patch("app.services.email_service.smtplib.SMTP")
    @patch("app.services.email_service.get_settings")
    def test_returns_false_on_smtp_error(self, mock_settings, mock_smtp):
        mock_settings.return_value = MagicMock(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            smtp_from="noreply@example.com",
            smtp_use_tls=True,
        )
        mock_smtp.side_effect = Exception("Connection refused")

        result = send_email("test@example.com", "Test", "<p>body</p>")
        assert result is False
