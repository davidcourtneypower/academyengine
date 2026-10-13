from __future__ import annotations

# Single source of truth for Academy Engine desktop + external overlay visuals.
# Keep semantic colors here so both surfaces move together when the design changes.
THEME_TOKENS = {
    "dark": {
        "bg": "#050f1b", "panel": "#081b2d", "panel_alt": "#061624", "border": "#1a4b6b",
        "text": "#f1f8ff", "text_strong": "#ffffff", "muted": "#8ba3b7", "accent": "#1dafff",
        "ps": "#b46cff", "plus": "#f6c844", "role": "#32e3aa",
        "info": "#2aa8ff", "good": "#35e58d", "warn": "#ffc857", "bad": "#ff5b76",
    },
    "light": {
        "bg": "#eef3f7", "panel": "#ffffff", "panel_alt": "#f7fafc", "border": "#cbd8e2",
        "text": "#182533", "text_strong": "#102331", "muted": "#667b89", "accent": "#057caa",
        "ps": "#7650c7", "plus": "#b07900", "role": "#0c8d69",
        "info": "#2d78c4", "good": "#23875b", "warn": "#b56c13", "bad": "#c53d55",
    },
}

BASE_DESKTOP_STYLE = r"""
*{font-family:'Segoe UI Variable','Segoe UI';font-size:13px;color:#eef5fb}
QMainWindow,QWidget{background:#071019}
QLabel{background:transparent}
QFrame#sidebar{background:#050b12;border-right:1px solid #142638}
QFrame#card,QFrame#metricCard,QFrame#eventCard,QFrame#developmentLane{background:#0d1924;border:1px solid #1c3346;border-radius:14px}
QFrame#metricCard{border-top:2px solid #2f7bdc}
QFrame#heroCard{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #10283a,stop:.55 #0d1b29,stop:1 #111829);border:1px solid #2b5270;border-radius:18px}
QFrame#filterBar{background:#0a1620;border:1px solid #1b3447;border-radius:13px}
QFrame#eventCard[eventKind="ps"]{border-left:4px solid #8b5cf6}
QFrame#eventCard[eventKind="plus"]{border-left:4px solid #f2c94c}
QFrame#eventCard[eventKind="role"]{border-left:4px solid #18d7a0}
QFrame#psBadge{background:#f3f5f7;border:1px solid #ffffff;border-radius:8px}
QFrame#psBadgePlus{background:#c99a21;border:1px solid #f1ce68;border-radius:8px}
QPushButton{background:#102130;border:1px solid #244359;border-radius:9px;padding:9px 13px;font-weight:600}
QPushButton:hover{background:#153049;border-color:#3c6d90}
QPushButton:pressed{background:#0e1b27}
QPushButton:disabled{background:#0b151d;border-color:#192a36;color:#5e7180}
QPushButton#nav{background:transparent;border:0;border-radius:9px;padding:11px 12px;color:#91a6b6;text-align:left}
QPushButton#nav:hover{background:#0d1c29;color:#ffffff}
QPushButton#nav:checked{background:#11283a;color:#ffffff;font-weight:700;border-left:3px solid #45d4ff}
QPushButton#primary{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1e74df,stop:1 #2aa6ed);border-color:#4ab6f4;color:white;font-weight:750}
QPushButton#danger{background:#2b151a;border:1px solid #66303a;color:#ffb7be;font-weight:650}
QPushButton#ghost{background:transparent}
QPushButton#staleRefresh{background:#4d3520;border:1px solid #d39a4a;color:#ffe0aa;font-weight:750}
QPushButton#staleRefreshAlt{background:#65451f;border:1px solid #f2bd68;color:#fff1ce;font-weight:800}
QLabel#brand{font-size:20px;font-weight:900;letter-spacing:1px;color:#f8fbff}
QLabel#brandAccent{font-size:11px;font-weight:800;letter-spacing:2px;color:#45d4ff}
QLabel#pageTitle{font-size:30px;font-weight:800;color:#ffffff}
QLabel#heroTitle{font-size:25px;font-weight:800;color:#ffffff}
QLabel#metricValue{font-size:27px;font-weight:850;color:#ffffff}
QLabel#sectionTitle{font-size:15px;font-weight:750;color:#f6fbff}
QLabel#muted{color:#8397a8}
QLabel#goodText{color:#4ade80;font-weight:700}
QLabel#warningText{color:#f0b55f;font-weight:700}
QLabel#successText{color:#48d597;font-weight:700}
QLabel#badText{color:#fb7185;font-weight:700}
QLabel#accent{color:#65c7ff;font-weight:700}
QLabel#ovrHero{font-size:38px;font-weight:900;color:#f2c94c}
QLabel#statusChipLabel{padding:4px 9px;border-radius:9px;font-size:11px;font-weight:800}
QLabel#statusChipLabel[kind="good"]{background:#0c3528;color:#6ef0ae;border:1px solid #216f51}
QLabel#statusChipLabel[kind="warn"]{background:#382b12;color:#ffd17b;border:1px solid #755520}
QLabel#statusChipLabel[kind="bad"]{background:#351820;color:#ff93a2;border:1px solid #7a3443}
QLabel#statusChipLabel[kind="info"]{background:#112d42;color:#76cfff;border:1px solid #285f84}
QLabel#statusChipLabel[kind="muted"]{background:#17232c;color:#9eb0bd;border:1px solid #344653}
QLabel#eventMarker[eventKind="ps"]{color:#a78bfa;font-size:18px}
QLabel#eventMarker[eventKind="plus"]{color:#f2c94c;font-size:18px}
QLabel#eventMarker[eventKind="role"]{color:#18d7a0;font-size:18px}
QFrame#psBadge QLabel{color:#071018} QLabel#psBadgeText{font-size:11px;font-weight:700;color:#071018} QFrame#psBadgePlus QLabel{color:#071018}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPlainTextEdit,QTableWidget,QListWidget{background:#0a151f;border:1px solid #203b4f;border-radius:8px;padding:6px}
QComboBox{padding-right:32px}
QComboBox::drop-down{width:28px;border:0;border-left:1px solid #203b4f}
QComboBox::down-arrow{width:0;height:0}
QComboBox QAbstractItemView{background:#0d1924;border:1px solid #29475b;padding:4px;selection-background-color:#173c56;outline:0}
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus{border-color:#45aef0}
QTableWidget{gridline-color:#142a39;selection-background-color:#163e58;alternate-background-color:#09141e}
QTableWidget::item{padding:5px}
QHeaderView::section{background:#0d1b27;color:#9db0bf;padding:9px;border:0;border-bottom:1px solid #274457;font-weight:700}
QGroupBox{background:#0c1822;border:1px solid #1e394d;border-radius:12px;margin-top:13px;padding:14px;font-weight:750}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 7px;color:#dcebf5}
QProgressBar{background:#061018;border:1px solid #1a3548;border-radius:8px;text-align:center;min-height:18px;color:#f8fbff;font-size:11px;font-weight:800}
QProgressBar::chunk{background:#347cdf;border-radius:7px}
QProgressBar#visualProgress[progressKind="ps"]::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6d3fd8,stop:1 #b277ff)}
QProgressBar#visualProgress[progressKind="plus"]::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #b88416,stop:1 #ffe06a)}
QProgressBar#visualProgress[progressKind="role"]::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0f9673,stop:1 #2ce6ad)}
QProgressBar#visualProgress[progressKind="info"]::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2375d8,stop:1 #45c8ff)}
QProgressBar#visualProgress[progressLevel="early"]::chunk{background:#d64f62}
QProgressBar#visualProgress[progressLevel="low"]::chunk{background:#d69532}
QProgressBar#visualProgress[progressLevel="mid"]::chunk{background:#347cdf}
QProgressBar#visualProgress[progressLevel="high"]::chunk{background:#19a984}
QProgressBar#visualProgress[progressLevel="complete"]::chunk{background:#35c978}
QScrollArea{border:0;background:transparent}
QScrollBar:vertical{background:#07121a;width:11px} QScrollBar::handle:vertical{background:#294459;border-radius:5px;min-height:30px}
QTabWidget::pane{background:#09151f;border:1px solid #244256;border-radius:10px;top:-1px}
QTabBar::tab{background:#0c1924;color:#91a8b9;border:1px solid #244256;border-bottom:0;padding:10px 16px;min-width:92px;margin-right:3px;border-top-left-radius:8px;border-top-right-radius:8px}
QTabBar::tab:hover{background:#11283a;color:#ffffff}
QTabBar::tab:selected{background:#173c56;color:#ffffff;font-weight:750;border-color:#3684b8}
QTabBar::tab:!selected{margin-top:3px}
QToolTip{background:#142634;color:white;border:1px solid #37627e;padding:7px}
"""

LIGHT_DESKTOP_OVERRIDES = r"""
*{color:#182533}
QMainWindow,QWidget{background:#eef3f7}
QLabel{background:transparent}
QFrame#sidebar{background:#f8fafc;border-right:1px solid #c8d5df}
QFrame#card,QFrame#metricCard,QFrame#eventCard,QFrame#developmentLane{background:#ffffff;border:1px solid #cbd8e2}
QFrame#metricCard{border-top:2px solid #2f7bdc}
QFrame#heroCard{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ffffff,stop:.6 #f5f9fc,stop:1 #edf4f8);border:1px solid #b8ccd9}
QFrame#filterBar{background:#ffffff;border:1px solid #cad8e2}
QPushButton{background:#ffffff;border:1px solid #b9cbd8;color:#183044}
QPushButton:hover{background:#edf6fc;border-color:#6aa9cf}
QPushButton:disabled{background:#e9eef2;border-color:#d3dde4;color:#98a7b2}
QPushButton#nav{background:transparent;color:#526878}
QPushButton#nav:hover{background:#e8f2f8;color:#183044}
QPushButton#nav:checked{background:#dceef8;color:#16384f;border-left:3px solid #149ed1}
QLabel#brand,QLabel#pageTitle,QLabel#heroTitle,QLabel#metricValue,QLabel#sectionTitle{color:#102331}
QLabel#brandAccent,QLabel#accent{color:#057caa}
QLabel#muted{color:#667b89}
QLabel#ovrHero{color:#b07900}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPlainTextEdit,QTableWidget,QListWidget{background:#ffffff;border:1px solid #bdceda;color:#172a38}
QComboBox::drop-down{border-left:1px solid #bdceda}
QComboBox QAbstractItemView{background:#ffffff;border:1px solid #a9becd;color:#172a38;selection-background-color:#d7edf8}
QTableWidget{gridline-color:#d7e1e8;selection-background-color:#cde9f7;alternate-background-color:#f7fafc}
QHeaderView::section{background:#eaf1f5;color:#405868;border-bottom:1px solid #bfcfda}
QGroupBox{background:#ffffff;border:1px solid #c7d6e0;color:#183044}
QGroupBox::title{color:#243d4d}
QProgressBar{background:#edf2f5;border:1px solid #c4d2dc;color:#1c2e3a}
QScrollBar:vertical{background:#edf2f5} QScrollBar::handle:vertical{background:#afc2cf}
QTabWidget::pane{background:#ffffff;border:1px solid #bdced9}
QTabBar::tab{background:#e9f0f4;color:#5c7180;border-color:#bdced9}
QTabBar::tab:hover{background:#dcebf4;color:#1c394b}
QTabBar::tab:selected{background:#ffffff;color:#17374a;border-color:#69a8ca}
QToolTip{background:#ffffff;color:#172a38;border:1px solid #819baa}
"""

def normalize_theme(theme: str | None) -> str:
    return "light" if str(theme or "dark").lower() == "light" else "dark"

def tokens(theme: str | None = None) -> dict[str, str]:
    return THEME_TOKENS[normalize_theme(theme)]

def desktop_stylesheet(theme: str | None = None) -> str:
    return BASE_DESKTOP_STYLE + (LIGHT_DESKTOP_OVERRIDES if normalize_theme(theme) == "light" else "")

def overlay_stylesheet(theme: str | None = None) -> str:
    # Start with the desktop stylesheet so standard widgets, progress levels, chips,
    # badges, tabs, tables and tooltips use exactly the same rules. Overlay-only
    # selectors below only define its shell/brand presentation.
    t = tokens(theme)
    alpha_bg = "rgba(238,243,247,250)" if normalize_theme(theme) == "light" else "rgba(4,10,16,247)"
    top_bg = "#f8fafc" if normalize_theme(theme) == "light" else "#0b1b27"
    return desktop_stylesheet(theme) + f"""
QWidget#academyBrowserOverlay{{background:{alpha_bg};border:1px solid {t['border']};border-radius:18px}}
QFrame#overlayTop{{background:{top_bg};border-bottom:1px solid {t['border']};border-top-left-radius:18px;border-top-right-radius:18px}}
QLabel#overlayBrand{{font-size:19px;font-weight:900;color:{t['text_strong']}}}
QLabel#overlayMuted{{color:{t['muted']}}}
QFrame#overlayMetric{{background:{t['panel']};border:1px solid {t['border']};border-radius:12px}}
QLabel#overlayMetricValue{{font-size:27px;font-weight:900;color:{t['text_strong']}}}
QLabel#overlayPageTitle{{font-size:22px;font-weight:900;color:{t['text_strong']}}}
QLabel#overlayPlayerTitle{{font-size:25px;font-weight:900;color:{t['text_strong']}}}
"""

def semantic_colors(theme: str | None = None) -> dict[str, str]:
    t=tokens(theme)
    return {k:t[k] for k in ("ps","plus","role","info","good","warn","bad","muted")}

def toast_stylesheet(theme: str | None = None) -> str:
    t=tokens(theme)
    bg = "rgba(255,255,255,248)" if normalize_theme(theme) == "light" else "rgba(13,25,36,246)"
    return f"""
QFrame#overlayToastFrame{{background:{bg};border:1px solid {t['border']};border-radius:12px}}
QLabel{{background:transparent;color:{t['text']}}}
QLabel#overlayToastTitle{{font-size:14px;font-weight:800;color:{t['text_strong']}}}
QLabel#overlayToastBody{{color:{t['text']}}}
"""
