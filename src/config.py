import os

from dotenv import load_dotenv

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
MARKDOWN_DATA_DIR = os.path.join(BASE_DIR, "data", "markdown")
KNOWLEDGE_BASE_DIR = MARKDOWN_DATA_DIR

# Output path for processed chunks
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
PROCESSED_CHUNKS_PATH = os.path.join(
    PROCESSED_DATA_DIR, "constitution_chunks.json"
)
VECTOR_DB_PATH = os.path.join(BASE_DIR, "data", "qdrant_db")

# Default input files
DEFAULT_PDF_PATH = os.path.join(RAW_DATA_DIR, "Ghana_1996-en.pdf")
DEFAULT_MD_PATH = os.path.join(
    MARKDOWN_DATA_DIR, "Ghana_Constitution_1992.md"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")
GROQ_CONTEXT_MAX_CHARS = int(os.getenv("GROQ_CONTEXT_MAX_CHARS", "16000"))
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "900"))