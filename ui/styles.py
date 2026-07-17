"""MikRapor Teal (A) tema — kurumsal finans / teal–navy design system.

Renk token'ları hem QSS hem view modülleri tarafından kullanılır.
"""

from __future__ import annotations

# ---- Design tokens (Teal A) -------------------------------------------------
BG = "#eef2f7"
BG_END = "#f7f9fc"
PAGE_BG = "#f4f6f9"
SURFACE = "#ffffff"
PANEL_BG = "#f7f9fc"
BORDER = "#e2e6ec"
BORDER_STRONG = "#cbd2dc"

INK = "#0f172a"
INK_SOFT = "#1f2937"
SUBINK = "#334155"
MUTED = "#64748b"
FAINT = "#94a3b8"

ACCENT = "#0f766e"          # teal CTA / seçili sekme
ACCENT_HOVER = "#0d9488"
ACCENT_PRESSED = "#0f5f5a"
ACCENT_SOFT = "#ecfdf5"     # açık teal zemin
ACCENT_MUTED = "#99f6e4"

NAVY = "#1e3a5f"            # bölüm başlıkları
NAVY_SOFT = "#e8eef5"

OK = "#15803d"
OK_BG = "#e8f6ee"
WARN = "#b45309"
WARN_BG = "#fdf3e0"
BAD = "#b91c1c"
BAD_BG = "#fdecec"

PRIMARY_SOFT = "#e6f5f3"    # KPI soft teal (eski mavi #eef4ff yerine)


APP_STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Segoe UI Variable", system-ui, sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{ background-color: {BG}; }}
QWidget {{ color: {INK_SOFT}; }}
QWidget#rootArea {{
    background-color: {BG};
}}

/* ---- Marka bar ---- */
QFrame#brandBar {{
    background-color: transparent;
    border: none;
    padding: 2px 0 4px 0;
}}
QLabel#titleLabel {{
    font-size: 24px;
    font-weight: 800;
    color: {NAVY};
    letter-spacing: -0.3px;
    padding-bottom: 2px;
}}
QLabel#brandSubtitle {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 500;
    padding-bottom: 2px;
}}
QLabel#connStatus {{
    color: {ACCENT};
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    background-color: {ACCENT_SOFT};
    border: 1px solid {ACCENT_MUTED};
    border-radius: 8px;
}}
QLabel#connStatus[connected="true"] {{
    color: {ACCENT};
}}
QLabel#connStatus[connected="false"] {{
    color: {MUTED};
    background-color: #f1f5f9;
    border: 1px solid {BORDER};
}}

/* ---- Sekme araç çubuğu ---- */
QFrame#tabToolbar {{
    background-color: #f4f7f9;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#toolbarHint {{
    color: {MUTED};
    font-size: 12px;
}}
QWidget#emptyState {{
    background-color: {SURFACE};
    border: none;
    border-radius: 12px;
}}
QWidget#emptyOverlay {{
    background: transparent;
}}

/* ---- Sekmeler ---- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {SURFACE};
    border-radius: 12px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {MUTED};
    padding: 10px 20px;
    margin-right: 2px;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 600;
    font-size: 13px;
}}
QTabBar::tab:hover {{ color: {INK_SOFT}; }}
QTabBar::tab:selected {{
    color: {INK};
    border-bottom: 3px solid {ACCENT};
}}

/* ---- Butonlar ---- */
QPushButton {{
    background-color: {SURFACE};
    color: {SUBINK};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
    text-align: center;
}}
QPushButton:hover {{ background-color: #f3f5f8; border-color: #9aa6b6; }}
QPushButton:pressed {{ background-color: #e9edf3; }}
QPushButton:disabled {{ background-color: #f1f3f6; color: #a8b0bd; border-color: {BORDER}; }}

QPushButton#primaryBtn {{
    background-color: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT};
    text-align: center;
    padding: 10px 18px;
    border-radius: 8px;
    min-height: 22px;
}}
QPushButton#primaryBtn:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton#primaryBtn:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}
QPushButton#primaryBtn:disabled {{
    background-color: #99d5cf;
    color: #eefaf8;
    border-color: #99d5cf;
}}

/* Empty-state CTA — gövde _EmptyCtaButton.paintEvent ile çizilir (alt kenar kırpılmasın) */
QPushButton#emptyCtaBtn {{
    background: transparent;
    border: none;
    padding: 0;
    min-width: 300px;
    max-width: 300px;
    min-height: 48px;
    max-height: 48px;
}}
QPushButton#emptyCtaBtn:hover,
QPushButton#emptyCtaBtn:pressed {{
    background: transparent;
    border: none;
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    color: {SUBINK};
    border: 1px solid {BORDER_STRONG};
    text-align: center;
}}

/* ---- Girdiler ---- */
QLineEdit, QComboBox, QTextEdit, QAbstractSpinBox, QDateEdit {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QAbstractSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QAbstractSpinBox:hover {{
    border-color: #9aa6b6;
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border-left: 1px solid {BORDER_STRONG};
    background-color: {ACCENT_SOFT};
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}}
QDateEdit#tarihEdit {{
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
    padding-right: 10px;
}}
QDateEdit#tarihEdit::drop-down {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
    image: none;
}}
QDateEdit#donemAralikEdit {{
    background: transparent;
    border: none;
    padding: 0 2px;
    font-size: 13px;
    font-weight: 600;
}}
QDateEdit#donemAralikEdit:focus {{
    background-color: {ACCENT_SOFT};
    border-radius: 4px;
}}
QDateEdit#donemAralikEdit::drop-down {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
    image: none;
}}
QWidget#calPopup {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
}}
QPushButton#calBtn {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
    border: 1px solid {BORDER_STRONG};
    border-left: none;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    padding: 0;
    font-size: 16px;
    min-height: 34px;
    max-height: 34px;
}}
QPushButton#calBtn:hover {{ background-color: #d1fae5; border-color: #9aa6b6; }}
QPushButton#calBtn:pressed {{ background-color: #a7f3d0; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QCalendarWidget QWidget {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    alternate-background-color: {PAGE_BG};
}}
QCalendarWidget QAbstractItemView:enabled {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QCalendarWidget QToolButton {{ color: {INK_SOFT}; background: transparent; }}
QCalendarWidget QToolButton:hover {{ background-color: #eef2f7; border-radius: 4px; }}

QTextBrowser {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
}}

QScrollArea {{ border: none; background-color: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; min-height: 30px; border-radius: 6px; }}
QScrollBar::handle:vertical:hover {{ background: #9aa6b6; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; min-width: 30px; border-radius: 6px; }}
QScrollBar::handle:horizontal:hover {{ background: #9aa6b6; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 14px;
    padding: 18px 16px 16px 16px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 2px;
    padding: 0 6px;
    color: {SUBINK};
}}

QTableWidget {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: #eef1f5;
    alternate-background-color: #f9fafc;
    selection-background-color: #ccfbf1;
    selection-color: {INK_SOFT};
}}
QHeaderView::section {{
    background-color: #f3f5f8;
    color: {SUBINK};
    padding: 9px 8px;
    border: none;
    border-right: 1px solid #e7eaef;
    border-bottom: 1px solid {BORDER};
    font-weight: 700;
}}

QLabel {{ color: {INK_SOFT}; }}
QToolTip {{
    background-color: {SURFACE};
    color: {INK_SOFT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
}}
"""

# Geriye uyumluluk — eski import adları
DARK_STYLESHEET = APP_STYLESHEET
LIGHT_STYLESHEET = APP_STYLESHEET
