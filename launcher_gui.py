import sys
import os
import subprocess
import threading
import time
import json
import socket
import webbrowser
from pathlib import Path
from typing import Dict, Optional

import psutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QPlainTextEdit, QComboBox,
    QCheckBox, QScrollArea, QFrame, QSizePolicy, QToolTip, QMessageBox,
    QDialog, QLineEdit, QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QFileDialog, QInputDialog, QTabWidget, QListWidget, QListWidgetItem,
    QAbstractItemView, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QUrl, QSize, QRect
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QKeySequence, QShortcut,
    QPixmap, QPainter, QPen, QBrush
)
from projector_screen import NativeProjectorWindow, ProjectorWindow

# Root directory of the repository
ROOT_DIR = Path(__file__).resolve().parent

# Color Palette
COLOR_BG_DARK = "#090d16"
COLOR_CARD_BG = "#111723"
COLOR_CARD_BORDER = "#1f2a3d"
COLOR_CYAN = "#00ffcc"
COLOR_GOLD = "#ffd700"
COLOR_GREEN = "#2ed573"
COLOR_RED = "#ff4757"
COLOR_PURPLE = "#9b5de5"
COLOR_TEXT_MAIN = "#f0f6fc"
COLOR_TEXT_MUTED = "#8b949e"
COLOR_TERMINAL_BG = "#05080e"

SERVICES_CONFIG = [
    {
        "id": "master_admin",
        "name": "Master Admin Panel",
        "port": 8000,
        "module": "master_admin.main:app",
        "icon": "⚙️",
        "url": "http://localhost:8000/",
        "description": "Central Operations Hub, Tailscale mesh, player database, cashier & status"
    },
    {
        "id": "bison_dash",
        "name": "Bison Dash Arena Engine",
        "port": 8001,
        "module": "game_hub.games.bison_dash.main:app",
        "icon": "🦬",
        "url": "http://localhost:8001/projector",
        "description": "1080p Arena Projector track, procedural dice simulation engine & telemetry"
    },
    {
        "id": "bughunt",
        "name": "Bug Bounty: Alpha Critical",
        "port": 8003,
        "module": "games.bughunt_server:app",
        "icon": "🐛",
        "url": "http://localhost:8003/",
        "description": "Tactile Kids' Booth interface, 5:1 bug-to-token converter & attendant desk"
    },
    {
        "id": "n64",
        "name": "N64 Tournament Station",
        "port": 8004,
        "module": "games.n64_server:app",
        "icon": "🎮",
        "url": "http://localhost:8004/",
        "description": "N64 Retro Tourney payout deck & 1v1 match settlement"
    },
    {
        "id": "token_bank",
        "name": "Token Bank & Cashier Desk",
        "port": 8005,
        "module": "games.token_bank_server:app",
        "icon": "🪙",
        "url": "http://localhost:8005/",
        "description": "QR pass scanner, instant token injection & Techlahoma donations"
    },
    {
        "id": "gauntlet",
        "name": "The AI Gauntlet",
        "port": 8007,
        "module": "games.gauntlet_server:app",
        "icon": "⚡",
        "url": "http://localhost:8007/",
        "description": "Survival challenge station & token multipliers"
    },
    {
        "id": "kiosk_1",
        "name": "Betting Station 1 (Port 8008)",
        "port": 8008,
        "module": "games.kiosk_server:app",
        "icon": "🎰",
        "url": "http://localhost:8008/",
        "description": "Floor betting tablet Station 1: PIN auth, 6-bison odds & wager modal"
    },
    {
        "id": "kiosk_2",
        "name": "Betting Station 2 (Port 8012)",
        "port": 8012,
        "module": "games.kiosk_server:app",
        "icon": "📱",
        "url": "http://localhost:8012/",
        "description": "Floor betting tablet Station 2: PIN auth, 6-bison odds & wager modal"
    },
    {
        "id": "player_portal",
        "name": "Player Portal (Mobile Sign-Up & Balance)",
        "port": 8009,
        "module": "games.portal_server:app",
        "icon": "📱",
        "url": "http://localhost:8009/",
        "description": "Mobile phone sign-up & token balance lookup terminal with 4-digit PIN"
    },
    {
        "id": "slideshow",
        "name": "Stadium Slideshow Server (DJ Mac)",
        "port": 8010,
        "module": "games.slideshow_server:app",
        "icon": "📽️",
        "url": "http://localhost:8010/slideshow",
        "description": "1080p Arena Slideshow for DJ's Mac and Presentation Cut-In Display"
    },
    {
        "id": "presremote",
        "name": "PresRemote (Mobile Stage Clicker)",
        "port": 8011,
        "module": "games.presremote_server:app",
        "icon": "🎤",
        "url": "http://localhost:8011/",
        "description": "Dedicated standalone mobile presenter remote & PWA clicker (Stage Presentation Controller)"
    }
]

def get_lan_ip() -> str:
    """Finds the local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def find_pid_on_port(port: int) -> Optional[int]:
    """Finds any listening PID on the given port."""
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                return conn.pid
    except Exception:
        pass
    return None

def kill_process_tree(pid: int):
    """Forcefully kills a process and all its children."""
    if sys.platform == "win32":
        try:
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return
        except Exception:
            pass

    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except Exception:
        pass


class ServiceWorker(QObject):
    """Manages a single background server process with hidden terminal."""
    log_received = pyqtSignal(str, str) # service_id, log_line
    status_changed = pyqtSignal(str, bool, int) # service_id, is_running, pid

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.service_id = config["id"]
        self.port = config["port"]
        self.module = config["module"]
        self.process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_requested = False

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self):
        if self.is_running():
            return

        # Pre-check port conflict
        existing_pid = find_pid_on_port(self.port)
        if existing_pid:
            self.log_received.emit(
                self.service_id,
                f"[SYSTEM] Port {self.port} was occupied by PID {existing_pid}. Terminating conflicting process..."
            )
            kill_process_tree(existing_pid)
            time.sleep(0.5)

        cmd = [
            sys.executable, "-m", "uvicorn", self.module,
            "--port", str(self.port),
            "--host", "0.0.0.0"
        ]

        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "cwd": str(ROOT_DIR)
        }

        if sys.platform == "win32":
            # CREATE_NO_WINDOW completely hides any console window from popping up
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            self._stop_requested = False
            self.process = subprocess.Popen(cmd, **kwargs)
            self.status_changed.emit(self.service_id, True, self.process.pid)
            self.log_received.emit(
                self.service_id,
                f"[SYSTEM] Started {self.config['name']} on port {self.port} (PID: {self.process.pid})"
            )

            # Start thread to capture stdout/stderr
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
        except Exception as e:
            self.log_received.emit(self.service_id, f"[ERROR] Failed to start process: {e}")
            self.status_changed.emit(self.service_id, False, 0)

    def _read_output(self):
        proc = self.process
        if not proc or not proc.stdout:
            return

        while not self._stop_requested and proc.poll() is None:
            line = proc.stdout.readline()
            if line:
                self.log_received.emit(self.service_id, line.rstrip("\r\n"))
            else:
                break

        # Flush remaining
        try:
            if proc.stdout:
                for line in proc.stdout.readlines():
                    self.log_received.emit(self.service_id, line.rstrip("\r\n"))
        except Exception:
            pass

        pid = proc.pid if proc else 0
        self.process = None
        self.status_changed.emit(self.service_id, False, 0)
        self.log_received.emit(self.service_id, f"[SYSTEM] Process {self.service_id} (PID {pid}) stopped.")

    def stop(self):
        if not self.is_running():
            return
        self._stop_requested = True
        pid = self.process.pid
        self.log_received.emit(self.service_id, f"[SYSTEM] Stopping process PID {pid}...")
        kill_process_tree(pid)
        self.process = None
        self.status_changed.emit(self.service_id, False, 0)


class ServiceCardWidget(QFrame):
    """UI Card for each service: on/off toggle, info, browser link, and collapsible terminal output."""
    toggle_requested = pyqtSignal(str, bool) # service_id, requested_state

    def __init__(self, config: dict, worker: ServiceWorker, parent=None):
        super().__init__(parent)
        self.config = config
        self.worker = worker
        self.service_id = config["id"]
        self.line_count = 0
        self.auto_scroll = True

        self.setObjectName("serviceCard")
        self.setStyleSheet(f"""
            QFrame#serviceCard {{
                background-color: {COLOR_CARD_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 10px;
                padding: 10px;
            }}
        """)

        self._build_ui()

        # Connect worker signals
        self.worker.log_received.connect(self._on_log)
        self.worker.status_changed.connect(self._on_status)

    def _build_ui(self):
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        # --- Top Header Row ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Status LED
        self.status_led = QLabel("○")
        self.status_led.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.status_led.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        header_layout.addWidget(self.status_led)

        # Icon & Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_row = QHBoxLayout()
        title_label = QLabel(f"{self.config['icon']}  {self.config['name']}")
        title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        title_row.addWidget(title_label)

        # Port Badge
        port_badge = QLabel(f"Port {self.config['port']}")
        port_badge.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        port_badge.setStyleSheet(f"""
            background: rgba(0, 255, 204, 0.12);
            color: {COLOR_CYAN};
            border: 1px solid rgba(0, 255, 204, 0.3);
            border-radius: 4px;
            padding: 2px 6px;
        """)
        title_row.addWidget(port_badge)
        title_row.addStretch()

        title_box.addLayout(title_row)

        desc_label = QLabel(self.config["description"])
        desc_label.setFont(QFont("Segoe UI", 8))
        desc_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        title_box.addWidget(desc_label)

        header_layout.addLayout(title_box, stretch=1)

        # PID Pill
        self.pid_badge = QLabel("OFFLINE")
        self.pid_badge.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self.pid_badge.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            padding: 3px 8px;
        """)
        header_layout.addWidget(self.pid_badge)

        # Action: Open Browser
        self.btn_browser = QPushButton("🌐 Open")
        self.btn_browser.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browser.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {COLOR_CYAN};
                color: #000;
                border-color: {COLOR_CYAN};
            }}
        """)
        self.btn_browser.clicked.connect(self._open_in_browser)
        header_layout.addWidget(self.btn_browser)

        # Action: Copy URL
        btn_copy = QPushButton("📋")
        btn_copy.setToolTip(f"Copy URL: {self.config['url']}")
        btn_copy.setFont(QFont("Segoe UI", 9))
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 6px;
                padding: 6px 9px;
            }}
            QPushButton:hover {{
                background: #27354d;
            }}
        """)
        btn_copy.clicked.connect(self._copy_url)
        header_layout.addWidget(btn_copy)

        # Quick Builder Shortcut Buttons for Services
        if self.config["id"] == "player_portal":
            btn_email_card = QPushButton("✉️ Edit Email Text")
            btn_email_card.setToolTip("Edit the registration pass email subject, body text, and PIN template")
            btn_email_card.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_email_card.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_email_card.setStyleSheet(f"""
                QPushButton {{
                    background: #172233;
                    border: 1px solid {COLOR_CYAN};
                    color: {COLOR_CYAN};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
            """)
            btn_email_card.clicked.connect(lambda: EmailSettingsDialog(self.window()).exec())
            header_layout.addWidget(btn_email_card)

            btn_start_tokens = QPushButton("🪙 Starting Tokens")
            btn_start_tokens.setToolTip("Configure how many tokens new attendees receive upon registration (Default: 50)")
            btn_start_tokens.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_start_tokens.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_start_tokens.setStyleSheet(f"""
                QPushButton {{
                    background: #112822;
                    border: 1px solid {COLOR_CYAN};
                    color: {COLOR_CYAN};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
            """)
            btn_start_tokens.clicked.connect(lambda: RegistrationStartingBalanceDialog(self.window()).exec())
            header_layout.addWidget(btn_start_tokens)

        if self.config["id"] == "bison_dash":
            btn_bison_card = QPushButton("🦬 Edit Racers")
            btn_bison_card.setToolTip("Configure the 6 static racers, robot jockeys, and sector stats sliders")
            btn_bison_card.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_bison_card.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_bison_card.setStyleSheet(f"""
                QPushButton {{
                    background: #2b1f12;
                    border: 1px solid {COLOR_GOLD};
                    color: {COLOR_GOLD};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: {COLOR_GOLD}; color: #000; }}
            """)
            btn_bison_card.clicked.connect(lambda: BisonRacersDialog(self.window()).exec())
            header_layout.addWidget(btn_bison_card)

            btn_test_race = QPushButton("🏁 Test Race")
            btn_test_race.setToolTip("Launch live test race sprint on the 1080p arena projector")
            btn_test_race.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_test_race.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_test_race.setStyleSheet(f"""
                QPushButton {{
                    background: #0f2c24;
                    border: 1px solid {COLOR_CYAN};
                    color: {COLOR_CYAN};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
            """)
            btn_test_race.clicked.connect(lambda: trigger_bison_test_race(self.window()))
            header_layout.addWidget(btn_test_race)

        if self.config["id"] == "bughunt":
            btn_bughunt_settings = QPushButton("⏱️ Settings")
            btn_bughunt_settings.setToolTip("Configure Bug Bounty timer duration, bugs-per-token ratio, and token cost")
            btn_bughunt_settings.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_bughunt_settings.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_bughunt_settings.setStyleSheet(f"""
                QPushButton {{
                    background: #11261d;
                    border: 1px solid #00ff66;
                    color: #00ff66;
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: #00ff66; color: #000; }}
            """)
            btn_bughunt_settings.clicked.connect(lambda: EconomySettingsDialog(self.window()).exec())
            header_layout.addWidget(btn_bughunt_settings)

        if self.config["id"] == "token_bank":
            btn_mint_settings = QPushButton("🪙 Mint Rate")
            btn_mint_settings.setToolTip("Configure Dollar-to-Token exchange rate ($1 = X tokens) for the Token Mint")
            btn_mint_settings.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_mint_settings.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_mint_settings.setStyleSheet("""
                QPushButton {{
                    background: #252011;
                    border: 1px solid #ffd700;
                    color: #ffd700;
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: #ffd700; color: #000; }}
            """)
            btn_mint_settings.clicked.connect(lambda: TokenMintSettingsDialog(self.window()).exec())
            header_layout.addWidget(btn_mint_settings)

        if self.config["id"] == "slideshow":
            btn_deck = QPushButton("🖼️ Deck")
            btn_deck.setToolTip("Open Slideshow Builder Popup (Visual Drag & Drop)")
            btn_deck.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_deck.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_deck.setStyleSheet(f"""
                QPushButton {{
                    background: #112822;
                    border: 1px solid {COLOR_CYAN};
                    color: {COLOR_CYAN};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
            """)
            btn_deck.clicked.connect(lambda: SlideshowBuilderDialog(self.window()).exec())
            header_layout.addWidget(btn_deck)

            btn_pres = QPushButton("📢 Pres")
            btn_pres.setToolTip("Open Stage Presentation Builder Popup")
            btn_pres.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_pres.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_pres.setStyleSheet(f"""
                QPushButton {{
                    background: #2b1f12;
                    border: 1px solid #ffaa00;
                    color: #ffaa00;
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: #ffaa00; color: #000; }}
            """)
            btn_pres.clicked.connect(lambda: PresentationBuilderDialog(self.window()).exec())
            header_layout.addWidget(btn_pres)

            btn_logo = QPushButton("🦬 Logo")
            btn_logo.setToolTip("Upload Bison Logo PNG (100x100) for DJ Mac Slideshow")
            btn_logo.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn_logo.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_logo.setStyleSheet(f"""
                QPushButton {{
                    background: #2a2012;
                    border: 1px solid {COLOR_GOLD};
                    color: {COLOR_GOLD};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                QPushButton:hover {{ background: {COLOR_GOLD}; color: #000; }}
            """)
            btn_logo.clicked.connect(self._upload_slideshow_logo)
            header_layout.addWidget(btn_logo)

        # Action: Toggle Terminal Watching Box
        self.btn_toggle_terminal = QPushButton("▼ Terminal (0)")
        self.btn_toggle_terminal.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.btn_toggle_terminal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_terminal.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.12);
                color: #fff;
            }}
        """)
        self.btn_toggle_terminal.clicked.connect(self._toggle_terminal)
        header_layout.addWidget(self.btn_toggle_terminal)

        # ON/OFF Toggle Switch Button
        self.btn_switch = QPushButton("START")
        self.btn_switch.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_switch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch.setMinimumWidth(80)
        self.btn_switch.setStyleSheet(f"""
            QPushButton {{
                background-color: #21262d;
                border: 1px solid #30363d;
                color: #c9d1d9;
                border-radius: 6px;
                padding: 7px 14px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_GREEN};
                color: #000;
                border-color: {COLOR_GREEN};
            }}
        """)
        self.btn_switch.clicked.connect(self._on_switch_clicked)
        header_layout.addWidget(self.btn_switch)

        card_layout.addLayout(header_layout)

        # --- Collapsible Terminal Watching Box ---
        self.terminal_container = QWidget()
        self.terminal_container.setVisible(False) # Collapsed by default for space!
        term_vbox = QVBoxLayout(self.terminal_container)
        term_vbox.setContentsMargins(0, 6, 0, 0)
        term_vbox.setSpacing(4)

        # Terminal Controls Row
        term_ctrl_layout = QHBoxLayout()
        term_title = QLabel("🖥️ Terminal Output (Hidden from desktop, monitored here):")
        term_title.setFont(QFont("Segoe UI", 8))
        term_title.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        term_ctrl_layout.addWidget(term_title)
        term_ctrl_layout.addStretch()

        chk_autoscroll = QCheckBox("Auto-scroll")
        chk_autoscroll.setChecked(True)
        chk_autoscroll.setFont(QFont("Segoe UI", 8))
        chk_autoscroll.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        chk_autoscroll.toggled.connect(lambda val: setattr(self, "auto_scroll", val))
        term_ctrl_layout.addWidget(chk_autoscroll)

        btn_clear = QPushButton("Clear")
        btn_clear.setFont(QFont("Segoe UI", 8))
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: #192231;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{ color: #fff; background: #222e42; }}
        """)
        btn_clear.clicked.connect(self._clear_terminal)
        term_ctrl_layout.addWidget(btn_clear)

        term_vbox.addLayout(term_ctrl_layout)

        # Terminal Rectangle Box
        self.terminal_edit = QPlainTextEdit()
        self.terminal_edit.setReadOnly(True)
        self.terminal_edit.setFont(QFont("Consolas", 9))
        self.terminal_edit.setFixedHeight(140) # Compact rectangle watching box
        self.terminal_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLOR_TERMINAL_BG};
                color: #39d353;
                border: 1px solid #162030;
                border-radius: 6px;
                padding: 6px;
                selection-background-color: #264f78;
            }}
        """)
        term_vbox.addWidget(self.terminal_edit)

        card_layout.addWidget(self.terminal_container)

    def _toggle_terminal(self):
        is_visible = self.terminal_container.isVisible()
        self.terminal_container.setVisible(not is_visible)
        if not is_visible:
            self.btn_toggle_terminal.setText(f"▲ Terminal ({self.line_count})")
        else:
            self.btn_toggle_terminal.setText(f"▼ Terminal ({self.line_count})")

    def _clear_terminal(self):
        self.terminal_edit.clear()
        self.line_count = 0
        if not self.terminal_container.isVisible():
            self.btn_toggle_terminal.setText("▼ Terminal (0)")
        else:
            self.btn_toggle_terminal.setText("▲ Terminal (0)")

    def _on_switch_clicked(self):
        if self.worker.is_running():
            self.worker.stop()
        else:
            self.worker.start()

    def _open_in_browser(self):
        url = self.config["url"]
        webbrowser.open(url)

    def _copy_url(self):
        url = self.config["url"]
        lan_ip = get_lan_ip()
        if "localhost" in url and lan_ip != "127.0.0.1":
            url = url.replace("localhost", lan_ip)
        clipboard = QApplication.clipboard()
        clipboard.setText(url)
        QToolTip.showText(self.btn_browser.mapToGlobal(self.btn_browser.rect().center()), f"URL Copied:\n{url}")

    def _upload_slideshow_logo(self):
        import master_admin.data_manager as dm
        fp, _ = QFileDialog.getOpenFileName(
            self,
            "Select Bison Logo PNG to Upload (Auto Formatted to 100x100)",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not fp:
            return
        try:
            with open(fp, "rb") as f:
                content = f.read()
            dm.save_custom_logo(content, Path(fp).name)
            QMessageBox.information(
                self,
                "Logo Uploaded",
                "Successfully uploaded & formatted Bison Logo to 100x100 PNG!\n"
                "The stadium projector on the DJ's screen has updated live."
            )
        except Exception as e:
            QMessageBox.critical(self, "Upload Failed", f"Failed to upload logo: {e}")

    def _on_log(self, svc_id: str, line: str):
        if svc_id != self.service_id:
            return
        self.line_count += 1
        self.terminal_edit.appendPlainText(line)
        if self.auto_scroll:
            self.terminal_edit.verticalScrollBar().setValue(
                self.terminal_edit.verticalScrollBar().maximum()
            )
        prefix = "▲" if self.terminal_container.isVisible() else "▼"
        self.btn_toggle_terminal.setText(f"{prefix} Terminal ({self.line_count})")

    def _on_status(self, svc_id: str, is_running: bool, pid: int):
        if svc_id != self.service_id:
            return
        if is_running:
            self.status_led.setText("●")
            self.status_led.setStyleSheet(f"color: {COLOR_GREEN};")
            self.pid_badge.setText(f"PID: {pid}")
            self.pid_badge.setStyleSheet(f"""
                color: {COLOR_GREEN};
                background: rgba(46, 213, 115, 0.12);
                border: 1px solid rgba(46, 213, 115, 0.3);
                border-radius: 4px;
                padding: 3px 8px;
            """)
            self.btn_switch.setText("STOP")
            self.btn_switch.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_RED};
                    border: 1px solid {COLOR_RED};
                    color: #ffffff;
                    border-radius: 6px;
                    padding: 7px 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #ff6b81;
                }}
            """)
        else:
            self.status_led.setText("○")
            self.status_led.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
            self.pid_badge.setText("OFFLINE")
            self.pid_badge.setStyleSheet(f"""
                color: {COLOR_TEXT_MUTED};
                background: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                padding: 3px 8px;
            """)
            self.btn_switch.setText("START")
            self.btn_switch.setStyleSheet(f"""
                QPushButton {{
                    background-color: #21262d;
                    border: 1px solid #30363d;
                    color: #c9d1d9;
                    border-radius: 6px;
                    padding: 7px 14px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_GREEN};
                    color: #000;
                    border-color: {COLOR_GREEN};
                }}
            """)


# ProjectorWindow is provided natively by projector_screen.NativeProjectorWindow


class EmailSettingsDialog(QDialog):
    """Dialog to configure SMTP settings for sending pass & notification emails."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Email & SMTP Configuration - Techlahoma BBGN")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
                font-size: 11px;
            }}
            QLineEdit, QSpinBox {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 8px 10px;
                color: #ffffff;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {COLOR_CYAN};
            }}
            QCheckBox {{
                color: {COLOR_TEXT_MAIN};
                font-size: 12px;
                spacing: 8px;
            }}
            QGroupBox {{
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: {COLOR_CYAN};
            }}
        """)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        lbl_head = QLabel("✉️ Registration Pass Email & SMTP Setup")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_CYAN};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Customize the attendee registration pass email text, dynamic token placeholders ({name}, {pin}, {balance}), and optional SMTP server credentials.")
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # 1. Email Message Template Box (PROMINENT AT TOP)
        tmpl_box = QGroupBox("1. Attendee Pass Email Message (Registration Text)")
        tmpl_layout = QVBoxLayout(tmpl_box)
        tmpl_layout.setSpacing(8)

        lbl_tokens = QLabel("Dynamic Placeholders (auto-injected): {name} = Attendee Name, {pin} = 4-Digit PIN, {balance} = Starting Tokens")
        lbl_tokens.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 11px; font-weight: bold;")
        tmpl_layout.addWidget(lbl_tokens)

        lbl_subj = QLabel("Email Subject:")
        lbl_subj.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-size: 11px; font-weight: bold;")
        tmpl_layout.addWidget(lbl_subj)

        self.txt_subject = QLineEdit()
        self.txt_subject.setPlaceholderText("Your Bison Bash Player Pass & 4-Digit PIN")
        tmpl_layout.addWidget(self.txt_subject)

        lbl_body = QLabel("Email Message Body:")
        lbl_body.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-size: 11px; font-weight: bold;")
        tmpl_layout.addWidget(lbl_body)

        self.txt_body = QPlainTextEdit()
        self.txt_body.setPlaceholderText("Enter email message body...\n\nExample:\nHi {name},\nWelcome to the Techlahoma Bison Bash!\nYour attendee PIN is: {pin}\nStarting token balance: {balance} tokens\nHave fun!")
        self.txt_body.setMinimumHeight(130)
        self.txt_body.setMaximumHeight(180)
        tmpl_layout.addWidget(self.txt_body)

        layout.addWidget(tmpl_box)

        # 2. SMTP Outbound Server Settings Box
        smtp_box = QGroupBox("2. SMTP Outbound Dispatch Server (Optional)")
        smtp_layout = QVBoxLayout(smtp_box)
        smtp_layout.setSpacing(10)

        self.chk_enabled = QCheckBox("Enable Outbound Pass Emails Upon Player Registration")
        self.chk_enabled.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        smtp_layout.addWidget(self.chk_enabled)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("smtp.gmail.com")
        form.addRow("SMTP Server:", self.txt_host)

        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(587)
        form.addRow("Port:", self.spn_port)

        sec_layout = QHBoxLayout()
        self.chk_tls = QCheckBox("Use TLS (STARTTLS - default for 587)")
        self.chk_ssl = QCheckBox("Use SSL (Port 465)")
        sec_layout.addWidget(self.chk_tls)
        sec_layout.addWidget(self.chk_ssl)
        form.addRow("Security:", sec_layout)

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("your-email@gmail.com")
        form.addRow("Username / Email:", self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("App Password or SMTP API Key")
        form.addRow("Password / Key:", self.txt_password)

        self.txt_from_name = QLineEdit()
        self.txt_from_name.setPlaceholderText("Techlahoma Bison Bash")
        form.addRow("Sender Name:", self.txt_from_name)

        self.txt_from_email = QLineEdit()
        self.txt_from_email.setPlaceholderText("no-reply@techlahoma.org (optional, defaults to username)")
        form.addRow("Sender Email:", self.txt_from_email)

        smtp_layout.addLayout(form)
        layout.addWidget(smtp_box)

        # Test Box
        test_box = QGroupBox("Send Test Verification Email")
        test_layout = QHBoxLayout(test_box)
        self.txt_test_to = QLineEdit()
        self.txt_test_to.setPlaceholderText("Enter recipient email to test...")
        btn_send_test = QPushButton("Send Test")
        btn_send_test.setStyleSheet(f"""
            QPushButton {{
                background: #1f2a3d;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_send_test.clicked.connect(self._send_test)
        test_layout.addWidget(self.txt_test_to)
        test_layout.addWidget(btn_send_test)
        layout.addWidget(test_box)

        # Status Label
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; padding: 8px 18px; color: #c9d1d9;
            }
            QPushButton:hover { background: #30363d; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Settings")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_CYAN}; border: none;
                border-radius: 6px; padding: 8px 24px; color: #000; font-weight: bold;
            }}
            QPushButton:hover {{ background: #26e6ba; }}
        """)
        btn_save.clicked.connect(self._save_and_close)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _load_values(self):
        try:
            import master_admin.email_manager as em
            cfg = em.load_email_config()
            self.chk_enabled.setChecked(cfg.get("enabled", False))
            self.txt_host.setText(cfg.get("smtp_host", "smtp.gmail.com"))
            self.spn_port.setValue(int(cfg.get("smtp_port", 587)))
            self.chk_tls.setChecked(cfg.get("use_tls", True))
            self.chk_ssl.setChecked(cfg.get("use_ssl", False))
            self.txt_username.setText(cfg.get("username", ""))
            self.txt_password.setText(cfg.get("password", ""))
            self.txt_from_name.setText(cfg.get("from_name", "Techlahoma Bison Bash"))
            self.txt_from_email.setText(cfg.get("from_email", ""))
            self.txt_subject.setText(cfg.get("subject_template", em.DEFAULT_CONFIG.get("subject_template", "Your Bison Bash Player Pass & 4-Digit PIN")))
            self.txt_body.setPlainText(cfg.get("body_template", em.DEFAULT_CONFIG.get("body_template", "")))
        except Exception:
            pass

    def _collect_config(self) -> dict:
        import master_admin.email_manager as em
        cfg = em.load_email_config()
        cfg.update({
            "enabled": self.chk_enabled.isChecked(),
            "smtp_host": self.txt_host.text().strip(),
            "smtp_port": self.spn_port.value(),
            "use_tls": self.chk_tls.isChecked(),
            "use_ssl": self.chk_ssl.isChecked(),
            "username": self.txt_username.text().strip(),
            "password": self.txt_password.text().strip(),
            "from_name": self.txt_from_name.text().strip(),
            "from_email": self.txt_from_email.text().strip() or self.txt_username.text().strip(),
            "subject_template": self.txt_subject.text().strip(),
            "body_template": self.txt_body.toPlainText()
        })
        return cfg

    def _send_test(self):
        to_email = self.txt_test_to.text().strip()
        if not to_email:
            self.lbl_status.setText("⚠️ Please enter a recipient email address for testing.")
            self.lbl_status.setStyleSheet("color: #ffa502;")
            return

        cfg = self._collect_config()
        self.lbl_status.setText("⏳ Connecting to SMTP server and sending test email...")
        self.lbl_status.setStyleSheet(f"color: {COLOR_CYAN};")
        QApplication.processEvents()

        import master_admin.email_manager as em
        success, msg = em.send_test_email(to_email, cfg)
        if success:
            self.lbl_status.setText(f"✅ Success: Test email delivered to {to_email}!")
            self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN};")
            self.chk_enabled.setChecked(True)
        else:
            self.lbl_status.setText(f"❌ Failed: {msg}")
            self.lbl_status.setStyleSheet(f"color: {COLOR_RED};")

    def _save_and_close(self):
        import master_admin.email_manager as em
        cfg = self._collect_config()
        em.save_email_config(cfg)
        QMessageBox.information(self, "Saved", "Email configuration saved successfully.")
        self.accept()


class RegistrationStartingBalanceDialog(QDialog):
    """Dialog to adjust Starting Token Balance given to attendees upon registration."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🪙 Registration Starting Balance - Techlahoma BBGN")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
                font-size: 11px;
            }}
            QSpinBox {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 8px 10px;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }}
            QSpinBox:focus {{
                border-color: {COLOR_CYAN};
            }}
            QGroupBox {{
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding: 14px 12px 12px 12px;
                font-weight: bold;
                color: {COLOR_CYAN};
            }}
        """)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_head = QLabel("🪙 Attendee Starting Balance Setup")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_CYAN};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Configure how many starting tokens each new attendee automatically receives "
            "when signing up at the Mobile Registration Portal (Port 8009). Default is 50 tokens."
        )
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        grp_allot = QGroupBox("Registration Pass Allotment")
        a_form = QFormLayout(grp_allot)
        a_form.setSpacing(10)

        self.spn_allotment = QSpinBox()
        self.spn_allotment.setRange(0, 10000)
        self.spn_allotment.setValue(50)
        self.spn_allotment.setSuffix(" Tokens / Credits")
        a_form.addRow("Starting Token Balance:", self.spn_allotment)
        layout.addWidget(grp_allot)

        lbl_note = QLabel(
            "ℹ️ This amount will immediately appear in the attendee's wallet upon registration, "
            "and will be injected into their confirmation email placeholder ({balance})."
        )
        lbl_note.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 11px;")
        lbl_note.setWordWrap(True)
        layout.addWidget(lbl_note)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; padding: 8px 18px; color: #c9d1d9;
            }
            QPushButton:hover { background: #30363d; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save Starting Balance")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_CYAN}; border: none;
                border-radius: 6px; padding: 8px 24px; color: #000; font-weight: bold;
            }}
            QPushButton:hover {{ background: #55ffdd; }}
        """)
        btn_save.clicked.connect(self._save_and_close)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _load_values(self):
        try:
            import master_admin.data_manager as dm
            cfg = dm.get_economy_config()
            self.spn_allotment.setValue(int(cfg.get("initial_allotment", 50)))
        except Exception:
            self.spn_allotment.setValue(50)

    def _save_and_close(self):
        try:
            import master_admin.data_manager as dm
            cfg = dm.get_economy_config()
            cfg["initial_allotment"] = self.spn_allotment.value()
            dm.save_economy_config(cfg)
            QMessageBox.information(
                self, "Starting Balance Saved",
                f"🪙 Registration starting balance saved!\n\nNew attendees will start with {self.spn_allotment.value()} Tokens."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save starting balance: {e}")


class TokenMintSettingsDialog(QDialog):
    """Dialog to adjust Dollar-to-Token exchange rate for the Token Mint / Cash Desk."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🪙 Token Mint & Cash Desk Exchange Rate - Techlahoma BBGN")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
                font-size: 11px;
            }}
            QSpinBox {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 8px 10px;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }}
            QSpinBox:focus {{
                border-color: #ffd700;
            }}
            QGroupBox {{
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding: 14px 12px 12px 12px;
                font-weight: bold;
                color: #ffd700;
            }}
        """)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_head = QLabel("🪙 Token Mint Rate Configuration")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet("color: #ffd700;")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Configure how many game tokens attendees receive for each US Dollar ($1.00) donated "
            "at the Token Bank & Cashier Desk (Port 8005). Default is 5 tokens per $1.00."
        )
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        grp_rate = QGroupBox("Exchange Rate")
        r_form = QFormLayout(grp_rate)
        r_form.setSpacing(10)

        self.spn_rate = QSpinBox()
        self.spn_rate.setRange(1, 500)
        self.spn_rate.setValue(5)
        self.spn_rate.setSuffix(" Tokens per $1.00 USD")
        self.spn_rate.valueChanged.connect(self._update_preview)
        r_form.addRow("Dollar to Token Rate:", self.spn_rate)
        layout.addWidget(grp_rate)

        # Quick Preview Box
        grp_preview = QGroupBox("Donation Preset Previews")
        prev_layout = QVBoxLayout(grp_preview)
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-size: 12px; line-height: 1.6;")
        prev_layout.addWidget(self.lbl_preview)
        layout.addWidget(grp_preview)

        self._update_preview(self.spn_rate.value())

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; padding: 8px 18px; color: #c9d1d9;
            }
            QPushButton:hover { background: #30363d; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save Mint Rate")
        btn_save.setStyleSheet("""
            QPushButton {
                background: #ffd700; border: none;
                border-radius: 6px; padding: 8px 24px; color: #000; font-weight: bold;
            }
            QPushButton:hover { background: #ffe44d; }
        """)
        btn_save.clicked.connect(self._save_and_close)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _update_preview(self, val):
        self.lbl_preview.setText(
            f"• $1.00 donation  ➔  <b>{val * 1}</b> Tokens<br>"
            f"• $5.00 donation  ➔  <b>{val * 5}</b> Tokens<br>"
            f"• $10.00 donation ➔  <b>{val * 10}</b> Tokens<br>"
            f"• $20.00 donation ➔  <b>{val * 20}</b> Tokens<br>"
            f"• $50.00 donation ➔  <b>{val * 50}</b> Tokens<br>"
            f"• $100.00 donation ➔  <b>{val * 100}</b> Tokens"
        )

    def _load_values(self):
        try:
            import master_admin.data_manager as dm
            cfg = dm.get_economy_config()
            self.spn_rate.setValue(int(cfg.get("tokens_per_dollar", 5)))
        except Exception:
            self.spn_rate.setValue(5)

    def _save_and_close(self):
        try:
            import master_admin.data_manager as dm
            cfg = dm.get_economy_config()
            cfg["tokens_per_dollar"] = self.spn_rate.value()
            dm.save_economy_config(cfg)
            QMessageBox.information(
                self, "Mint Rate Saved",
                f"🪙 Token Mint exchange rate saved!\n\n$1.00 USD = {self.spn_rate.value()} Tokens\nLive across all cash desks."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save mint rate: {e}")


class EconomySettingsDialog(QDialog):
    """Dialog to adjust station play costs, game payouts, and initial player allotment."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🪙 Economy, Costs & Payouts - Techlahoma BBGN")
        self.setMinimumWidth(720)
        self.setMinimumHeight(640)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
                font-size: 11px;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {COLOR_CYAN};
            }}
            QGroupBox {{
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding: 14px 12px 12px 12px;
                font-weight: bold;
                color: {COLOR_GOLD};
                font-size: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
        """)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Header
        lbl_head = QLabel("🪙 Event Economy, Play Costs & Payouts")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_GOLD};")
        main_layout.addWidget(lbl_head)

        lbl_desc = QLabel("Adjust station entry fees, game multipliers, and starting wallet allotments. Changes save instantly across all active stations with zero server restarts required.")
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        lbl_desc.setWordWrap(True)
        main_layout.addWidget(lbl_desc)

        # Scroll Area for clean layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(14)
        c_layout.setContentsMargins(4, 4, 12, 4)

        # 1. Player Portal & Starting Allotment
        grp_portal = QGroupBox("1. Player Portal & Initial Allotment")
        portal_form = QFormLayout(grp_portal)
        portal_form.setSpacing(8)
        self.spn_initial_allotment = QSpinBox()
        self.spn_initial_allotment.setRange(0, 10000)
        self.spn_initial_allotment.setSuffix(" Credits")
        lbl_allot_info = QLabel("Granted immediately upon registration or pass lookup on the Mobile Portal (Port 8009).")
        lbl_allot_info.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 10px;")
        portal_form.addRow("Starting Token Pass:", self.spn_initial_allotment)
        portal_form.addRow("", lbl_allot_info)
        c_layout.addWidget(grp_portal)

        # 2. Station Entry Fees (Play Costs)
        grp_costs = QGroupBox("2. Station Play Costs / Entry Fees (0 = Free-to-Play)")
        cost_form = QFormLayout(grp_costs)
        cost_form.setSpacing(8)

        self.spn_cost_n64 = QSpinBox()
        self.spn_cost_n64.setRange(0, 1000)
        self.spn_cost_n64.setSuffix(" Credits")
        cost_form.addRow("N64 Retro Tourney (Per Match Entry):", self.spn_cost_n64)

        self.spn_cost_bughunt = QSpinBox()
        self.spn_cost_bughunt.setRange(0, 1000)
        self.spn_cost_bughunt.setSuffix(" Credits")
        cost_form.addRow("Bug Bounty Hunt (Per 60s Session):", self.spn_cost_bughunt)

        self.spn_cost_gauntlet = QSpinBox()
        self.spn_cost_gauntlet.setRange(0, 1000)
        self.spn_cost_gauntlet.setSuffix(" Credits")
        cost_form.addRow("The AI Gauntlet (Per Door Run):", self.spn_cost_gauntlet)

        self.spn_cost_bison_min_bet = QSpinBox()
        self.spn_cost_bison_min_bet.setRange(1, 1000)
        self.spn_cost_bison_min_bet.setSuffix(" Credits")
        cost_form.addRow("Bison Dash Kiosk (Minimum Bet):", self.spn_cost_bison_min_bet)

        c_layout.addWidget(grp_costs)

        # 3. Game Payouts & Multipliers
        grp_payouts = QGroupBox("3. Game Payouts & Multipliers")
        payout_layout = QVBoxLayout(grp_payouts)
        payout_layout.setSpacing(10)

        p_form = QFormLayout()
        p_form.setSpacing(8)

        self.spn_payout_n64 = QSpinBox()
        self.spn_payout_n64.setRange(0, 1000)
        self.spn_payout_n64.setSuffix(" Credits")
        p_form.addRow("N64 Winner Prize:", self.spn_payout_n64)

        self.spn_payout_bison_mult = QDoubleSpinBox()
        self.spn_payout_bison_mult.setRange(1.0, 50.0)
        self.spn_payout_bison_mult.setSingleStep(0.1)
        self.spn_payout_bison_mult.setDecimals(1)
        self.spn_payout_bison_mult.setSuffix("x")
        p_form.addRow("Bison Dash Win Multiplier:", self.spn_payout_bison_mult)

        self.spn_payout_bughunt_ratio = QSpinBox()
        self.spn_payout_bughunt_ratio.setRange(1, 50)
        self.spn_payout_bughunt_ratio.setSuffix(" Bugs per 1 Token")
        p_form.addRow("Bug Bounty Ratio:", self.spn_payout_bughunt_ratio)

        self.spn_payout_bughunt_pity = QSpinBox()
        self.spn_payout_bughunt_pity.setRange(0, 50)
        self.spn_payout_bughunt_pity.setSuffix(" Credits")
        p_form.addRow("Bug Bounty Toddler Pity Credit:", self.spn_payout_bughunt_pity)

        self.spn_bughunt_timer = QSpinBox()
        self.spn_bughunt_timer.setRange(10, 600)
        self.spn_bughunt_timer.setSingleStep(5)
        self.spn_bughunt_timer.setSuffix(" Seconds")
        p_form.addRow("Bug Bounty Hunt Timer Duration:", self.spn_bughunt_timer)

        payout_layout.addLayout(p_form)

        # AI Gauntlet Stages
        lbl_gaunt = QLabel("AI Gauntlet Level Payouts:")
        lbl_gaunt.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_gaunt.setStyleSheet(f"color: {COLOR_CYAN}; margin-top: 6px;")
        payout_layout.addWidget(lbl_gaunt)

        g_grid = QHBoxLayout()
        self.spn_gauntlet_s1 = QSpinBox(); self.spn_gauntlet_s1.setRange(0, 500); self.spn_gauntlet_s1.setPrefix("S1: +")
        self.spn_gauntlet_s2 = QSpinBox(); self.spn_gauntlet_s2.setRange(0, 500); self.spn_gauntlet_s2.setPrefix("S2: +")
        self.spn_gauntlet_s3 = QSpinBox(); self.spn_gauntlet_s3.setRange(0, 500); self.spn_gauntlet_s3.setPrefix("S3: +")
        self.spn_gauntlet_s4 = QSpinBox(); self.spn_gauntlet_s4.setRange(0, 500); self.spn_gauntlet_s4.setPrefix("S4: +")
        self.spn_gauntlet_jackpot = QSpinBox(); self.spn_gauntlet_jackpot.setRange(0, 1000); self.spn_gauntlet_jackpot.setPrefix("Jackpot: +")
        self.spn_gauntlet_runner_up = QSpinBox(); self.spn_gauntlet_runner_up.setRange(0, 500); self.spn_gauntlet_runner_up.setPrefix("Runner-Up: +")

        g_grid.addWidget(self.spn_gauntlet_s1)
        g_grid.addWidget(self.spn_gauntlet_s2)
        g_grid.addWidget(self.spn_gauntlet_s3)
        g_grid.addWidget(self.spn_gauntlet_s4)
        g_grid.addWidget(self.spn_gauntlet_jackpot)
        g_grid.addWidget(self.spn_gauntlet_runner_up)
        payout_layout.addLayout(g_grid)

        c_layout.addWidget(grp_payouts)

        # 4. Token Mint & Cash Desk Exchange Rate
        grp_mint = QGroupBox("4. Token Mint & Cash Desk ($1 = Tokens Exchange Rate)")
        mint_form = QFormLayout(grp_mint)
        mint_form.setSpacing(8)

        self.spn_tokens_per_dollar = QSpinBox()
        self.spn_tokens_per_dollar.setRange(1, 500)
        self.spn_tokens_per_dollar.setValue(5)
        self.spn_tokens_per_dollar.setSuffix(" Tokens per $1.00 USD")
        mint_form.addRow("Dollar to Token Rate:", self.spn_tokens_per_dollar)

        lbl_mint_desc = QLabel("Attendees donating cash receive this exchange rate (e.g. $1=5 tokens, $5=25 tokens, $20=100 tokens). Default is 5.")
        lbl_mint_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 10px;")
        mint_form.addRow("", lbl_mint_desc)

        c_layout.addWidget(grp_mint)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Bottom Button Bar
        btn_bar = QHBoxLayout()
        btn_reset = QPushButton("↺ Reset to Defaults")
        btn_reset.setStyleSheet("""
            QPushButton {
                background: #2a1616; border: 1px solid #ff4757;
                border-radius: 6px; padding: 8px 16px; color: #ff6b81; font-weight: bold;
            }
            QPushButton:hover { background: #ff4757; color: #fff; }
        """)
        btn_reset.clicked.connect(self._reset_defaults)
        btn_bar.addWidget(btn_reset)

        btn_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; padding: 8px 18px; color: #c9d1d9;
            }
            QPushButton:hover { background: #30363d; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        btn_save = QPushButton("Save Economy Rules")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_GOLD}; border: none;
                border-radius: 6px; padding: 8px 24px; color: #000; font-weight: bold;
            }}
            QPushButton:hover {{ background: #ffea70; }}
        """)
        btn_save.clicked.connect(self._save_and_close)
        btn_bar.addWidget(btn_save)

        main_layout.addLayout(btn_bar)

    def _load_values(self):
        import master_admin.data_manager as dm
        cfg = dm.get_economy_config()
        self.spn_initial_allotment.setValue(int(cfg.get("initial_allotment", 50)))

        costs = cfg.get("costs", {})
        self.spn_cost_n64.setValue(int(costs.get("n64", 0)))
        self.spn_cost_bughunt.setValue(int(costs.get("bughunt", 0)))
        self.spn_cost_gauntlet.setValue(int(costs.get("gauntlet", 4)))
        self.spn_cost_bison_min_bet.setValue(int(costs.get("bison_dash_min_bet", 5)))

        payouts = cfg.get("payouts", {})
        self.spn_payout_n64.setValue(int(payouts.get("n64_winner", 8)))
        self.spn_payout_bison_mult.setValue(float(payouts.get("bison_dash_multiplier", 2.0)))
        self.spn_payout_bughunt_ratio.setValue(int(payouts.get("bughunt_bugs_per_token", 3)))
        self.spn_payout_bughunt_pity.setValue(int(payouts.get("bughunt_pity_tokens", 0)))

        timers = cfg.get("timers", {})
        self.spn_bughunt_timer.setValue(int(timers.get("bughunt_duration", cfg.get("bughunt_timer_seconds", 60))))

        self.spn_tokens_per_dollar.setValue(int(cfg.get("tokens_per_dollar", 5)))

        gaunt = payouts.get("gauntlet", {})
        self.spn_gauntlet_s1.setValue(int(gaunt.get("stage1", 2)))
        self.spn_gauntlet_s2.setValue(int(gaunt.get("stage2", 3)))
        self.spn_gauntlet_s3.setValue(int(gaunt.get("stage3", 5)))
        self.spn_gauntlet_s4.setValue(int(gaunt.get("stage4", 8)))
        self.spn_gauntlet_jackpot.setValue(int(gaunt.get("vault_jackpot", 25)))
        self.spn_gauntlet_runner_up.setValue(int(gaunt.get("vault_runner_up", 10)))

    def _reset_defaults(self):
        import master_admin.data_manager as dm
        reply = QMessageBox.question(
            self,
            "Reset Economy Defaults",
            "Are you sure you want to restore all payouts and costs to their factory defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            dm.save_economy_config(dm.DEFAULT_ECONOMY_CONFIG)
            self._load_values()
            QMessageBox.information(self, "Defaults Restored", "Default economy configuration restored!")

    def _save_and_close(self):
        import master_admin.data_manager as dm
        cfg = {
            "initial_allotment": self.spn_initial_allotment.value(),
            "costs": {
                "n64": self.spn_cost_n64.value(),
                "bughunt": self.spn_cost_bughunt.value(),
                "gauntlet": self.spn_cost_gauntlet.value(),
                "bison_dash_min_bet": self.spn_cost_bison_min_bet.value()
            },
            "payouts": {
                "n64_winner": self.spn_payout_n64.value(),
                "bughunt_bugs_per_token": self.spn_payout_bughunt_ratio.value(),
                "bughunt_pity_tokens": self.spn_payout_bughunt_pity.value(),
                "gauntlet": {
                    "stage1": self.spn_gauntlet_s1.value(),
                    "stage2": self.spn_gauntlet_s2.value(),
                    "stage3": self.spn_gauntlet_s3.value(),
                    "stage4": self.spn_gauntlet_s4.value(),
                    "vault_jackpot": self.spn_gauntlet_jackpot.value(),
                    "vault_runner_up": self.spn_gauntlet_runner_up.value()
                },
                "bison_dash_multiplier": round(self.spn_payout_bison_mult.value(), 2)
            },
            "timers": {
                "bughunt_duration": self.spn_bughunt_timer.value()
            },
            "tokens_per_dollar": self.spn_tokens_per_dollar.value()
        }
        dm.save_economy_config(cfg)
        QMessageBox.information(self, "Economy Saved", "✓ Economy configuration saved!\nChanges are live across all stations.")
        self.accept()


def trigger_bison_test_race(parent_window=None):
    """Starts Bison Dash if offline, triggers /api/bisondash/test_race, and opens /projector in browser."""
    import urllib.request
    import webbrowser

    # Ensure port 8001 is listening
    pid = find_pid_on_port(8001)
    if not pid:
        if parent_window and hasattr(parent_window, "workers") and "bison_dash" in parent_window.workers:
            parent_window.workers["bison_dash"].start()
        else:
            cmd = [
                sys.executable, "-m", "uvicorn", "game_hub.games.bison_dash.main:app",
                "--port", "8001", "--host", "0.0.0.0"
            ]
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(cmd, cwd=str(ROOT_DIR), creationflags=flags)
        time.sleep(1.2)

    # Trigger test race sprint endpoint
    try:
        req = urllib.request.Request(
            "http://localhost:8001/api/bisondash/test_race",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=3.0)
    except Exception as e:
        print(f"[Bison Dash Test Race] Notice calling test race endpoint: {e}")

    # Open projector view in default browser
    webbrowser.open("http://localhost:8001/projector")


class BisonRacersDialog(QDialog):
    """Dialog to inspect and manually adjust stats and details for the 6 static Bison Dash racers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🦬 Bison Dash - Static Racers & Stats Editor")
        self.setMinimumWidth(840)
        self.setMinimumHeight(660)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
                font-size: 11px;
            }}
            QLineEdit, QSpinBox {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {COLOR_CYAN};
            }}
            QTabWidget::pane {{
                border: 1px solid {COLOR_CARD_BORDER};
                background: {COLOR_CARD_BG};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: #141c2b;
                color: {COLOR_TEXT_MUTED};
                padding: 10px 18px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: {COLOR_CARD_BG};
                color: {COLOR_CYAN};
                border: 1px solid {COLOR_CARD_BORDER};
                border-bottom: none;
            }}
            QGroupBox {{
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding: 14px 12px 12px 12px;
                font-weight: bold;
                color: {COLOR_GOLD};
                font-size: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #1f2a3d;
                height: 8px;
                background: #0d131f;
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLOR_CYAN};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 1px solid #1f2a3d;
                width: 18px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {COLOR_GOLD};
            }}
        """)
        self.racer_editors = []
        self._build_ui()
        self._load_racers()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Title Header
        hdr_layout = QHBoxLayout()
        vbox_title = QVBoxLayout()
        vbox_title.setSpacing(2)
        lbl_h = QLabel("🦬 Static Bison Dash Racers (Slots 1–6)")
        lbl_h.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_h.setStyleSheet("color: #ffffff;")
        vbox_title.addWidget(lbl_h)

        lbl_sub = QLabel("Configure racer names, colors, and sector performance sliders for the arena races.")
        lbl_sub.setFont(QFont("Segoe UI", 9))
        lbl_sub.setStyleSheet(f"color: {COLOR_CYAN};")
        vbox_title.addWidget(lbl_sub)
        hdr_layout.addLayout(vbox_title)
        hdr_layout.addStretch()
        main_layout.addLayout(hdr_layout)

        # Tabs for Slots 1 to 6
        self.tabs = QTabWidget()
        for slot in range(1, 7):
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(16, 14, 16, 14)
            tab_layout.setSpacing(12)

            # Slot Header
            slot_banner = QHBoxLayout()
            lbl_slot_tag = QLabel(f"TRACK SLOT {slot}")
            lbl_slot_tag.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            lbl_slot_tag.setStyleSheet(f"""
                background: rgba(0, 255, 204, 0.12);
                color: {COLOR_CYAN};
                border: 1px solid rgba(0, 255, 204, 0.35);
                border-radius: 6px;
                padding: 4px 10px;
            """)
            slot_banner.addWidget(lbl_slot_tag)
            slot_banner.addStretch()
            tab_layout.addLayout(slot_banner)

            # Profile Info (Name, Jockey, Color)
            info_group = QGroupBox("Racer Identity")
            info_form = QFormLayout(info_group)
            info_form.setSpacing(10)

            txt_name = QLineEdit()
            txt_name.setPlaceholderText(f"Racer {slot} Name")
            info_form.addRow("Racer Name:", txt_name)

            txt_jockey = QLineEdit()
            txt_jockey.setPlaceholderText("Jockey Name")
            info_form.addRow("Robot Jockey:", txt_jockey)

            txt_color = QLineEdit()
            txt_color.setPlaceholderText("#ff4757")
            info_form.addRow("Color (Hex):", txt_color)

            tab_layout.addWidget(info_group)

            # Stats Sliders Group
            stats_group = QGroupBox("Track Sector Performance Sliders")
            stats_vbox = QVBoxLayout(stats_group)
            stats_vbox.setSpacing(12)

            def create_slider_row(label_text, min_val, max_val, default_val, desc):
                row_vbox = QVBoxLayout()
                row_vbox.setSpacing(3)

                lbl_row = QLabel(f"{label_text}:")
                lbl_row.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

                h_slider = QHBoxLayout()
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(min_val, max_val)
                slider.setValue(default_val)

                spin = QSpinBox()
                spin.setRange(min_val, max_val)
                spin.setValue(default_val)
                spin.setFixedWidth(70)

                slider.valueChanged.connect(spin.setValue)
                spin.valueChanged.connect(slider.setValue)

                h_slider.addWidget(lbl_row)
                h_slider.addStretch()
                h_slider.addWidget(spin)

                desc_lbl = QLabel(desc)
                desc_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 10px;")

                row_vbox.addLayout(h_slider)
                row_vbox.addWidget(slider)
                row_vbox.addWidget(desc_lbl)
                stats_vbox.addLayout(row_vbox)
                return slider, spin

            sl_reaction, sp_reaction = create_slider_row(
                "🚀 Jockey Reaction (Launch Phase)", 1, 20, 10,
                "Determines starting separation out of the gates (Start Line -> Turn 1 IN)"
            )
            sl_speed, sp_speed = create_slider_row(
                "⚡ Top Speed (Back Stretch)", 10, 100, 65,
                "Raw horsepower down the North straightaway (Turn 1 OUT -> Turn 2 IN)"
            )
            sl_cornering, sp_cornering = create_slider_row(
                "🔄 Cornering Precision (Turns 1 & 2)", 1, 10, 5,
                "Hugs the semicircular East & West curves without bogging down"
            )
            sl_stamina, sp_stamina = create_slider_row(
                "🔋 Stamina (Home Stretch Sprint)", 10, 100, 50,
                "Endurance during final charge from Turn 2 OUT across the Finish Line"
            )

            tab_layout.addWidget(stats_group)
            tab_layout.addStretch()

            self.racer_editors.append({
                "slot": slot,
                "txt_name": txt_name,
                "txt_jockey": txt_jockey,
                "txt_color": txt_color,
                "sl_reaction": sl_reaction,
                "sp_reaction": sp_reaction,
                "sl_speed": sl_speed,
                "sp_speed": sp_speed,
                "sl_cornering": sl_cornering,
                "sp_cornering": sp_cornering,
                "sl_stamina": sl_stamina,
                "sp_stamina": sp_stamina
            })

            self.tabs.addTab(tab_widget, f"Slot {slot}")

        main_layout.addWidget(self.tabs, stretch=1)

        # Dialog Buttons
        btn_bar = QHBoxLayout()
        btn_reset = QPushButton("🔄 Reset Defaults")
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #27354d; }}
        """)
        btn_reset.clicked.connect(self._reset_defaults)
        btn_bar.addWidget(btn_reset)

        btn_test_race = QPushButton("🏁 Test Race Now")
        btn_test_race.setToolTip("Save racer stats and immediately launch live race sprint on projector screen")
        btn_test_race.setStyleSheet(f"""
            QPushButton {{
                background: #0f2c24;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_test_race.clicked.connect(self._on_test_race)
        btn_bar.addWidget(btn_test_race)

        btn_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background: #27354d; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save & Apply Racers")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_GREEN};
                color: #000000;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #4cd137; }}
        """)
        btn_save.clicked.connect(self._save_racers)
        btn_bar.addWidget(btn_save)

        main_layout.addLayout(btn_bar)

    def _load_racers(self):
        racers_file = ROOT_DIR / "game_hub" / "games" / "bison_dash" / "data" / "bison_racers.json"
        racers = []
        if racers_file.exists():
            try:
                with open(racers_file, "r", encoding="utf-8") as f:
                    racers = json.load(f)
            except Exception:
                pass

        if not racers or len(racers) != 6:
            self._reset_defaults()
            return

        for i, ed in enumerate(self.racer_editors):
            r = racers[i] if i < len(racers) else {}
            ed["txt_name"].setText(r.get("name", f"Bison #{ed['slot']}"))
            ed["txt_jockey"].setText(r.get("jockey_name", "Rider"))
            ed["txt_color"].setText(r.get("color", "#ff4757"))
            st = r.get("stats", {})
            ed["sl_reaction"].setValue(int(st.get("jockey_reaction", 10)))
            ed["sl_speed"].setValue(int(st.get("bison_speed", 65)))
            ed["sl_cornering"].setValue(int(st.get("bison_cornering", 5)))
            ed["sl_stamina"].setValue(int(st.get("bison_stamina", 50)))

    def _reset_defaults(self):
        defaults = [
            {"name": "Thunder Stampede", "color": "#ff4757", "jockey": "Jockey Jax", "reaction": 12, "speed": 65, "cornering": 6, "stamina": 55},
            {"name": "Cyber Steer", "color": "#2ed573", "jockey": "Dash Volt", "reaction": 10, "speed": 70, "cornering": 5, "stamina": 50},
            {"name": "Prairie Rocket", "color": "#3742fa", "jockey": "Nova Drift", "reaction": 14, "speed": 60, "cornering": 7, "stamina": 45},
            {"name": "Iron Horn", "color": "#ffa502", "jockey": "Steel Spur", "reaction": 8, "speed": 75, "cornering": 4, "stamina": 60},
            {"name": "Neon Goliath", "color": "#9b5de5", "jockey": "Pulse Rider", "reaction": 11, "speed": 62, "cornering": 5, "stamina": 65},
            {"name": "Solar Flare", "color": "#00d2d3", "jockey": "Blaze Vector", "reaction": 13, "speed": 68, "cornering": 6, "stamina": 50}
        ]
        for i, ed in enumerate(self.racer_editors):
            d = defaults[i]
            ed["txt_name"].setText(d["name"])
            ed["txt_jockey"].setText(d["jockey"])
            ed["txt_color"].setText(d["color"])
            ed["sl_reaction"].setValue(d["reaction"])
            ed["sl_speed"].setValue(d["speed"])
            ed["sl_cornering"].setValue(d["cornering"])
            ed["sl_stamina"].setValue(d["stamina"])

    def _on_test_race(self):
        self._save_racers(show_msg=False)
        trigger_bison_test_race(self.parent())

    def _save_racers(self, show_msg: bool = True):
        data_dir = ROOT_DIR / "game_hub" / "games" / "bison_dash" / "data"
        racers_file = data_dir / "bison_racers.json"
        bisons_dir = data_dir / "bisons"
        lineup_file = data_dir / "lineup.json"
        bisons_dir.mkdir(parents=True, exist_ok=True)

        racers = []
        lineup = []

        for ed in self.racer_editors:
            slot = ed["slot"]
            b_id = f"bison_{slot}"
            r_data = {
                "id": b_id,
                "slot": slot,
                "name": ed["txt_name"].text().strip() or f"Bison #{slot}",
                "color": ed["txt_color"].text().strip() or "#ff4757",
                "jockey_name": ed["txt_jockey"].text().strip() or "Rider",
                "jockey_color": ed["txt_color"].text().strip() or "#ff4757",
                "stats": {
                    "jockey_reaction": ed["sl_reaction"].value(),
                    "bison_speed": ed["sl_speed"].value(),
                    "bison_cornering": ed["sl_cornering"].value(),
                    "bison_stamina": ed["sl_stamina"].value(),
                    "jockey_aggression": 5,
                    "jockey_luck": 5
                }
            }
            racers.append(r_data)
            lineup.append({"slot": slot, "bison_id": b_id})

            try:
                with open(bisons_dir / f"{b_id}.json", "w", encoding="utf-8") as f:
                    json.dump(r_data, f, indent=2)
            except Exception:
                pass

        with open(racers_file, "w", encoding="utf-8") as f:
            json.dump(racers, f, indent=2)

        with open(lineup_file, "w", encoding="utf-8") as f:
            json.dump({"lineup": lineup}, f, indent=2)

        try:
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:8001/api/bisondash/racers/save",
                data=json.dumps(racers).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass

        if show_msg:
            QMessageBox.information(self, "Racers Saved", "✓ All 6 Bison Dash racers updated and saved!\nStats and details will take effect on the next race.")
            self.accept()


def make_slide_thumbnail(slide_data: dict, deck_type: str = "regular") -> QIcon:
    """Generates a crisp 160x90 (16:9) thumbnail QIcon for visual slide ordering."""
    import master_admin.data_manager as dm
    canvas = QPixmap(160, 90)
    canvas.fill(QColor("#080c14"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    filename = slide_data.get("filename")
    stype = slide_data.get("type", "custom_image" if deck_type == "regular" else "presentation_image")

    image_drawn = False
    if filename:
        img_path = dm.SLIDES_DIR / filename
        if img_path.exists():
            pix = QPixmap(str(img_path))
            if not pix.isNull():
                thumb = pix.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                px = (160 - thumb.width()) // 2
                py = (90 - thumb.height()) // 2
                painter.drawPixmap(px, py, thumb)
                image_drawn = True

    if not image_drawn:
        painter.setPen(QPen(QColor(COLOR_CARD_BORDER), 2))
        painter.setBrush(QBrush(QColor("#111723")))
        painter.drawRoundedRect(3, 3, 154, 84, 6, 6)

        emoji = "🖼️"
        label = "SLIDE"
        color = COLOR_CYAN
        if stype == "leaderboard":
            emoji = "🏆"
            label = "LEADERBOARD"
            color = COLOR_GOLD
        elif stype == "builtin_qr":
            emoji = "📱"
            label = "PIN / QR PASS"
            color = COLOR_CYAN
        elif stype == "builtin_welcome":
            emoji = "👋"
            label = "WELCOME"
            color = COLOR_PURPLE
        elif stype == "builtin_booths":
            emoji = "🕹️"
            label = "BOOTH GAMES"
            color = COLOR_GREEN
        elif deck_type == "presentation":
            emoji = "📢"
            label = "PRESENTATION"
            color = "#ffaa00"

        painter.setFont(QFont("Segoe UI Emoji", 20))
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(QRect(0, 10, 160, 36), Qt.AlignmentFlag.AlignCenter, emoji)

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(color)))
        painter.drawText(QRect(4, 48, 152, 26), Qt.AlignmentFlag.AlignCenter, label)

    painter.setPen(QPen(QColor(COLOR_CARD_BORDER), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(0, 0, 159, 89)
    painter.end()
    return QIcon(canvas)


class SlideshowBuilderDialog(QDialog):
    """
    Visual drag-and-drop builder popup for the Stadium Projector Slideshow Deck (DJ's Mac).
    Enables image uploading (1920x1080 auto-resizing), visual thumbnail display,
    drag-and-drop reordering, duration editing, toggling, and atomic order persistence.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖼️ Stadium Slideshow Builder (DJ's Mac Projector Deck)")
        self.resize(960, 680)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
            }}
            QListWidget {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                color: #ffffff;
                padding: 8px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                margin-bottom: 4px;
            }}
            QListWidget::item:selected {{
                background: #1b263b;
                color: {COLOR_CYAN};
                border: 1px solid rgba(0, 255, 204, 0.4);
            }}
        """)
        self._build_ui()
        self._refresh_branding_ui()
        self._load_slides()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Row
        head_row = QHBoxLayout()
        vbox_head = QVBoxLayout()
        lbl_head = QLabel("🖼️ Visual Slideshow Deck Builder")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_CYAN};")
        vbox_head.addWidget(lbl_head)

        lbl_sub = QLabel("Drag & drop slides into the exact rotation order you want. Images are auto-scaled & letterboxed to 1920x1080 (16:9).")
        lbl_sub.setFont(QFont("Segoe UI", 8))
        lbl_sub.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        vbox_head.addWidget(lbl_sub)
        head_row.addLayout(vbox_head, stretch=1)

        # Upload Button
        btn_upload = QPushButton("➕ Upload Slide(s)")
        btn_upload.setToolTip("Upload one or multiple images (PNG, JPG, WEBP). Automatically letterboxed to 1920x1080.")
        btn_upload.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_CYAN};
                color: #000;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #55ffdd; }}
        """)
        btn_upload.clicked.connect(self._upload_slides)
        head_row.addWidget(btn_upload)

        # Save Order Button
        btn_save_top = QPushButton("💾 Save Order")
        btn_save_top.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_save_top.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_top.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_GREEN};
                color: #000;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #5af095; }}
        """)
        btn_save_top.clicked.connect(self._save_order)
        head_row.addWidget(btn_save_top)

        layout.addLayout(head_row)

        # Branding & Display Toggles Bar
        brand_row = QFrame()
        brand_row.setStyleSheet(f"""
            QFrame {{
                background: #0f1624;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        b_layout = QHBoxLayout(brand_row)
        b_layout.setContentsMargins(12, 8, 12, 8)
        b_layout.setSpacing(12)

        lbl_logo_tag = QLabel("Bison Logo (100x100 PNG):")
        lbl_logo_tag.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_logo_tag.setStyleSheet(f"color: {COLOR_CYAN};")
        b_layout.addWidget(lbl_logo_tag)

        self.lbl_logo_preview = QLabel()
        self.lbl_logo_preview.setFixedSize(40, 40)
        self.lbl_logo_preview.setScaledContents(True)
        self.lbl_logo_preview.setStyleSheet(f"border: 1px solid {COLOR_CARD_BORDER}; border-radius: 4px; background: #080c14;")
        b_layout.addWidget(self.lbl_logo_preview)

        btn_upload_logo = QPushButton("🦬 Upload Logo (PNG)")
        btn_upload_logo.setToolTip("Upload custom Bison logo (PNG, JPG, WEBP). Formatted to 100x100 so it's crisp next to Techlahoma title.")
        btn_upload_logo.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_upload_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload_logo.setStyleSheet(f"""
            QPushButton {{
                background: #1b263b;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_upload_logo.clicked.connect(self._upload_custom_logo)
        b_layout.addWidget(btn_upload_logo)

        btn_reset_logo = QPushButton("Reset Logo")
        btn_reset_logo.setToolTip("Restore default placeholder bison logo.")
        btn_reset_logo.setFont(QFont("Segoe UI", 8))
        btn_reset_logo.setStyleSheet(self._btn_style_secondary())
        btn_reset_logo.clicked.connect(self._reset_custom_logo)
        b_layout.addWidget(btn_reset_logo)

        b_layout.addSpacing(16)

        lbl_toggles = QLabel("Header Toggles:")
        lbl_toggles.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_toggles.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")
        b_layout.addWidget(lbl_toggles)

        self.chk_show_title = QCheckBox("Show Techlahoma / Title Header")
        self.chk_show_title.setChecked(True)
        self.chk_show_title.setToolTip("Toggle display of the Techlahoma Bison Bash logo/title header on the stadium projector.")
        self.chk_show_title.setFont(QFont("Segoe UI", 9))
        self.chk_show_title.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")
        self.chk_show_title.toggled.connect(self._on_branding_toggle)
        b_layout.addWidget(self.chk_show_title)

        self.chk_show_clock = QCheckBox("Show Live Clock Pill")
        self.chk_show_clock.setChecked(True)
        self.chk_show_clock.setToolTip("Toggle display of the live clock pill on the top right.")
        self.chk_show_clock.setFont(QFont("Segoe UI", 9))
        self.chk_show_clock.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")
        self.chk_show_clock.toggled.connect(self._on_branding_toggle)
        b_layout.addWidget(self.chk_show_clock)

        b_layout.addStretch()
        layout.addWidget(brand_row)

        # Center Body: List on left, Action Toolbar on right
        body_row = QHBoxLayout()
        body_row.setSpacing(14)

        # Drag-and-drop Visual List
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(160, 90))
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        self.list_widget.model().rowsMoved.connect(self._on_order_changed)
        body_row.addWidget(self.list_widget, stretch=1)

        # Right Action Sidebar
        side_panel = QVBoxLayout()
        side_panel.setSpacing(8)

        lbl_tools = QLabel("SLIDE ACTIONS")
        lbl_tools.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_tools.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        side_panel.addWidget(lbl_tools)

        btn_up = QPushButton("⬆️ Move Up")
        btn_up.setStyleSheet(self._btn_style_secondary())
        btn_up.clicked.connect(lambda: self._move_selected(-1))
        side_panel.addWidget(btn_up)

        btn_down = QPushButton("⬇️ Move Down")
        btn_down.setStyleSheet(self._btn_style_secondary())
        btn_down.clicked.connect(lambda: self._move_selected(1))
        side_panel.addWidget(btn_down)

        btn_toggle = QPushButton("👁️ Toggle Active / Off")
        btn_toggle.setStyleSheet(self._btn_style_secondary())
        btn_toggle.clicked.connect(self._toggle_selected)
        side_panel.addWidget(btn_toggle)

        btn_duration = QPushButton("⏱️ Set Duration (sec)")
        btn_duration.setStyleSheet(self._btn_style_secondary())
        btn_duration.clicked.connect(self._edit_duration)
        side_panel.addWidget(btn_duration)

        btn_add_builtin = QPushButton("➕ Add Built-in Slide")
        btn_add_builtin.setStyleSheet(self._btn_style_secondary())
        btn_add_builtin.clicked.connect(self._add_builtin_slide)
        side_panel.addWidget(btn_add_builtin)

        btn_delete = QPushButton("🗑️ Remove Slide")
        btn_delete.setStyleSheet(f"""
            QPushButton {{
                background: #21161d;
                border: 1px solid rgba(255, 71, 87, 0.4);
                color: {COLOR_RED};
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLOR_RED}; color: #fff; }}
        """)
        btn_delete.clicked.connect(self._delete_selected)
        side_panel.addWidget(btn_delete)

        side_panel.addSpacing(12)

        lbl_venue = QLabel("VENUE CONTROLS")
        lbl_venue.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_venue.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        side_panel.addWidget(lbl_venue)

        btn_restart = QPushButton("🔄 Restart at #1")
        btn_restart.setToolTip("Remotely resets DJ's screen to the very first slide of regular rotation.")
        btn_restart.setStyleSheet(f"""
            QPushButton {{
                background: #112822;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_restart.clicked.connect(self._restart_regular)
        side_panel.addWidget(btn_restart)

        btn_web = QPushButton("🌐 Open DJ View")
        btn_web.setStyleSheet(self._btn_style_secondary())
        btn_web.clicked.connect(lambda: webbrowser.open("http://localhost:8010/slideshow"))
        side_panel.addWidget(btn_web)

        side_panel.addStretch()
        body_row.addLayout(side_panel)

        layout.addLayout(body_row, stretch=1)

        # Footer Row
        foot_row = QHBoxLayout()
        btn_folder = QPushButton("📂 Open Slides Folder")
        btn_folder.setStyleSheet(self._btn_style_secondary())
        btn_folder.clicked.connect(self._open_slides_folder)
        foot_row.addWidget(btn_folder)

        self.lbl_status = QLabel("Ready • Click and drag items to reorder.")
        self.lbl_status.setFont(QFont("Segoe UI", 9))
        self.lbl_status.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        foot_row.addWidget(self.lbl_status, stretch=1)

        btn_save_bot = QPushButton("💾 Save Order")
        btn_save_bot.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_save_bot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_bot.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_GREEN};
                color: #000;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #5af095; }}
        """)
        btn_save_bot.clicked.connect(self._save_order)
        foot_row.addWidget(btn_save_bot)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(self._btn_style_secondary())
        btn_close.clicked.connect(self.accept)
        foot_row.addWidget(btn_close)

        layout.addLayout(foot_row)

    def _btn_style_secondary(self):
        return f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 6px;
                padding: 7px 14px;
            }}
            QPushButton:hover {{ background: #27354d; color: #fff; }}
        """

    def _load_slides(self):
        import master_admin.data_manager as dm
        manifest = dm.get_slides_manifest()
        slides = sorted(manifest.get("slides", []), key=lambda s: s.get("order", 0))

        self.list_widget.clear()
        for idx, s in enumerate(slides):
            icon = make_slide_thumbnail(s, deck_type="regular")
            item = QListWidgetItem(icon, "")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self._format_item_label(item, s, idx)
            self.list_widget.addItem(item)

        self.lbl_status.setText(f"Loaded {len(slides)} slides. Drag to reorder.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")

    def _format_item_label(self, item: QListWidgetItem, s: dict, index: int):
        title = s.get("title") or s.get("filename") or "Untitled Slide"
        dur = s.get("duration", 10)
        enabled = s.get("enabled", True)
        stype = s.get("type", "custom_image")

        tag = "🖼️ SLIDE"
        if stype == "leaderboard":
            tag = "🏆 LEADERBOARD"
        elif stype == "builtin_qr":
            tag = "📱 PIN / QR"
        elif stype == "builtin_welcome":
            tag = "👋 WELCOME"
        elif stype == "builtin_booths":
            tag = "🕹️ BOOTHS"

        status_str = "✓ ACTIVE" if enabled else "✗ DISABLED"
        fname_str = f"  [{s.get('filename')}]" if s.get("filename") else ""
        item.setText(f"#{index + 1}   {tag}   {title}   ({dur}s)   —   {status_str}{fname_str}")

        if not enabled:
            item.setForeground(QColor(COLOR_TEXT_MUTED))
        elif stype == "leaderboard":
            item.setForeground(QColor(COLOR_GOLD))
        else:
            item.setForeground(QColor(COLOR_TEXT_MAIN))

    def _on_order_changed(self, *args):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            s = item.data(Qt.ItemDataRole.UserRole)
            self._format_item_label(item, s, i)
        self.lbl_status.setText("⚠️ Order changed — click '💾 Save Order' to update live slideshow.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_GOLD}; font-weight: bold;")

    def _move_selected(self, delta: int):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if 0 <= new_row < self.list_widget.count():
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(new_row, item)
            self.list_widget.setCurrentRow(new_row)
            self._on_order_changed()

    def _save_order(self):
        import master_admin.data_manager as dm
        ordered_ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            s = item.data(Qt.ItemDataRole.UserRole)
            if s and "id" in s:
                ordered_ids.append(s["id"])

        dm.reorder_slides(ordered_ids)
        self.lbl_status.setText(f"✅ Saved! {len(ordered_ids)} slides ordered. DJ display updated.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN}; font-weight: bold;")
        QMessageBox.information(
            self,
            "Slideshow Order Saved",
            f"Successfully updated slide rotation order ({len(ordered_ids)} slides).\n"
            "Changes are live on the DJ's Mac stadium display!"
        )

    def _upload_slides(self):
        import master_admin.data_manager as dm
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Slide Image(s) to Upload (Auto 1920x1080 Resize)",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_paths:
            return

        success_count = 0
        for fp in file_paths:
            try:
                with open(fp, "rb") as f:
                    content = f.read()
                title = Path(fp).stem.replace("_", " ").title()
                dm.process_and_save_slide(content, Path(fp).name, title=title, deck="regular")
                success_count += 1
            except Exception as e:
                QMessageBox.critical(self, "Upload Error", f"Error uploading {Path(fp).name}: {e}")

        if success_count > 0:
            self._load_slides()
            self.lbl_status.setText(f"✅ Uploaded & resized {success_count} slide(s) to 1920x1080.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN}; font-weight: bold;")

    def _toggle_selected(self):
        import master_admin.data_manager as dm
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Slide", "Please select a slide to toggle.")
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        cur = s.get("enabled", True)
        dm.toggle_slide(s["id"], not cur)
        s["enabled"] = not cur
        item.setData(Qt.ItemDataRole.UserRole, s)
        self._format_item_label(item, s, self.list_widget.currentRow())
        self.lbl_status.setText(f"Slide '{s.get('title')}' is now {'ACTIVE' if not cur else 'DISABLED'}.")

    def _edit_duration(self):
        import master_admin.data_manager as dm
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Slide", "Please select a slide to change duration.")
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        cur_dur = int(s.get("duration", 10))
        new_dur, ok = QInputDialog.getInt(
            self,
            "Slide Duration",
            f"Display duration for '{s.get('title')}' (seconds):",
            value=cur_dur,
            min=3,
            max=180
        )
        if ok:
            manifest = dm.get_slides_manifest()
            for sl in manifest.get("slides", []):
                if sl.get("id") == s.get("id"):
                    sl["duration"] = new_dur
                    break
            dm.save_slides_manifest(manifest)
            s["duration"] = new_dur
            item.setData(Qt.ItemDataRole.UserRole, s)
            self._format_item_label(item, s, self.list_widget.currentRow())
            self.lbl_status.setText(f"Duration for '{s.get('title')}' set to {new_dur}s.")

    def _add_builtin_slide(self):
        import master_admin.data_manager as dm
        options = [
            "🏆 Live Stadium Leaderboard (Built-in)",
            "📱 PIN Pass & Mobile QR (Built-in)",
            "👋 Welcome to the Arena (Built-in)",
            "🕹️ Arcade Stations Showcase (Built-in)"
        ]
        choice, ok = QInputDialog.getItem(
            self,
            "Add Built-in Slide",
            "Choose a built-in arena slide to add into rotation:",
            options,
            0,
            False
        )
        if not ok or not choice:
            return

        manifest = dm.get_slides_manifest()
        slides = manifest.setdefault("slides", [])
        max_order = max([s.get("order", 0) for s in slides], default=-1)

        if "Leaderboard" in choice:
            new_s = {
                "id": "builtin_leaderboard",
                "type": "leaderboard",
                "title": "Live Stadium Leaderboard",
                "enabled": True,
                "duration": 12,
                "order": max_order + 1
            }
        elif "PIN" in choice:
            new_s = {
                "id": "builtin_qr",
                "type": "builtin_qr",
                "title": "Mobile PIN Pass & QR",
                "enabled": True,
                "duration": 10,
                "order": max_order + 1
            }
        elif "Welcome" in choice:
            new_s = {
                "id": "builtin_welcome",
                "type": "builtin_welcome",
                "title": "Welcome to the Arena",
                "enabled": True,
                "duration": 10,
                "order": max_order + 1
            }
        else:
            new_s = {
                "id": "builtin_booths",
                "type": "builtin_booths",
                "title": "Interactive Arcade Stations",
                "enabled": True,
                "duration": 10,
                "order": max_order + 1
            }

        slides.append(new_s)
        dm.save_slides_manifest(manifest)
        self._load_slides()
        self.lbl_status.setText(f"Added built-in slide '{new_s['title']}' to rotation.")

    def _delete_selected(self):
        import master_admin.data_manager as dm
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Slide", "Please select a slide to delete.")
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete slide '{s.get('title')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            dm.delete_slide(s["id"])
            self._load_slides()
            self.lbl_status.setText(f"Deleted slide '{s.get('title')}'.")

    def _restart_regular(self):
        import master_admin.data_manager as dm
        dm.restart_regular_slideshow()
        QMessageBox.information(
            self,
            "Slideshow Restarted",
            "Broadcasted restart command!\nThe DJ's stadium projector will reset rotation to slide #1 immediately."
        )

    def _open_slides_folder(self):
        import master_admin.data_manager as dm
        folder = dm.SLIDES_DIR
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])

    def _refresh_branding_ui(self):
        import master_admin.data_manager as dm
        branding = dm.get_slideshow_branding()
        logo_path = dm.STATIC_IMG_DIR / "bison_logo.png"
        if logo_path.exists():
            self.lbl_logo_preview.setPixmap(QPixmap(str(logo_path)))

        self.chk_show_title.blockSignals(True)
        self.chk_show_title.setChecked(branding.get("show_header_title", True))
        self.chk_show_title.blockSignals(False)

        self.chk_show_clock.blockSignals(True)
        self.chk_show_clock.setChecked(branding.get("show_clock", True))
        self.chk_show_clock.blockSignals(False)

    def _upload_custom_logo(self):
        import master_admin.data_manager as dm
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Bison Logo PNG to Upload (Auto Formatted to 100x100)",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            dm.save_custom_logo(content, Path(file_path).name)
            self._refresh_branding_ui()
            self.lbl_status.setText("✅ Bison Logo updated to 100x100 PNG! Live on DJ screen.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN}; font-weight: bold;")
            QMessageBox.information(
                self,
                "Logo Updated",
                "Successfully uploaded & formatted Bison Logo to 100x100 PNG!\n"
                "The stadium projector on the DJ's screen has updated live."
            )
        except Exception as e:
            QMessageBox.critical(self, "Upload Failed", f"Failed to upload logo: {e}")

    def _reset_custom_logo(self):
        import master_admin.data_manager as dm
        dm.reset_custom_logo()
        self._refresh_branding_ui()
        self.lbl_status.setText("Logo restored to default placeholder.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_CYAN};")

    def _on_branding_toggle(self):
        import master_admin.data_manager as dm
        show_t = self.chk_show_title.isChecked()
        show_c = self.chk_show_clock.isChecked()
        dm.set_slideshow_branding(show_header_title=show_t, show_clock=show_c)
        self.lbl_status.setText(f"Display toggles saved: Title={'ON' if show_t else 'OFF'}, Clock={'ON' if show_c else 'OFF'}.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN};")


class PresentationBuilderDialog(QDialog):
    """
    Visual drag-and-drop builder popup for the Stage Presentation Cut-In Deck.
    Enables slide uploading (auto 1920x1080 letterbox), 16:9 thumbnail previews,
    drag-and-drop sequence ordering, slide deletion, presenter remote launching,
    and instant order persistence for the DJ's display.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📢 Stage Presentation Builder (Presenter Remote & DJ Cut-In)")
        self.resize(960, 680)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
            }}
            QListWidget {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                color: #ffffff;
                padding: 8px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                margin-bottom: 4px;
            }}
            QListWidget::item:selected {{
                background: #2a2012;
                color: #ffaa00;
                border: 1px solid rgba(255, 170, 0, 0.4);
            }}
        """)
        self._build_ui()
        self._load_slides()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Row
        head_row = QHBoxLayout()
        vbox_head = QVBoxLayout()
        lbl_head = QLabel("📢 Stage Presentation Deck Builder")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet("color: #ffaa00;")
        vbox_head.addWidget(lbl_head)

        lbl_sub = QLabel("Drag & drop speaker slides into the exact presentation sequence. The presenter navigates this order using their mobile remote.")
        lbl_sub.setFont(QFont("Segoe UI", 8))
        lbl_sub.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        vbox_head.addWidget(lbl_sub)
        head_row.addLayout(vbox_head, stretch=1)

        # Upload Button
        btn_upload = QPushButton("➕ Upload Presentation Slide(s)")
        btn_upload.setToolTip("Upload presentation slides (PNG, JPG, WEBP). Automatically letterboxed to 1920x1080.")
        btn_upload.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload.setStyleSheet(f"""
            QPushButton {{
                background: #ffaa00;
                color: #000;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #ffbb33; }}
        """)
        btn_upload.clicked.connect(self._upload_slides)
        head_row.addWidget(btn_upload)

        # Save Order Button
        btn_save_top = QPushButton("💾 Save Sequence")
        btn_save_top.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_save_top.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_top.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_GREEN};
                color: #000;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #5af095; }}
        """)
        btn_save_top.clicked.connect(self._save_order)
        head_row.addWidget(btn_save_top)

        layout.addLayout(head_row)

        # Center Body: List on left, Action Toolbar on right
        body_row = QHBoxLayout()
        body_row.setSpacing(14)

        # Drag-and-drop Visual List
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(160, 90))
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        self.list_widget.model().rowsMoved.connect(self._on_order_changed)
        body_row.addWidget(self.list_widget, stretch=1)

        # Right Action Sidebar
        side_panel = QVBoxLayout()
        side_panel.setSpacing(8)

        lbl_tools = QLabel("SEQUENCE ACTIONS")
        lbl_tools.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_tools.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        side_panel.addWidget(lbl_tools)

        btn_up = QPushButton("⬆️ Move Up")
        btn_up.setStyleSheet(self._btn_style_secondary())
        btn_up.clicked.connect(lambda: self._move_selected(-1))
        side_panel.addWidget(btn_up)

        btn_down = QPushButton("⬇️ Move Down")
        btn_down.setStyleSheet(self._btn_style_secondary())
        btn_down.clicked.connect(lambda: self._move_selected(1))
        side_panel.addWidget(btn_down)

        btn_rename = QPushButton("✏️ Rename Title")
        btn_rename.setStyleSheet(self._btn_style_secondary())
        btn_rename.clicked.connect(self._rename_selected)
        side_panel.addWidget(btn_rename)

        btn_delete = QPushButton("🗑️ Remove Slide")
        btn_delete.setStyleSheet(f"""
            QPushButton {{
                background: #21161d;
                border: 1px solid rgba(255, 71, 87, 0.4);
                color: {COLOR_RED};
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLOR_RED}; color: #fff; }}
        """)
        btn_delete.clicked.connect(self._delete_selected)
        side_panel.addWidget(btn_delete)

        side_panel.addSpacing(12)

        lbl_venue = QLabel("REMOTE & CUT-IN")
        lbl_venue.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_venue.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        side_panel.addWidget(lbl_venue)

        btn_remote = QPushButton("📱 Open PresRemote")
        btn_remote.setToolTip("Opens mobile PresRemote PWA controller for smartphones.")
        btn_remote.setStyleSheet(f"""
            QPushButton {{
                background: #112822;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_remote.clicked.connect(lambda: webbrowser.open("http://localhost:8011/"))
        side_panel.addWidget(btn_remote)

        btn_web = QPushButton("🌐 Open DJ View")
        btn_web.setStyleSheet(self._btn_style_secondary())
        btn_web.clicked.connect(lambda: webbrowser.open("http://localhost:8010/slideshow"))
        side_panel.addWidget(btn_web)

        btn_start_cutin = QPushButton("▶️ Test Cut-In Now")
        btn_start_cutin.setToolTip("Instantly overrides projector screen with presentation slide 1.")
        btn_start_cutin.setStyleSheet(f"""
            QPushButton {{
                background: #2b1f12;
                border: 1px solid #ffaa00;
                color: #ffaa00;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #ffaa00; color: #000; }}
        """)
        btn_start_cutin.clicked.connect(self._start_cutin)
        side_panel.addWidget(btn_start_cutin)

        btn_stop_cutin = QPushButton("⏹️ End Cut-In")
        btn_stop_cutin.setStyleSheet(self._btn_style_secondary())
        btn_stop_cutin.clicked.connect(self._stop_cutin)
        side_panel.addWidget(btn_stop_cutin)

        side_panel.addStretch()
        body_row.addLayout(side_panel)

        layout.addLayout(body_row, stretch=1)

        # Footer Row
        foot_row = QHBoxLayout()
        btn_folder = QPushButton("📂 Open Slides Folder")
        btn_folder.setStyleSheet(self._btn_style_secondary())
        btn_folder.clicked.connect(self._open_slides_folder)
        foot_row.addWidget(btn_folder)

        self.lbl_status = QLabel("Ready • Drag slides into talk order.")
        self.lbl_status.setFont(QFont("Segoe UI", 9))
        self.lbl_status.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        foot_row.addWidget(self.lbl_status, stretch=1)

        btn_save_bot = QPushButton("💾 Save Sequence")
        btn_save_bot.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_save_bot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_bot.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_GREEN};
                color: #000;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #5af095; }}
        """)
        btn_save_bot.clicked.connect(self._save_order)
        foot_row.addWidget(btn_save_bot)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(self._btn_style_secondary())
        btn_close.clicked.connect(self.accept)
        foot_row.addWidget(btn_close)

        layout.addLayout(foot_row)

    def _btn_style_secondary(self):
        return f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 6px;
                padding: 7px 14px;
            }}
            QPushButton:hover {{ background: #27354d; color: #fff; }}
        """

    def _load_slides(self):
        import master_admin.data_manager as dm
        slides = dm.get_presentation_slides()

        self.list_widget.clear()
        for idx, s in enumerate(slides):
            icon = make_slide_thumbnail(s, deck_type="presentation")
            item = QListWidgetItem(icon, "")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self._format_item_label(item, s, idx)
            self.list_widget.addItem(item)

        self.lbl_status.setText(f"Loaded {len(slides)} presentation slide(s). Drag to reorder.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")

    def _format_item_label(self, item: QListWidgetItem, s: dict, index: int):
        title = s.get("title") or s.get("filename") or f"Slide {index + 1}"
        fname = s.get("filename", "")
        fname_str = f"  [{fname}]" if fname else ""
        item.setText(f"Slide {index + 1}   •   {title}{fname_str}")
        item.setForeground(QColor("#ffcc66"))

    def _on_order_changed(self, *args):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            s = item.data(Qt.ItemDataRole.UserRole)
            self._format_item_label(item, s, i)
        self.lbl_status.setText("⚠️ Order changed — click '💾 Save Sequence' to apply.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_GOLD}; font-weight: bold;")

    def _move_selected(self, delta: int):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if 0 <= new_row < self.list_widget.count():
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(new_row, item)
            self.list_widget.setCurrentRow(new_row)
            self._on_order_changed()

    def _save_order(self):
        import master_admin.data_manager as dm
        ordered_ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            s = item.data(Qt.ItemDataRole.UserRole)
            if s and "id" in s:
                ordered_ids.append(s["id"])

        dm.reorder_presentation_slides(ordered_ids)
        self.lbl_status.setText(f"✅ Presentation sequence saved! ({len(ordered_ids)} slides)")
        self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN}; font-weight: bold;")
        QMessageBox.information(
            self,
            "Presentation Order Saved",
            f"Successfully updated presentation deck sequence ({len(ordered_ids)} slides).\n"
            "Changes are live on the DJ's display and Presenter Remote!"
        )

    def _upload_slides(self):
        import master_admin.data_manager as dm
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Presentation Slide(s) to Upload (Auto 1920x1080 Resize)",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_paths:
            return

        success_count = 0
        for fp in file_paths:
            try:
                with open(fp, "rb") as f:
                    content = f.read()
                title = Path(fp).stem.replace("_", " ").title()
                dm.process_and_save_slide(content, Path(fp).name, title=title, deck="presentation")
                success_count += 1
            except Exception as e:
                QMessageBox.critical(self, "Upload Error", f"Error uploading {Path(fp).name}: {e}")

        if success_count > 0:
            self._load_slides()
            self.lbl_status.setText(f"✅ Uploaded & resized {success_count} presentation slide(s) to 1920x1080.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN}; font-weight: bold;")

    def _rename_selected(self):
        import master_admin.data_manager as dm
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Slide", "Please select a presentation slide to rename.")
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        cur_title = s.get("title", "")
        new_title, ok = QInputDialog.getText(
            self,
            "Rename Presentation Slide",
            "Enter new slide title:",
            text=cur_title
        )
        if ok and new_title.strip():
            manifest = dm.get_slides_manifest()
            for sl in manifest.get("presentation_slides", []):
                if sl.get("id") == s.get("id"):
                    sl["title"] = new_title.strip()
                    break
            dm.save_slides_manifest(manifest)
            s["title"] = new_title.strip()
            item.setData(Qt.ItemDataRole.UserRole, s)
            self._format_item_label(item, s, self.list_widget.currentRow())
            self.lbl_status.setText(f"Renamed slide to '{new_title.strip()}'.")

    def _delete_selected(self):
        import master_admin.data_manager as dm
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Slide", "Please select a slide to delete.")
            return
        s = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete presentation slide '{s.get('title')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            dm.delete_presentation_slide(s["id"])
            self._load_slides()
            self.lbl_status.setText(f"Deleted presentation slide '{s.get('title')}'.")

    def _start_cutin(self):
        import master_admin.data_manager as dm
        dm.start_presentation_mode(0)
        self.lbl_status.setText("🔴 Presentation Cut-In ACTIVE on DJ's display.")
        self.lbl_status.setStyleSheet("color: #ffaa00; font-weight: bold;")

    def _stop_cutin(self):
        import master_admin.data_manager as dm
        dm.stop_presentation_mode()
        self.lbl_status.setText("⚪ Presentation Cut-In stopped. Slideshow rotation resumed.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_GREEN};")

    def _open_slides_folder(self):
        import master_admin.data_manager as dm
        folder = dm.SLIDES_DIR
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])


class SlideManagerDialog(QDialog):
    """Backwards-compatible launcher dialog that tabs both Slideshow Builder and Presentation Builder."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖼️ Stadium Slide & Presentation Builder Hub")
        self.resize(1000, 720)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLOR_BG_DARK}; color: {COLOR_TEXT_MAIN}; }}
            QTabWidget::pane {{ border: 1px solid {COLOR_CARD_BORDER}; background: #0c121d; border-radius: 8px; }}
            QTabBar::tab {{ background: #141c2b; color: {COLOR_TEXT_MUTED}; padding: 8px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; font-weight: bold; }}
            QTabBar::tab:selected {{ background: #1f2d44; color: {COLOR_CYAN}; border-bottom: 2px solid {COLOR_CYAN}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.tabs = QTabWidget()
        self.slideshow_tab = SlideshowBuilderDialog(self)
        self.presentation_tab = PresentationBuilderDialog(self)
        self.tabs.addTab(self.slideshow_tab, "🖼️ Regular Slideshow Deck")
        self.tabs.addTab(self.presentation_tab, "📢 Stage Presentation Deck")
        layout.addWidget(self.tabs)


class SlideshowTimerDialog(QDialog):
    """Dialog to manually trigger and manage the Bison Dash Race Countdown slide on the Stadium Projector (DJ's Mac)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏱️ Stadium Slideshow & Race Countdown - DJ's Mac Controller")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_MAIN};
            }}
            QLabel {{
                color: {COLOR_TEXT_MAIN};
            }}
            QLineEdit, QSpinBox {{
                background: #0d131f;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 8px 10px;
                color: #ffffff;
                font-size: 13px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {COLOR_CYAN};
            }}
            QGroupBox {{
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: {COLOR_PURPLE};
            }}
        """)
        self._build_ui()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(500)
        self.poll_timer.timeout.connect(self._poll_status)
        self.poll_timer.start()
        self._poll_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        # Header
        lbl_head = QLabel("📽️ Arena Projector & Bison Dash Countdown (DJ's Mac)")
        lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_PURPLE};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Controls the 1080p stadium slideshow running on the DJ's Mac (Port 8010). Starting the countdown slide "
            "immediately overrides the regular slideshow with the digital timer, bison running animation, and betting kiosks."
        )
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # DJ's Mac Connection Card
        lan_ip = get_lan_ip()
        dj_card = QFrame()
        dj_card.setStyleSheet(f"""
            QFrame {{
                background: #0f1624;
                border: 1px solid rgba(0, 255, 204, 0.25);
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        dj_c_layout = QVBoxLayout(dj_card)
        dj_c_layout.setSpacing(6)

        row_dj = QHBoxLayout()
        lbl_dj_title = QLabel("🍎 DJ's Mac Projector Display (Port 8010):")
        lbl_dj_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_dj_title.setStyleSheet(f"color: {COLOR_CYAN};")
        row_dj.addWidget(lbl_dj_title)

        lbl_dj_link = QLabel(f"http://{lan_ip}:8010/slideshow")
        lbl_dj_link.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        lbl_dj_link.setStyleSheet("color: #ffd700;")
        row_dj.addWidget(lbl_dj_link)
        row_dj.addStretch()

        btn_copy_dj = QPushButton("📋 Copy Link")
        btn_copy_dj.setStyleSheet(f"background: #1b2838; border: 1px solid {COLOR_CYAN}; color: {COLOR_CYAN}; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_copy_dj.clicked.connect(self._copy_dj_link)
        row_dj.addWidget(btn_copy_dj)

        btn_prev_dj = QPushButton("🌐 Preview")
        btn_prev_dj.setStyleSheet(f"background: #21262d; border: 1px solid #30363d; color: #fff; border-radius: 4px; padding: 4px 10px; font-size: 11px;")
        btn_prev_dj.clicked.connect(lambda: webbrowser.open("http://localhost:8010/slideshow"))
        row_dj.addWidget(btn_prev_dj)
        dj_c_layout.addLayout(row_dj)

        row_rem = QHBoxLayout()
        lbl_rem_title = QLabel("📱 PresRemote (Mobile PWA & Clicker):")
        lbl_rem_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_rem_title.setStyleSheet("color: #ffaa00;")
        row_rem.addWidget(lbl_rem_title)

        lbl_rem_link = QLabel(f"http://{lan_ip}:8011/")
        lbl_rem_link.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        lbl_rem_link.setStyleSheet("color: #ffaa00;")
        row_rem.addWidget(lbl_rem_link)
        row_rem.addStretch()

        btn_copy_rem = QPushButton("📋 Copy Link")
        btn_copy_rem.setStyleSheet("background: #2a2012; border: 1px solid #ffaa00; color: #ffaa00; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
        btn_copy_rem.clicked.connect(self._copy_remote_link)
        row_rem.addWidget(btn_copy_rem)
        dj_c_layout.addLayout(row_rem)

        layout.addWidget(dj_card)

        # Status Banner Box
        status_box = QFrame()
        status_box.setStyleSheet(f"""
            QFrame {{
                background: #111723;
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        s_layout = QHBoxLayout(status_box)
        s_layout.setContentsMargins(10, 8, 10, 8)

        lbl_s_title = QLabel("CURRENT SCREEN:")
        lbl_s_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_s_title.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        s_layout.addWidget(lbl_s_title)

        self.lbl_mode_pill = QLabel("SLIDESHOW ROTATION")
        self.lbl_mode_pill.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.lbl_mode_pill.setStyleSheet(f"""
            background: rgba(0, 255, 204, 0.12);
            color: {COLOR_CYAN};
            border: 1px solid rgba(0, 255, 204, 0.3);
            border-radius: 4px;
            padding: 4px 10px;
        """)
        s_layout.addWidget(self.lbl_mode_pill)

        s_layout.addStretch()

        self.lbl_time_pill = QLabel("--:--")
        self.lbl_time_pill.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.lbl_time_pill.setStyleSheet(f"""
            background: rgba(255, 255, 255, 0.05);
            color: {COLOR_GOLD};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 4px;
            padding: 4px 10px;
        """)
        s_layout.addWidget(self.lbl_time_pill)

        layout.addWidget(status_box)

        # Time Left Controls Group
        grp_time = QGroupBox("⏱️ Time Left Till Race")
        grp_layout = QVBoxLayout(grp_time)
        grp_layout.setSpacing(12)

        # Quick preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        lbl_presets = QLabel("Quick Presets:")
        lbl_presets.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        preset_row.addWidget(lbl_presets)

        for mins in [1, 2, 3, 5, 10]:
            btn = QPushButton(f"{mins}m")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1b2332;
                    border: 1px solid {COLOR_CARD_BORDER};
                    color: #fff;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background: {COLOR_PURPLE}; }}
            """)
            btn.clicked.connect(lambda checked, m=mins: self._set_preset(m))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        grp_layout.addLayout(preset_row)

        # Inputs row
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        min_box = QVBoxLayout()
        min_box.setSpacing(3)
        lbl_m = QLabel("MINUTES")
        lbl_m.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_MUTED}; font-weight: bold;")
        self.spn_min = QSpinBox()
        self.spn_min.setRange(0, 60)
        self.spn_min.setValue(5)
        min_box.addWidget(lbl_m)
        min_box.addWidget(self.spn_min)
        input_row.addLayout(min_box)

        sec_box = QVBoxLayout()
        sec_box.setSpacing(3)
        lbl_s = QLabel("SECONDS")
        lbl_s.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_MUTED}; font-weight: bold;")
        self.spn_sec = QSpinBox()
        self.spn_sec.setRange(0, 59)
        self.spn_sec.setSingleStep(5)
        self.spn_sec.setValue(0)
        sec_box.addWidget(lbl_s)
        sec_box.addWidget(self.spn_sec)
        input_row.addLayout(sec_box)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        lbl_t = QLabel("RACE TITLE / BANNER")
        lbl_t.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_MUTED}; font-weight: bold;")
        self.txt_title = QLineEdit()
        self.txt_title.setText("Next Bison Dash Race")
        title_box.addWidget(lbl_t)
        title_box.addWidget(self.txt_title)
        input_row.addLayout(title_box, stretch=1)

        grp_layout.addLayout(input_row)
        layout.addWidget(grp_time)

        # Action Buttons
        btn_action_row = QHBoxLayout()
        btn_action_row.setSpacing(10)

        btn_start_cd = QPushButton("🏇 Start Race (5m Cut-In)")
        btn_start_cd.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_start_cd.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_start_cd.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_CYAN};
                color: #000;
                border-radius: 6px;
                padding: 10px 18px;
                border: none;
            }}
            QPushButton:hover {{ background: #55ffdd; }}
        """)
        btn_start_cd.clicked.connect(self._start_countdown)
        btn_action_row.addWidget(btn_start_cd)

        btn_launch_sprint = QPushButton("⚡ Launch Sprint Now")
        btn_launch_sprint.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_launch_sprint.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_launch_sprint.setStyleSheet(f"""
            QPushButton {{
                background: #11281e;
                border: 1px solid {COLOR_GREEN};
                color: {COLOR_GREEN};
                border-radius: 6px;
                padding: 10px 14px;
            }}
            QPushButton:hover {{ background: {COLOR_GREEN}; color: #000; }}
        """)
        btn_launch_sprint.clicked.connect(self._launch_sprint_now)
        btn_action_row.addWidget(btn_launch_sprint)

        btn_stop_cd = QPushButton("⏹️ End Race Mode & Return to Slideshow")
        btn_stop_cd.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_stop_cd.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_stop_cd.setStyleSheet(f"""
            QPushButton {{
                background: #21262d;
                border: 1px solid {COLOR_RED};
                color: {COLOR_RED};
                border-radius: 6px;
                padding: 10px 16px;
            }}
            QPushButton:hover {{ background: {COLOR_RED}; color: #fff; }}
        """)
        btn_stop_cd.clicked.connect(self._stop_countdown)
        btn_action_row.addWidget(btn_stop_cd)

        btn_restart_cd = QPushButton("🔄 Restart Regular Slideshow")
        btn_restart_cd.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_restart_cd.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restart_cd.setStyleSheet(f"""
            QPushButton {{
                background: #112822;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 10px 16px;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_restart_cd.clicked.connect(self._restart_regular)
        btn_action_row.addWidget(btn_restart_cd)

        layout.addLayout(btn_action_row)

        # Stage Presentation Cut-In Deck Section
        grp_pres = QGroupBox("📢 Stage Presentation Cut-In")
        grp_pres.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid rgba(255, 170, 0, 0.4);
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                background: #131a24;
            }}
            QGroupBox::title {{
                color: #ffaa00;
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 4px;
            }}
        """)
        pres_layout = QVBoxLayout(grp_pres)
        pres_layout.setSpacing(8)

        lbl_pres_desc = QLabel("Trigger conference/speaker slides on demand. Overrides the projector instantly.")
        lbl_pres_desc.setFont(QFont("Segoe UI", 8))
        lbl_pres_desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        pres_layout.addWidget(lbl_pres_desc)

        pres_btn_row = QHBoxLayout()
        pres_btn_row.setSpacing(8)

        btn_start_pres = QPushButton("▶️ Start Presentation")
        btn_start_pres.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_start_pres.setStyleSheet("""
            QPushButton {
                background: #ffaa00;
                color: #000;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #ffbb33; }
        """)
        btn_start_pres.clicked.connect(lambda: self._start_presentation(0))
        pres_btn_row.addWidget(btn_start_pres)

        btn_prev_pres = QPushButton("⬅️ Prev")
        btn_prev_pres.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        btn_prev_pres.setStyleSheet("""
            QPushButton {
                background: #21262d;
                border: 1px solid #30363d;
                color: #fff;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #30363d; }
        """)
        btn_prev_pres.clicked.connect(lambda: self._step_presentation(-1))
        pres_btn_row.addWidget(btn_prev_pres)

        btn_next_pres = QPushButton("Next ➡️")
        btn_next_pres.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        btn_next_pres.setStyleSheet("""
            QPushButton {
                background: #21262d;
                border: 1px solid #30363d;
                color: #fff;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #30363d; }
        """)
        btn_next_pres.clicked.connect(lambda: self._step_presentation(1))
        pres_btn_row.addWidget(btn_next_pres)

        btn_stop_pres = QPushButton("⏹️ End Presentation")
        btn_stop_pres.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        btn_stop_pres.setStyleSheet(f"""
            QPushButton {{
                background: #21262d;
                border: 1px solid {COLOR_RED};
                color: {COLOR_RED};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background: {COLOR_RED}; color: #fff; }}
        """)
        btn_stop_pres.clicked.connect(self._stop_presentation)
        pres_btn_row.addWidget(btn_stop_pres)

        pres_btn_row.addStretch()
        pres_layout.addLayout(pres_btn_row)
        layout.addWidget(grp_pres)

        # Stage Mode Buttons
        staged_row = QHBoxLayout()
        staged_row.setSpacing(8)

        btn_prerace = QPushButton("🏁 Pre-Race Slide")
        btn_prerace.setFont(QFont("Segoe UI", 8))
        btn_prerace.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background: {COLOR_PURPLE}; color: #fff; }}
        """)
        btn_prerace.clicked.connect(lambda: self._set_mode("bison_prerace"))
        staged_row.addWidget(btn_prerace)

        btn_liverace = QPushButton("🏇 Live Race Track")
        btn_liverace.setFont(QFont("Segoe UI", 8))
        btn_liverace.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_liverace.clicked.connect(lambda: self._set_mode("bison_race"))
        staged_row.addWidget(btn_liverace)

        staged_row.addStretch()
        layout.addLayout(staged_row)

        # Footer
        footer_row = QHBoxLayout()
        btn_prev_web = QPushButton("🌐 Preview DJ Mac View")
        btn_prev_web.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_prev_web.setStyleSheet(f"""
            QPushButton {{
                background: #112822;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_prev_web.clicked.connect(lambda: webbrowser.open("http://localhost:8010/slideshow"))
        footer_row.addWidget(btn_prev_web)

        btn_prev_remote = QPushButton("📱 PresRemote")
        btn_prev_remote.setFont(QFont("Segoe UI", 9))
        btn_prev_remote.setStyleSheet("""
            QPushButton {
                background: #2a2012;
                border: 1px solid #ffaa00;
                color: #ffaa00;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover { background: #ffaa00; color: #000; }
        """)
        btn_prev_remote.clicked.connect(lambda: webbrowser.open("http://localhost:8011/"))
        footer_row.addWidget(btn_prev_remote)

        btn_proj = QPushButton("🖥️ Local Native Window (Optional)")
        btn_proj.setFont(QFont("Segoe UI", 8))
        btn_proj.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background: {COLOR_PURPLE}; color: #fff; }}
        """)
        btn_proj.clicked.connect(self._launch_or_focus_projector)
        footer_row.addWidget(btn_proj)

        footer_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: #21262d;
                border: 1px solid #30363d;
                color: {COLOR_TEXT_MAIN};
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{ background: #30363d; }}
        """)
        btn_close.clicked.connect(self.accept)
        footer_row.addWidget(btn_close)

        layout.addLayout(footer_row)

    def _copy_dj_link(self):
        lan_ip = get_lan_ip()
        url = f"http://{lan_ip}:8010/slideshow"
        QApplication.clipboard().setText(url)
        QMessageBox.information(
            self,
            "DJ Mac Link Copied",
            f"Copied DJ Mac presentation link:\n\n{url}\n\n"
            "Open this in Chrome/Safari on the DJ's Mac and press F11 for fullscreen."
        )

    def _copy_remote_link(self):
        lan_ip = get_lan_ip()
        url = f"http://{lan_ip}:8011/"
        QApplication.clipboard().setText(url)
        QMessageBox.information(
            self,
            "PresRemote Link Copied",
            f"Copied PresRemote mobile link:\n\n{url}\n\n"
            "Open this on a smartphone or install as a PWA to advance presentation slides remotely."
        )

    def _launch_or_focus_projector(self):
        parent = self.parent()
        if parent and hasattr(parent, "_toggle_projector_window"):
            if not parent.projector_window or not parent.projector_window.isVisible():
                parent._toggle_projector_window()
            else:
                parent.projector_window.raise_()
                parent.projector_window.activateWindow()

    def _set_preset(self, mins: int):
        self.spn_min.setValue(mins)
        self.spn_sec.setValue(0)

    def _start_countdown(self):
        import master_admin.data_manager as dm
        m = self.spn_min.value()
        s = self.spn_sec.value()
        title = self.txt_title.text().strip() or "Next Bison Dash Race"
        dm.set_slideshow_countdown(minutes=m, seconds=s, title=title)
        self._poll_status()

    def _launch_sprint_now(self):
        import master_admin.data_manager as dm
        import urllib.request
        try:
            req = urllib.request.Request("http://localhost:8001/api/bisondash/test_race", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=3.0)
        except Exception:
            pass
        dm.set_slideshow_mode("bison_race")
        self._poll_status()

    def _stop_countdown(self):
        import master_admin.data_manager as dm
        dm.stop_slideshow_countdown()
        self._poll_status()

    def _restart_regular(self):
        import master_admin.data_manager as dm
        dm.restart_regular_slideshow()
        self._poll_status()

    def _start_presentation(self, index: int = 0):
        import master_admin.data_manager as dm
        dm.start_presentation_mode(index)
        self._poll_status()

    def _step_presentation(self, delta: int):
        import master_admin.data_manager as dm
        dm.step_presentation_slide(delta)
        self._poll_status()

    def _stop_presentation(self):
        import master_admin.data_manager as dm
        dm.stop_presentation_mode()
        self._poll_status()

    def _set_mode(self, mode: str):
        import master_admin.data_manager as dm
        dm.set_slideshow_mode(mode)
        self._poll_status()

    def _poll_status(self):
        import master_admin.data_manager as dm
        try:
            state = dm.get_slideshow_state()
            mode = state.get("mode", "slideshow")
            cd = state.get("countdown", {})

            if mode == "bison_countdown" and cd.get("active"):
                self.lbl_mode_pill.setText("🏇 RACE COUNTDOWN ACTIVE")
                self.lbl_mode_pill.setStyleSheet(f"""
                    background: rgba(255, 71, 87, 0.2);
                    color: {COLOR_RED};
                    border: 1px solid {COLOR_RED};
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
                target = cd.get("target_timestamp", 0)
                rem = max(0, int(target - time.time()))
                mins = rem // 60
                secs = rem % 60
                self.lbl_time_pill.setText(f"{mins:02d}:{secs:02d} REMAINING")
                self.lbl_time_pill.setStyleSheet(f"""
                    background: rgba(255, 215, 0, 0.15);
                    color: {COLOR_GOLD};
                    border: 1px solid {COLOR_GOLD};
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
            elif mode == "presentation" or state.get("presentation", {}).get("active"):
                pres = state.get("presentation", {})
                cur = pres.get("current_index", 0) + 1
                total = len(dm.get_presentation_slides())
                self.lbl_mode_pill.setText(f"📢 PRESENTATION (SLIDE {cur}/{total})")
                self.lbl_mode_pill.setStyleSheet(f"""
                    background: rgba(255, 170, 0, 0.2);
                    color: #ffaa00;
                    border: 1px solid #ffaa00;
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
                self.lbl_time_pill.setText(f"STAGE SLIDE {cur} OF {total}")
                self.lbl_time_pill.setStyleSheet(f"""
                    background: rgba(255, 215, 0, 0.15);
                    color: {COLOR_GOLD};
                    border: 1px solid {COLOR_GOLD};
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
            elif mode == "bison_prerace":
                self.lbl_mode_pill.setText("🏁 PRE-RACE SLIDE")
                self.lbl_mode_pill.setStyleSheet(f"""
                    background: rgba(155, 93, 229, 0.2);
                    color: {COLOR_PURPLE};
                    border: 1px solid {COLOR_PURPLE};
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
                self.lbl_time_pill.setText("MANUAL OVERRIDE")
            elif mode == "bison_race":
                self.lbl_mode_pill.setText("🏇 LIVE RACE TRACK")
                self.lbl_mode_pill.setStyleSheet(f"""
                    background: rgba(0, 255, 204, 0.2);
                    color: {COLOR_CYAN};
                    border: 1px solid {COLOR_CYAN};
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
                self.lbl_time_pill.setText("MANUAL OVERRIDE")
            else:
                self.lbl_mode_pill.setText("📽️ SLIDESHOW ROTATION")
                self.lbl_mode_pill.setStyleSheet(f"""
                    background: rgba(0, 255, 204, 0.12);
                    color: {COLOR_CYAN};
                    border: 1px solid rgba(0, 255, 204, 0.3);
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
                self.lbl_time_pill.setText("NORMAL ROTATION")
                self.lbl_time_pill.setStyleSheet(f"""
                    background: rgba(255, 255, 255, 0.05);
                    color: {COLOR_TEXT_MUTED};
                    border: 1px solid {COLOR_CARD_BORDER};
                    border-radius: 4px;
                    padding: 4px 10px;
                """)
        except Exception:
            pass

    def closeEvent(self, event):
        self.poll_timer.stop()
        event.accept()


class MainWindow(QMainWindow):
    """Main Control Deck for BBGN multi-port gaming network."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BBGN Central Command & Arena Deck - Techlahoma")
        self.setMinimumSize(850, 550)
        self.resize(1180, 860)
        self.lan_ip = get_lan_ip()

        self.workers: Dict[str, ServiceWorker] = {}
        self.card_widgets: Dict[str, ServiceCardWidget] = {}

        self._setup_palette()
        self._build_ui()

        # Start timer to update system overview stats
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self._update_system_stats)
        self.stats_timer.start()

    def _setup_palette(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BG_DARK};
            }}
            QWidget {{
                color: {COLOR_TEXT_MAIN};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: #0d121c;
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #25334a;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLOR_CYAN};
            }}
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # =========================================================================
        # 1. TOP HEADER & NETWORK STATUS BAR (2-TIER RESPONSIVE LAYOUT)
        # =========================================================================
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet(f"""
            QFrame#topBar {{
                background-color: {COLOR_CARD_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 12px;
                padding: 10px 14px;
            }}
        """)
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(10)

        # --- Tier 1: Header, IP, Active Count, Global Controls & Fullscreen ---
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # Title & Subtitle
        brand_vbox = QVBoxLayout()
        brand_vbox.setSpacing(2)
        lbl_title = QLabel("🦬 BBGN Central Command & Service Mesh")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #ffffff;")
        brand_vbox.addWidget(lbl_title)

        lbl_sub = QLabel("Bison Bash Multi-Port Gaming Network • Single Machine Host • Isolated Terminals")
        lbl_sub.setFont(QFont("Segoe UI", 8))
        lbl_sub.setStyleSheet(f"color: {COLOR_CYAN};")
        brand_vbox.addWidget(lbl_sub)
        row1.addLayout(brand_vbox)

        row1.addStretch()

        # Network IP Pill
        ip_vbox = QVBoxLayout()
        ip_vbox.setSpacing(2)
        lbl_ip_title = QLabel("LOCAL HOST IP (FLOOR DEVICES)")
        lbl_ip_title.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl_ip_title.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        ip_vbox.addWidget(lbl_ip_title)

        ip_hrow = QHBoxLayout()
        self.lbl_ip = QLabel(self.lan_ip)
        self.lbl_ip.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.lbl_ip.setStyleSheet(f"color: {COLOR_GOLD};")
        ip_hrow.addWidget(self.lbl_ip)

        btn_copy_ip = QPushButton("Copy IP")
        btn_copy_ip.setFont(QFont("Segoe UI", 8))
        btn_copy_ip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_ip.setStyleSheet(f"""
            QPushButton {{
                background: #1b2332;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{ background: {COLOR_CYAN}; color: #000; }}
        """)
        btn_copy_ip.clicked.connect(self._copy_ip)
        ip_hrow.addWidget(btn_copy_ip)

        ip_vbox.addLayout(ip_hrow)
        row1.addLayout(ip_vbox)

        # Active Servers Counter
        self.lbl_active_count = QLabel("0 / 9 Running")
        self.lbl_active_count.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.lbl_active_count.setStyleSheet(f"""
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {COLOR_CARD_BORDER};
            color: {COLOR_TEXT_MUTED};
            border-radius: 8px;
            padding: 6px 12px;
        """)
        row1.addWidget(self.lbl_active_count)

        # Global Start All / Stop All
        btn_start_all = QPushButton("▶ Start All")
        btn_start_all.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_start_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_start_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GREEN};
                color: #000000;
                border-radius: 7px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background-color: #4cd137; }}
        """)
        btn_start_all.clicked.connect(self._start_all)
        row1.addWidget(btn_start_all)

        btn_stop_all = QPushButton("■ Stop All")
        btn_stop_all.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_stop_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_stop_all.setStyleSheet(f"""
            QPushButton {{
                background-color: #21262d;
                border: 1px solid #30363d;
                color: {COLOR_RED};
                border-radius: 7px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background-color: {COLOR_RED}; color: #fff; }}
        """)
        btn_stop_all.clicked.connect(self._stop_all)
        row1.addWidget(btn_stop_all)

        # Fullscreen Toggle Button
        self.btn_fullscreen = QPushButton("⛶ Fullscreen")
        self.btn_fullscreen.setToolTip("Toggle Fullscreen Mode (F11)")
        self.btn_fullscreen.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fullscreen.setStyleSheet(f"""
            QPushButton {{
                background-color: #16202e;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MAIN};
                border-radius: 7px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: #223147; color: #fff; border-color: {COLOR_CYAN}; }}
        """)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        row1.addWidget(self.btn_fullscreen)

        top_layout.addLayout(row1)

        # --- Tier 2: Event Station Tools & Admin Actions ---
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        lbl_tools = QLabel("QUICK TOOLS:")
        lbl_tools.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_tools.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        row2.addWidget(lbl_tools)

        # Slideshow Builder Popup Button
        btn_slideshow_bld = QPushButton("🖼️ Slideshow Builder")
        btn_slideshow_bld.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_slideshow_bld.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_slideshow_bld.setStyleSheet(f"""
            QPushButton {{
                background-color: #122822;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: {COLOR_CYAN}; color: #000; }}
        """)
        btn_slideshow_bld.clicked.connect(self._open_slideshow_builder)
        row2.addWidget(btn_slideshow_bld)

        # Presentation Builder Popup Button
        btn_pres_bld = QPushButton("📢 Presentation Builder")
        btn_pres_bld.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_pres_bld.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pres_bld.setStyleSheet(f"""
            QPushButton {{
                background-color: #2b1f12;
                border: 1px solid #ffaa00;
                color: #ffaa00;
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: #ffaa00; color: #000; }}
        """)
        btn_pres_bld.clicked.connect(self._open_presentation_builder)
        row2.addWidget(btn_pres_bld)

        # 1-Click Start Race Cut-In Button (KISS)
        btn_start_race = QPushButton("🏇 Start Race (Cut-In)")
        btn_start_race.setToolTip("1-Click KISS Cut-In: Starts 5m countdown on stadium slideshow, runs 40s race, shows results 30s, and resumes slideshow.")
        btn_start_race.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_start_race.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_start_race.setStyleSheet(f"""
            QPushButton {{
                background-color: #2b1738;
                border: 1.5px solid {COLOR_PURPLE};
                color: #e599f7;
                border-radius: 6px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{ background-color: {COLOR_PURPLE}; color: #000; }}
        """)
        btn_start_race.clicked.connect(self._trigger_start_race_cutin)
        row2.addWidget(btn_start_race)

        # Test Race Button
        btn_test_race = QPushButton("🏁 Test Race")
        btn_test_race.setToolTip("Trigger live 40s test race sprint and view the arena projector track")
        btn_test_race.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_test_race.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test_race.setStyleSheet(f"""
            QPushButton {{
                background-color: #0f2c24;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: {COLOR_CYAN}; color: #000; }}
        """)
        btn_test_race.clicked.connect(self._launch_test_race)
        row2.addWidget(btn_test_race)

        # Bison Racers & Stats Editor Button
        btn_bison_racers = QPushButton("🦬 Edit Bison Racers")
        btn_bison_racers.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_bison_racers.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bison_racers.setStyleSheet(f"""
            QPushButton {{
                background-color: #2b1f12;
                border: 1px solid {COLOR_GOLD};
                color: {COLOR_GOLD};
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: {COLOR_GOLD}; color: #000; }}
        """)
        btn_bison_racers.clicked.connect(self._open_bison_racers_editor)
        row2.addWidget(btn_bison_racers)

        # Economy & Payouts Button
        btn_economy = QPushButton("🪙 Economy & Payouts")
        btn_economy.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_economy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_economy.setStyleSheet(f"""
            QPushButton {{
                background-color: #2b2512;
                border: 1px solid {COLOR_GOLD};
                color: {COLOR_GOLD};
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: {COLOR_GOLD}; color: #000; }}
        """)
        btn_economy.clicked.connect(self._open_economy_settings)
        row2.addWidget(btn_economy)

        # Email Setup Button
        btn_email = QPushButton("✉️ Registration Email")
        btn_email.setToolTip("Edit the registration pass email subject, body text, and SMTP settings")
        btn_email.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_email.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_email.setStyleSheet(f"""
            QPushButton {{
                background-color: #172233;
                border: 1px solid {COLOR_CYAN};
                color: {COLOR_CYAN};
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: {COLOR_CYAN}; color: #000; }}
        """)
        btn_email.clicked.connect(self._open_email_settings)
        row2.addWidget(btn_email)

        row2.addStretch()

        # Clear All Players Button
        btn_clear = QPushButton("🗑️ Clear Players")
        btn_clear.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a1219;
                border: 1px solid rgba(255, 71, 87, 0.6);
                color: {COLOR_RED};
                border-radius: 6px;
                padding: 5px 11px;
            }}
            QPushButton:hover {{ background-color: {COLOR_RED}; color: #fff; }}
        """)
        btn_clear.clicked.connect(self._clear_players)
        row2.addWidget(btn_clear)

        top_layout.addLayout(row2)

        main_layout.addWidget(top_bar)

        # =========================================================================
        # 2. SCROLLABLE SERVICES LIST WITH COLLAPSIBLE TERMINAL BOXES
        # =========================================================================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.cards_vbox = QVBoxLayout(scroll_content)
        self.cards_vbox.setContentsMargins(0, 4, 8, 4)
        self.cards_vbox.setSpacing(10)

        # Instantiate workers and cards for each service
        for cfg in SERVICES_CONFIG:
            worker = ServiceWorker(cfg)
            self.workers[cfg["id"]] = worker

            card = ServiceCardWidget(cfg, worker)
            self.card_widgets[cfg["id"]] = card
            self.cards_vbox.addWidget(card)

        self.cards_vbox.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        # =========================================================================
        # 4. BOTTOM UTILITY BAR
        # =========================================================================
        bot_bar = QHBoxLayout()
        bot_bar.setSpacing(12)

        lbl_hint = QLabel("💡 Tip: Click '▼ Terminal' on any service above to toggle open its live terminal output box.")
        lbl_hint.setFont(QFont("Segoe UI", 8))
        lbl_hint.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        bot_bar.addWidget(lbl_hint)

        bot_bar.addStretch()

        btn_free_ports = QPushButton("🧹 Clean Orphaned Ports")
        btn_free_ports.setToolTip("Force-kills any hanging processes occupying ports 8000-8010.")
        btn_free_ports.setFont(QFont("Segoe UI", 8))
        btn_free_ports.setStyleSheet(f"""
            QPushButton {{
                background: #151a24;
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 5px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ color: #fff; background: #202838; }}
        """)
        btn_free_ports.clicked.connect(self._clean_all_ports)
        bot_bar.addWidget(btn_free_ports)

        main_layout.addLayout(bot_bar)

    def _copy_ip(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.lan_ip)
        QToolTip.showText(self.lbl_ip.mapToGlobal(self.lbl_ip.rect().center()), "LAN IP Copied!")

    def _start_all(self):
        for worker in self.workers.values():
            if not worker.is_running():
                worker.start()
                time.sleep(0.15) # slight stagger

    def _stop_all(self):
        for worker in self.workers.values():
            if worker.is_running():
                worker.stop()

    def _clean_all_ports(self):
        freed = 0
        for cfg in SERVICES_CONFIG:
            port = cfg["port"]
            pid = find_pid_on_port(port)
            if pid:
                kill_process_tree(pid)
                freed += 1
        QMessageBox.information(self, "Port Cleanup", f"Freed {freed} ports successfully.")

    def _open_email_settings(self):
        dialog = EmailSettingsDialog(self)
        dialog.exec()

    def _open_economy_settings(self):
        dialog = EconomySettingsDialog(self)
        dialog.exec()

    def _open_bison_racers_editor(self):
        dialog = BisonRacersDialog(self)
        dialog.exec()

    def _launch_test_race(self):
        trigger_bison_test_race(self)

    def _trigger_start_race_cutin(self):
        import master_admin.data_manager as dm
        dm.set_slideshow_countdown(minutes=5, seconds=0, title="Bison Dash: Championship Track")
        QMessageBox.information(
            self,
            "Race Cut-In Started",
            "🏇 5-Minute Race Cut-In is now ACTIVE on the Stadium Projector!\n\n"
            "• Countdown timer ticking down from 05:00 on the projector\n"
            "• Projector is cycling through all 6 bison contender display images & stats\n"
            "• Floor betting kiosks (/bet1 & /bet2) are open for wagers\n"
            "• When 5m elapses, it will automatically sprint into the 40s race\n"
            "• Race results will display for 30s, and then the slideshow will resume automatically."
        )

    def _open_slideshow_builder(self):
        dialog = SlideshowBuilderDialog(self)
        dialog.exec()

    def _open_presentation_builder(self):
        dialog = PresentationBuilderDialog(self)
        dialog.exec()

    def _clear_players(self):
        reply = QMessageBox.question(
            self,
            "Clear All Players - Confirmation",
            "Are you sure you want to delete ALL player accounts from the database?\n\n"
            "This will completely reset players.json to empty for fresh testing.\n\n"
            "This action CANNOT be undone. Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import master_admin.data_manager as dm
                dm.clear_all_players(force=True)
                QMessageBox.information(
                    self,
                    "Players Cleared",
                    "Player accounts have been cleared.\n"
                    "A safety snapshot was preserved in master_admin/data/players_safe_backup/."
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear players: {e}")

    def _update_system_stats(self):
        active_count = sum(1 for w in self.workers.values() if w.is_running())
        total = len(self.workers)
        self.lbl_active_count.setText(f"{active_count} / {total} Running")
        if active_count == total:
            self.lbl_active_count.setStyleSheet(f"""
                background: rgba(46, 213, 115, 0.15);
                border: 1px solid {COLOR_GREEN};
                color: {COLOR_GREEN};
                border-radius: 8px;
                padding: 8px 14px;
            """)
        elif active_count > 0:
            self.lbl_active_count.setStyleSheet(f"""
                background: rgba(255, 215, 0, 0.12);
                border: 1px solid {COLOR_GOLD};
                color: {COLOR_GOLD};
                border-radius: 8px;
                padding: 8px 14px;
            """)
        else:
            self.lbl_active_count.setStyleSheet(f"""
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid {COLOR_CARD_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-radius: 8px;
                padding: 8px 14px;
            """)

    def toggle_fullscreen(self):
        """Toggle true borderless fullscreen mode (F11 shortcut)."""
        if self.isFullScreen():
            self.showMaximized()
            if hasattr(self, "btn_fullscreen"):
                self.btn_fullscreen.setText("⛶ Fullscreen")
                self.btn_fullscreen.setToolTip("Toggle Fullscreen Mode (F11)")
        else:
            self.showFullScreen()
            if hasattr(self, "btn_fullscreen"):
                self.btn_fullscreen.setText("⛶ Exit Fullscreen")
                self.btn_fullscreen.setToolTip("Exit Fullscreen Mode (F11 or Esc)")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for presentation / fullscreen display."""
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showMaximized()
            if hasattr(self, "btn_fullscreen"):
                self.btn_fullscreen.setText("⛶ Fullscreen")
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Cleanly shutdown all subprocesses when closing application."""
        for worker in self.workers.values():
            if worker.is_running():
                worker.stop()
        event.accept()


def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("BBGN Central Command")

    window = MainWindow()
    # Launch maximized so it cleanly fills the desktop screen without geometry errors
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
