"""PDF report generation for portfolio and backtest results."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm
BRAND_COLOR = colors.HexColor("#3B82F6")
GREEN = colors.HexColor("#10B981")
RED = colors.HexColor("#EF4444")
GRAY = colors.HexColor("#6B7280")
DARK = colors.HexColor("#1F2937")


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create custom paragraph styles."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=base["Title"],
            fontSize=22, textColor=DARK, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"],
            fontSize=11, textColor=GRAY, spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "Heading", parent=base["Heading2"],
            fontSize=14, textColor=BRAND_COLOR, spaceBefore=16, spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=10, textColor=DARK, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"],
            fontSize=8, textColor=GRAY,
        ),
    }


def _make_table(headers: list[str], rows: list[list[str]],
                col_widths: list[float] | None = None) -> Table:
    """Build a styled table from header + row data."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _format_won(value: float) -> str:
    if abs(value) >= 1e8:
        return f"₩{value / 1e8:,.1f}억"
    if abs(value) >= 1e4:
        return f"₩{value / 1e4:,.0f}만"
    return f"₩{value:,.0f}"


def _pnl_str(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{_format_won(value)}"


def generate_portfolio_report(
    user_name: str,
    stats: dict[str, Any],
    positions: list[dict[str, Any]],
    risk_data: dict[str, Any] | None = None,
) -> bytes:
    """Generate a portfolio summary PDF.

    Returns:
        PDF content as bytes
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )

    styles = _build_styles()
    elements: list[Any] = []

    # ── Header ──
    elements.append(Paragraph("ABLE Portfolio Report", styles["title"]))
    elements.append(Paragraph(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} for {user_name}",
        styles["subtitle"],
    ))
    elements.append(HRFlowable(width="100%", color=BRAND_COLOR, thickness=1))
    elements.append(Spacer(1, 10))

    # ── Portfolio Summary ──
    elements.append(Paragraph("Portfolio Summary", styles["heading"]))

    pv = stats.get("portfolio_value", 0)
    inv = stats.get("total_invested", 0)
    upnl = stats.get("unrealized_pnl", 0)
    rpnl = stats.get("realized_pnl", 0)
    tpnl = stats.get("total_pnl", 0)
    tpct = stats.get("total_pnl_pct", 0)

    summary_rows = [
        ["Portfolio Value", _format_won(pv)],
        ["Total Invested", _format_won(inv)],
        ["Unrealized P&L", _pnl_str(upnl)],
        ["Realized P&L", _pnl_str(rpnl)],
        ["Total P&L", f"{_pnl_str(tpnl)} ({tpct:+.2f}%)"],
        ["Positions", str(stats.get("position_count", 0))],
    ]
    t = _make_table(["Metric", "Value"], summary_rows, col_widths=[200, 250])
    elements.append(t)
    elements.append(Spacer(1, 10))

    # ── Trade Stats ──
    ts = stats.get("trade_stats", {})
    if ts:
        elements.append(Paragraph("Trade Statistics", styles["heading"]))
        trade_rows = [
            ["Total Trades", str(ts.get("total_trades", 0))],
            ["Win Rate", f"{ts.get('win_rate', 0) * 100:.1f}%"],
            ["Profit Factor", f"{ts.get('profit_factor', 0):.2f}"],
            ["Winning Trades", str(ts.get("winning_trades", 0))],
            ["Losing Trades", str(ts.get("losing_trades", 0))],
        ]
        t = _make_table(["Metric", "Value"], trade_rows, col_widths=[200, 250])
        elements.append(t)
        elements.append(Spacer(1, 10))

    # ── Positions Table ──
    if positions:
        elements.append(Paragraph("Open Positions", styles["heading"]))
        pos_headers = ["Stock", "Qty", "Avg Cost", "Current", "P&L"]
        pos_rows = []
        for p in positions:
            name = p.get("stock_name") or p.get("stock_code", "")
            qty = str(p.get("quantity", 0))
            avg = _format_won(p.get("avg_cost_price", 0))
            cur = _format_won(p["current_price"]) if p.get("current_price") else "--"
            pnl = _pnl_str(p["unrealized_pnl"]) if p.get("unrealized_pnl") is not None else "--"
            pos_rows.append([name, qty, avg, cur, pnl])

        widths = [130, 50, 90, 90, 90]
        t = _make_table(pos_headers, pos_rows, col_widths=widths)
        elements.append(t)
        elements.append(Spacer(1, 10))

    # ── Risk Analysis ──
    if risk_data:
        elements.append(Paragraph("Risk Analysis", styles["heading"]))
        var_rows = []
        for method in ["historical", "parametric", "monte_carlo"]:
            v = risk_data.get(method, {})
            if v:
                var_rows.append([
                    method.replace("_", " ").title(),
                    _format_won(v.get("var", 0)),
                    _format_won(v.get("cvar", 0)),
                ])
        if var_rows:
            t = _make_table(["Method", "VaR", "CVaR"], var_rows, col_widths=[150, 150, 150])
            elements.append(t)

        # Stress test results
        stress = risk_data.get("stress_tests", [])
        if stress:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Stress Test Scenarios", styles["heading"]))
            stress_rows = []
            for s in stress:
                stress_rows.append([
                    s.get("scenario", ""),
                    _format_won(s.get("portfolio_loss", 0)),
                    f"{s.get('loss_percent', 0):.1f}%",
                ])
            t = _make_table(["Scenario", "Loss", "Loss %"], stress_rows, col_widths=[160, 140, 80])
            elements.append(t)

    # ── Footer ──
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", color=GRAY, thickness=0.5))
    elements.append(Paragraph(
        "ABLE — AI-Powered Korean Stock Auto-Trading Platform. "
        "This report is for informational purposes only and does not constitute financial advice.",
        styles["small"],
    ))

    doc.build(elements)
    return buf.getvalue()


def generate_backtest_report(
    strategy_name: str,
    params: dict[str, Any],
    results: dict[str, Any],
    trades: list[dict[str, Any]] | None = None,
) -> bytes:
    """Generate a backtest result PDF.

    Returns:
        PDF content as bytes
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )

    styles = _build_styles()
    elements: list[Any] = []

    # ── Header ──
    elements.append(Paragraph("ABLE Backtest Report", styles["title"]))
    elements.append(Paragraph(
        f"Strategy: {strategy_name} | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles["subtitle"],
    ))
    elements.append(HRFlowable(width="100%", color=BRAND_COLOR, thickness=1))
    elements.append(Spacer(1, 10))

    # ── Parameters ──
    elements.append(Paragraph("Strategy Parameters", styles["heading"]))
    param_rows = [[str(k), str(v)] for k, v in params.items()]
    if param_rows:
        t = _make_table(["Parameter", "Value"], param_rows, col_widths=[200, 250])
        elements.append(t)
        elements.append(Spacer(1, 10))

    # ── Performance Metrics ──
    elements.append(Paragraph("Performance Metrics", styles["heading"]))
    metric_rows = [
        ["Total Return", f"{results.get('total_return', 0):.2f}%"],
        ["Annual Return", f"{results.get('annual_return', 0):.2f}%"],
        ["Max Drawdown", f"{results.get('max_drawdown', 0):.2f}%"],
        ["Sharpe Ratio", f"{results.get('sharpe_ratio', 0):.2f}"],
        ["Win Rate", f"{results.get('win_rate', 0) * 100:.1f}%"],
        ["Total Trades", str(results.get("total_trades", 0))],
        ["Profit Factor", f"{results.get('profit_factor', 0):.2f}"],
    ]
    t = _make_table(["Metric", "Value"], metric_rows, col_widths=[200, 250])
    elements.append(t)
    elements.append(Spacer(1, 10))

    # ── Recent Trades ──
    if trades:
        elements.append(Paragraph(f"Trades (showing {min(len(trades), 20)} of {len(trades)})", styles["heading"]))
        trade_headers = ["Date", "Side", "Stock", "Qty", "Price", "P&L"]
        trade_rows = []
        for tr in trades[:20]:
            trade_rows.append([
                str(tr.get("date", "")),
                str(tr.get("side", "")),
                str(tr.get("stock_code", "")),
                str(tr.get("quantity", 0)),
                _format_won(tr.get("price", 0)),
                _pnl_str(tr.get("pnl", 0)),
            ])
        widths = [70, 40, 70, 50, 90, 90]
        t = _make_table(trade_headers, trade_rows, col_widths=widths)
        elements.append(t)

    # ── Footer ──
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", color=GRAY, thickness=0.5))
    elements.append(Paragraph(
        "ABLE — AI-Powered Korean Stock Auto-Trading Platform. "
        "Past performance does not guarantee future results.",
        styles["small"],
    ))

    doc.build(elements)
    return buf.getvalue()
