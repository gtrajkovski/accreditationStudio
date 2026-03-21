"""Chart Generator for PDF Reports.

Generates matplotlib charts as base64-encoded PNG images for embedding in PDFs.
Uses headless 'Agg' backend for server-side rendering.
"""

import io
import base64
from typing import Dict, List, Any

# CRITICAL: Set backend BEFORE importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


class ChartGenerator:
    """Generates charts for PDF reports."""

    # Project color scheme
    COLORS = {
        "compliance": "#4ade80",     # green
        "evidence": "#3b82f6",       # blue
        "documents": "#f59e0b",      # amber
        "consistency": "#a78bfa",    # purple
        "critical": "#ef4444",       # red
        "high": "#fb923c",           # orange
        "medium": "#fbbf24",         # yellow
        "low": "#4ade80",            # green
    }

    @staticmethod
    def generate_readiness_chart(readiness: Dict[str, Any]) -> str:
        """Generate ring chart showing readiness sub-scores.

        Args:
            readiness: Readiness dict with compliance, evidence, documents, consistency scores

        Returns:
            Base64-encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(6, 6), dpi=150)

        # Extract scores
        scores = [
            readiness.get("compliance", 0),
            readiness.get("evidence", 0),
            readiness.get("documents", 0),
            readiness.get("consistency", 0),
        ]
        labels = ["Compliance", "Evidence", "Documents", "Consistency"]
        colors = [
            ChartGenerator.COLORS["compliance"],
            ChartGenerator.COLORS["evidence"],
            ChartGenerator.COLORS["documents"],
            ChartGenerator.COLORS["consistency"],
        ]

        # Create ring chart (donut)
        wedges, texts, autotexts = ax.pie(
            scores,
            labels=labels,
            colors=colors,
            autopct='%1.0f%%',
            startangle=90,
            wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2),
            textprops=dict(color="black", fontsize=10, weight="bold"),
        )

        # Center text showing total score
        total_score = readiness.get("total", 0)
        ax.text(
            0, 0, f"{total_score}",
            ha='center', va='center',
            fontsize=32, weight='bold', color='#1a1a2e'
        )
        ax.text(
            0, -0.15, "TOTAL",
            ha='center', va='center',
            fontsize=12, weight='normal', color='#6b7280'
        )

        # Make autopct text black for visibility
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_weight('bold')

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor='white', dpi=150)
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return f"data:image/png;base64,{image_base64}"

    @staticmethod
    def generate_findings_bar_chart(findings_summary: Dict[str, Dict[str, int]]) -> str:
        """Generate horizontal bar chart showing findings by severity.

        Args:
            findings_summary: Dict with critical/high/medium/low keys, each with count/resolved/open

        Returns:
            Base64-encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)

        severities = ["Critical", "High", "Medium", "Low"]
        severity_keys = ["critical", "high", "medium", "low"]

        open_counts = [findings_summary.get(k, {}).get("open", 0) for k in severity_keys]
        in_progress_counts = [findings_summary.get(k, {}).get("in_progress", 0) for k in severity_keys]
        resolved_counts = [findings_summary.get(k, {}).get("resolved", 0) for k in severity_keys]

        # Horizontal stacked bar chart
        y_pos = range(len(severities))

        bars1 = ax.barh(y_pos, open_counts, color='#ef4444', label='Open')
        bars2 = ax.barh(y_pos, in_progress_counts, left=open_counts, color='#fbbf24', label='In Progress')

        # Calculate left position for resolved bars
        left_resolved = [open_counts[i] + in_progress_counts[i] for i in range(len(severities))]
        bars3 = ax.barh(y_pos, resolved_counts, left=left_resolved, color='#4ade80', label='Resolved')

        ax.set_yticks(y_pos)
        ax.set_yticklabels(severities)
        ax.set_xlabel('Number of Findings', fontsize=10, weight='bold')
        ax.set_title('Compliance Findings by Severity', fontsize=12, weight='bold', pad=15)
        ax.legend(loc='upper right', frameon=False, fontsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor='white', dpi=150)
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return f"data:image/png;base64,{image_base64}"
