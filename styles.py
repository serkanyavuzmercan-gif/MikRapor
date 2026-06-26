"""MikRapor açık (light) tema QSS — temiz, finans/rapor görünümü."""

# Renk paleti:
#   Arka plan #f4f6f9 · Kart/panel #ffffff · Kenarlık #e2e6ec
#   Metin #1f2937 · Soluk #6b7280 · Başlık #111827
#   Ana vurgu #2f6fed (hover #2563eb, pressed #1d4ed8)
#   Başarı #15803d · Uyarı #b45309 · Hata #b91c1c

DARK_STYLESHEET = """
* {
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 12px;
}

QMainWindow, QDialog { background-color: #f4f6f9; }
QWidget { color: #1f2937; }
QWidget#rootArea { background-color: #f4f6f9; }

/* ---- Sekmeler ---- */
QTabWidget::pane {
    border: 1px solid #e2e6ec;
    background-color: #ffffff;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    background-color: transparent;
    color: #6b7280;
    padding: 9px 22px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}
QTabBar::tab:hover { color: #1f2937; }
QTabBar::tab:selected { color: #111827; border-bottom: 2px solid #2f6fed; }

/* ---- Butonlar ---- */
QPushButton {
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #cbd2dc;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
}
QPushButton:hover { background-color: #f3f5f8; border-color: #9aa6b6; }
QPushButton:pressed { background-color: #e9edf3; }
QPushButton:disabled { background-color: #f1f3f6; color: #a8b0bd; border-color: #e2e6ec; }

QPushButton#primaryBtn { background-color: #2f6fed; color: #ffffff; border: 1px solid #2f6fed; }
QPushButton#primaryBtn:hover { background-color: #2563eb; border-color: #2563eb; }
QPushButton#primaryBtn:pressed { background-color: #1d4ed8; }
QPushButton#primaryBtn:disabled { background-color: #a9c2f5; color: #eef3fd; border-color: #a9c2f5; }

/* ---- Girdiler ---- */
QLineEdit, QComboBox, QTextEdit, QAbstractSpinBox, QDateEdit {
    background-color: #ffffff;
    color: #1f2937;
    border: 1px solid #cbd2dc;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QAbstractSpinBox:focus, QDateEdit:focus {
    border: 1px solid #2f6fed;
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QAbstractSpinBox:hover { border-color: #9aa6b6; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1f2937;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
    border: 1px solid #e2e6ec;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

/* Takvim açılır penceresi (QDateEdit) */
QCalendarWidget QWidget { background-color: #ffffff; color: #1f2937; alternate-background-color: #f4f6f9; }
QCalendarWidget QAbstractItemView:enabled { background-color: #ffffff; color: #1f2937; selection-background-color: #2f6fed; selection-color: #ffffff; }
QCalendarWidget QToolButton { color: #1f2937; background: transparent; }
QCalendarWidget QToolButton:hover { background-color: #eef2f7; border-radius: 4px; }

/* ---- Bilanço görünümü (HTML) ---- */
QTextBrowser {
    background-color: #ffffff;
    color: #1f2937;
    border: 1px solid #e2e6ec;
    border-radius: 10px;
    padding: 4px;
}

/* ---- Kaydırma çubukları ---- */
QScrollArea { border: none; background-color: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd2dc; min-height: 30px; border-radius: 6px; }
QScrollBar::handle:vertical:hover { background: #9aa6b6; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cbd2dc; min-width: 30px; border-radius: 6px; }
QScrollBar::handle:horizontal:hover { background: #9aa6b6; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---- Gruplar / tablolar (varsa) ---- */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e6ec;
    border-radius: 12px;
    margin-top: 14px;
    padding: 18px 16px 16px 16px;
    font-weight: 700;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 16px; top: 2px; padding: 0 6px; color: #374151; }

QTableWidget {
    background-color: #ffffff; color: #1f2937;
    border: 1px solid #e2e6ec; border-radius: 10px;
    gridline-color: #eef1f5; alternate-background-color: #f9fafc;
    selection-background-color: #dbe7ff; selection-color: #1f2937;
}
QHeaderView::section { background-color: #f3f5f8; color: #374151; padding: 9px 8px; border: none; border-right: 1px solid #e7eaef; border-bottom: 1px solid #e2e6ec; font-weight: 700; }

/* ---- Etiketler ---- */
QLabel { color: #1f2937; }
QLabel#titleLabel { font-size: 22px; font-weight: 800; color: #111827; }

QToolTip { background-color: #ffffff; color: #1f2937; border: 1px solid #e2e6ec; border-radius: 6px; padding: 6px 8px; }
"""
