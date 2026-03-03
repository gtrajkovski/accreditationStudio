"""AccreditAI - Main Flask Application.

AI-powered accreditation management platform for post-secondary
educational institutions.
"""

import atexit
import click
from flask import Flask, render_template, redirect, url_for

from src.config import Config
from src.ai.client import AIClient
from src.core.workspace import WorkspaceManager
from src.core.task_queue import get_task_queue, shutdown_task_queue
from src.core.standards_store import StandardsStore
from src.api import (
    chat_bp,
    init_chat_bp,
    agents_bp,
    init_agents_bp,
    institutions_bp,
    init_institutions_bp,
    standards_bp,
    init_standards_bp,
    settings_bp,
    init_settings_bp,
    work_queue_bp,
    init_work_queue_bp,
    autopilot_bp,
    init_autopilot_bp,
)
from src.api.readiness import readiness_bp, init_readiness_bp
from src.api.audits import audits_bp, init_audits_bp
from src.api.remediation import remediation_bp, init_remediation_bp
from src.api.checklists import checklists_bp, init_checklists_bp
from src.api.packets import packets_bp, init_packets_bp
from src.i18n import t, get_all_strings, get_supported_locales, DEFAULT_LOCALE, SUPPORTED_LOCALES


# Initialize Flask app
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Initialize core services
workspace_manager = WorkspaceManager()
standards_store = StandardsStore()

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
init_standards_bp(standards_store)
init_settings_bp()
init_readiness_bp(workspace_manager)
init_work_queue_bp(workspace_manager)
init_autopilot_bp(workspace_manager)
init_audits_bp(workspace_manager)
init_remediation_bp(workspace_manager)
init_checklists_bp(workspace_manager)
init_packets_bp(workspace_manager)

app.register_blueprint(chat_bp)
app.register_blueprint(agents_bp)
app.register_blueprint(institutions_bp)
app.register_blueprint(standards_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(readiness_bp)
app.register_blueprint(work_queue_bp)
app.register_blueprint(autopilot_bp)
app.register_blueprint(audits_bp)
app.register_blueprint(remediation_bp)
app.register_blueprint(checklists_bp)
app.register_blueprint(packets_bp)


# =============================================================================
# Template Context Processor (i18n)
# =============================================================================

@app.context_processor
def inject_i18n():
    """Inject i18n helpers into all templates."""
    from src.api.settings import get_current_locale, get_current_theme

    # Get current user preferences
    try:
        locale = get_current_locale()
        theme = get_current_theme()
    except Exception:
        locale = DEFAULT_LOCALE
        theme = "system"

    return {
        't': lambda key, params=None: t(key, locale, params),
        'locale': locale,
        'theme': theme,
        'supported_locales': get_supported_locales(),
        'i18n_strings': get_all_strings(locale),
    }

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

    # Calculate metrics
    total_documents = sum(inst.get('document_count', 0) for inst in institutions)

    # Calculate average compliance rate
    assessed = [i for i in institutions if i.get('compliance_status') != 'not_assessed']
    if assessed:
        compliance_scores = {
            'compliant': 100,
            'partial': 50,
            'non_compliant': 0,
        }
        total_score = sum(compliance_scores.get(i['compliance_status'], 0) for i in assessed)
        compliance_rate = round(total_score / len(assessed))
    else:
        compliance_rate = 0

    # Get recent agent sessions across all institutions
    active_sessions = []
    for inst in institutions[:10]:  # Check first 10 institutions
        sessions = workspace_manager.list_agent_sessions(inst['id'], limit=5)
        for sess in sessions:
            if sess.get('status') in ('pending', 'running'):
                sess['institution_name'] = inst['name']
                active_sessions.append(sess)

    # Sort by created_at and limit
    active_sessions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    active_sessions = active_sessions[:5]

    # Count pending actions (checkpoints awaiting approval)
    pending_actions = sum(
        1 for sess in active_sessions
        if sess.get('status') == 'waiting_for_human'
    )

    return render_template(
        'dashboard.html',
        institutions=institutions,
        compliance_rate=compliance_rate,
        pending_actions=pending_actions,
        total_documents=total_documents,
        active_sessions=active_sessions,
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

    # Serialize programs for JavaScript
    programs_json = [p.to_dict() for p in institution.programs]

    return render_template(
        'institutions/overview.html',
        institution=institution,
        current_institution=institution,
        programs_json=programs_json,
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


@app.route('/institutions/<id>/autopilot')
def institution_autopilot(id):
    """Institution autopilot settings page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/autopilot.html',
        institution=institution,
        current_institution=institution,
    )


@app.route('/institutions/<id>/workbench')
def institution_workbench(id):
    """Document workbench for remediation review."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/workbench.html',
        institution=institution,
        current_institution=institution,
    )


@app.route('/institutions/<id>/submissions')
def institution_submissions(id):
    """Submission organizer page for packet assembly."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/submissions.html',
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


@app.route('/work-queue')
def work_queue():
    """Unified work queue page."""
    institutions = workspace_manager.list_institutions()
    return render_template('work_queue.html', institutions=institutions)


@app.route('/settings')
def settings_page():
    """User settings page."""
    return render_template('settings.html')


@app.route('/settings/glossary')
def glossary_page():
    """Terminology glossary editor."""
    return render_template('settings/glossary.html')


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
# Database CLI Commands
# =============================================================================

@app.cli.group()
def db():
    """Database management commands."""
    pass


@db.command()
def upgrade():
    """Apply pending database migrations."""
    from src.db.migrate import apply_migrations, get_db_path

    click.echo(f"Database: {get_db_path()}")
    click.echo("Applying migrations...")

    try:
        applied = apply_migrations()
        if applied:
            click.echo(click.style(f"Applied {len(applied)} migration(s):", fg="green"))
            for version in applied:
                click.echo(f"  - {version}")
        else:
            click.echo(click.style("No pending migrations.", fg="yellow"))
    except Exception as e:
        click.echo(click.style(f"Migration failed: {e}", fg="red"), err=True)
        raise SystemExit(1)


@db.command()
def status():
    """Show database migration status."""
    from src.db.migrate import get_migration_status

    status = get_migration_status()

    click.echo(f"Database: {status['db_path']}")
    click.echo(f"Total migrations: {status['total']}")
    click.echo(f"Applied: {len(status['applied'])}")
    click.echo(f"Pending: {len(status['pending'])}")

    if status['applied']:
        click.echo(click.style("\nApplied:", fg="green"))
        for v in status['applied']:
            click.echo(f"  [x] {v}")

    if status['pending']:
        click.echo(click.style("\nPending:", fg="yellow"))
        for v in status['pending']:
            click.echo(f"  [ ] {v}")


@app.cli.command('init-db')
def init_db():
    """Initialize the database (runs all migrations)."""
    from src.db.migrate import apply_migrations, get_db_path

    click.echo(f"Initializing database at: {get_db_path()}")

    try:
        applied = apply_migrations()
        click.echo(click.style(f"Database initialized with {len(applied)} migration(s).", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Initialization failed: {e}", fg="red"), err=True)
        raise SystemExit(1)


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
