from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

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

    def remove_candidate(self, review_id, option_path):
        for record in self.records:
            if record["id"] != review_id:
                continue
            if record.get("kind") == "gallery":
                self.exclude_candidate(review_id, option_path)
                return
            record["candidate_options"] = [
                option
                for option in record.get("candidate_options", [])
                if option.get("path") != option_path
            ]
            if record.get("selected_path") == option_path:
                record["selected_action"] = ""
                record["selected_path"] = ""
                record["selected_url"] = ""

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
    assert dialog.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    assert dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint

    current = dialog.table.cellWidget(0, 2)
    current_layout = current.layout()
    assert current_layout is not None
    image_card = current_layout.itemAt(0).widget()
    current_apply = current_layout.itemAt(1).widget()
    current_image = image_card.layout().itemAt(0).widget()
    current_remove = image_card.layout().itemAt(1).widget()
    alternatives = dialog.table.cellWidget(0, 3)
    assert isinstance(current_image, _ImageChoiceLabel)
    assert isinstance(current_remove, QPushButton)
    assert current_remove.text() == "X"
    assert isinstance(current_apply, QPushButton)
    assert current_apply.text() == "APLICAR"
    assert current_apply.isEnabled()

    alternative_card = alternatives.layout().itemAt(0).widget()
    assert isinstance(alternative_card, QWidget)
    alternative_image = alternative_card.layout().itemAt(0).widget()
    alternative_remove = alternative_card.layout().itemAt(1).widget()
    assert isinstance(alternative_image, _ImageChoiceLabel)
    assert isinstance(alternative_remove, QPushButton)
    assert alternative_remove.text() == "X"
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
    current_layout = current.layout()
    assert current_layout is not None
    current_card = current_layout.itemAt(0).widget()
    current_image = current_card.layout().itemAt(0).widget()
    assert current_image.property("image_path") == (
        "image_review_staging/FB-100-new.webp"
    )

    alternative_container = dialog.table.cellWidget(0, 3)
    alternative_card = alternative_container.layout().itemAt(0).widget()
    alternative_image = alternative_card.layout().itemAt(0).widget()
    assert alternative_image.property("image_path") == ""
    assert alternative_image.toolTip().startswith("Imagen actual anterior")
    assert service.finalize_calls == []
    assert dialog.apply_button.isEnabled()

    dialog.close()

    assert service.records[0]["selected_action"] == "candidate"


def test_image_review_dialog_current_apply_is_always_enabled_and_keeps_image():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    current_container = dialog.table.cellWidget(0, 2)
    current_apply = current_container.layout().itemAt(1).widget()
    assert isinstance(current_apply, QPushButton)
    assert current_apply.isEnabled()

    current_apply.click()

    assert service.selection_calls == [("review-1", "keep", None)]
    assert service.finalize_calls == [["review-1"]]
    assert dialog.records == []

    dialog.close()


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


def test_image_review_dialog_can_apply_one_review_individually():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternatives_container = dialog.table.cellWidget(0, 3)
    alternative = alternatives_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)
    alternative._callback()

    current_container = dialog.table.cellWidget(0, 2)
    current_apply = current_container.layout().itemAt(1).widget()
    assert isinstance(current_apply, QPushButton)
    assert current_apply.isEnabled()

    current_apply.click()

    assert service.finalize_calls == [["review-1"]]
    assert dialog.records == []

    dialog.close()


def test_image_review_dialog_responsive_widget_reflows_by_width():
    _qapp()
    service = FakeReviewService()
    service.records[0]["candidate_options"] = [
        {
            "path": f"image_review_staging/FB-100-{index}.webp",
            "hash": f"hash-{index}",
            "url": f"https://site.test/{index}.webp",
            "gallery": False,
        }
        for index in range(4)
    ]
    dialog = ImageReviewDialog(service=service)

    alternatives = dialog.table.cellWidget(0, 3)
    narrow_height = alternatives.heightForWidth(140)
    wide_height = alternatives.heightForWidth(560)

    assert narrow_height > wide_height

    dialog.close()


def test_image_review_dialog_can_exclude_an_alternative_without_committing():
    _qapp()
    service = FakeReviewService()
    service.records[0]["kind"] = "gallery"
    dialog = ImageReviewDialog(service=service)

    alternatives_container = dialog.table.cellWidget(0, 3)
    option_container = alternatives_container.layout().itemAt(0).widget()
    assert isinstance(option_container, QWidget)
    alternative = option_container.layout().itemAt(0).widget()
    assert isinstance(alternative, _ImageChoiceLabel)

    reject_button = option_container.layout().itemAt(1).widget()
    assert isinstance(reject_button, QPushButton)
    assert reject_button.text() == "X"

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


def test_image_review_dialog_can_remove_replacement_alternative():
    _qapp()
    service = FakeReviewService()
    dialog = ImageReviewDialog(service=service)

    alternatives = dialog.table.cellWidget(0, 3)
    card = alternatives.layout().itemAt(0).widget()
    remove_button = card.layout().itemAt(1).widget()
    assert isinstance(remove_button, QPushButton)
    assert remove_button.text() == "X"

    remove_button.click()

    assert service.finalize_calls == []
    assert service.records[0]["candidate_options"] == []
    assert dialog.table.cellWidget(0, 3).layout().itemAt(0).widget().text() == (
        "No hay alternativas detectadas."
    )

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
