"""Central settings. Values come from .env (laptop) or from the host's environment variables (cloud)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./support.db")
    # Neon and Render give "postgresql://..." or "postgres://...", SQLAlchemy needs the driver name too.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "")
    SMTP_APP_PASSWORD: str = os.getenv("SMTP_APP_PASSWORD", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    DATABASE_URL: str = _database_url()

    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")  # set LLM_MODEL to a model your key can use
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SUPPORT_TEAM_EMAIL: str = os.getenv("SUPPORT_TEAM_EMAIL", "")  # gets a mail for every new ticket
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")  # password for the admin page

    # ---- email through the Brevo API (free hosts block SMTP). Empty key = use Gmail SMTP as before ----
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "")  # a sender address verified in Brevo

    # ---- knowledge base: defaults suit a small cloud server (no torch, no chromadb) ----
    EMBEDDINGS_PROVIDER: str = os.getenv("EMBEDDINGS_PROVIDER", "gemini")  # "gemini" or "local"
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"  # only for EMBEDDINGS_PROVIDER=local
    VECTOR_STORE: str = os.getenv("VECTOR_STORE", "memory")  # "memory" (rebuilt at start) or "chroma" (on disk)
    CHROMA_DIR: str = "./chroma_db"


settings = Settings()
