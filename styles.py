"""MikRapor koyu tema QSS stilleri."""

DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1a1d23;
    color: #e8eaed;
    font-family: "Segoe UI", sans-serif;
    font-size: 11px;
}

QTabWidget::pane {
    border: 1px solid #2d3340;
    background-color: #1a1d23;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #252830;
    color: #9aa0a8;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #2d3340;
    color: #e8eaed;
    font-weight: 600;
}

QPushButton {
    background-color: #2d3340;
    color: #e8eaed;
    border: 1px solid #343a46;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3a4150;
    border-color: #4fc3f7;
}

QPushButton:pressed {
    background-color: #252830;
}

QPushButton#primaryBtn {
    background-color: #1565c0;
    border-color: #1976d2;
}

QPushButton#primaryBtn:hover {
    background-color: #1976d2;
}

QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background-color: #252830;
    color: #e8eaed;
    border: 1px solid #343a46;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #1565c0;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #252830;
    color: #e8eaed;
    selection-background-color: #1565c0;
    border: 1px solid #343a46;
}

QTableWidget {
    gridline-color: #343a46;
    alternate-background-color: #1e2128;
}

QHeaderView::section {
    background-color: #2d3340;
    color: #e8eaed;
    padding: 6px;
    border: 1px solid #343a46;
    font-weight: 600;
}

QScrollArea {
    border: none;
    background-color: #1a1d23;
}

QFrame#kpiCard {
    background-color: #252830;
    border: 1px solid #343a46;
    border-radius: 8px;
}

QLabel#kpiValue {
    font-size: 15px;
    font-weight: 700;
    color: #4fc3f7;
}

QLabel#kpiLabel {
    font-size: 10px;
    color: #9aa0a8;
}

QLabel#contextLabel {
    font-size: 11px;
    color: #81c784;
    background-color: #252830;
    border: 1px solid #343a46;
    border-radius: 6px;
    padding: 8px 12px;
}

QLabel#titleLabel {
    font-size: 20px;
    font-weight: 700;
    color: #e8eaed;
}

QGroupBox {
    border: 1px solid #343a46;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
    color: #9aa0a8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #e8eaed;
}
"""
