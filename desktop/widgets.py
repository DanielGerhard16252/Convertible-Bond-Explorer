"""Reusable search input widgets."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QComboBox, QPlainTextEdit


class CheckableComboBox(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setEditable(False)
        self.setPlaceholderText("Select credit ratings")
        self.setCurrentIndex(-1)
        self.view().pressed.connect(self.toggle_item)

    def toggle_item(self, index) -> None:
        item = self.model().itemFromIndex(index)
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(
            Qt.CheckState.Unchecked
            if checked
            else Qt.CheckState.Checked
        )
        self.setCurrentIndex(-1)


class RequestInput(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        is_enter = event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        )
        is_multiline = bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )

        if is_enter and not is_multiline:
            self.submitted.emit()
            event.accept()
            return

        super().keyPressEvent(event)


