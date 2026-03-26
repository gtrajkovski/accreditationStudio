"""API blueprints for AccreditAI.

Flask blueprints for REST API endpoints.
"""

from src.api.chat import chat_bp, init_chat_bp
from src.api.agents import agents_bp, init_agents_bp
from src.api.institutions import institutions_bp, init_institutions_bp
from src.api.standards import standards_bp, init_standards_bp
from src.api.settings import settings_bp, init_settings_bp
from src.api.work_queue import work_queue_bp, init_work_queue_bp
from src.api.autopilot import autopilot_bp, init_autopilot_bp
from src.api.reports import reports_bp, init_reports_bp
from src.api.audit_trails import audit_trails_bp, init_audit_trails_bp
from src.api.contextual_search import contextual_search_bp, init_contextual_search_bp

__all__ = [
    "chat_bp",
    "init_chat_bp",
    "agents_bp",
    "init_agents_bp",
    "institutions_bp",
    "init_institutions_bp",
    "standards_bp",
    "init_standards_bp",
    "settings_bp",
    "init_settings_bp",
    "work_queue_bp",
    "init_work_queue_bp",
    "autopilot_bp",
    "init_autopilot_bp",
    "reports_bp",
    "init_reports_bp",
    "audit_trails_bp",
    "init_audit_trails_bp",
    "contextual_search_bp",
    "init_contextual_search_bp",
]
