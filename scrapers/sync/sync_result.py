from dataclasses import dataclass, field


@dataclass
class SyncResult:
    """
    Resultado completo de una sincronización.
    """

    new: list = field(
        default_factory=list
    )

    updated: list = field(
        default_factory=list
    )

    unchanged: list = field(
        default_factory=list
    )


    images_processed: int = 0

    image_errors: int = 0


    errors: list = field(
        default_factory=list
    )


    @property
    def new_count(self):
        return len(self.new)


    @property
    def updated_count(self):
        return len(self.updated)


    @property
    def unchanged_count(self):
        return len(self.unchanged)


    def summary(self):

        return {
            "new": self.new_count,
            "updated": self.updated_count,
            "unchanged": self.unchanged_count,
            "images_processed": self.images_processed,
            "image_errors": self.image_errors,
            "errors": len(self.errors),
        }