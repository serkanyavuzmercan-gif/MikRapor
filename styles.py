"""MikRapor koyu tema QSS stilleri — modern, ferah, okunabilir."""

# Renk paleti (tek yerde):
#   Arka plan (pencere)   #0f1216   |  Panel/kart          #171a21
#   Girdi alanı           #1e222b   |  Kenarlık            #2a2f3a
#   Metin                 #e6e8eb   |  Soluk metin         #8b929e
#   Ana vurgu (mavi)      #2f6fed   |  hover #3b82f6  pressed #1d4ed8
#   Başarı (yeşil)        #34d399   |  Uyarı #fbbf24  Hata #f87171

DARK_STYLESHEET = """
* {
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 12px;
}

QMainWindow, QDialog {
    background-color: #0f1216;
}

QWidget {
    background-color: transparent;
    color: #e6e8eb;
}

/* ---- Sekmeler ---- */
QTabWidget::pane {
    border: 1px solid #2a2f3a;
    background-color: #12151b;
    border-radius: 10px;
    top: -1px;
}

QTabBar::tab {
    background-color: transparent;
    color: #8b929e;
    padding: 9px 20px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}

QTabBar::tab:hover {
    color: #e6e8eb;
}

QTabBar::tab:selected {
    color: #e6e8eb;
    border-bottom: 2px solid #2f6fed;
}

/* ---- Butonlar ---- */
QPushButton {
    background-color: #232834;
    color: #e6e8eb;
    border: 1px solid #333a47;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2c3340;
    border-color: #3f475a;
}

QPushButton:pressed {
    background-color: #1c212b;
}

QPushButton:disabled {
    background-color: #1a1e26;
    color: #5b626e;
    border-color: #262b35;
}

QPushButton#primaryBtn {
    background-color: #2f6fed;
    color: #ffffff;
    border: 1px solid #2f6fed;
}

QPushButton#primaryBtn:hover {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

QPushButton#primaryBtn:pressed {
    background-color: #1d4ed8;
}

QPushButton#primaryBtn:disabled {
    background-color: #24304a;
    color: #8aa0c8;
    border-color: #24304a;
}

/* ---- Girdiler ---- */
QLineEdit, QComboBox, QTextEdit, QAbstractSpinBox {
    background-color: #1e222b;
    color: #e6e8eb;
    border: 1px solid #2a2f3a;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QAbstractSpinBox:focus {
    border: 1px solid #2f6fed;
}

QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {
    border-color: #3f475a;
}

QComboBox::drop-down {
    border: none;
    width: 26px;
}

QComboBox QAbstractItemView {
    background-color: #1e222b;
    color: #e6e8eb;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
    border: 1px solid #2a2f3a;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    width: 18px;
    border: none;
    background-color: #232834;
}

QAbstractSpinBox::up-button { border-top-right-radius: 8px; }
QAbstractSpinBox::down-button { border-bottom-right-radius: 8px; }

QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {
    background-color: #2c3340;
}

/* ---- Tablolar ---- */
QTableWidget {
    background-color: #12151b;
    color: #e6e8eb;
    border: 1px solid #2a2f3a;
    border-radius: 10px;
    gridline-color: #232834;
    alternate-background-color: #161a21;
    selection-background-color: #233153;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 6px 8px;
    border: none;
}

QHeaderView::section {
    background-color: #1a1e26;
    color: #b9c0cc;
    padding: 9px 8px;
    border: none;
    border-right: 1px solid #232834;
    border-bottom: 1px solid #2a2f3a;
    font-weight: 700;
}

QTableCornerButton::section {
    background-color: #1a1e26;
    border: none;
}

/* ---- Kaydırma çubukları ---- */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #2a2f3a;
    min-height: 30px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover { background: #3f475a; }

QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: #2a2f3a;
    min-width: 30px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover { background: #3f475a; }

QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---- Gruplar / kartlar ---- */
QGroupBox {
    background-color: #171a21;
    border: 1px solid #262b35;
    border-radius: 12px;
    margin-top: 14px;
    padding: 18px 16px 16px 16px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 2px;
    padding: 0 6px;
    color: #c6ccd6;
}

/* ---- Etiketler ---- */
QLabel { color: #e6e8eb; }

QLabel#titleLabel {
    font-size: 21px;
    font-weight: 800;
    color: #f3f5f7;
}

QLabel#contextLabel {
    font-size: 12px;
    color: #a7f3d0;
    background-color: #171a21;
    border: 1px solid #262b35;
    border-radius: 8px;
    padding: 10px 14px;
}

/* ---- KPI kartları ---- */
QFrame#kpiCard {
    background-color: #1b1f28;
    border: 1px solid #2a2f3a;
    border-radius: 10px;
}

QLabel#kpiValue {
    font-size: 16px;
    font-weight: 800;
    color: #60a5fa;
}

QLabel#kpiLabel {
    font-size: 11px;
    color: #8b929e;
}

QToolTip {
    background-color: #1e222b;
    color: #e6e8eb;
    border: 1px solid #2a2f3a;
    border-radius: 6px;
    padding: 6px 8px;
}
"""
