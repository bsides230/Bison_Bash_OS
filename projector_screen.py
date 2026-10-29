"""
Native PyQt Stadium Slideshow & Arena Projector Screen - Techlahoma Bison Bash
=============================================================================
A native PyQt presentation window designed to run off a laptop and go full-screen
on an external arena projector (or primary screen).

Features:
- Pure native PyQt UI (no browser or QWebEngine dependencies).
- Fullscreen projector output targeting (Display 1, Display 2 / Projector).
- High-resolution (1920x1080) aspect-preserved rendering of custom uploaded slides.
- Live Leaderboard slide included in the regular rotation mix, auto-refreshing scores.
- Built-in Welcome, Mobile Pass QR Code, and Game Booth showcase slides.
- Bison Dash Manual Activation Overrides:
    - Giant "Time Left Till Race" Digital Countdown Clock.
    - Visual racetrack progress bar with running cyber-bison icon.
    - Tablet betting kiosk callouts (Port 8008) and mobile pass QR code.
    - Staged Pre-Race lineup and Live Race sprint slides.
- Hotkeys: F11 (Fullscreen Toggle), Esc (Windowed Mode), Space (Pause/Resume),
           Left/Right Arrows (Skip Slide), R (Reload Manifest).
"""

import sys
import os
import io
import time
import socket
from pathlib import Path
from typing import Optional, List, Dict

import qrcode
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QProgressBar, QFrame, QSizePolicy, QApplication,
    QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QTime, QRect, QPoint
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QPainter, QBrush, QPen, QKeySequence,
    QShortcut, QLinearGradient, QFontDatabase
)

# Root repository directory
ROOT_DIR = Path(__file__).resolve().parent

# Color Palette
COLOR_BG_DARK = "#080c14"
COLOR_CARD_BG = "#111724"
COLOR_CARD_BORDER = "#1f2d44"
COLOR_CYAN = "#00ffcc"
COLOR_GOLD = "#ffd700"
COLOR_GREEN = "#2ed573"
COLOR_RED = "#ff4757"
COLOR_PURPLE = "#9b5de5"
COLOR_TEXT_MAIN = "#f0f6fc"
COLOR_TEXT_MUTED = "#8b949e"

def get_lan_ip() -> str:
    """Detects active local LAN IP for spectator QR codes."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_qr_pixmap(data: str, size: int = 240) -> QPixmap:
    """Generates a crisp scannable QR Code as a QPixmap."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pix = QPixmap()
    pix.loadFromData(buf.getvalue())
    return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


# =========================================================================
# 1. TOP HUD / HEADER BAR WIDGET
# =========================================================================

class HeaderWidget(QFrame):
    """Stadium Projector Top HUD bar with brand logo, clock, and mode status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f1522, stop:1 #080c14);
                border-bottom: 2px solid {COLOR_CARD_BORDER};
                padding: 0 24px;
            }}
        """)
        self._build_ui()

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(16)

        # Brand Logo & Title
        lbl_logo = QLabel()
        logo_path = dm.STATIC_IMG_DIR / "bison_logo.png"
        if logo_path.exists():
            lbl_logo.setPixmap(QPixmap(str(logo_path)).scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            lbl_logo.setText("🦬")
            lbl_logo.setFont(QFont("Segoe UI Emoji", 26))
        layout.addWidget(lbl_logo)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        lbl_title = QLabel("TECHLAHOMA BISON BASH")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {COLOR_GOLD}; letter-spacing: 1px;")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel("LIVE ARENA STADIUM SCREEN • OCTOBER 23RD")
        lbl_sub.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; letter-spacing: 0.5px;")
        title_vbox.addWidget(lbl_sub)
        layout.addLayout(title_vbox)

        layout.addStretch()

        # Mode Badge Pill
        self.lbl_mode_badge = QLabel("📽️ ROTATING SLIDESHOW")
        self.lbl_mode_badge.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.lbl_mode_badge.setStyleSheet(f"""
            background: rgba(0, 255, 204, 0.12);
            color: {COLOR_CYAN};
            border: 1px solid rgba(0, 255, 204, 0.4);
            border-radius: 6px;
            padding: 6px 14px;
        """)
        layout.addWidget(self.lbl_mode_badge)

        # Live Digital Clock
        self.lbl_clock = QLabel("12:00:00 PM")
        self.lbl_clock.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.lbl_clock.setStyleSheet(f"""
            color: #ffffff;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 6px;
            padding: 6px 14px;
        """)
        layout.addWidget(self.lbl_clock)

    def _update_clock(self):
        self.lbl_clock.setText(QTime.currentTime().toString("hh:mm:ss AP"))

    def set_mode(self, mode_text: str, is_race: bool = False):
        self.lbl_mode_badge.setText(mode_text)
        if is_race:
            self.lbl_mode_badge.setStyleSheet(f"""
                background: rgba(255, 71, 87, 0.2);
                color: {COLOR_RED};
                border: 1px solid {COLOR_RED};
                border-radius: 6px;
                padding: 6px 14px;
            """)
        else:
            self.lbl_mode_badge.setStyleSheet(f"""
                background: rgba(0, 255, 204, 0.12);
                color: {COLOR_CYAN};
                border: 1px solid rgba(0, 255, 204, 0.4);
                border-radius: 6px;
                padding: 6px 14px;
            """)


# =========================================================================
# 2. BASE SLIDE WIDGET
# =========================================================================

class BaseSlideWidget(QWidget):
    """Base class for all slideshow slides."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {COLOR_BG_DARK};")

    def on_activate(self):
        """Hook called when this slide becomes visible."""
        pass


# =========================================================================
# 3. CUSTOM IMAGE SLIDE (1920x1080 AUTO-RESIZED)
# =========================================================================

class CustomImageSlide(BaseSlideWidget):
    """Displays a custom user-uploaded slide image centered with smooth 1080p scaling."""
    def __init__(self, image_path: Path, title: str = "", parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.title = title
        self.pixmap: Optional[QPixmap] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"background-color: {COLOR_BG_DARK};")
        layout.addWidget(self.image_label)

        self._load_image()

    def _load_image(self):
        if self.image_path.exists():
            self.pixmap = QPixmap(str(self.image_path))
            self._update_scaled_pixmap()

    def set_image_path(self, image_path: Path, title: str = ""):
        self.image_path = Path(image_path)
        self.title = title
        self._load_image()

    def _update_scaled_pixmap(self):
        if not self.pixmap or self.pixmap.isNull():
            return
        target_size = self.size()
        if target_size.width() <= 10 or target_size.height() <= 10:
            target_size = self.parentWidget().size() if self.parentWidget() else target_size

        scaled = self.pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()


# =========================================================================
# 4. LIVE LEADERBOARD SLIDE (IN REGULAR MIX)
# =========================================================================

class LeaderboardSlide(BaseSlideWidget):
    """
    Live Arena Leaderboard slide included in the regular slideshow rotation.
    Queries master_admin.data_manager.get_all_players() each activation for real-time scores!
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 30, 60, 40)
        layout.setSpacing(20)

        # Header Title
        hdr_layout = QVBoxLayout()
        hdr_layout.setSpacing(4)
        lbl_head = QLabel("🏆 LIVE ARENA LEADERBOARD")
        lbl_head.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_GOLD}; letter-spacing: 2px;")
        lbl_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(lbl_head)

        lbl_sub = QLabel("TOP TOKEN ACCUMULATORS & ARENA CONTENDERS • REAL-TIME STANDINGS")
        lbl_sub.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLOR_CYAN}; letter-spacing: 1px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(lbl_sub)
        layout.addLayout(hdr_layout)

        # Grid of player ranking cards (Top 8-10 players)
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(16)
        layout.addLayout(self.cards_grid, stretch=1)

        # Footnote
        lbl_note = QLabel("📱 Enter your 4-digit PIN at any station or betting kiosk to play and climb the ranks!")
        lbl_note.setFont(QFont("Segoe UI", 11))
        lbl_note.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        lbl_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_note)

    def on_activate(self):
        """Live refreshes standings when slide rotates into view."""
        self._refresh_leaderboard()

    def _refresh_leaderboard(self):
        # Clear existing cards
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            import master_admin.data_manager as dm
            players = dm.get_all_players()
        except Exception:
            players = []

        # Sort by balance descending
        players.sort(key=lambda p: p.get("balance", 0), reverse=True)
        top_players = players[:10]

        if not top_players:
            lbl_empty = QLabel("⚡ No registered contestants yet! Scan QR to claim 100 starter tokens.")
            lbl_empty.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            lbl_empty.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_grid.addWidget(lbl_empty, 0, 0, 1, 2)
            return

        # Render 2 columns of 5 cards each
        for idx, p in enumerate(top_players):
            row = idx % 5
            col = idx // 5

            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {COLOR_CARD_BG};
                    border: 1px solid {COLOR_CARD_BORDER};
                    border-radius: 10px;
                    padding: 8px 16px;
                }}
            """)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(14, 8, 14, 8)
            c_layout.setSpacing(14)

            # Rank Icon / Number
            rank_str = f"#{idx+1}"
            rank_color = COLOR_TEXT_MUTED
            if idx == 0:
                rank_str = "🥇 #1"
                rank_color = COLOR_GOLD
            elif idx == 1:
                rank_str = "🥈 #2"
                rank_color = "#e2e8f0"
            elif idx == 2:
                rank_str = "🥉 #3"
                rank_color = "#cd7f32"

            lbl_rank = QLabel(rank_str)
            lbl_rank.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            lbl_rank.setStyleSheet(f"color: {rank_color};")
            lbl_rank.setFixedWidth(70)
            c_layout.addWidget(lbl_rank)

            # Name and PIN
            name_box = QVBoxLayout()
            name_box.setSpacing(2)
            lbl_name = QLabel(p.get("name") or p.get("id"))
            lbl_name.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lbl_name.setStyleSheet("color: #ffffff;")
            name_box.addWidget(lbl_name)

            lbl_pin = QLabel(f"PIN: {p.get('pin', '—')} • ID: {p.get('id', '')[:8]}")
            lbl_pin.setFont(QFont("Consolas", 9))
            lbl_pin.setStyleSheet(f"color: {COLOR_CYAN};")
            name_box.addWidget(lbl_pin)
            c_layout.addLayout(name_box, stretch=1)

            # Balance Display
            bal_box = QVBoxLayout()
            bal_box.setSpacing(1)
            bal_box.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_bal = QLabel(f"{p.get('balance', 0):,}")
            lbl_bal.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            lbl_bal.setStyleSheet(f"color: {COLOR_GOLD};")
            bal_box.addWidget(lbl_bal)

            lbl_unit = QLabel("TOKENS")
            lbl_unit.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            lbl_unit.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
            bal_box.addWidget(lbl_unit)
            c_layout.addLayout(bal_box)

            self.cards_grid.addWidget(card, row, col)


# =========================================================================
# 5. BUILT-IN SLIDE: WELCOME TO BISON BASH
# =========================================================================

class WelcomeSlide(BaseSlideWidget):
    """Hero slide welcoming attendees and highlighting venue features."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 40, 60, 50)
        layout.setSpacing(25)

        # Hero Banner
        hdr_layout = QVBoxLayout()
        hdr_layout.setSpacing(6)
        lbl_head = QLabel("WELCOME TO BISON BASH")
        lbl_head.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_GOLD}; letter-spacing: 2px;")
        lbl_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(lbl_head)

        lbl_sub = QLabel("TECHLAHOMA PREMIER RETRO GAMING & CYBER-BISON PREDICTION ARENA")
        lbl_sub.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLOR_CYAN}; letter-spacing: 1px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(lbl_sub)
        layout.addLayout(hdr_layout)

        # 3 Highlights Cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)

        card1 = self._create_feature_card(
            "🪙", "Token Bank & Cashier Desk", "Port 8005",
            "Exchange donations for game tokens. Support Techlahoma's non-profit mission while fueling your gaming!"
        )
        card2 = self._create_feature_card(
            "📱", "Instant Mobile Pass Portal", "Port 8009",
            "Scan the venue QR code from your phone to claim 100 starter tokens and receive your 4-digit PIN pass."
        )
        card3 = self._create_feature_card(
            "🦬", "Bison Dash Championship", "Port 8001",
            "Spectator tablet betting with 2.0x odds multiplier. Watch chaotic live cyber-bison sprints on this screen!"
        )

        cards_layout.addWidget(card1)
        cards_layout.addWidget(card2)
        cards_layout.addWidget(card3)
        layout.addLayout(cards_layout, stretch=1)

    def _create_feature_card(self, icon: str, title: str, port_tag: str, desc: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_CARD_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 14px;
                padding: 24px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        lbl_icon = QLabel(icon)
        lbl_icon.setFont(QFont("Segoe UI Emoji", 32))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(lbl_icon)

        lbl_t = QLabel(title)
        lbl_t.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_t.setStyleSheet("color: #ffffff;")
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(lbl_t)

        lbl_tag = QLabel(port_tag)
        lbl_tag.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        lbl_tag.setStyleSheet(f"color: {COLOR_GOLD}; background: #000; border: 1px solid {COLOR_CARD_BORDER}; border-radius: 4px; padding: 2px 8px;")
        lbl_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(lbl_tag)

        lbl_d = QLabel(desc)
        lbl_d.setFont(QFont("Segoe UI", 10))
        lbl_d.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; line-height: 1.4;")
        lbl_d.setWordWrap(True)
        lbl_d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(lbl_d)

        c_layout.addStretch()
        return card


# =========================================================================
# 6. BUILT-IN SLIDE: MOBILE PASS & QR SIGNUP
# =========================================================================

class MobilePassQrSlide(BaseSlideWidget):
    """Displays large scannable QR Code and step-by-step instructions for player pass."""
    def __init__(self, lan_ip: str, parent=None):
        super().__init__(parent)
        self.lan_ip = lan_ip
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(80, 40, 80, 50)
        layout.setSpacing(50)

        # Left Column: QR Code Display Card
        qr_card = QFrame()
        qr_card.setStyleSheet(f"""
            QFrame {{
                background: #ffffff;
                border: 4px solid {COLOR_CYAN};
                border-radius: 20px;
                padding: 20px;
            }}
        """)
        qr_layout = QVBoxLayout(qr_card)
        qr_layout.setContentsMargins(10, 10, 10, 10)
        qr_layout.setSpacing(12)

        portal_url = f"http://{self.lan_ip}:8009/"
        qr_pixmap = generate_qr_pixmap(portal_url, size=320)

        lbl_qr = QLabel()
        lbl_qr.setPixmap(qr_pixmap)
        lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(lbl_qr)

        lbl_url = QLabel(portal_url)
        lbl_url.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        lbl_url.setStyleSheet("color: #080c14;")
        lbl_url.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(lbl_url)

        layout.addWidget(qr_card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Right Column: Instructions
        info_layout = QVBoxLayout()
        info_layout.setSpacing(16)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_title = QLabel("GET YOUR INSTANT PLAYER PASS")
        lbl_title.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {COLOR_CYAN};")
        info_layout.addWidget(lbl_title)

        steps = [
            ("1. Scan with Phone Camera", "Point your smartphone camera at the QR code to open the venue portal."),
            ("2. Enter Name & Email", "Quick registration gives you your official 4-digit PIN player credential."),
            ("3. Receive Starter Tokens", "New accounts receive starter credits instantly to wager and compete."),
            ("4. Use PIN Across the Venue", "Punch your 4-digit PIN at N64, Bug Hunt, Gauntlet, and Betting Kiosks.")
        ]

        for s_title, s_desc in steps:
            s_box = QVBoxLayout()
            s_box.setSpacing(2)
            lbl_st = QLabel(s_title)
            lbl_st.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lbl_st.setStyleSheet(f"color: {COLOR_GOLD};")
            s_box.addWidget(lbl_st)

            lbl_sd = QLabel(s_desc)
            lbl_sd.setFont(QFont("Segoe UI", 10))
            lbl_sd.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
            s_box.addWidget(lbl_sd)
            info_layout.addLayout(s_box)

        layout.addLayout(info_layout, stretch=1)


# =========================================================================
# 7. BUILT-IN SLIDE: GAME BOOTHS SHOWCASE
# =========================================================================

class GameStationsSlide(BaseSlideWidget):
    """Showcases the 4 interactive mini-game booths on the floor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 40, 60, 50)
        layout.setSpacing(25)

        hdr_layout = QVBoxLayout()
        hdr_layout.setSpacing(4)
        lbl_head = QLabel("🎮 MULTI-BOOTH ARCADE STATIONS")
        lbl_head.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        lbl_head.setStyleSheet(f"color: {COLOR_PURPLE};")
        lbl_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(lbl_head)

        lbl_sub = QLabel("EARN TOKENS ACROSS ALL 4 INTERACTIVE STATIONS ON THE VENUE FLOOR")
        lbl_sub.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLOR_CYAN};")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(lbl_sub)
        layout.addLayout(hdr_layout)

        # 4 Station Cards in 1 Row
        grid = QHBoxLayout()
        grid.setSpacing(16)

        booths = [
            ("🪙", "Token Mint & Cashier", "Port 8005", "Convert cash or card to tokens, top up your PIN pass, and pick up prizes."),
            ("🐛", "Bug Bounty: Alpha", "Port 8003", "Tactile kids booth with instant 5:1 bug-to-token converter & friendly attendants."),
            ("🎮", "N64 Retro Tourney", "Port 8004", "1v1 retro tournament deck. Winner takes the tournament prize purse directly into their pass!"),
            ("⚡", "The AI Gauntlet", "Port 8007", "4-door trivia survival gauntlet with scaling token payouts and vault jackpot.")
        ]

        for icon, title, port_tag, desc in booths:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {COLOR_CARD_BG};
                    border: 1px solid {COLOR_CARD_BORDER};
                    border-radius: 12px;
                    padding: 20px 16px;
                }}
            """)
            c_box = QVBoxLayout(card)
            c_box.setSpacing(10)

            lbl_ic = QLabel(icon)
            lbl_ic.setFont(QFont("Segoe UI Emoji", 30))
            lbl_ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_box.addWidget(lbl_ic)

            lbl_t = QLabel(title)
            lbl_t.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lbl_t.setStyleSheet("color: #fff;")
            lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_box.addWidget(lbl_t)

            lbl_p = QLabel(port_tag)
            lbl_p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            lbl_p.setStyleSheet(f"color: {COLOR_GOLD}; background: #000; border-radius: 4px; padding: 2px 6px;")
            lbl_p.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_box.addWidget(lbl_p)

            lbl_d = QLabel(desc)
            lbl_d.setFont(QFont("Segoe UI", 9))
            lbl_d.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
            lbl_d.setWordWrap(True)
            lbl_d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_box.addWidget(lbl_d)

            c_box.addStretch()
            grid.addWidget(card)

        layout.addLayout(grid, stretch=1)


# =========================================================================
# 8. BISON DASH MANUAL CUT-IN: TIME LEFT TILL RACE (COUNTDOWN SLIDE)
# =========================================================================

class BisonCountdownSlide(BaseSlideWidget):
    """
    Dedicated Stadium Countdown Slide for Bison Dash races.
    Displays:
    - Giant digital countdown clock (MM:SS).
    - Visual racetrack with animated running cyber-bison icon.
    - Tablet Betting Kiosks (Port 8008, 2.0x odds).
    - Instant mobile pass QR code.
    """
    def __init__(self, lan_ip: str, parent=None):
        super().__init__(parent)
        self.lan_ip = lan_ip
        self.target_timestamp = 0
        self.total_duration = 180
        self.race_title = "Next Bison Dash Race"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(80, 30, 80, 40)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Race Alert Pill
        alert_box = QHBoxLayout()
        lbl_alert = QLabel("🔴 UPCOMING ARENA RACE • WAGERS OPEN AT TABLET KIOSKS")
        lbl_alert.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_alert.setStyleSheet(f"""
            background: rgba(255, 71, 87, 0.15);
            color: {COLOR_RED};
            border: 2px solid {COLOR_RED};
            border-radius: 20px;
            padding: 6px 20px;
            letter-spacing: 1px;
        """)
        alert_box.addWidget(lbl_alert, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(alert_box)

        # Race Title Banner
        self.lbl_race_title = QLabel("Bison Dash: Championship Track")
        self.lbl_race_title.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.lbl_race_title.setStyleSheet(f"color: {COLOR_GOLD}; letter-spacing: 1px;")
        self.lbl_race_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_race_title)

        # Giant Digital Timer Box
        timer_box = QFrame()
        timer_box.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121929, stop:1 #0b0f19);
                border: 3px solid rgba(0, 255, 204, 0.5);
                border-radius: 24px;
                padding: 16px 40px;
            }}
        """)
        tb_layout = QVBoxLayout(timer_box)
        tb_layout.setContentsMargins(30, 10, 30, 14)
        tb_layout.setSpacing(0)

        self.lbl_timer_clock = QLabel("03:00")
        self.lbl_timer_clock.setFont(QFont("Consolas", 72, QFont.Weight.Bold))
        self.lbl_timer_clock.setStyleSheet(f"color: {COLOR_CYAN}; letter-spacing: 4px;")
        self.lbl_timer_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_layout.addWidget(self.lbl_timer_clock)

        lbl_tl = QLabel("TIME LEFT TILL RACE")
        lbl_tl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_tl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; letter-spacing: 2px;")
        lbl_tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_layout.addWidget(lbl_tl)
        layout.addWidget(timer_box, alignment=Qt.AlignmentFlag.AlignCenter)

        # Racetrack Progress Bar with Running Bison Icon
        track_container = QWidget()
        track_container.setFixedHeight(50)
        track_container.setMinimumWidth(800)
        self.track_layout = QVBoxLayout(track_container)
        self.track_layout.setContentsMargins(0, 0, 0, 0)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CYAN}, stop:1 {COLOR_GOLD});
                border-radius: 8px;
            }}
        """)
        self.track_layout.addWidget(self.progress_bar)

        # Runner Icon
        self.lbl_runner = QLabel(track_container)
        logo_path = dm.STATIC_IMG_DIR / "bison_logo.png"
        if logo_path.exists():
            self.lbl_runner.setPixmap(QPixmap(str(logo_path)).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.lbl_runner.setText("🦬")
            self.lbl_runner.setFont(QFont("Segoe UI Emoji", 24))
        self.lbl_runner.move(0, -6)
        layout.addWidget(track_container)

        # Callouts Row: Betting Kiosks & QR Code
        callouts_row = QHBoxLayout()
        callouts_row.setSpacing(20)

        # Betting Kiosk Guidance Card
        kiosk_card = QFrame()
        kiosk_card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_CARD_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 14px;
                padding: 16px 20px;
            }}
        """)
        k_layout = QHBoxLayout(kiosk_card)
        k_layout.setSpacing(16)

        lbl_k_icon = QLabel("🎰")
        lbl_k_icon.setFont(QFont("Segoe UI Emoji", 28))
        k_layout.addWidget(lbl_k_icon)

        k_info = QVBoxLayout()
        k_info.setSpacing(3)
        lbl_kt = QLabel("Tablet Betting Kiosks (Ports 8008 & 8012)")
        lbl_kt.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_kt.setStyleSheet("color: #ffffff;")
        k_info.addWidget(lbl_kt)

        lbl_kd = QLabel("Punch in your 4-digit PIN at any floor tablet to back a cyber-bison!")
        lbl_kd.setFont(QFont("Segoe UI", 9))
        lbl_kd.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        k_info.addWidget(lbl_kd)

        lbl_kh = QLabel("2.0x Win Payout • Min Bet: 1 Token")
        lbl_kh.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_kh.setStyleSheet(f"color: {COLOR_GOLD};")
        k_info.addWidget(lbl_kh)
        k_layout.addLayout(k_info)
        callouts_row.addWidget(kiosk_card, stretch=1)

        # Mobile Pass Fast QR Code Card
        qr_card = QFrame()
        qr_card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_CARD_BG};
                border: 1px solid {COLOR_CYAN};
                border-radius: 14px;
                padding: 10px 16px;
            }}
        """)
        q_layout = QHBoxLayout(qr_card)
        q_layout.setSpacing(14)

        portal_url = f"http://{self.lan_ip}:8009/"
        qr_mini = generate_qr_pixmap(portal_url, size=74)
        lbl_q_img = QLabel()
        lbl_q_img.setPixmap(qr_mini)
        q_layout.addWidget(lbl_q_img)

        q_info = QVBoxLayout()
        q_info.setSpacing(2)
        lbl_qt = QLabel("Instant Mobile Pass")
        lbl_qt.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_qt.setStyleSheet("color: #ffffff;")
        q_info.addWidget(lbl_qt)

        lbl_qd = QLabel("Scan to claim starter tokens & check balance.")
        lbl_qd.setFont(QFont("Segoe UI", 8))
        lbl_qd.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        q_info.addWidget(lbl_qd)

        lbl_qu = QLabel(portal_url)
        lbl_qu.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        lbl_qu.setStyleSheet(f"color: {COLOR_CYAN};")
        q_info.addWidget(lbl_qu)
        q_layout.addLayout(q_info)
        callouts_row.addWidget(qr_card)

        layout.addLayout(callouts_row)

    def set_countdown(self, target_ts: float, total_sec: int, title: str = ""):
        self.target_timestamp = target_ts
        self.total_duration = max(5, total_sec)
        if title:
            self.lbl_race_title.setText(title)
        self.update_tick()

    def update_tick(self):
        now = time.time()
        rem = max(0, int(self.target_timestamp - now))
        mins = rem // 60
        secs = rem % 60
        self.lbl_timer_clock.setText(f"{mins:02d}:{secs:02d}")

        # Danger pulse under 30s
        if rem <= 30:
            self.lbl_timer_clock.setStyleSheet(f"color: {COLOR_RED}; letter-spacing: 4px;")
        else:
            self.lbl_timer_clock.setStyleSheet(f"color: {COLOR_CYAN}; letter-spacing: 4px;")

        # Progress bar fill (0 -> 1000)
        elapsed = self.total_duration - rem
        pct = max(0.0, min(1.0, elapsed / self.total_duration))
        self.progress_bar.setValue(int(pct * 1000))

        # Position runner icon along the width
        track_w = self.progress_bar.width()
        if track_w > 50:
            x_pos = int(pct * (track_w - 30))
            self.lbl_runner.move(x_pos, -6)


# =========================================================================
# 9. STAGED PRE-RACE & LIVE RACE PLACEHOLDER SLIDES
# =========================================================================

class BisonPreRaceSlide(BaseSlideWidget):
    """Staged slide for introducing contestants once betting locks."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        lbl_icon = QLabel("🏁")
        lbl_icon.setFont(QFont("Segoe UI Emoji", 48))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_icon)

        lbl_t = QLabel("BISON DASH: PRE-RACE LINEUP")
        lbl_t.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        lbl_t.setStyleSheet(f"color: {COLOR_PURPLE};")
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_t)

        lbl_sub = QLabel("WAGERS LOCKED • INTRODUCING THE CYBER-BISON RUNNERS")
        lbl_sub.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLOR_CYAN};")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)


class BisonLiveRaceSlide(BaseSlideWidget):
    """Staged slide for live race track sprints."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        lbl_icon = QLabel("🏇")
        lbl_icon.setFont(QFont("Segoe UI Emoji", 48))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_icon)

        lbl_t = QLabel("BISON DASH: LIVE ARENA SPRINT!")
        lbl_t.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        lbl_t.setStyleSheet(f"color: {COLOR_CYAN};")
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_t)

        lbl_sub = QLabel("THE GATE HAS DROPPED • SPRINTING TOWARDS THE FINISH LINE")
        lbl_sub.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLOR_GOLD};")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)


# =========================================================================
# 10. BOTTOM TICKER / PROGRESS BAR WIDGET
# =========================================================================

class BottomProgressBarWidget(QFrame):
    """Bottom presentation progress bar showing slide advance timer and hotkey hints."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            QFrame {{
                background: #080c14;
                border-top: 1px solid {COLOR_CARD_BORDER};
                padding: 0 20px;
            }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(14)

        self.lbl_slide_info = QLabel("Slide 1 of 5 • Welcome")
        self.lbl_slide_info.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_slide_info.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.lbl_slide_info)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_CYAN};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar, stretch=1)

        self.lbl_hints = QLabel("F11: Fullscreen | Esc: Window | Space: Pause | ◀ ▶: Skip")
        self.lbl_hints.setFont(QFont("Segoe UI", 8))
        self.lbl_hints.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        layout.addWidget(self.lbl_hints)


# =========================================================================
# 11. MAIN NATIVE PROJECTOR WINDOW
# =========================================================================

class NativeProjectorWindow(QMainWindow):
    """
    Dedicated Native PyQt Presentation Window for the Stadium Projector.
    - Fullscreen projector placement.
    - Automatic rotation between custom 1080p images, live leaderboard, and builtins.
    - Instant override cut-in to Bison Dash Countdown Slide on manual trigger.
    """
    mode_changed = pyqtSignal(str) # "Slideshow", "Race Countdown", "Pre-Race", "Live Race"

    def __init__(self, target_screen=None, lan_ip: str = "127.0.0.1", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Techlahoma Bison Bash - Stadium Projector Screen")
        self.setStyleSheet(f"background-color: {COLOR_BG_DARK};")
        self.lan_ip = lan_ip
        self.is_paused = False

        # Slides playlist and tracking
        self.playlist: List[Dict] = []
        self.current_slide_idx = 0
        self.slide_elapsed_ms = 0
        self.slide_duration_ms = 10000

        # Build UI layout
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top HUD
        self.header = HeaderWidget(self)
        main_layout.addWidget(self.header)

        # 2. Central Stacked Widget
        self.stack = QStackedWidget(self)
        self.stack.setStyleSheet(f"background-color: {COLOR_BG_DARK};")
        main_layout.addWidget(self.stack, stretch=1)

        # 3. Bottom Progress Bar
        self.bottom_bar = BottomProgressBarWidget(self)
        main_layout.addWidget(self.bottom_bar)

        # Instantiate persistent Bison Dash & Presentation override slides
        self.countdown_slide = BisonCountdownSlide(lan_ip=self.lan_ip)
        self.prerace_slide = BisonPreRaceSlide()
        self.liverace_slide = BisonLiveRaceSlide()
        self.presentation_slide = CustomImageSlide(Path(""), title="Stage Presentation")
        self.last_restart_trigger = 0.0

        self.stack.addWidget(self.countdown_slide) # Special index
        self.stack.addWidget(self.prerace_slide)
        self.stack.addWidget(self.liverace_slide)
        self.stack.addWidget(self.presentation_slide)

        # Keyboard Shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.next_slide)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.prev_slide)
        QShortcut(QKeySequence(Qt.Key.Key_R), self, self.reload_manifest)

        # Slide Rotation Tick Timer (ticks every 100ms for smooth progress bar)
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(100)
        self.tick_timer.timeout.connect(self._on_tick)
        self.tick_timer.start()

        # State Polling Timer (Checks for Bison Dash Countdown triggers every 400ms)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(400)
        self.poll_timer.timeout.connect(self._poll_arena_state)
        self.poll_timer.start()

        # Build initial deck from manifest
        self.reload_manifest()

        # Target screen setup
        if target_screen:
            self.set_target_screen(target_screen)

    def set_target_screen(self, screen):
        """Positions this window on the target monitor and goes full-screen."""
        self.setScreen(screen)
        geom = screen.geometry()
        self.move(geom.x(), geom.y())
        self.resize(geom.width(), geom.height())
        self.showFullScreen()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        status = " (PAUSED)" if self.is_paused else ""
        self._update_bottom_bar()

    def reload_manifest(self):
        """Loads slides_manifest.json and populates the slide deck."""
        import master_admin.data_manager as dm
        manifest = dm.get_slides_manifest()
        raw_slides = manifest.get("slides", [])

        # Remove existing dynamic slides from stack (keep the last 4 override slides)
        while self.stack.count() > 4:
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()

        self.playlist = []

        # Build slide widgets in order
        insert_idx = 0
        for s in raw_slides:
            if not s.get("enabled", True):
                continue

            s_type = s.get("type")
            s_id = s.get("id")
            s_title = s.get("title", "")
            duration = int(s.get("duration", 10))

            widget = None
            if s_type == "custom_image":
                filename = s.get("filename", "")
                img_path = dm.SLIDES_DIR / filename
                widget = CustomImageSlide(image_path=img_path, title=s_title)
            elif s_type == "leaderboard":
                widget = LeaderboardSlide()
            elif s_id == "builtin_welcome":
                widget = WelcomeSlide()
            elif s_id == "builtin_qr":
                widget = MobilePassQrSlide(lan_ip=self.lan_ip)
            elif s_id == "builtin_booths":
                widget = GameStationsSlide()
            else:
                widget = WelcomeSlide()

            self.stack.insertWidget(insert_idx, widget)
            self.playlist.append({
                "widget": widget,
                "title": s_title,
                "duration": duration,
                "type": s_type
            })
            insert_idx += 1

        if self.playlist:
            self.current_slide_idx = 0
            self.slide_elapsed_ms = 0
            self.slide_duration_ms = self.playlist[0]["duration"] * 1000
            self.stack.setCurrentIndex(0)
            self.playlist[0]["widget"].on_activate()
            self._update_bottom_bar()

    def next_slide(self):
        if not self.playlist:
            return
        self.current_slide_idx = (self.current_slide_idx + 1) % len(self.playlist)
        self._show_playlist_slide(self.current_slide_idx)

    def prev_slide(self):
        if not self.playlist:
            return
        self.current_slide_idx = (self.current_slide_idx - 1 + len(self.playlist)) % len(self.playlist)
        self._show_playlist_slide(self.current_slide_idx)

    def _show_playlist_slide(self, idx: int):
        self.current_slide_idx = idx
        self.slide_elapsed_ms = 0
        item = self.playlist[idx]
        self.slide_duration_ms = item["duration"] * 1000
        self.stack.setCurrentWidget(item["widget"])
        item["widget"].on_activate()
        self._update_bottom_bar()

    def _update_bottom_bar(self):
        if not self.playlist:
            return
        item = self.playlist[self.current_slide_idx]
        paused = " [PAUSED]" if self.is_paused else ""
        type_str = " (Live Leaderboard)" if item["type"] == "leaderboard" else ""
        self.bottom_bar.lbl_slide_info.setText(
            f"Slide {self.current_slide_idx + 1} of {len(self.playlist)} • {item['title']}{type_str}{paused}"
        )

    def _on_tick(self):
        """Called every 100ms: updates slide countdown and running bison position."""
        # 1. Update countdown tick if countdown slide is active
        if self.stack.currentWidget() == self.countdown_slide:
            self.countdown_slide.update_tick()
            return

        if self.is_paused:
            return

        # 2. Advance regular playlist timer
        self.slide_elapsed_ms += 100
        pct = min(100, int((self.slide_elapsed_ms / self.slide_duration_ms) * 100))
        self.bottom_bar.progress_bar.setValue(pct)

        if self.slide_elapsed_ms >= self.slide_duration_ms:
            self.next_slide()

    def _poll_arena_state(self):
        """Monitors slideshow_state.json for manual Bison Dash countdown, presentation & race triggers."""
        try:
            import master_admin.data_manager as dm
            state = dm.get_slideshow_state()
            mode = state.get("mode", "slideshow")
            cd = state.get("countdown", {})
            pres = state.get("presentation", {})

            # Handle restart regular trigger
            trigger = float(state.get("restart_trigger", 0))
            if trigger > self.last_restart_trigger:
                self.last_restart_trigger = trigger
                self.current_slide_idx = 0
                if self.playlist:
                    self._show_playlist_slide(0)

            if mode == "bison_countdown" and cd.get("active"):
                target = cd.get("target_timestamp", 0)
                dur = cd.get("duration_seconds", 180)
                title = cd.get("title", "Next Bison Dash Race")

                self.countdown_slide.set_countdown(target, dur, title)
                if self.stack.currentWidget() != self.countdown_slide:
                    self.stack.setCurrentWidget(self.countdown_slide)
                    self.header.set_mode("⏱️ RACE COUNTDOWN IN PROGRESS", is_race=True)
                    self.bottom_bar.lbl_slide_info.setText(f"OVERRIDE: {title} (Countdown Active)")
                    self.mode_changed.emit("Race Countdown")
            elif mode == "presentation" or pres.get("active"):
                pres_slides = dm.get_presentation_slides()
                cur_idx = pres.get("current_index", 0)
                total_pres = len(pres_slides)
                if total_pres > 0:
                    valid_idx = max(0, min(cur_idx, total_pres - 1))
                    target_slide = pres_slides[valid_idx]
                    img_file = dm.SLIDES_DIR / target_slide.get("filename", "")
                    self.presentation_slide.set_image_path(img_file, target_slide.get("title", "Presentation"))
                    self.bottom_bar.lbl_slide_info.setText(f"STAGE PRESENTATION: Slide {valid_idx + 1} of {total_pres} - {target_slide.get('title', '')}")
                else:
                    self.bottom_bar.lbl_slide_info.setText("STAGE PRESENTATION: (No slides uploaded)")

                if self.stack.currentWidget() != self.presentation_slide:
                    self.stack.setCurrentWidget(self.presentation_slide)
                    self.header.set_mode(f"📢 PRESENTATION (SLIDE {cur_idx + 1}/{total_pres})", is_race=False)
                    self.mode_changed.emit("Presentation")
            elif mode == "bison_prerace":
                if self.stack.currentWidget() != self.prerace_slide:
                    self.stack.setCurrentWidget(self.prerace_slide)
                    self.header.set_mode("🏁 PRE-RACE LINEUP", is_race=True)
                    self.bottom_bar.lbl_slide_info.setText("OVERRIDE: Pre-Race Lineup Slide")
                    self.mode_changed.emit("Pre-Race")
            elif mode == "bison_race":
                if self.stack.currentWidget() != self.liverace_slide:
                    self.stack.setCurrentWidget(self.liverace_slide)
                    self.header.set_mode("🏇 LIVE RACE SPRINT", is_race=True)
                    self.bottom_bar.lbl_slide_info.setText("OVERRIDE: Live Race Track Sprint")
                    self.mode_changed.emit("Live Race")
            else:
                # Regular slideshow mode
                if self.stack.currentWidget() in [self.countdown_slide, self.prerace_slide, self.liverace_slide, self.presentation_slide]:
                    self.header.set_mode("📽️ ROTATING SLIDESHOW", is_race=False)
                    if self.playlist:
                        self._show_playlist_slide(self.current_slide_idx)
                    self.mode_changed.emit("Slideshow")
        except Exception:
            pass


ProjectorWindow = NativeProjectorWindow


# Standalone runner for testing or launching directly
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BBGN Stadium Projector")
    win = NativeProjectorWindow(lan_ip=get_lan_ip())
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
