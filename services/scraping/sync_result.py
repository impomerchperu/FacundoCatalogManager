class SyncResult:
    def __init__(self):

        self.created = 0
        self.updated = 0
        self.unchanged = 0
        self.errors = 0

    def to_dict(self):

        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "errors": self.errors,
        }
