"""Cost Tracking Service for AI API usage."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from src.db.connection import get_conn
from src.services.batch_service import MODEL_PRICING


def log_api_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    institution_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    operation: Optional[str] = None
) -> str:
    """Log an API call with token usage and cost.

    Args:
        model: Model name (e.g., 'claude-sonnet-4-20250514')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        institution_id: Institution ID (optional)
        agent_type: Agent type name (optional)
        operation: Operation type (e.g., 'audit', 'chat') (optional)

    Returns:
        ID of the logged cost record
    """
    conn = get_conn()

    # Calculate cost
    pricing = MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})
    cost = (input_tokens / 1_000_000 * pricing["input"] +
            output_tokens / 1_000_000 * pricing["output"])

    call_id = f"cost_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

    conn.execute("""
        INSERT INTO ai_cost_log (id, institution_id, agent_type, model,
                                  input_tokens, output_tokens, cost_usd, operation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (call_id, institution_id, agent_type, model,
          input_tokens, output_tokens, cost, operation))
    conn.commit()

    return call_id


def get_cost_summary(
    institution_id: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """Get cost summary for time period.

    Args:
        institution_id: Filter by institution (None = all institutions)
        days: Number of days to look back

    Returns:
        Dictionary with:
            - total_cost: Total cost in USD
            - input_tokens: Total input tokens
            - output_tokens: Total output tokens
            - call_count: Number of API calls
            - by_agent: List of cost breakdowns by agent type
            - by_model: List of cost breakdowns by model
            - daily_trend: List of daily cost totals
            - period_days: Number of days in period
    """
    conn = get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Build query
    where = "WHERE created_at > ?"
    params = [cutoff]
    if institution_id:
        where += " AND institution_id = ?"
        params.append(institution_id)

    # Total cost
    cursor = conn.execute(f"""
        SELECT SUM(cost_usd) as total,
               SUM(input_tokens) as input_tokens,
               SUM(output_tokens) as output_tokens,
               COUNT(*) as call_count
        FROM ai_cost_log {where}
    """, params)
    row = cursor.fetchone()

    # By agent type
    cursor = conn.execute(f"""
        SELECT agent_type, SUM(cost_usd) as cost, COUNT(*) as calls
        FROM ai_cost_log {where}
        GROUP BY agent_type
        ORDER BY cost DESC
    """, params)
    by_agent = [dict(r) for r in cursor.fetchall()]

    # By model
    cursor = conn.execute(f"""
        SELECT model, SUM(cost_usd) as cost, COUNT(*) as calls
        FROM ai_cost_log {where}
        GROUP BY model
        ORDER BY cost DESC
    """, params)
    by_model = [dict(r) for r in cursor.fetchall()]

    # Daily trend
    cursor = conn.execute(f"""
        SELECT DATE(created_at) as date, SUM(cost_usd) as cost
        FROM ai_cost_log {where}
        GROUP BY DATE(created_at)
        ORDER BY date
    """, params)
    daily = [dict(r) for r in cursor.fetchall()]

    return {
        "total_cost": round(row["total"] or 0, 2),
        "input_tokens": row["input_tokens"] or 0,
        "output_tokens": row["output_tokens"] or 0,
        "call_count": row["call_count"] or 0,
        "by_agent": by_agent,
        "by_model": by_model,
        "daily_trend": daily,
        "period_days": days,
    }


def check_budget(institution_id: str) -> Dict[str, Any]:
    """Check if institution is approaching budget limit.

    Args:
        institution_id: Institution ID

    Returns:
        Dictionary with:
            - has_budget: Whether institution has a budget configured
            - monthly_budget: Monthly budget limit (if has_budget)
            - used: Amount used this month (if has_budget)
            - remaining: Amount remaining (if has_budget)
            - percent_used: Percentage of budget used (if has_budget)
            - alert: Whether alert threshold has been exceeded (if has_budget)
    """
    conn = get_conn()

    # Get budget
    cursor = conn.execute("""
        SELECT monthly_budget_usd, alert_threshold
        FROM ai_budgets WHERE institution_id = ?
    """, (institution_id,))
    budget_row = cursor.fetchone()

    if not budget_row:
        return {"has_budget": False}

    budget = budget_row["monthly_budget_usd"]
    threshold = budget_row["alert_threshold"]

    # Get current month usage
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    cursor = conn.execute("""
        SELECT SUM(cost_usd) as used
        FROM ai_cost_log
        WHERE institution_id = ? AND created_at >= ?
    """, (institution_id, month_start.isoformat()))
    used = cursor.fetchone()["used"] or 0

    return {
        "has_budget": True,
        "monthly_budget": budget,
        "used": round(used, 2),
        "remaining": round(budget - used, 2),
        "percent_used": round(used / budget * 100, 1) if budget > 0 else 0,
        "alert": used >= budget * threshold,
    }


def set_budget(
    institution_id: str,
    monthly_budget_usd: float,
    alert_threshold: float = 0.8
) -> None:
    """Set or update budget for an institution.

    Args:
        institution_id: Institution ID
        monthly_budget_usd: Monthly budget limit in USD
        alert_threshold: Alert threshold (0.0-1.0, default 0.8 = 80%)
    """
    conn = get_conn()

    conn.execute("""
        INSERT INTO ai_budgets (institution_id, monthly_budget_usd, alert_threshold)
        VALUES (?, ?, ?)
        ON CONFLICT(institution_id) DO UPDATE SET
            monthly_budget_usd = excluded.monthly_budget_usd,
            alert_threshold = excluded.alert_threshold,
            updated_at = datetime('now')
    """, (institution_id, monthly_budget_usd, alert_threshold))
    conn.commit()
