from pathlib import Path


SPIDER_SRC_DIR = Path(__file__).resolve().parents[1]
QCWY_DIR = SPIDER_SRC_DIR / "QCWY"
QCWY_DEFAULT_OUTPUT_DIR = QCWY_DIR / "data" / "api"
QCWY_DEFAULT_PROFILE_DIR = QCWY_DIR / ".browser_profile"
