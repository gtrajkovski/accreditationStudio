"""AccreditAI configuration module.

Reads configuration from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # AI Model Settings
    MODEL = os.getenv("MODEL", "claude-sonnet-4-20250514")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "claude-embed-1")
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))

    # Server Settings
    PORT = int(os.getenv("PORT", "5003"))
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # Directory Paths
    BASE_DIR = Path(__file__).parent.parent
    WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", BASE_DIR / "workspace"))
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
    DATABASE = Path(os.getenv("DATABASE", BASE_DIR / "accreditai.db"))

    # Agent Configuration
    AGENT_CONFIDENCE_THRESHOLD = float(os.getenv("AGENT_CONFIDENCE_THRESHOLD", "0.7"))
    AGENT_AUTO_APPROVE = os.getenv("AGENT_AUTO_APPROVE", "false").lower() == "true"
    AGENT_MAX_CONCURRENT_TASKS = int(os.getenv("AGENT_MAX_CONCURRENT_TASKS", "3"))
    AGENT_SESSION_LOG = os.getenv("AGENT_SESSION_LOG", "true").lower() == "true"

    # Vector Store Configuration
    VECTOR_STORE = os.getenv("VECTOR_STORE", "sqlite-vss")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

    # PII Configuration
    PII_DETECTION = os.getenv("PII_DETECTION", "regex+ai")
    PII_ENCRYPTION_KEY = os.getenv("PII_ENCRYPTION_KEY", "")

    @classmethod
    def ensure_dirs(cls) -> None:
        """Ensure all required directories exist."""
        cls.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def ai_enabled(cls) -> bool:
        """Check if AI features are enabled (API key present)."""
        return bool(cls.ANTHROPIC_API_KEY)
