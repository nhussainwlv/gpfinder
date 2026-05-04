"""GPFinder configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Flask
SECRET_KEY = os.environ.get("GPFINDER_SECRET_KEY", "dev-secret-change-in-production")
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# Rate limiting (per IP)
RATELIMIT_DEFAULT = "60 per minute"
RATELIMIT_STORAGE_URI = "memory://"

# Cache (in-memory; use Redis URL in production for multi-worker)
CACHE_TYPE = "SimpleCache"
CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes for search results

# Data
DATA_GP_CSV = BASE_DIR / "data" / "ukgp.csv"
DATA_FEEDBACK_JSONL = BASE_DIR / "data" / "feedback.jsonl"

# NHS API (optional - set GPFINDER_NHS_ORD_API_KEY if using ORD API)
NHS_ORD_API_BASE = "https://directory.spineservices.nhs.uk/ORD/2-0-0"
NHS_ORD_API_KEY = os.environ.get("GPFINDER_NHS_ORD_API_KEY", "")
# Elasticsearch (optional but recommended for production search)
ELASTICSEARCH_ENABLED = os.environ.get("GPFINDER_ES_ENABLED", "true").lower() == "true"
ELASTICSEARCH_URL = os.environ.get("GPFINDER_ES_URL", "")
ELASTICSEARCH_INDEX = os.environ.get("GPFINDER_ES_INDEX", "gpfinder-practices")

