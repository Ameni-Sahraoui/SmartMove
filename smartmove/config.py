import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("SMARTMOVE_DATA_DIR", ROOT / "data")).resolve()
ARTIFACTS = Path(os.environ.get("SMARTMOVE_ARTIFACTS_DIR", ROOT / "artifacts")).resolve()
EXPORTS = Path(os.environ.get("SMARTMOVE_EXPORTS_DIR", ROOT / "exports")).resolve()
DB = DATA / "smartmove.db"
PRODUCTION = os.environ.get("SMARTMOVE_ENV") == "production"
COOKIE_SECURE = PRODUCTION
AS_OF = "2026-08-31"
DATASET_VERSION = "synthetic-ca-v1-seed42"
for path in (DATA, ARTIFACTS, EXPORTS):
    path.mkdir(parents=True, exist_ok=True)
