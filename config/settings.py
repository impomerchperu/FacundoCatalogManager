from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


DATABASE_PATH = BASE_DIR / "database" / "catalog.db"


LOG_PATH = BASE_DIR / "logs" / "fcm.log"


RESOURCES_PATH = BASE_DIR / "resources"
