# Technology Stack

**Analysis Date:** 2026-03-21

## Languages

**Primary:**
- Python 3.x - Backend application, agents, document processing, AI orchestration
- Jinja2 - HTML templating for server-side rendering
- JavaScript (vanilla) - Frontend interactivity, charts, interactive UI

## Runtime

**Environment:**
- Python runtime (no specific version constraint in requirements.txt)
- Flask 3.0.0+ embedded development server (development)
- Gunicorn 21.0.0+ (production WSGI server)

**Package Manager:**
- pip - Python package manager
- Lockfile: Not detected (uses requirements.txt)

## Frameworks

**Core:**
- Flask 3.0.0+ - Web framework, routing, templating engine
- Flask-Login 0.6.3+ - User session management
- Flask-SSE 1.0.0+ - Server-Sent Events for real-time streaming (agent progress)

**Testing:**
- pytest 7.4.0+ - Test runner
- pytest-cov 4.1.0+ - Code coverage reporting

**Build/Dev:**
- No build system detected (vanilla JS, no bundler)

## Key Dependencies

**Critical:**
- anthropic 0.40.0+ - Anthropic API client for Claude models (core to agentic system)
- python-dotenv 1.0.0+ - Environment variable management from .env files
- pydantic 2.5.0+ - Data validation and serialization

**Document Processing:**
- python-docx 1.1.0+ - DOCX file parsing and generation
- pdfplumber 0.10.0+ - PDF text extraction and analysis
- mammoth 1.6.0+ - DOCX to HTML conversion
- pytesseract 0.3.10+ - OCR via Tesseract engine
- Pillow 10.0.0+ - Image processing for OCR
- openpyxl 3.1.0+ - Excel file parsing

**Vector Store & RAG:**
- chromadb 0.4.0+ - Vector database for semantic search (persistent client mode)
- sentence-transformers 2.2.0+ - Embedding model (all-MiniLM-L6-v2, 384 dimensions)
- numpy 1.24.0+ - Numerical computing foundation

**Security:**
- bcrypt 4.1.0+ - Password hashing
- cryptography 41.0.0+ - Encryption utilities

**External Communications:**
- requests 2.31.0+ - HTTP client for external API calls
- icalendar 5.0.0+ - iCalendar file parsing and generation
- Flask-Mail 0.10.0+ - SMTP email delivery

**Scheduling:**
- APScheduler 3.10.0+ - Job scheduling and background task execution
- Flask-APScheduler 1.13.0+ - Flask integration for APScheduler

**PDF & Visualization:**
- weasyprint 68.0.0+ - HTML to PDF conversion
- Flask-WeasyPrint 1.0.0+ - Flask integration for PDF generation
- matplotlib 3.9.0+ - Chart generation and visualization

## Configuration

**Environment:**
- Configuration loaded from environment variables via `python-dotenv`
- Primary config file: `src/config.py` reads from `.env` file
- Supports: `ENVIRONMENT`, `ANTHROPIC_API_KEY`, `MODEL`, `PORT`, `WORKSPACE_DIR`, `DATABASE`, `MAIL_*` settings

**Build:**
- No explicit build configuration (Flask development/production modes set via `ENVIRONMENT` env var)
- Database migrations: SQL scripts in `src/db/migrations/` applied programmatically

## Platform Requirements

**Development:**
- Python 3.8+ (inferred from package versions)
- SQLite3 (included in Python standard library)
- Tesseract OCR engine (required if OCR features used)
- SMTP server access for email delivery (Gmail SMTP by default)

**Production:**
- Python 3.8+ runtime
- Gunicorn WSGI server
- SMTP credentials for email functionality
- Anthropic API key for AI features

---

*Stack analysis: 2026-03-21*
