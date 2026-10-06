import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
MARKDOWN_DATA_DIR = os.path.join(BASE_DIR, "data", "markdown")

# Default input files
DEFAULT_PDF_PATH = os.path.join(RAW_DATA_DIR, "Ghana_1996-en.pdf")
DEFAULT_MD_PATH = os.path.join(
    MARKDOWN_DATA_DIR, "Ghana_Constitution_1992.md"
)