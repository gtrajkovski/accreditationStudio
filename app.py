"""AccreditAI - Main Flask Application.

AI-powered accreditation management platform for post-secondary
educational institutions.
"""

import atexit
from flask import Flask, render_template, redirect, url_for

from src.config import Config
from src.ai.client import AIClient
from src.core.workspace import WorkspaceManager
from src.core.task_queue import get_task_queue, shutdown_task_queue
from src.api import (
    chat_bp,
    init_chat_bp,
    agents_bp,
    init_agents_bp,
    institutions_bp,
    init_institutions_bp,
)


# Initialize Flask app
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Initialize core services
workspace_manager = WorkspaceManager()

# Initialize AI client (may fail if no API key)
try:
    ai_client = AIClient()
except ValueError as e:
    print(f"Warning: {e}")
    ai_client = None

# Initialize and register blueprints
init_chat_bp(workspace_manager, ai_client)
init_agents_bp(workspace_manager)
init_institutions_bp(workspace_manager)

app.register_blueprint(chat_bp)
app.register_blueprint(agents_bp)
app.register_blueprint(institutions_bp)

# Start task queue
task_queue = get_task_queue()

# Cleanup on shutdown
atexit.register(shutdown_task_queue)


# =============================================================================
# Page Routes
# =============================================================================

@app.route('/')
def index():
    """Redirect to dashboard."""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    """Main dashboard page."""
    institutions = workspace_manager.list_institutions()

    return render_template(
        'dashboard.html',
        institutions=institutions,
        compliance_rate=0,  # TODO: Calculate from institutions
        pending_actions=0,  # TODO: Count pending checkpoints
        total_documents=0,  # TODO: Sum documents across institutions
        active_sessions=[],  # TODO: Get from agent sessions
    )


@app.route('/institutions')
def institutions_list():
    """List all institutions."""
    institutions = workspace_manager.list_institutions()
    return render_template('institutions/list.html', institutions=institutions)


@app.route('/institutions/new')
def institution_create():
    """Create new institution form."""
    from src.core.models import AccreditingBody
    return render_template(
        'institutions/create.html',
        accrediting_bodies=[b.value for b in AccreditingBody],
    )


@app.route('/institutions/<id>')
def institution_overview(id):
    """Institution overview page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/overview.html',
        institution=institution,
        current_institution=institution,
    )


@app.route('/institutions/<id>/documents')
def institution_documents(id):
    """Institution documents page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/documents.html',
        institution=institution,
        current_institution=institution,
    )


@app.route('/institutions/<id>/compliance')
def institution_compliance(id):
    """Institution compliance status page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/compliance.html',
        institution=institution,
        current_institution=institution,
    )


@app.route('/institutions/<id>/self-study')
def institution_self_study(id):
    """Institution self-study drafts page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/self_study.html',
        institution=institution,
        current_institution=institution,
    )


@app.route('/chat')
def chat():
    """AI chat interface page."""
    return render_template('chat.html')


@app.route('/agent-sessions')
def agent_sessions():
    """Agent sessions management page."""
    return render_template('agent_sessions.html')


# =============================================================================
# Error Handlers
# =============================================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500


# =============================================================================
# Health Check
# =============================================================================

@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "ai_enabled": ai_client is not None,
    }


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    print(f"Starting AccreditAI on port {Config.PORT}...")
    print(f"Workspace directory: {Config.WORKSPACE_DIR}")
    print(f"AI enabled: {ai_client is not None}")

    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=True,
    )
