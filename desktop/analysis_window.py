"""AI analysis conversations and their background requests."""

from shared.errors import short_error


import pandas as pd
from PySide6.QtCore import Signal, Slot, QThreadPool
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget, QPushButton, QMessageBox

from desktop.analysis_browser import AnalysisBrowser
from desktop.background import BackgroundJob
from desktop.styles import APP_STYLESHEET
from desktop.widgets import RequestInput
from server.ai_analysis import run_post_analysis


class AnalysisWindow(QMainWindow):
    closed = Signal(object)

    def __init__(self, question: str, result: str,
                 dataset: pd.DataFrame | None = None, bql_query: str = "") -> None:
        super().__init__()
        self.history = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": result},
        ]
        self.dataset = dataset.copy(deep=True) if dataset is not None else pd.DataFrame()
        self.bql_query = bql_query
        self._job = None
        self._closed = False
        self.setWindowTitle("AI Post Analysis")
        self.resize(800, 600)
        self.setStyleSheet(APP_STYLESHEET)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("AI post analysis")
        title.setObjectName("pageTitle")
        self.question_label = QLabel(question)
        self.question_label.setWordWrap(True)

        self.result_text = AnalysisBrowser()
        self._render_history()

        layout.addWidget(title)
        self.question_label.hide()
        layout.addWidget(self.result_text, 1)
        self.follow_up = RequestInput()
        self.follow_up.setPlaceholderText("Ask a follow-up question (Enter to send, Shift+Enter for a new line)")
        self.follow_up.setMaximumHeight(90)
        self.follow_up.submitted.connect(self.submit_follow_up)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.submit_follow_up)
        self.send_button.setEnabled(not self.dataset.empty)
        layout.addWidget(self.follow_up)
        layout.addWidget(self.send_button)
        self.setCentralWidget(container)

    def _render_history(self) -> None:
        self.result_text.setMarkdown("\n\n---\n\n".join(
            f"**{'You' if message['role'] == 'user' else 'AI'}**\n\n{message['content']}"
            for message in self.history
        ))
        scrollbar = self.result_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def submit_follow_up(self) -> None:
        question = self.follow_up.toPlainText().strip()
        if self._closed or self._job is not None or not question or self.dataset.empty:
            return
        self._job = BackgroundJob(
            run_post_analysis, question, self.dataset.copy(deep=True),
            self.bql_query, [dict(message) for message in self.history],
        )
        self.history.append({"role": "user", "content": question})
        self._render_history()
        self.follow_up.clear()
        self.send_button.setEnabled(False)
        self.send_button.setText("Waiting...")
        self._job.signals.completed.connect(self._follow_up_finished)
        QThreadPool.globalInstance().start(self._job)

    @Slot(object, object)
    def _follow_up_finished(self, result, error) -> None:
        self._job = None
        if self._closed:
            return
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")
        if error is not None:
            question = self.history.pop()["content"]
            if not self.follow_up.toPlainText().strip():
                self.follow_up.setPlainText(question)
            QMessageBox.critical(self, "Analysis failed", short_error(error))
        else:
            self.history.append({"role": "assistant", "content": result})
        self._render_history()

    def closeEvent(self, event) -> None:
        self._closed = True
        self.history.clear()
        self.dataset = pd.DataFrame()
        self.bql_query = ""
        self.result_text.clear()
        self.follow_up.clear()
        self.question_label.clear()
        self.closed.emit(self)
        super().closeEvent(event)

