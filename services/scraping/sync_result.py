from datetime import datetime, timezone


class SyncResult:
    """
    Resultado de una sincronización de catálogo.

    Mantiene métricas del proceso:

    - productos procesados
    - creados
    - actualizados
    - sin cambios
    - errores
    - campos modificados
    - fallos encontrados
    - duración
    """

    def __init__(self):
        self.created = 0
        self.updated = 0
        self.unchanged = 0
        self.errors = 0

        self.processed = 0

        self.changes = []
        self.failures = []

        self.started_at = datetime.now(
            timezone.utc,
        )

        self.finished_at = None

    def increment_processed(self):
        """
        Incrementa cantidad de productos evaluados.
        """

        self.processed += 1

    def finish(self):
        """
        Marca finalización del proceso.
        """

        self.finished_at = datetime.now(
            timezone.utc,
        )

    @property
    def duration_seconds(self):
        """
        Duración total de sincronización.
        """

        if not self.finished_at:
            return 0

        return (
            self.finished_at - self.started_at
        ).total_seconds()

    def to_dict(self):
        """
        Convierte resultado a diccionario.
        """

        return {
            "processed": self.processed,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "changes": self.changes,
            "failures": self.failures,
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat()
                if self.finished_at
                else None
            ),
            "duration_seconds": self.duration_seconds,
        }

    def summary(self):
        """
        Resumen legible para logs.
        """

        return {
            "Procesados": self.processed,
            "Nuevos": self.created,
            "Actualizados": self.updated,
            "Sin cambios": self.unchanged,
            "Errores": self.errors,
            "Duración": self.duration_seconds,
        }
