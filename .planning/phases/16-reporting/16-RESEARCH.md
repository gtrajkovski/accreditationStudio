# Phase 16: Reporting - Research

**Researched:** 2026-03-20
**Domain:** PDF generation, executive dashboards, scheduled reporting
**Confidence:** MEDIUM

## Summary

Phase 16 implements professional compliance reporting with three key features: (1) PDF compliance reports with charts and metrics, (2) executive summary dashboard with export capabilities, and (3) scheduled report generation with email delivery.

The Python ecosystem offers mature solutions for PDF generation, with WeasyPrint (HTML/CSS to PDF) being the recommended choice for 90% of use cases due to developer familiarity with HTML/CSS and template reusability with existing Jinja2 infrastructure. For chart generation, matplotlib provides the simplest path for embedding static charts in PDFs, while Chart.js (already in use) handles interactive dashboard visualizations. APScheduler integrates seamlessly with Flask for in-process scheduled tasks, making it ideal for this single-user localhost application.

**Primary recommendation:** Use WeasyPrint + Jinja2 templates + matplotlib charts + APScheduler for a unified, maintainable reporting system that leverages existing project patterns.

## Standard Stack

### Core PDF Generation
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| WeasyPrint | 68.x | HTML/CSS to PDF conversion | Industry standard for HTML-based PDF generation, active maintenance, CSS3 support |
| Jinja2 | 3.x (existing) | Template rendering | Already in project, reuse existing template skills |
| Flask-WeasyPrint | 1.0.x | Flask integration | Simplifies integration, handles base_url and static assets |

### Chart Generation
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| matplotlib | 3.9.x | Static chart generation for PDFs | Most widely used Python plotting library, simple API, PNG/SVG export |
| Chart.js | 4.x (existing) | Interactive dashboard charts | Already in project (portfolio comparison), proven in codebase |

### Scheduling & Email
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.10.x (existing) | Task scheduling | Already in requirements.txt, perfect for in-process scheduling |
| Flask-Mail | 0.10.x | Email sending | De facto standard for Flask email, simple SMTP configuration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | 10.x (existing) | Image processing | Chart export to PNG for embedding in PDFs |
| python-docx | 1.1.x (existing) | DOCX manipulation | Reference for styling patterns (already used by PacketAgent) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WeasyPrint | ReportLab | ReportLab offers more control but requires verbose Python code vs. HTML/CSS skills |
| WeasyPrint | PDFKit/wkhtmltopdf | wkhtmltopdf deprecated, WeasyPrint more actively maintained |
| APScheduler | Celery | Celery overkill for single-user localhost app, requires message broker (Redis/RabbitMQ) |
| matplotlib | plotly | plotly better for interactive web, matplotlib simpler for static PDF charts |

**Installation:**
```bash
pip install weasyprint>=68.0.0
pip install Flask-WeasyPrint>=1.0.0
pip install Flask-Mail>=0.10.0
pip install matplotlib>=3.9.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── services/
│   ├── report_service.py          # Report data aggregation and generation
│   ├── scheduler_service.py       # APScheduler configuration and job management
│   └── email_service.py           # Email sending with Flask-Mail
├── api/
│   └── reports.py                 # API endpoints (generate, schedule, history)
├── exporters/
│   ├── pdf_exporter.py            # WeasyPrint PDF generation
│   └── chart_generator.py         # Matplotlib chart rendering
templates/
├── reports/
│   ├── compliance_report.html     # Main PDF template
│   ├── executive_summary.html     # Executive summary template
│   └── partials/
│       ├── report_header.html     # Reusable header
│       ├── chart_section.html     # Chart container
│       └── metrics_table.html     # Metric tables
├── pages/
│   └── reports.html               # UI for report generation/scheduling
static/
├── css/
│   └── pdf.css                    # PDF-specific styles (print media query)
└── js/
    └── reports.js                 # Dashboard interactions, schedule management
```

### Pattern 1: Service-Based Report Generation
**What:** Separate data aggregation (service) from rendering (exporter)
**When to use:** All report types
**Example:**
```python
# src/services/report_service.py
class ReportService:
    def generate_compliance_report_data(self, institution_id: str) -> Dict[str, Any]:
        """Aggregate data for compliance report."""
        from src.services.readiness_service import compute_readiness
        from src.db.connection import get_conn

        readiness = compute_readiness(institution_id)

        # Query recent findings
        conn = get_conn()
        findings = conn.execute("""
            SELECT standard_code, severity, status, COUNT(*) as count
            FROM compliance_findings
            WHERE institution_id = ?
            GROUP BY standard_code, severity, status
        """, (institution_id,)).fetchall()

        return {
            "institution": self._get_institution(institution_id),
            "readiness": readiness,
            "findings_summary": findings,
            "generated_at": now_iso(),
        }
```

### Pattern 2: Template-Based PDF Generation
**What:** Use Jinja2 templates with print-optimized CSS for PDF rendering
**When to use:** All PDF exports
**Example:**
```python
# src/exporters/pdf_exporter.py
from flask import render_template
from flask_weasyprint import HTML, render_pdf

class PDFExporter:
    def generate_compliance_report(self, data: Dict[str, Any]) -> bytes:
        """Generate PDF from template and data."""
        html = render_template(
            "reports/compliance_report.html",
            **data
        )
        return render_pdf(HTML(string=html))
```

**Template structure:**
```html
<!-- templates/reports/compliance_report.html -->
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/pdf.css') }}">
    <style>
        @page {
            size: letter;
            margin: 1in;
            @top-center { content: "Compliance Report - {{ institution.name }}"; }
            @bottom-center { content: "Page " counter(page) " of " counter(pages); }
        }
    </style>
</head>
<body>
    {% include "reports/partials/report_header.html" %}

    <section class="executive-summary">
        <h1>Executive Summary</h1>
        <!-- Readiness ring chart -->
        <img src="data:image/png;base64,{{ readiness_chart }}" alt="Readiness Score">
    </section>

    <!-- More sections -->
</body>
</html>
```

### Pattern 3: Chart Embedding in PDFs
**What:** Generate matplotlib charts as PNG, embed as base64 data URIs
**When to use:** Static charts in PDF reports
**Example:**
```python
# src/exporters/chart_generator.py
import base64
import io
import matplotlib.pyplot as plt
from typing import Dict, Any

class ChartGenerator:
    def generate_readiness_chart(self, readiness: Dict[str, int]) -> str:
        """Generate readiness ring chart as base64 PNG."""
        fig, ax = plt.subplots(figsize=(6, 6))

        # Create ring chart
        scores = [readiness['compliance'], readiness['evidence'],
                  readiness['documents'], readiness['consistency']]
        labels = ['Compliance', 'Evidence', 'Documents', 'Consistency']
        colors = ['#4ade80', '#3b82f6', '#f59e0b', '#a78bfa']

        wedges, texts, autotexts = ax.pie(
            scores, labels=labels, colors=colors,
            autopct='%1.0f%%', startangle=90, pctdistance=0.85
        )

        # Add center circle for ring effect
        centre_circle = plt.Circle((0,0), 0.70, fc='white')
        ax.add_artist(centre_circle)

        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()

        # Return base64 encoded
        return base64.b64encode(buf.read()).decode('utf-8')
```

### Pattern 4: APScheduler Integration
**What:** Configure APScheduler as Flask extension for background jobs
**When to use:** Scheduled report generation
**Example:**
```python
# src/services/scheduler_service.py
from flask_apscheduler import APScheduler
from src.services.report_service import ReportService
from src.services.email_service import EmailService

scheduler = APScheduler()

def init_scheduler(app):
    """Initialize APScheduler with Flask app."""
    scheduler.init_app(app)
    scheduler.start()

def schedule_report(institution_id: str, report_type: str,
                   cron_expression: str, recipients: List[str]) -> str:
    """Schedule recurring report generation and email."""
    job_id = f"report_{generate_id('job')}"

    scheduler.add_job(
        id=job_id,
        func=_send_scheduled_report,
        trigger='cron',
        **_parse_cron(cron_expression),
        args=[institution_id, report_type, recipients]
    )

    return job_id

def _send_scheduled_report(institution_id: str, report_type: str, recipients: List[str]):
    """Background task to generate and email report."""
    report_service = ReportService()
    email_service = EmailService()

    # Generate report
    data = report_service.generate_compliance_report_data(institution_id)
    pdf_bytes = PDFExporter().generate_compliance_report(data)

    # Send email
    email_service.send_report(
        recipients=recipients,
        subject=f"{report_type} - {data['institution']['name']}",
        pdf_attachment=pdf_bytes,
        filename=f"{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
    )
```

### Pattern 5: Executive Dashboard KPI Layout
**What:** Top-rail hero metrics + detail cards (Z-pattern layout)
**When to use:** Executive summary dashboard
**Example:**
```html
<!-- templates/pages/reports.html -->
<div class="executive-dashboard">
    <!-- Hero Metrics (top rail) -->
    <div class="hero-metrics">
        <div class="hero-metric">
            <div class="metric-value {{ 'ready' if readiness >= 80 else 'at-risk' }}">
                {{ readiness }}
            </div>
            <div class="metric-label">Overall Readiness</div>
            <div class="metric-trend">
                <span class="trend-indicator {{ 'up' if trend > 0 else 'down' }}">
                    {{ trend }}%
                </span>
                vs. last month
            </div>
        </div>
        <!-- 3-5 more hero metrics -->
    </div>

    <!-- Detail Charts -->
    <div class="dashboard-grid">
        <div class="card">
            <canvas id="compliance-trend"></canvas>
        </div>
        <div class="card">
            <canvas id="findings-by-severity"></canvas>
        </div>
    </div>
</div>
```

### Anti-Patterns to Avoid
- **Generating PDFs synchronously in request handlers:** Use background tasks for large reports to avoid request timeouts
- **Inline CSS in templates:** Use external stylesheets with `@media print` for maintainability
- **Complex CSS Grid/Flexbox in PDFs:** WeasyPrint has limited support; use simple block layouts or tables for reliability
- **Large CSS frameworks in PDFs:** Bootstrap/Tailwind drastically slow rendering; use minimal custom CSS
- **Storing PDFs in database:** Store in workspace filesystem, reference by path in database

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF layout engine | Custom PDF writer | WeasyPrint | Page breaks, CSS cascade, font embedding, PDF/A compliance are complex |
| Email queue with retries | Custom retry logic | Flask-Mail + APScheduler | Handles SMTP connection pooling, retry backoff, bounce handling |
| Chart rendering | Custom SVG/Canvas | matplotlib | Bar charts, pie charts, line graphs have edge cases (label overlaps, axis scaling) |
| Cron parsing | Custom cron parser | APScheduler triggers | Cron syntax is deceptively complex (ranges, steps, day-of-week/month conflicts) |
| Report history tracking | Custom JSON files | Database table | Need queries for filtering, pagination, report status tracking |

**Key insight:** PDF generation has hidden complexity around pagination (widow/orphan control, page break avoidance), font subsetting, and CSS cascade. WeasyPrint handles these edge cases that would take months to implement correctly.

## Common Pitfalls

### Pitfall 1: WeasyPrint Performance Degradation
**What goes wrong:** Large documents with heavy CSS cause 30+ second rendering times or memory issues
**Why it happens:** Global cascade algorithm recalculates styles for entire document on each page break
**How to avoid:**
- Remove unused CSS (avoid loading full Bootstrap/Tailwind)
- Use explicit page breaks (`page-break-before: always`) to localize layout dependencies
- Simplify table layouts (tables are slowest element type)
- Cache chart images instead of regenerating per report
**Warning signs:** PDF generation taking >10 seconds for <50 page document

### Pitfall 2: Static Assets Not Loading in PDF
**What goes wrong:** Images, CSS, fonts show as broken in generated PDFs
**Why it happens:** WeasyPrint doesn't have access to Flask request context (cookies, base URL)
**How to avoid:**
- Use `Flask-WeasyPrint`'s `render_pdf()` which auto-handles base_url
- For manual generation, use `url_for(..., _external=True)` for all asset references
- Host fonts locally, don't rely on external CDNs (network requests fail in PDF context)
**Warning signs:** Images render fine in browser but missing in PDF

### Pitfall 3: APScheduler Jobs Persist Across Restarts
**What goes wrong:** Scheduled jobs run multiple times or fail silently after app restart
**Why it happens:** Default MemoryJobStore loses jobs on restart, or jobs registered multiple times
**How to avoid:**
- Use SQLAlchemyJobStore for persistence across restarts
- Check `if not scheduler.get_job(job_id)` before adding jobs
- Set `replace_existing=True` when adding jobs in `init_app()`
**Warning signs:** Duplicate emails sent, or schedules disappear after restart

### Pitfall 4: Email Blocking Request Thread
**What goes wrong:** HTTP requests timeout while waiting for email to send
**Why it happens:** SMTP connection can take 5-10 seconds, blocking Flask worker
**How to avoid:**
- Always send emails in APScheduler background jobs, not directly in routes
- For immediate "send now" feature, queue job with `scheduler.add_job(func, trigger='date', run_date=now())`
**Warning signs:** Slow response times on report generation endpoints

### Pitfall 5: Chart Text Rendering Issues in PDFs
**What goes wrong:** Chart labels cut off, overlapping, or wrong font in PDFs
**Why it happens:** matplotlib defaults to interactive backend, different font metrics than PDF
**How to avoid:**
- Set `matplotlib.use('Agg')` backend for headless rendering
- Explicitly set DPI (150-300) for sharp text rendering
- Use `bbox_inches='tight'` when saving to prevent label cutoff
- Test with longest expected label text
**Warning signs:** Charts look perfect in preview but garbled in PDF

## Code Examples

Verified patterns from official sources:

### WeasyPrint with Flask
```python
# Source: Flask-WeasyPrint documentation
from flask import Flask, render_template
from flask_weasyprint import HTML, render_pdf

app = Flask(__name__)

@app.route('/report.pdf')
def compliance_report_pdf():
    data = {"institution": "Example College", "readiness": 85}
    html = render_template('reports/compliance_report.html', **data)
    return render_pdf(HTML(string=html))
```

### APScheduler CRUD Pattern
```python
# Source: Flask-APScheduler documentation
from flask_apscheduler import APScheduler

scheduler = APScheduler()

# Add job
scheduler.add_job(
    id='weekly_report',
    func=generate_report,
    trigger='cron',
    day_of_week='mon',
    hour=8,
    replace_existing=True
)

# List jobs
jobs = scheduler.get_jobs()

# Remove job
scheduler.remove_job('weekly_report')

# Pause/resume
scheduler.pause_job('weekly_report')
scheduler.resume_job('weekly_report')
```

### Flask-Mail Attachment Pattern
```python
# Source: Flask-Mail documentation
from flask_mail import Mail, Message

mail = Mail(app)

msg = Message(
    subject="Weekly Compliance Report",
    recipients=["compliance@institution.edu"],
    body="Please find attached this week's compliance report."
)

# Attach PDF
msg.attach(
    filename="compliance_report.pdf",
    content_type="application/pdf",
    data=pdf_bytes
)

mail.send(msg)
```

### Matplotlib Ring Chart for Readiness
```python
# Source: matplotlib documentation, adapted for readiness scoring
import matplotlib.pyplot as plt

def create_readiness_ring(scores: Dict[str, int]) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 6))

    sizes = [scores['compliance'], scores['evidence'],
             scores['documents'], scores['consistency']]
    labels = ['Compliance\n40%', 'Evidence\n25%',
              'Documents\n20%', 'Consistency\n15%']
    colors = ['#4ade80', '#3b82f6', '#f59e0b', '#a78bfa']

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct='%1.0f%%', startangle=90,
        wedgeprops=dict(width=0.3)  # Ring width
    )

    # Center label with total score
    weighted_total = sum(
        scores[k] * w for k, w in
        zip(['compliance', 'evidence', 'documents', 'consistency'],
            [0.40, 0.25, 0.20, 0.15])
    )
    ax.text(0, 0, f'{int(weighted_total)}',
            ha='center', va='center', fontsize=48, weight='bold')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white')
    plt.close()
    buf.seek(0)
    return buf.read()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| wkhtmltopdf | WeasyPrint | 2022-2024 | wkhtmltopdf officially deprecated, WeasyPrint actively maintained |
| Custom email retry | APScheduler jobs | Ongoing | Built-in retry with exponential backoff |
| ReportLab imperative | HTML/CSS templates | 2020+ | Faster development, designer-friendly, template reuse |
| Celery for all async | APScheduler for periodic | 2023+ | Simpler stack for in-process scheduling |
| External chart services | matplotlib/Chart.js | Ongoing | Privacy, offline capability, no API quotas |

**Deprecated/outdated:**
- **wkhtmltopdf/pdfkit:** Project abandoned, Qt WebKit unmaintained, use WeasyPrint instead
- **xhtml2pdf:** Limited CSS support, WeasyPrint has better standards compliance
- **Celery Beat for simple scheduling:** Overkill for single-user app, APScheduler sufficient

## Open Questions

1. **PDF/A Compliance for Archival**
   - What we know: WeasyPrint supports PDF/A-1b, PDF/A-2b, PDF/A-3b via `--pdf-variant` flag
   - What's unclear: Whether accreditation bodies require specific PDF/A variant
   - Recommendation: Start with standard PDF, add PDF/A-3b option if requested (simplest to implement: `HTML(...).write_pdf(target, pdf_variant='pdf/a-3b')`)

2. **Report Storage and Retention**
   - What we know: Generated reports should be versioned and stored
   - What's unclear: Retention policy (how long to keep generated reports)
   - Recommendation: Store in `workspace/{institution_id}/reports/{report_id}.pdf`, add database table for metadata, implement manual cleanup UI (no auto-deletion)

3. **Email Delivery Reliability**
   - What we know: SMTP can fail silently (firewall, invalid recipient, quota)
   - What's unclear: How to handle failed deliveries in scheduled jobs
   - Recommendation: Log all send attempts to database, add retry with exponential backoff (APScheduler supports this), surface failed sends in UI

4. **Chart Accessibility in PDFs**
   - What we know: Screen readers cannot parse image-based charts
   - What's unclear: Whether to include alt text or data tables for accessibility
   - Recommendation: Include data tables below charts in PDF (hidden in web view), helps both accessibility and print readability

5. **Multi-Institution Report Scheduling**
   - What we know: Project has portfolio support (multiple institutions)
   - What's unclear: Whether to support portfolio-wide scheduled reports
   - Recommendation: Phase 1 = single institution reports only, Phase 2 (if needed) = portfolio aggregates

## Sources

### Primary (HIGH confidence)
- [WeasyPrint Official Documentation](https://doc.courtbouillon.org/weasyprint/stable/) - CSS support, API reference, performance optimization
- [Flask-WeasyPrint Documentation](https://pythonhosted.org/Flask-WeasyPrint/) - Flask integration patterns
- [APScheduler User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) - Triggers, job stores, configuration
- [Flask-APScheduler Documentation](https://viniciuschiele.github.io/flask-apscheduler/) - Flask integration, REST API
- [Flask-Mail Documentation](https://flask-mail.readthedocs.io/) - Configuration, message sending, attachments
- [matplotlib Documentation](https://matplotlib.org/stable/contents.html) - Chart types, saving figures

### Secondary (MEDIUM confidence)
- [Generate PDFs in Python: WeasyPrint vs ReportLab - DEV Community](https://dev.to/claudeprime/generate-pdfs-in-python-weasyprint-vs-reportlab-ifi) - Library comparison (2025)
- [Creating PDF Reports with Pandas, Jinja and WeasyPrint - Practical Business Python](https://pbpython.com/pdf-reports.html) - Template patterns
- [Flask PDF Generation: ReportLab, WeasyPrint, and PDFKit Compared](https://www.codingeasypeasy.com/blog/flask-pdf-generation-reportlab-weasyprint-and-pdfkit-compared) - Flask integration comparison
- [Executive Dashboards: 13+ Examples, Templates & Best Practices [2026 Guide]](https://improvado.io/blog/executive-dashboards) - KPI dashboard design patterns
- [Scheduling Tasks in Python APScheduler vs Celery Beat](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat) - Scheduler comparison (2025)
- [Flask Send Email: Tutorial with Code Snippets [2026]](https://mailtrap.io/blog/flask-email-sending/) - Flask-Mail patterns (August 2025)

### Tertiary (LOW confidence)
- [Tips and Tricks for Using Weasyprint to Generate PDFs](https://www.naveenmk.me/blog/weasyprint/) - Performance optimization tips (no date, unverified)
- [How to speed up your structured WeasyPrint PDF generation](https://cliffordgama.com/tech/speed-up-weasyprint-pdf-generation/) - Optimization patterns (needs verification with docs)

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - WeasyPrint verified from official docs, but limited production examples in Flask ecosystem
- Architecture: MEDIUM - Patterns verified from Flask-WeasyPrint and APScheduler docs, chart embedding pattern is common practice
- Pitfalls: HIGH - Performance issues and asset loading documented in official WeasyPrint docs, APScheduler persistence is documented behavior

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days - stable libraries, mature ecosystem)
