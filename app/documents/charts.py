# app/documents/charts.py

"""Matplotlib Chart Generation Utilities for Kirana AI Agent.

Generates high-resolution chart images for PPTX presentation slides with
safe resource cleanup (try...finally plt.close()) and headless backend compatibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless server execution
import matplotlib.pyplot as plt


def create_daily_sales_chart(daily_sales: List[Dict[str, Any]], output_path: Path) -> Path:
    """Generate line/bar chart for daily sales trend."""
    dates = [item.get("date", "") for item in daily_sales]
    sales = [float(item.get("total_sales", 0)) for item in daily_sales]

    if not dates:
        dates = ["No Data"]
        sales = [0.0]

    fig = plt.figure(figsize=(6.5, 4.0), dpi=150)
    try:
        plt.plot(dates, sales, marker="o", color="#2B6CB0", linewidth=2.5, markersize=6)
        plt.fill_between(dates, sales, color="#EBF8FF", alpha=0.5)

        plt.title("Daily Sales Trend (₹)", fontsize=12, fontweight="bold", pad=12, color="#1A365D")
        plt.xlabel("Date", fontsize=10, labelpad=8)
        plt.ylabel("Sales (₹)", fontsize=10, labelpad=8)
        plt.xticks(rotation=30, ha="right", fontsize=8)
        plt.yticks(fontsize=8)
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, format="png", bbox_inches="tight")
    finally:
        plt.close(fig)

    return output_path


def create_payment_method_chart(payment_summary: Dict[str, Any], output_path: Path) -> Path:
    """Generate pie/donut chart for payment method breakdown."""
    methods = []
    amounts = []

    # Map payment breakdown dictionary
    for method, amt in payment_summary.items():
        val = float(amt)
        if val > 0:
            methods.append(str(method))
            amounts.append(val)

    if not amounts:
        methods = ["No Transactions"]
        amounts = [1.0]

    colors_list = ["#319795", "#3182CE", "#D69E2E", "#DD6B20", "#805AD5"][: len(methods)]

    fig = plt.figure(figsize=(6.5, 4.0), dpi=150)
    try:
        wedges, texts, autotexts = plt.pie(
            amounts,
            labels=methods,
            autopct="%1.1f%%" if sum(amounts) > 1 else "",
            startangle=140,
            colors=colors_list,
            textprops={"fontsize": 9},
        )
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")

        plt.title("Payment Method Breakdown", fontsize=12, fontweight="bold", pad=12, color="#1A365D")
        plt.tight_layout()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, format="png", bbox_inches="tight")
    finally:
        plt.close(fig)

    return output_path


def create_top_products_chart(top_products: List[Dict[str, Any]], output_path: Path) -> Path:
    """Generate horizontal bar chart for top products by revenue."""
    names = [item.get("name", "Product")[:20] for item in reversed(top_products)]
    revenues = [float(item.get("total_revenue", 0)) for item in reversed(top_products)]

    if not names:
        names = ["No Data"]
        revenues = [0.0]

    fig = plt.figure(figsize=(6.5, 4.0), dpi=150)
    try:
        bars = plt.barh(names, revenues, color="#2B6CB0", height=0.6)

        plt.title("Top Products by Revenue (₹)", fontsize=12, fontweight="bold", pad=12, color="#1A365D")
        plt.xlabel("Total Revenue (₹)", fontsize=10, labelpad=8)
        plt.xticks(fontsize=8)
        plt.yticks(fontsize=8)
        plt.grid(axis="x", linestyle="--", alpha=0.5)

        # Annotate bar values
        for bar in bars:
            width = bar.get_width()
            if width > 0:
                plt.text(
                    width + (max(revenues) * 0.01 if revenues else 1),
                    bar.get_y() + bar.get_height() / 2,
                    f"₹{width:,.0f}",
                    ha="left",
                    va="center",
                    fontsize=8,
                    color="#2D3748",
                )

        plt.tight_layout()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, format="png", bbox_inches="tight")
    finally:
        plt.close(fig)

    return output_path
