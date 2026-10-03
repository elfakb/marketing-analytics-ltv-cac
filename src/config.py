"""Project-wide paths and constants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
POWERBI_DIR = ROOT / "powerbi" / "data"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
SQL_DIR = ROOT / "sql"
DB_PATH = DATA_PROCESSED / "marketing.db"

SEED = 42
START_DATE = "2025-01-01"
END_DATE = "2025-12-31"
LTV_WINDOWS = (90, 180)   # days after first order
CURRENCY = "TRY"
