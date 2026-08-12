class CatalogLoadRepository:
    """Compatibilidad con código legado; no gestiona el catálogo activo."""

    def __init__(self, db) -> None:
        self.db = db

    def ensure_initial_applied_load(self) -> None:
        return None

    def restore_latest_applied(self) -> None:
        return None

    def cleanup_expired_history(self, retention_days=None) -> int:
        return 0
