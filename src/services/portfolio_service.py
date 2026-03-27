"""Portfolio Service for Multi-Institution Mode.

Manages portfolios (named groups of institutions) for consultants managing
20-50+ institutions. Provides aggregate readiness metrics, comparison data,
and recent institution tracking for quick navigation.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from src.db.connection import get_conn
from src.services.readiness_service import get_or_compute_readiness, CACHE_WINDOW_MINUTES


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Portfolio:
    """A named group of institutions."""
    id: str
    name: str
    description: Optional[str] = None
    color: str = "#C9A84C"
    icon: str = "folder"
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""
    institution_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items()}

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Portfolio":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            color=row.get("color", "#C9A84C"),
            icon=row.get("icon", "folder"),
            sort_order=row.get("sort_order", 0),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            institution_count=row.get("institution_count", 0),
        )


@dataclass
class PortfolioReadiness:
    """Aggregate readiness metrics for a portfolio."""
    portfolio_id: str
    avg_score: int
    min_score: int
    max_score: int
    institution_count: int
    at_risk_count: int  # score < 60
    ready_count: int    # score >= 80
    breakdown: Dict[str, Any] = field(default_factory=dict)
    institutions: List[Dict[str, Any]] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "avg_score": self.avg_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "institution_count": self.institution_count,
            "at_risk_count": self.at_risk_count,
            "ready_count": self.ready_count,
            "breakdown": self.breakdown,
            "institutions": self.institutions,
            "computed_at": self.computed_at,
        }


# =============================================================================
# Portfolio CRUD
# =============================================================================

def generate_id(prefix: str = "portfolio") -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


def create_portfolio(
    name: str,
    description: Optional[str] = None,
    color: str = "#C9A84C",
    icon: str = "folder"
) -> Portfolio:
    """Create a new portfolio."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    portfolio_id = generate_id("portfolio")

    conn.execute(
        """
        INSERT INTO portfolios (id, name, description, color, icon, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM portfolios), ?, ?)
        """,
        (portfolio_id, name, description, color, icon, now, now)
    )
    conn.commit()

    return Portfolio(
        id=portfolio_id,
        name=name,
        description=description,
        color=color,
        icon=icon,
        created_at=now,
        updated_at=now,
        institution_count=0,
    )


def update_portfolio(
    portfolio_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    sort_order: Optional[int] = None
) -> Optional[Portfolio]:
    """Update portfolio metadata."""
    conn = get_conn()

    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if color is not None:
        updates.append("color = ?")
        params.append(color)
    if icon is not None:
        updates.append("icon = ?")
        params.append(icon)
    if sort_order is not None:
        updates.append("sort_order = ?")
        params.append(sort_order)

    if not updates:
        return get_portfolio(portfolio_id)

    updates.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).isoformat())
    params.append(portfolio_id)

    conn.execute(
        f"UPDATE portfolios SET {', '.join(updates)} WHERE id = ?",
        params
    )
    conn.commit()

    return get_portfolio(portfolio_id)


def delete_portfolio(portfolio_id: str) -> bool:
    """Delete a portfolio (not its institutions)."""
    if portfolio_id == "portfolio_all":
        return False  # Cannot delete default portfolio

    conn = get_conn()
    cursor = conn.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_portfolio(portfolio_id: str) -> Optional[Portfolio]:
    """Get a portfolio by ID with institution count."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM portfolio_institutions pi WHERE pi.portfolio_id = p.id) as institution_count
        FROM portfolios p
        WHERE p.id = ?
        """,
        (portfolio_id,)
    ).fetchone()

    if not row:
        return None

    return Portfolio.from_row(dict(row))


def list_portfolios() -> List[Portfolio]:
    """List all portfolios with institution counts."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM portfolio_institutions pi WHERE pi.portfolio_id = p.id) as institution_count
        FROM portfolios p
        ORDER BY p.sort_order ASC, p.name ASC
        """
    ).fetchall()

    return [Portfolio.from_row(dict(row)) for row in rows]


# =============================================================================
# Portfolio Membership
# =============================================================================

def add_institutions_to_portfolio(portfolio_id: str, institution_ids: List[str]) -> int:
    """Add institutions to a portfolio. Returns count added."""
    conn = get_conn()
    added = 0

    for inst_id in institution_ids:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO portfolio_institutions (id, portfolio_id, institution_id, sort_order)
                VALUES (?, ?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1
                                  FROM portfolio_institutions WHERE portfolio_id = ?))
                """,
                (generate_id("pi"), portfolio_id, inst_id, portfolio_id)
            )
            added += 1
        except Exception as e:
            logger.debug("Institution %s already in portfolio or error: %s", inst_id, e)

    conn.commit()
    return added


def remove_institution_from_portfolio(portfolio_id: str, institution_id: str) -> bool:
    """Remove an institution from a portfolio."""
    conn = get_conn()
    cursor = conn.execute(
        "DELETE FROM portfolio_institutions WHERE portfolio_id = ? AND institution_id = ?",
        (portfolio_id, institution_id)
    )
    conn.commit()
    return cursor.rowcount > 0


def get_portfolio_institutions(portfolio_id: str) -> List[str]:
    """Get institution IDs in a portfolio."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT institution_id
        FROM portfolio_institutions
        WHERE portfolio_id = ?
        ORDER BY sort_order ASC
        """,
        (portfolio_id,)
    ).fetchall()

    return [row["institution_id"] for row in rows]


def get_institution_portfolios(institution_id: str) -> List[Portfolio]:
    """Get portfolios containing an institution."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM portfolio_institutions pi2 WHERE pi2.portfolio_id = p.id) as institution_count
        FROM portfolios p
        JOIN portfolio_institutions pi ON p.id = pi.portfolio_id
        WHERE pi.institution_id = ?
        ORDER BY p.sort_order ASC
        """,
        (institution_id,)
    ).fetchall()

    return [Portfolio.from_row(dict(row)) for row in rows]


def reorder_portfolio_institutions(portfolio_id: str, institution_ids: List[str]) -> bool:
    """Reorder institutions within a portfolio."""
    conn = get_conn()

    for idx, inst_id in enumerate(institution_ids):
        conn.execute(
            "UPDATE portfolio_institutions SET sort_order = ? WHERE portfolio_id = ? AND institution_id = ?",
            (idx, portfolio_id, inst_id)
        )

    conn.commit()
    return True


# =============================================================================
# Portfolio Readiness Aggregation
# =============================================================================

def get_batch_readiness_snapshots(
    institution_ids: List[str],
    cache_window_minutes: int = CACHE_WINDOW_MINUTES
) -> Dict[str, Dict[str, Any]]:
    """Batch load recent readiness snapshots for multiple institutions.

    Returns dict mapping institution_id -> readiness dict (or None if stale/missing).
    This avoids N+1 queries when computing portfolio readiness.

    Args:
        institution_ids: List of institution IDs to fetch
        cache_window_minutes: Only return snapshots newer than this

    Returns:
        Dict mapping institution_id to readiness scores dict
    """
    if not institution_ids:
        return {}

    conn = get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cache_window_minutes)).isoformat()

    # Single query for all institutions
    placeholders = ",".join("?" * len(institution_ids))
    cursor = conn.execute(f"""
        SELECT institution_id, score_total, score_documents, score_compliance,
               score_evidence, score_consistency, created_at
        FROM institution_readiness_snapshots
        WHERE institution_id IN ({placeholders})
          AND created_at > ?
        ORDER BY created_at DESC
    """, (*institution_ids, cutoff))

    results = {}
    seen = set()
    for row in cursor:
        inst_id = row["institution_id"]
        if inst_id not in seen:  # Take most recent per institution
            seen.add(inst_id)
            results[inst_id] = {
                "total": row["score_total"],
                "documents": row["score_documents"],
                "compliance": row["score_compliance"],
                "evidence": row["score_evidence"],
                "consistency": row["score_consistency"],
            }

    return results


def compute_portfolio_readiness(
    portfolio_id: str,
    workspace_manager,
    force_recompute: bool = False
) -> PortfolioReadiness:
    """Compute aggregate readiness metrics for a portfolio.

    Args:
        portfolio_id: Portfolio ID or 'portfolio_all' for all institutions
        workspace_manager: WorkspaceManager instance for listing institutions
        force_recompute: Force fresh computation of individual scores

    Returns:
        PortfolioReadiness with aggregate metrics and per-institution scores
    """
    # Get institution IDs
    if portfolio_id == "portfolio_all":
        # All institutions from workspace
        all_insts = workspace_manager.list_institutions()
        institution_ids = [inst["id"] for inst in all_insts]
    else:
        institution_ids = get_portfolio_institutions(portfolio_id)

    if not institution_ids:
        return PortfolioReadiness(
            portfolio_id=portfolio_id,
            avg_score=0,
            min_score=0,
            max_score=0,
            institution_count=0,
            at_risk_count=0,
            ready_count=0,
            institutions=[],
        )

    # Get institution details from workspace
    all_insts = workspace_manager.list_institutions()
    inst_map = {inst["id"]: inst for inst in all_insts}

    # Batch load cached snapshots (1 query instead of N) - Phase 28 optimization
    cached_snapshots = {} if force_recompute else get_batch_readiness_snapshots(institution_ids)

    # Compute readiness for each institution
    institutions = []
    scores = []
    at_risk = 0
    ready = 0
    by_accreditor = {}

    for inst_id in institution_ids:
        inst_info = inst_map.get(inst_id)
        if not inst_info:
            continue

        # Use cached snapshot if available, else compute (avoids N+1 queries)
        if inst_id in cached_snapshots:
            readiness = cached_snapshots[inst_id]
            score = readiness.get("total", 0)
        else:
            # Only compute for institutions without cached snapshot
            try:
                readiness = get_or_compute_readiness(inst_id, force_recompute=force_recompute)
                score = readiness.get("total", 0)
            except Exception as e:
                logger.debug("Readiness computation failed for %s: %s", inst_id, e)
                score = 0
                readiness = {"total": 0, "documents": 0, "compliance": 0, "evidence": 0, "consistency": 0}

        scores.append(score)

        # Track risk/ready counts
        if score < 60:
            at_risk += 1
        elif score >= 80:
            ready += 1

        # Group by accreditor
        accreditor = inst_info.get("accrediting_body", "Unknown")
        if accreditor not in by_accreditor:
            by_accreditor[accreditor] = {"count": 0, "total_score": 0, "institutions": []}
        by_accreditor[accreditor]["count"] += 1
        by_accreditor[accreditor]["total_score"] += score
        by_accreditor[accreditor]["institutions"].append(inst_id)

        institutions.append({
            "id": inst_id,
            "name": inst_info.get("name", "Unknown"),
            "accreditor": accreditor,
            "score": score,
            "documents": readiness.get("documents", 0),
            "compliance": readiness.get("compliance", 0),
            "evidence": readiness.get("evidence", 0),
            "consistency": readiness.get("consistency", 0),
            "status": "at_risk" if score < 60 else ("ready" if score >= 80 else "moderate"),
        })

    # Compute aggregates
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0

    # Compute by-accreditor averages
    for accr in by_accreditor:
        by_accreditor[accr]["avg_score"] = round(
            by_accreditor[accr]["total_score"] / by_accreditor[accr]["count"]
        )
        del by_accreditor[accr]["total_score"]

    # Score distribution
    distribution = {
        "excellent": len([s for s in scores if s >= 90]),
        "good": len([s for s in scores if 80 <= s < 90]),
        "moderate": len([s for s in scores if 60 <= s < 80]),
        "at_risk": len([s for s in scores if s < 60]),
    }

    return PortfolioReadiness(
        portfolio_id=portfolio_id,
        avg_score=avg_score,
        min_score=min_score,
        max_score=max_score,
        institution_count=len(institutions),
        at_risk_count=at_risk,
        ready_count=ready,
        breakdown={
            "by_accreditor": by_accreditor,
            "distribution": distribution,
        },
        institutions=sorted(institutions, key=lambda x: x["score"], reverse=True),
    )


def persist_portfolio_snapshot(portfolio_id: str, readiness: PortfolioReadiness) -> str:
    """Persist a portfolio readiness snapshot."""
    conn = get_conn()
    snapshot_id = generate_id("psnap")

    conn.execute(
        """
        INSERT INTO portfolio_readiness_snapshots
        (id, portfolio_id, avg_score, min_score, max_score, institution_count,
         at_risk_count, ready_count, breakdown_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            portfolio_id,
            readiness.avg_score,
            readiness.min_score,
            readiness.max_score,
            readiness.institution_count,
            readiness.at_risk_count,
            readiness.ready_count,
            json.dumps(readiness.breakdown),
            readiness.computed_at,
        )
    )
    conn.commit()
    return snapshot_id


def get_portfolio_history(portfolio_id: str, days: int = 90) -> List[Dict[str, Any]]:
    """Get historical portfolio snapshots."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM portfolio_readiness_snapshots
        WHERE portfolio_id = ?
        AND created_at >= datetime('now', ?)
        ORDER BY created_at ASC
        """,
        (portfolio_id, f"-{days} days")
    ).fetchall()

    return [
        {
            "id": row["id"],
            "avg_score": row["avg_score"],
            "min_score": row["min_score"],
            "max_score": row["max_score"],
            "institution_count": row["institution_count"],
            "at_risk_count": row["at_risk_count"],
            "ready_count": row["ready_count"],
            "breakdown": json.loads(row["breakdown_json"]) if row["breakdown_json"] else {},
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# =============================================================================
# Comparison Data
# =============================================================================

def get_portfolio_comparison(
    portfolio_id: str,
    workspace_manager,
    institution_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Get comparison data for institutions in a portfolio.

    Args:
        portfolio_id: Portfolio ID
        workspace_manager: WorkspaceManager instance
        institution_ids: Optional subset of institutions to compare (max 4)

    Returns:
        Comparison data with radar chart format and sortable metrics
    """
    readiness = compute_portfolio_readiness(portfolio_id, workspace_manager)

    # Filter to specific institutions if provided
    institutions = readiness.institutions
    if institution_ids:
        institutions = [i for i in institutions if i["id"] in institution_ids]

    # Limit to 4 for comparison
    institutions = institutions[:4]

    # Format for radar chart (Chart.js)
    labels = ["Documents", "Compliance", "Evidence", "Consistency"]
    datasets = []

    colors = ["#C9A84C", "#4ade80", "#3b82f6", "#f472b6"]

    for idx, inst in enumerate(institutions):
        datasets.append({
            "label": inst["name"],
            "data": [
                inst["documents"],
                inst["compliance"],
                inst["evidence"],
                inst["consistency"],
            ],
            "borderColor": colors[idx % len(colors)],
            "backgroundColor": colors[idx % len(colors)] + "33",  # 20% opacity
        })

    return {
        "portfolio_id": portfolio_id,
        "institutions": institutions,
        "chart": {
            "type": "radar",
            "labels": labels,
            "datasets": datasets,
        },
        "metrics": [
            {"key": "score", "label": "Overall Score"},
            {"key": "documents", "label": "Documents"},
            {"key": "compliance", "label": "Compliance"},
            {"key": "evidence", "label": "Evidence"},
            {"key": "consistency", "label": "Consistency"},
        ],
    }


# =============================================================================
# Recent Institution Tracking
# =============================================================================

def record_institution_access(institution_id: str) -> None:
    """Record that an institution was accessed (for quick-switcher)."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    # Upsert: insert or update accessed_at
    conn.execute(
        """
        INSERT INTO recent_institutions (id, institution_id, accessed_at)
        VALUES (?, ?, ?)
        ON CONFLICT(institution_id) DO UPDATE SET accessed_at = excluded.accessed_at
        """,
        (generate_id("recent"), institution_id, now)
    )
    conn.commit()

    # Keep only last 20 entries
    conn.execute(
        """
        DELETE FROM recent_institutions
        WHERE id NOT IN (
            SELECT id FROM recent_institutions
            ORDER BY accessed_at DESC
            LIMIT 20
        )
        """
    )
    conn.commit()


def get_recent_institutions(limit: int = 5) -> List[str]:
    """Get recently accessed institution IDs."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT institution_id
        FROM recent_institutions
        ORDER BY accessed_at DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    return [row["institution_id"] for row in rows]


def clear_recent_institutions() -> None:
    """Clear recent institution history."""
    conn = get_conn()
    conn.execute("DELETE FROM recent_institutions")
    conn.commit()
