"""AccreditAI - Main Flask Application.
app.config["TEMPLATES_AUTO_RELOAD"] = Config.ENVIRONMENT != "production"

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
    reports_bp,
    init_reports_bp,
)
from src.api.readiness import readiness_bp, init_readiness_bp
from src.api.audits import audits_bp, init_audits_bp
from src.api.remediation import remediation_bp, init_remediation_bp
from src.api.checklists import checklists_bp, init_checklists_bp
from src.api.packets import packets_bp, init_packets_bp
from src.api.action_plans import action_plans_bp, init_action_plans_bp
from src.api.faculty import faculty_bp, init_faculty_bp
from src.api.catalog import catalog_bp, init_catalog_bp
from src.api.exhibits import exhibits_bp, init_exhibits_bp
from src.api.achievements import achievements_bp, init_achievements_bp
from src.api.interview_prep import interview_prep_bp, init_interview_prep_bp
from src.api.ser import ser_bp, init_ser_bp
from src.api.team_reports import team_reports_bp, init_team_reports_bp
from src.api.compliance_calendar import compliance_calendar_bp, init_compliance_calendar_bp
from src.api.document_reviews import document_reviews_bp, init_document_reviews_bp
from src.api.documents import documents_bp, init_documents_bp
from src.api.impact_analysis import impact_analysis_bp, init_impact_analysis_bp
from src.api.knowledge_graph import knowledge_graph_bp, init_knowledge_graph_bp
from src.api.timeline_planner import timeline_planner_bp, init_timeline_planner_bp
from src.api.site_visit import site_visit_bp, init_site_visit_bp
from src.api.coverage_map import coverage_map_bp, init_coverage_map_bp
from src.api.simulation import simulation_bp, init_simulation_bp
from src.api.portfolios import portfolios_bp, init_portfolios_bp
from src.api.evidence_highlighting import evidence_highlighting_bp, init_evidence_highlighting_bp
from src.api.compliance_heatmap import compliance_heatmap_bp, init_compliance_heatmap_bp
from src.api.batch_history import batch_history_bp, init_batch_history_bp
from src.api.global_search import global_search_bp, init_global_search_bp
from src.api.standard_explainer import standard_explainer_bp, init_standard_explainer_bp
from src.api.evidence_assistant import evidence_assistant_bp, init_evidence_assistant_bp
from src.i18n import t, get_all_strings, get_supported_locales, DEFAULT_LOCALE, SUPPORTED_LOCALES
from src.services.readiness_service import compute_readiness
from src.services.chat_context_service import ChatContextService


# Initialize Flask app
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config["TEMPLATES_AUTO_RELOAD"] = Config.ENVIRONMENT != "production"

# Initialize core services
workspace_manager = WorkspaceManager()
standards_store = StandardsStore()

# Initialize AI client (may fail if no API key)
try:
    ai_client = AIClient()
except ValueError as e:
    print(f"Warning: {e}")
    ai_client = None

# Initialize chat context service
chat_service = ChatContextService(ai_client=ai_client)

# Initialize and register blueprints
init_chat_bp(workspace_manager, ai_client, chat_service)
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
init_action_plans_bp(workspace_manager)
init_faculty_bp(workspace_manager)
init_catalog_bp(workspace_manager)
init_exhibits_bp(workspace_manager)
init_achievements_bp(workspace_manager)
init_interview_prep_bp(workspace_manager)
init_ser_bp(workspace_manager)
init_team_reports_bp(workspace_manager)
init_compliance_calendar_bp(workspace_manager)
init_document_reviews_bp(workspace_manager)
init_documents_bp(workspace_manager)
init_impact_analysis_bp(workspace_manager)
init_knowledge_graph_bp(workspace_manager, standards_store)
init_timeline_planner_bp(workspace_manager)
init_site_visit_bp(workspace_manager)
init_coverage_map_bp(workspace_manager)
init_simulation_bp(workspace_manager)
init_portfolios_bp(workspace_manager)
init_evidence_highlighting_bp(workspace_manager)
init_compliance_heatmap_bp(workspace_manager)
init_batch_history_bp(workspace_manager)
init_global_search_bp(workspace_manager)
init_standard_explainer_bp(ai_client, standards_store)
init_evidence_assistant_bp(ai_client, standards_store)
init_reports_bp(workspace_manager)

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
app.register_blueprint(action_plans_bp)
app.register_blueprint(faculty_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(exhibits_bp)
app.register_blueprint(achievements_bp)
app.register_blueprint(interview_prep_bp)
app.register_blueprint(ser_bp)
app.register_blueprint(team_reports_bp)
app.register_blueprint(compliance_calendar_bp)
app.register_blueprint(document_reviews_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(impact_analysis_bp)
app.register_blueprint(knowledge_graph_bp)
app.register_blueprint(timeline_planner_bp)
app.register_blueprint(site_visit_bp)
app.register_blueprint(coverage_map_bp)
app.register_blueprint(simulation_bp)
app.register_blueprint(portfolios_bp)
app.register_blueprint(evidence_highlighting_bp)
app.register_blueprint(compliance_heatmap_bp)
app.register_blueprint(batch_history_bp)
app.register_blueprint(global_search_bp)
app.register_blueprint(standard_explainer_bp)
app.register_blueprint(evidence_assistant_bp)
app.register_blueprint(reports_bp)


# =============================================================================
# Security Headers
# =============================================================================

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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


def _get_readiness_score(institution_id: str) -> int:
    """Get readiness score for an institution (safe helper)."""
    try:
        readiness = compute_readiness(institution_id)
        return readiness.total
    except Exception:
        return 0


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
        readiness_score=_get_readiness_score(id),
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
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/documents/<doc_id>/viewer')
def document_viewer(id, doc_id):
    """Document viewer with evidence highlighting."""
    from src.core.models import Document

    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    # Get document from database
    from src.db.connection import get_conn
    conn = get_conn()
    cursor = conn.execute(
        "SELECT id, title, doc_type, page_count FROM documents WHERE id = ? AND institution_id = ?",
        (doc_id, id),
    )
    row = cursor.fetchone()
    if not row:
        return render_template('404.html'), 404

    document = {
        'id': row['id'],
        'title': row['title'],
        'doc_type': row['doc_type'],
        'page_count': row['page_count'] or 1,
    }

    return render_template(
        'institutions/document_viewer.html',
        institution=institution,
        current_institution=institution,
        document=document,
        readiness_score=_get_readiness_score(id),
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
        readiness_score=_get_readiness_score(id),
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
        readiness_score=_get_readiness_score(id),
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
        readiness_score=_get_readiness_score(id),
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
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/batch-history')
def institution_batch_history(id):
    """Batch history page for institution."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/batch_history.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
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
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/impact')
def institution_impact(id):
    """Impact analysis page for fact-to-document dependencies."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/impact.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/knowledge-graph')
def institution_knowledge_graph(id):
    """Knowledge graph visualization page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/knowledge_graph.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/timeline-planner')
def institution_timeline_planner(id):
    """Timeline planner page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/timeline_planner.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/coverage-map')
def institution_coverage_map(id):
    """Evidence coverage map page."""
    from src.db.connection import get_conn

    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    # Get available accreditors
    conn = get_conn()
    cursor = conn.execute("SELECT id, code, name FROM accreditors ORDER BY code")
    accreditors = [dict(row) for row in cursor.fetchall()]

    return render_template(
        'institutions/coverage_map.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
        accreditors=accreditors,
    )


@app.route('/institutions/<id>/compliance-heatmap')
def institution_compliance_heatmap(id):
    """Compliance heatmap page (documents × standards matrix)."""
    from src.db.connection import get_conn

    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    # Get available accreditors
    conn = get_conn()
    cursor = conn.execute("SELECT id, code, name FROM accreditors ORDER BY code")
    accreditors = [dict(row) for row in cursor.fetchall()]

    return render_template(
        'institutions/compliance_heatmap.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
        accreditors=accreditors,
    )


@app.route('/institutions/<id>/simulation')
def institution_simulation(id):
    """Accreditation simulation page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/simulation.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/faculty')
def institution_faculty(id):
    """Faculty credential management page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/faculty.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/catalog')
def institution_catalog(id):
    """Catalog builder page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/catalog.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/exhibits')
def institution_exhibits(id):
    """Exhibits management page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/exhibits.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/achievements')
def institution_achievements(id):
    """Student achievements page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/achievements.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/interview-prep')
def institution_interview_prep(id):
    """Interview preparation page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/interview_prep.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/ser')
def institution_ser(id):
    """Self-Evaluation Report drafting page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/ser_drafting.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/visit-readiness')
def institution_visit_readiness(id):
    """Visit readiness and mock evaluation page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/visit_readiness.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/team-reports')
def institution_team_reports(id):
    """Team report responses page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/team_reports.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/calendar')
def institution_calendar(id):
    """Compliance calendar page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/compliance_calendar.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/institutions/<id>/document-reviews')
def institution_document_reviews(id):
    """Document review scheduler page."""
    institution = workspace_manager.load_institution(id)
    if not institution:
        return render_template('404.html'), 404

    return render_template(
        'institutions/document_reviews.html',
        institution=institution,
        current_institution=institution,
        readiness_score=_get_readiness_score(id),
    )


@app.route('/chat')
def chat():
    """AI chat interface page."""
    return render_template('chat.html')


@app.route('/evidence-assistant')
def evidence_assistant():
    """Evidence Assistant page."""
    return render_template('evidence_assistant.html')


@app.route('/agent-sessions')
def agent_sessions():
    """Agent sessions management page."""
    return render_template('agent_sessions.html')


@app.route('/work-queue')
def work_queue():
    """Unified work queue page."""
    institutions = workspace_manager.list_institutions()
    return render_template('work_queue.html', institutions=institutions)


@app.route('/portfolios')
def portfolios_list():
    """Portfolio list page for multi-institution management."""
    from src.services.portfolio_service import list_portfolios, compute_portfolio_readiness
    portfolios = list_portfolios()
    # Compute aggregate metrics for each portfolio
    for p in portfolios:
        if p.institution_count > 0:
            readiness = compute_portfolio_readiness(p.id, workspace_manager)
            p.avg_score = readiness.avg_score
            p.at_risk_count = readiness.at_risk_count
        else:
            p.avg_score = 0
            p.at_risk_count = 0
    return render_template('portfolios/list.html', portfolios=portfolios)


@app.route('/portfolios/<portfolio_id>')
def portfolio_dashboard(portfolio_id):
    """Portfolio dashboard with aggregate metrics."""
    from src.services.portfolio_service import get_portfolio, compute_portfolio_readiness
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return render_template('404.html'), 404
    readiness = compute_portfolio_readiness(portfolio_id, workspace_manager)
    return render_template('portfolios/dashboard.html',
                          portfolio=portfolio,
                          readiness=readiness)


@app.route('/portfolios/<portfolio_id>/compare')
def portfolio_compare(portfolio_id):
    """Institution comparison view."""
    from src.services.portfolio_service import get_portfolio, get_portfolio_comparison
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return render_template('404.html'), 404
    comparison = get_portfolio_comparison(portfolio_id, workspace_manager)
    return render_template('portfolios/compare.html',
                          portfolio=portfolio,
                          comparison=comparison)


@app.route('/settings')
def settings_page():
    """User settings page."""
    return render_template('settings.html')


@app.route('/settings/glossary')
def glossary_page():
    """Terminology glossary editor."""
    return render_template('settings/glossary.html')


@app.route('/reports')
def reports_page():
    """Executive dashboard and reports page."""
    institution_id = request.args.get("institution_id", "")
    return render_template('pages/reports.html', institution_id=institution_id)


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
        debug=False,
    )
