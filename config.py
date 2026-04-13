import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "pmo-dev-secret").strip()
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "1").strip() in ("1", "true", "True")

DB_HOST = os.getenv("DB_HOST", "localhost").strip()
DB_NAME = os.getenv("DB_NAME", "pmo").strip()
DB_USER = os.getenv("DB_USER", "postgres").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456").strip()
DB_SCHEMA = os.getenv("DB_SCHEMA", "pmo").strip()
DB_PORT = int(os.getenv("DB_PORT", "5432").strip())
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5").strip())

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
).strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()

_provider_env = os.getenv("AI_PROVIDER", "").strip().lower()
if _provider_env:
    AI_PROVIDER = _provider_env
elif GEMINI_API_KEY:
    AI_PROVIDER = "gemini"
elif OPENROUTER_API_KEY:
    AI_PROVIDER = "openrouter"
elif OPENAI_API_KEY:
    AI_PROVIDER = "openai"
else:
    AI_PROVIDER = "gemini"
