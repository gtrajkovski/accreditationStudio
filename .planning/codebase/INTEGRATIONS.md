# External Integrations

**Analysis Date:** 2026-03-21

## APIs & External Services

**Anthropic Claude API:**
- Claude language models (primary AI backbone)
  - SDK/Client: `anthropic` package (v0.40.0+)
  - Auth: Environment variable `ANTHROPIC_API_KEY`
  - Model: Configurable via `MODEL` env var (default: `claude-sonnet-4-20250514`)
  - Implementation: `src/ai/client.py` wraps Anthropic SDK
  - Error handling: Catches `anthropic.APIError` for API failures

**External HTTP Calls:**
- Generic HTTP client: `requests` package (v2.31.0+)
- Location: Used throughout agents and services for API integrations
- No specific third-party APIs currently integrated (extensible via requests)

## Data Storage

**Databases:**
- SQLite 3 (local file-based)
  - Connection: `src/db/connection.py` manages sqlite3 connections
  - Path: Configurable via `DATABASE` env var (default: `./accreditai.db`)
  - Schema: Versioned migrations in `src/db/migrations/` (20+ migration files)
  - Features: Foreign key constraints enabled, Row factory for dict-like access

**File Storage:**
- Local filesystem only
  - Workspace directory: `WORKSPACE_DIR` (default: `./workspace/`)
  - Upload directory: `UPLOAD_DIR` (default: `./uploads/`)
  - Institution-specific folders: `workspace/{institution_id}/`
  - Document storage structure: `originals/`, `audits/`, `redlines/`, `finals/`, `exhibits/`

**Caching:**
- ChromaDB vector cache: `src/search/vector_store.py`
  - Persistent storage: `WORKSPACE_DIR/{institution_id}/vectors/`
  - Embedding model: `all-MiniLM-L6-v2` (384 dimensions)
  - Type: Semantic search index for document chunks

## Authentication & Identity

**Auth Provider:**
- Flask-Login (session-based, local)
  - Implementation: Custom user session management
  - Cookie-based Flask sessions with `SECRET_KEY` configuration
  - No external OAuth/SAML integration detected

## Monitoring & Observability

**Error Tracking:**
- Not detected (no Sentry, Rollbar, etc.)
- Fallback: Python logging module used throughout codebase

**Logs:**
- Python standard logging (`logging` module)
- Console output during development
- Structured logging in services (e.g., email_service.py logs delivery attempts)

## CI/CD & Deployment

**Hosting:**
- Local Flask development server (port configurable, default 5003)
- Production: Gunicorn WSGI server (v21.0.0+)
- No cloud platform integration detected (AWS, GCP, Azure, Heroku, etc.)

**CI Pipeline:**
- Not detected (no GitHub Actions, GitLab CI, Jenkins config files)

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Anthropic API credentials (critical)
- `MODEL` - Claude model ID (default: `claude-sonnet-4-20250514`)
- `ENVIRONMENT` - Deployment environment: "development" or "production"
- `PORT` - Server port (default: 5003)
- `WORKSPACE_DIR` - Path to workspace data (default: ./workspace)
- `DATABASE` - SQLite database path (default: ./accreditai.db)

**Optional env vars:**
- `SECRET_KEY` - Flask session key (auto-generated if not set)
- `MAX_TOKENS` - Max tokens per AI request (default: 8192)
- `EMBEDDING_MODEL` - Embedding model name (default: all-MiniLM-L6-v2)
- `AGENT_CONFIDENCE_THRESHOLD` - AI confidence floor (default: 0.7)
- `CHUNK_SIZE`, `CHUNK_OVERLAP` - Document chunking params (default: 500, 50)
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD` - SMTP config
- `MAIL_DEFAULT_SENDER` - From address for emails (default: noreply@accreditai.local)
- `PII_DETECTION` - Detection mode (default: "regex+ai")

**Secrets location:**
- `.env` file (project root) - Contains API keys and credentials
- Never committed to git (in .gitignore)
- Loaded via `python-dotenv` at application startup

## Webhooks & Callbacks

**Incoming:**
- Not detected (no webhook endpoints defined)

**Outgoing:**
- Email delivery via SMTP (Flask-Mail)
  - Configured for Gmail SMTP by default (`smtp.gmail.com:587`)
  - Used by `src/services/email_service.py` for report delivery
  - Not currently integrated with calendar systems (iCalendar parsing only, no POST)

## Third-Party Libraries (No API Integration)

**Document Parsing (Local Processing):**
- `pdfplumber` - Local PDF text extraction
- `python-docx` - Local DOCX file handling
- `mammoth` - Local DOCX conversion
- `pytesseract` - Local OCR via Tesseract
- `Pillow` - Local image processing
- `openpyxl` - Local Excel parsing

**Schedule & Calendar:**
- `APScheduler` + `Flask-APScheduler` - Local job scheduling (no external calendar service)
- `icalendar` - Local iCalendar file parsing (import only, no Outlook/Google Calendar sync)

---

*Integration audit: 2026-03-21*
