# AccreditAI Dockerfile
# Production-ready container for accreditation management platform

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR for document processing
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    # PDF processing
    poppler-utils \
    # Build tools for Python packages
    build-essential \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data persistence
RUN mkdir -p workspace uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5003 \
    WORKSPACE_DIR=/app/workspace \
    UPLOAD_DIR=/app/uploads \
    DATABASE=/app/accreditai.db

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5003/api/health')" || exit 1

# Initialize database and start gunicorn production server
CMD ["sh", "-c", "flask init-db && gunicorn --bind 0.0.0.0:5003 --workers 2 --timeout 120 --access-logfile - wsgi:app"]
