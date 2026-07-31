class SyncRepository:
    def __init__(self):

        self.records = {}

    def get(self, code):

        return self.records.get(code)

    def save(self, record):

        self.records[record.code] = record
