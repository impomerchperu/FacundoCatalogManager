from PySide6.QtWidgets import QApplication

from gui.image_review_dialog import ImageReviewDialog, _ImageChoiceLabel


def _qapp():
    return QApplication.instance() or QApplication([])


class FakeReviewService:
    def __init__(self):
        self.records = [
            {
                "id": "review-1",
                "status": "pending",
                "kind": "replacement",
                "code": "FB-100",
                "product_name": "Producto",
                "current_path": "",
                "current_hash": "old-hash",
                "current_url": "https://site.test/old.webp",
                "candidate_options": [
                    {
                        "path": "image_review_staging/FB-100-new.webp",
                        "hash": "new-hash",
                        "url": "https://site.test/new.webp",
                        "gallery": True,
                    }
                ],
                "candidate_path": "image_review_staging/FB-100-new.webp",
                "candidate_hash": "new-hash",
                "candidate_url": "https://site.test/new.webp",
            }
        ]
        self.selection_calls = []
        self.finalize_calls = []
        self.discard_calls = 0

    def available(self):
        return [dict(record) for record in self.records]

    def apply_selection(self, review_id, action, manual_path=None):
        self.selection_calls.append((review_id, action, manual_path))
        for record in self.records:
            if record["id"] == review_id:
                record["selected_action"] = action
                record["selected_path"] = manual_path or record["candidate_path"]
                record["selected_url"] = (
                    record["candidate_url"] if action == "candidate" else ""
                )
        return {"selected": True, "changed": False}

    def finalize_selected(self, review_ids):
        self.finalize_calls.append(list(review_ids))
        self.records = [
            record for record in self.records if record["id"] not in review_ids
        ]
        return [{"code": "FB-100", "changed": True}]

    def discard_selections(self, review_ids=None):
        self.discard_calls += 1
        for record in self.records:
            record.pop("selected_action", None)
            record.pop("selected_path", None)
            record.pop("selected_url", None)


def test_image_review_dialog_has_no_actions_column_and_has_apply_button():
    _qapp()
    service = FakeReviewService()

    dialog = ImageReviewDialog(service=service)

    assert dialog.table.columnCount() == 4
    assert [
        dialog.table.horizontalHeaderItem(index).text()
        for index in range(dialog.table.columnCount())
    ] == ["Código", "Producto", "Imagen actual", "Imágenes detectadas"]
    assert not hasattr(dialog, "close_button")
    assert dialog.apply_button.text() == "APLICAR"
    assert not dialog.apply_button.isEnabled()

    current = dialog.table.cellWidget(0, 2)
    alternatives = dialog.table.cellWidget(0, 3)
    assert isinstance(current, _ImageChoiceLabel)
    assert isinstance(alternatives, type(dialog.table.cellWidget(0, 2)))
    assert alternatives.layout().itemAt(0).widget() is not None

    dialog.close()


def test_image_review_dialog_selection_updates_current_preview_without_committing():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternative_container = dialog.table.cellWidget(0, 3)
    alternative = alternative_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)

    alternative._callback()

    assert service.selection_calls == [
        ("review-1", "candidate", "image_review_staging/FB-100-new.webp")
    ]
    current = dialog.table.cellWidget(0, 2)
    assert isinstance(current, _ImageChoiceLabel)
    assert service.finalize_calls == []
    assert dialog.apply_button.isEnabled()

    dialog.close()


def test_image_review_dialog_close_discards_unapplied_selection():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternative_container = dialog.table.cellWidget(0, 3)
    alternative = alternative_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)
    alternative._callback()

    dialog.close()

    assert service.finalize_calls == []
    assert service.discard_calls == 1
