"""Shared desktop appearance."""

APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #f3f6fb;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 9pt;
}

QLabel#pageTitle {
    color: #102a56;
    font-size: 15.75pt;
    font-weight: 700;
}

QLabel#pageSubtitle, QLabel#mutedLabel {
    color: #64748b;
}

QLabel#pageSubtitle {
    font-size: 9pt;
    margin-bottom: 2px;
}

QLabel#sectionLabel {
    color: #173c78;
    font-size: 9.75pt;
    font-weight: 650;
}

QFrame#card {
    background-color: #ffffff;
    border: 1px solid #dce5f2;
    border-radius: 12px;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dce5f2;
    border-radius: 9px;
    font-weight: 600;
    margin-top: 7px;
    padding: 8px 6px 5px 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    padding: 0 5px;
    color: #334e75;
    background-color: #f3f6fb;
}

QGroupBox:disabled {
    background-color: #e5e9ef;
    border-color: #cbd2dc;
    color: #8b96a8;
}

QGroupBox::title:disabled {
    color: #8b96a8;
    background-color: #f3f6fb;
}

QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox {
    background-color: #f8fafc;
    border: 1px solid #cbd7e6;
    border-radius: 7px;
    padding: 4px 7px;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus, QComboBox:focus {
    background-color: #ffffff;
    border: 2px solid #4381ee;
}

QPushButton {
    min-height: 18px;
    background-color: #e8eef8;
    color: #214578;
    border: 1px solid #c9d7eb;
    border-radius: 7px;
    padding: 5px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #dbe7f8;
    border-color: #9fb9df;
}

QPushButton:pressed {
    background-color: #c9daf3;
}

QPushButton:disabled {
    color: #94a3b8;
    background-color: #edf1f6;
    border-color: #dce3eb;
}

QPushButton#primaryButton {
    min-width: 130px;
    background-color: #2563d8;
    color: #ffffff;
    border-color: #2563d8;
}

QPushButton#primaryButton:hover {
    background-color: #1d55bf;
    border-color: #1d55bf;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #dce5f2;
    border-radius: 9px;
    gridline-color: transparent;
    selection-background-color: #dbeafe;
    selection-color: #153868;
    outline: none;
}

QTableWidget::item {
    padding: 4px 7px;
    border-bottom: 1px solid #edf2f7;
}

QTableWidget::item:selected {
    background-color: #e3ecfa;
    color: #172033;
}

QTableWidget::item:selected:!active {
    background-color: #e3ecfa;
    color: #172033;
}

QHeaderView::section {
    background-color: #173c78;
    color: #ffffff;
    border: none;
    border-right: 1px solid #31558d;
    padding: 6px;
    font-weight: 600;
}

QScrollBar:vertical {
    background: #edf2f7;
    width: 11px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #a9bad0;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #edf2f7;
    height: 12px;
    margin: 2px 0;
    border: none;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #a9bad0;
    border-radius: 4px;
    min-width: 36px;
}

QScrollBar::handle:horizontal:hover {
    background: #829bbd;
}

QScrollBar::handle:horizontal:pressed {
    background: #5d7fae;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: transparent;
    border: none;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""

