"""Render AI answers without loading embedded files or opening local links."""

from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QTextBrowser


class AnalysisBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self.open_citation)

    def loadResource(self, resource_type, url):
        # Markdown/HTML from a model must not load local files or remote images.
        return None

    def open_citation(self, url):
        if url.scheme().lower() in {"https", "http"} and url.host():
            QDesktopServices.openUrl(url)
