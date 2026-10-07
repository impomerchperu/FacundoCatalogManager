from PySide6.QtWidgets import QApplication, QPushButton

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
                "excluded_options": [],
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

    def exclude_candidate(self, review_id, option_path):
        for record in self.records:
            if record["id"] == review_id:
                record.setdefault("excluded_options", []).append(option_path)
                if record.get("selected_path") == option_path:
                    record["selected_action"] = ""
                    record["selected_path"] = ""
                    record["selected_url"] = ""

    def discard_selections(self, review_ids=None):
        self.discard_calls += 1


def test_image_review_dialog_has_no_actions_column_and_has_apply_button():
    _qapp()
    service = FakeReviewService()

    dialog = ImageReviewDialog(service=service)

    assert dialog.table.columnCount() == 4
    assert [
        dialog.table.horizontalHeaderItem(index).text()
        for index in range(dialog.table.columnCount())
    ] == ["Código", "Producto", "Imagen actual", "Imágenes detectadas"]
    assert dialog.apply_button.text() == "APLICAR"
    assert not dialog.apply_button.isEnabled()

    current = dialog.table.cellWidget(0, 2)
    alternatives = dialog.table.cellWidget(0, 3)
    assert isinstance(current, _ImageChoiceLabel)
    assert not isinstance(current, QPushButton)
    assert alternatives.layout().itemAt(0).widget() is not None
    assert not isinstance(alternatives.layout().itemAt(0).widget(), QPushButton)
    assert all(
        not isinstance(dialog.table.cellWidget(0, column), QPushButton)
        for column in range(dialog.table.columnCount())
    )

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

    assert service.records[0]["selected_action"] == "candidate"


def test_image_review_dialog_apply_commits_selected_records_only():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternative_container = dialog.table.cellWidget(0, 3)
    alternative = alternative_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)
    alternative._callback()

    dialog._apply_changes()

    assert service.finalize_calls == [["review-1"]]
    assert dialog.records == []


def test_image_review_dialog_can_exclude_an_alternative_without_committing():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternative_container = dialog.table.cellWidget(0, 3)
    alternative = alternative_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)

    reject_button = alternative_container.layout().itemAt(0).widget()
    # The alternative itself is inside the nested option container.
    option_container = alternative.parentWidget()
    reject_button = option_container.layout().itemAt(1).widget()
    assert isinstance(reject_button, QPushButton)

    reject_button.click()

    assert service.finalize_calls == []
    assert service.records[0]["excluded_options"] == [
        "image_review_staging/FB-100-new.webp"
    ]
    assert dialog.table.cellWidget(0, 3).layout().itemAt(0).widget().text() == (
        "No hay alternativas detectadas."
    )
    assert dialog.apply_button.isEnabled()

    dialog.close()


def test_image_review_dialog_close_preserves_unapplied_selection():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternative_container = dialog.table.cellWidget(0, 3)
    alternative = alternative_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)
    alternative._callback()

    dialog.close()

    assert service.finalize_calls == []
    assert service.discard_calls == 0
    assert service.records[0]["selected_action"] == "candidate"
