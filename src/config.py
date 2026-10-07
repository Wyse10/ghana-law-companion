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

# Default input files
DEFAULT_PDF_PATH = os.path.join(RAW_DATA_DIR, "Ghana_1996-en.pdf")
DEFAULT_MD_PATH = os.path.join(
    MARKDOWN_DATA_DIR, "Ghana_Constitution_1992.md"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")