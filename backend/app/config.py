"""Central settings: reads values from .env so other files use settings.X"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "")
    SMTP_APP_PASSWORD: str = os.getenv("SMTP_APP_PASSWORD", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./support.db")
    SUPPORT_TEAM_EMAIL: str = os.getenv("SUPPORT_TEAM_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")  # check name on AI Studio
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"  # local, no key
    CHROMA_DIR: str = "./chroma_db"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

settings = Settings()
