# AccreditAI Deployment Guide

This guide covers deploying AccreditAI as a localhost single-user tool for managing accreditation workflows.

## Prerequisites

- **Python 3.11+** (3.11 recommended)
- **Tesseract OCR** (for document text extraction)
- **Anthropic API Key** (for AI features)

### Installing Tesseract

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki
Add to PATH after installation.

---

## Local Installation

### 1. Clone and Setup

```bash
git clone https://github.com/gtrajkovski/accreditationStudio.git
cd accreditationStudio

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional (defaults shown)
MODEL=claude-sonnet-4-20250514
PORT=5003
WORKSPACE_DIR=./workspace
UPLOAD_DIR=./uploads
DATABASE=./accreditai.db
AGENT_CONFIDENCE_THRESHOLD=0.7
```

### 3. Initialize Database

```bash
flask init-db
```

### 4. Start the Application

```bash
python app.py
```

Access at: http://localhost:5003

---

## Docker Deployment

### 1. Build and Run

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f
```

### 2. Stop

```bash
docker-compose down
```

### Data Persistence

Data is persisted in:
- `./workspace/` - Institution workspaces and documents
- `./uploads/` - Uploaded files
- `./accreditai.db` - SQLite database

---

## Database Management

### Check Migration Status
```bash
flask db status
```

### Apply Pending Migrations
```bash
flask db upgrade
```

### Fresh Database
```bash
rm accreditai.db
flask init-db
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Anthropic API key for AI features |
| `MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `PORT` | `5003` | Server port |
| `WORKSPACE_DIR` | `./workspace` | Institution data directory |
| `UPLOAD_DIR` | `./uploads` | Uploaded files directory |
| `DATABASE` | `./accreditai.db` | SQLite database path |
| `SECRET_KEY` | (auto-generated) | Flask session secret |
| `AGENT_CONFIDENCE_THRESHOLD` | `0.7` | AI confidence threshold |

---

## Troubleshooting

### "No API key" Warning
Ensure `ANTHROPIC_API_KEY` is set in `.env` or environment.

### Document Parsing Fails
- Verify Tesseract is installed: `tesseract --version`
- Check file permissions on workspace/uploads directories

### Database Errors
```bash
flask db status  # Check migration state
flask db upgrade # Apply pending migrations
```

### Port Already in Use
Change the port in `.env`:
```env
PORT=5004
```

### Docker Issues
```bash
# Rebuild without cache
docker-compose build --no-cache

# Check container logs
docker logs accreditai
```

---

## Health Check

Verify the application is running:
```bash
curl http://localhost:5003/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "ai_enabled": true
}
```

---

## Security Notes

- This is a **localhost single-user tool** - not designed for multi-user deployment
- The application auto-generates a secure `SECRET_KEY` if not provided
- Uploaded documents are stored locally - back up your `workspace/` directory
- PII is automatically redacted from document text before AI processing
