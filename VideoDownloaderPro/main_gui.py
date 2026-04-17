#!/usr/bin/env python3
"""
Video Downloader Pro v5.0 - PySide6 Edition
Beautiful interface in Spicetify Manager style with full download logic
"""

import sys
import os
import json
import time
import shutil
import zipfile
import platform
import subprocess
import re
import tempfile
import threading
import urllib.request
import ssl
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

# Windows: установка AppUserModelID для корректной иконки в панели задач
if platform.system() == 'Windows':
    try:
        import ctypes
        # Уникальный ID приложения
        app_id = 'VideoDownloaderPro.App.5.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGraphicsOpacityEffect,
    QSizePolicy, QDialog, QScrollArea, QLineEdit, QGridLayout
)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QIcon, QPen, QBrush, QLinearGradient, QPixmap


# ============================================================
# ВСТРОЕННАЯ ИКОНКА (генерируется программно)
# ============================================================

def resource_path(relative_path):
    """Получить путь к ресурсу (работает и в exe и в dev режиме)"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_app_icon():
    """Получить иконку приложения"""
    icon = QIcon()
    for path in [resource_path("assets/icon.png"), resource_path("assets/icon.ico"), resource_path("icon.png"), resource_path("icon.ico")]:
        if os.path.exists(path):
            icon.addFile(path)
            break
    return icon

# ============================================================
# КОНСТАНТЫ И НАСТРОЙКИ
# ============================================================

FPS_75 = 13
APP_VERSION = "5.0"

# PowerShell-style font
MAIN_FONT = "Cascadia Code"
FALLBACK_FONT = "Consolas"
MONO_FONT_FAMILY = f"'{MAIN_FONT}', '{FALLBACK_FONT}', 'Courier New', monospace"

if platform.system() == 'Windows':
    DEFAULT_DOWNLOAD_FOLDER = os.path.join(
        os.environ.get('USERPROFILE', os.path.expanduser('~')),
        'Downloads', 'VideoDownloader'
    )
    APP_FOLDER = os.path.join(
        os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
        'VideoDownloaderPro'
    )
else:
    DEFAULT_DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads', 'VideoDownloader')
    APP_FOLDER = os.path.join(os.path.expanduser('~'), '.local', 'share', 'VideoDownloaderPro')

BIN_FOLDER = os.path.join(APP_FOLDER, 'bin')
CONFIG_FILE = os.path.join(APP_FOLDER, 'config.json')
SETTINGS_FILE = os.path.join(APP_FOLDER, 'settings.json')

# ============================================================
# ЗЕРКАЛА ДЛЯ СКАЧИВАНИЯ (fallback URLs)
# ============================================================

DOWNLOAD_MIRRORS = {
    'yt-dlp_windows': [
        'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
        'https://github.com/yt-dlp/yt-dlp/releases/download/2024.08.06/yt-dlp.exe',
        'https://objects.githubusercontent.com/github-production-release-asset-2e65be/309587873/latest/yt-dlp.exe',
    ],
    'yt-dlp_linux': [
        'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp',
        'https://github.com/yt-dlp/yt-dlp/releases/download/2024.08.06/yt-dlp',
    ],
    'ffmpeg_windows': [
        'https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
    ],
    'ffmpeg_linux': [
        'https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
    ]
}

# ============================================================
# ФОРМАТЫ
# ============================================================

@dataclass
class FormatOption:
    id: str
    name: str
    description: str
    format_str: str
    is_audio: bool
    needs_merge: bool
    audio_codec: str = ""
    audio_bitrate: str = ""
    color: tuple = (34, 211, 238)
    icon: str = ""


FORMATS = [
    # Video formats - без ограничения контейнера, чтобы брать VP9/AV1 (лучшее качество)
    # Best Quality и 4K - розовый цвет
    FormatOption("1", "Best Quality", "8K/4K/2K - Auto", "bestvideo+bestaudio/best", False, True, color=(220, 120, 180), icon="⬆"),
    FormatOption("2", "4K Ultra HD", "2160p", "bestvideo[height<=2160]+bestaudio/best[height<=2160]", False, True, color=(220, 120, 180), icon="4K"),
    # 2K и Full HD - зелёный цвет
    FormatOption("3", "2K Quad HD", "1440p", "bestvideo[height<=1440]+bestaudio/best[height<=1440]", False, True, color=(100, 200, 120), icon="2K"),
    FormatOption("4", "Full HD", "1080p", "bestvideo[height<=1080]+bestaudio/best[height<=1080]", False, True, color=(100, 200, 120), icon="HD"),
    # Остальные без изменений
    FormatOption("5", "HD", "720p", "bestvideo[height<=720]+bestaudio/best[height<=720]", False, True, color=(255, 180, 50), icon=""),
    FormatOption("6", "SD", "480p", "bestvideo[height<=480]+bestaudio/best[height<=480]", False, True, color=(255, 180, 50), icon=""),
    FormatOption("7", "Low", "360p", "bestvideo[height<=360]+bestaudio/best[height<=360]", False, True, color=(150, 150, 150), icon=""),
    FormatOption("8", "Very Low", "240p", "bestvideo[height<=240]+bestaudio/best[height<=240]", False, True, color=(150, 150, 150), icon=""),
    FormatOption("9", "Minimum", "144p", "worst", False, False, color=(100, 100, 100), icon=""),
    # Audio formats
    FormatOption("10", "MP3 320kbps", "Best MP3", "", True, False, "mp3", "320", (180, 120, 255), "♪"),
    FormatOption("11", "MP3 192kbps", "Standard", "", True, False, "mp3", "192", (180, 120, 255), "♪"),
    FormatOption("12", "MP3 128kbps", "Compact", "", True, False, "mp3", "128", (180, 120, 255), "♪"),
    FormatOption("13", "AAC 256kbps", "High Quality", "", True, False, "aac", "256", (255, 100, 150), "♪"),
    FormatOption("14", "FLAC", "Lossless", "", True, False, "flac", "0", (255, 100, 150), "♪"),
    FormatOption("15", "WAV", "Uncompressed", "", True, False, "wav", "0", (255, 100, 150), "♪"),
    FormatOption("16", "M4A", "Apple Format", "", True, False, "m4a", "256", (255, 100, 150), "♪"),
    FormatOption("17", "OPUS", "Best Compression", "", True, False, "opus", "0", (255, 100, 150), "♪"),
]

# ============================================================
# ЛОКАЛИЗАЦИЯ
# ============================================================

TRANSLATIONS = {
    "ru": {
        "app_title": "VIDEO DOWNLOADER PRO",
        "window_title": "Video Downloader Pro",
        "subtitle": "Скачивайте видео с 1000+ сайтов",
        "enter_url": "Введите URL видео",
        "url_placeholder": "Вставьте ссылку на YouTube, TikTok, Instagram...",
        "btn_search": "Поиск",
        "btn_paste": "Вставить",
        "btn_clear": "Очистить",
        "btn_download": "Скачать",
        "btn_cancel": "Отмена",
        "btn_back": "Назад",
        "btn_open_folder": "Открыть папку",
        "btn_home": "Домой",
        "btn_install": "Установить",
        "btn_uninstall": "Удалить",
        "btn_change": "Изменить",
        "status_ready": "Готов к работе",
        "status_ytdlp_ready": "● yt-dlp готов",
        "status_ytdlp_missing": "○ yt-dlp не установлен",
        "status_ffmpeg_ready": "● ffmpeg готов",
        "status_ffmpeg_missing": "○ ffmpeg не установлен",
        "fetching_info": "Получение информации о видео...",
        "select_quality": "Выберите качество",
        "video_formats": " ВИДЕО",
        "audio_formats": " ТОЛЬКО АУДИО",
        "downloading": "Скачивание...",
        "downloading_video": "Скачивание видео...",
        "downloading_audio": "Скачивание аудио...",
        "merging": "Объединение видео и аудио...",
        "extracting_audio": "Извлечение аудио...",
        "download_complete": "Скачивание завершено!",
        "download_cancelled": "Скачивание отменено",
        "download_failed": "Ошибка скачивания",
        "saved_to": "Сохранено в:",
        "components": "Компоненты",
        "components_title": "МЕНЕДЖЕР КОМПОНЕНТОВ",
        "ytdlp_desc": "Основной движок скачивания. Поддерживает 1000+ сайтов.",
        "ffmpeg_desc": "Для объединения видео+аудио и конвертации форматов.",
        "download_folder": "Папка загрузок",
        "installing": "Установка...",
        "downloading_ytdlp": "Скачивание yt-dlp...",
        "downloading_ffmpeg": "Скачивание FFmpeg (~90MB)...",
        "install_success": "Успешно установлено!",
        "install_failed": "Ошибка установки",
        "uninstall_confirm": "Вы уверены, что хотите удалить",
        "uninstalled": "Удалено",
        "error": "Ошибка",
        "error_empty_url": "Введите URL!",
        "error_no_ytdlp": "yt-dlp не установлен. Перейдите в Компоненты.",
        "error_fetch_failed": "Не удалось получить информацию о видео",
        "platforms": "YouTube • TikTok • Instagram • Twitter/X • Vimeo • VK • Facebook • Twitch • и 1000+ других",
        "speed": "Скорость",
        "eta": "Осталось",
        "size": "Размер",
        "views": "просмотров",
        "footer_copyright": "© 2024 Video Downloader Pro. Все права защищены.",
        "footer_powered": "Powered by yt-dlp + FFmpeg",
        "nav_home": "Главная",
        "nav_components": "Компоненты",
        "nav_folder": "Папка загрузок",
        "auto_install_title": "УСТАНОВКА КОМПОНЕНТОВ",
        "auto_install_desc": "Для работы необходимо установить компоненты",
        "auto_install_ytdlp": "yt-dlp — движок скачивания",
        "auto_install_ffmpeg": "FFmpeg — обработка медиа",
        "auto_install_complete": "Все компоненты установлены!",
        "auto_install_btn": "Установить всё",
        "error_no_components": "Компоненты не установлены! Перейдите в ⚙ Компоненты.",
    },
    "en": {
        "app_title": "VIDEO DOWNLOADER PRO",
        "window_title": "Video Downloader Pro",
        "subtitle": "Download videos from 1000+ sites",
        "enter_url": "Enter Video URL",
        "url_placeholder": "Paste YouTube, TikTok, Instagram link...",
        "btn_search": "Search",
        "btn_paste": "Paste",
        "btn_clear": "Clear",
        "btn_download": "Download",
        "btn_cancel": "Cancel",
        "btn_back": "Back",
        "btn_open_folder": "Open Folder",
        "btn_home": "Home",
        "btn_install": "Install",
        "btn_uninstall": "Uninstall",
        "btn_change": "Change",
        "status_ready": "Ready",
        "status_ytdlp_ready": "● yt-dlp ready",
        "status_ytdlp_missing": "○ yt-dlp not installed",
        "status_ffmpeg_ready": "● ffmpeg ready",
        "status_ffmpeg_missing": "○ ffmpeg not installed",
        "fetching_info": "Fetching video information...",
        "select_quality": "Select Quality",
        "video_formats": " VIDEO",
        "audio_formats": " AUDIO ONLY",
        "downloading": "Downloading...",
        "downloading_video": "Downloading video...",
        "downloading_audio": "Downloading audio...",
        "merging": "Merging video and audio...",
        "extracting_audio": "Extracting audio...",
        "download_complete": "Download Complete!",
        "download_cancelled": "Download cancelled",
        "download_failed": "Download failed",
        "saved_to": "Saved to:",
        "components": "Components",
        "components_title": "COMPONENTS MANAGER",
        "ytdlp_desc": "Core download engine. Supports 1000+ sites.",
        "ffmpeg_desc": "For merging video+audio and format conversion.",
        "download_folder": "Download Folder",
        "installing": "Installing...",
        "downloading_ytdlp": "Downloading yt-dlp...",
        "downloading_ffmpeg": "Downloading FFmpeg (~90MB)...",
        "install_success": "Successfully installed!",
        "install_failed": "Installation failed",
        "uninstall_confirm": "Are you sure you want to uninstall",
        "uninstalled": "Uninstalled",
        "error": "Error",
        "error_empty_url": "Please enter URL!",
        "error_no_ytdlp": "yt-dlp not installed. Go to Components.",
        "error_fetch_failed": "Could not fetch video info",
        "platforms": "YouTube • TikTok • Instagram • Twitter/X • Vimeo • VK • Facebook • Twitch • and 1000+ more",
        "speed": "Speed",
        "eta": "ETA",
        "size": "Size",
        "views": "views",
        "footer_copyright": "© 2024 Video Downloader Pro. All rights reserved.",
        "footer_powered": "Powered by yt-dlp + FFmpeg",
        "nav_home": "Home",
        "nav_components": "Components",
        "nav_folder": "Download Folder",
        "auto_install_title": "INSTALLING COMPONENTS",
        "auto_install_desc": "Components are required for the app to work",
        "auto_install_ytdlp": "yt-dlp — download engine",
        "auto_install_ffmpeg": "FFmpeg — media processing",
        "auto_install_complete": "All components installed!",
        "auto_install_btn": "Install All",
        "error_no_components": "Components not installed! Go to ⚙ Components.",
    }
}

_current_language = None

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"language": "en"}

def save_settings(settings):
    os.makedirs(APP_FOLDER, exist_ok=True)
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_current_language():
    global _current_language
    if _current_language is None:
        _current_language = load_settings().get("language", "en")
    return _current_language

def set_current_language(lang):
    global _current_language
    _current_language = lang
    settings = load_settings()
    settings["language"] = lang
    save_settings(settings)

def get_text(key, lang=None):
    if lang is None:
        lang = get_current_language()
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


# ============================================================
# ПЕРЕКЛЮЧАТЕЛЬ ЯЗЫКА
# ============================================================

class LanguageToggle(QWidget):
    language_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._enabled = True
        self._hover_ru = False
        self._hover_en = False
        self._ru_brightness = 0.0
        self._en_brightness = 0.0
        self.setMouseTracking(True)
        self._is_english = get_current_language() == "en"
        
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.start(30)
    
    def _animate_hover(self):
        changed = False
        if self._hover_ru and self._enabled and self._is_english:
            if self._ru_brightness < 1.0:
                self._ru_brightness = min(1.0, self._ru_brightness + 0.15)
                changed = True
        else:
            if self._ru_brightness > 0.0:
                self._ru_brightness = max(0.0, self._ru_brightness - 0.15)
                changed = True
        if self._hover_en and self._enabled and not self._is_english:
            if self._en_brightness < 1.0:
                self._en_brightness = min(1.0, self._en_brightness + 0.15)
                changed = True
        else:
            if self._en_brightness > 0.0:
                self._en_brightness = max(0.0, self._en_brightness - 0.15)
                changed = True
        if changed:
            self.update()
    
    def setEnabled(self, enabled):
        self._enabled = enabled
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)
        self.update()
    
    def mouseMoveEvent(self, event):
        if not self._enabled:
            return
        x = event.position().x()
        self._hover_ru = x < self.width() / 2
        self._hover_en = x >= self.width() / 2
    
    def leaveEvent(self, event):
        self._hover_ru = self._hover_en = False
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._enabled:
            x = event.position().x()
            if x < self.width() / 2 and self._is_english:
                self._is_english = False
                self.language_changed.emit("ru")
            elif x >= self.width() / 2 and not self._is_english:
                self._is_english = True
                self.language_changed.emit("en")
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        w, h = self.width(), self.height()
        
        if self._enabled:
            painter.setPen(QPen(QColor(60, 60, 65), 1))
            painter.setBrush(QColor(25, 25, 30, 200))
        else:
            painter.setPen(QPen(QColor(40, 40, 45), 1))
            painter.setBrush(QColor(20, 20, 25, 150))
        painter.drawRoundedRect(0, 0, w, h, 4, 4)
        
        painter.setPen(QPen(QColor(60, 60, 65) if self._enabled else QColor(40, 40, 45), 1))
        painter.drawLine(int(w/2), 4, int(w/2), h - 4)
        
        font = QFont(MAIN_FONT, 9, QFont.Bold)
        painter.setFont(font)
        
        if self._is_english:
            base_gray = 80
            r = int(base_gray + (140 - base_gray) * self._ru_brightness)
            g = int(base_gray + (200 - base_gray) * self._ru_brightness)
            b = int(base_gray + (160 - base_gray) * self._ru_brightness)
            painter.setPen(QColor(r, g, b) if self._enabled else QColor(50, 50, 50))
            painter.drawText(QRectF(0, 0, w/2, h), Qt.AlignCenter, "RU")
            painter.setPen(QColor(100, 200, 120) if self._enabled else QColor(50, 100, 60))
            painter.drawText(QRectF(w/2, 0, w/2, h), Qt.AlignCenter, "EN")
        else:
            painter.setPen(QColor(100, 200, 120) if self._enabled else QColor(50, 100, 60))
            painter.drawText(QRectF(0, 0, w/2, h), Qt.AlignCenter, "RU")
            base_gray = 80
            r = int(base_gray + (140 - base_gray) * self._en_brightness)
            g = int(base_gray + (200 - base_gray) * self._en_brightness)
            b = int(base_gray + (160 - base_gray) * self._en_brightness)
            painter.setPen(QColor(r, g, b) if self._enabled else QColor(50, 50, 50))
            painter.drawText(QRectF(w/2, 0, w/2, h), Qt.AlignCenter, "EN")


# ============================================================
# КНОПКА
# ============================================================

class GlowButton(QPushButton):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.base_color = color
        self.text_brightness = 0.0
        self.border_brightness = 0.0
        self.is_hovered = False
        self._is_disabled = False
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self.update_style()
        
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.animate_hover)
        self.hover_timer.start(20)
    
    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self._is_disabled = not enabled
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)
        self.is_hovered = False
        self.text_brightness = 0.0
        self.border_brightness = 0.0
        self.update_style()
    
    def enterEvent(self, event):
        if not self._is_disabled:
            self.is_hovered = True
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.is_hovered = False
        super().leaveEvent(event)
    
    def update_style(self):
        r, g, b = self.base_color
        # Безопасное ограничение значений
        def clamp(v):
            return max(0, min(255, int(v)))
        
        # Базовые цвета текста с учётом brightness
        tr = clamp(r * 0.6 + self.text_brightness)
        tg = clamp(g * 0.6 + self.text_brightness)
        tb_c = clamp(b * 0.6 + self.text_brightness)
        
        # Базовые цвета рамки с учётом brightness
        br = clamp(r * 0.5 + self.border_brightness)
        bg_c = clamp(g * 0.5 + self.border_brightness)
        bb = clamp(b * 0.5 + self.border_brightness)
        
        # Прозрачность рамки
        ba = min(1.0, 0.3 + (self.border_brightness / 100.0))
        
        # Disabled цвета
        dr = clamp(r * 0.3)
        dg = clamp(g * 0.3)
        db = clamp(b * 0.3)
        dbr = clamp(r * 0.2)
        dbg = clamp(g * 0.2)
        dbb = clamp(b * 0.2)
        
        self.setStyleSheet(f"""QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(30,30,35,0.95), stop:1 rgba(25,25,30,0.95));
            color: rgb({tr},{tg},{tb_c}); 
            border: 1.5px solid rgba({br},{bg_c},{bb},{ba}); 
            border-radius: 10px;
            padding: 10px 18px; 
            font-weight: bold; 
            font-size: 13px;
            font-family: {MONO_FONT_FAMILY};
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(40,40,45,0.95), stop:1 rgba(35,35,40,0.95));
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(20,20,25,0.95), stop:1 rgba(25,25,30,0.95));
        }}
        QPushButton:disabled {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(20,20,25,0.95), stop:1 rgba(15,15,20,0.95));
            color: rgb({dr},{dg},{db}); 
            border: 1.5px solid rgba({dbr},{dbg},{dbb},0.2);
        }}""")
    
    def animate_hover(self):
        if self.is_hovered and not self._is_disabled:
            self.text_brightness = min(80.0, self.text_brightness + 6.0)
            self.border_brightness = min(80.0, self.border_brightness + 6.0)
        else:
            self.text_brightness = max(0.0, self.text_brightness - 6.0)
            self.border_brightness = max(0.0, self.border_brightness - 6.0)
        self.update_style()


class NavButton(QPushButton):
    """Навигационная кнопка с иконкой"""
    def __init__(self, icon, tooltip, color, parent=None):
        super().__init__(icon, parent)
        self.base_color = color
        self.hover_brightness = 0.0
        self.is_hovered = False
        self.setFixedSize(40, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.update_style()
        
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.animate_hover)
        self.hover_timer.start(20)
    
    def enterEvent(self, event):
        self.is_hovered = True
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.is_hovered = False
        super().leaveEvent(event)
    
    def update_style(self):
        r, g, b = self.base_color
        
        # Цвет границы с hover эффектом
        border_alpha = 0.3 + (self.hover_brightness / 100.0) * 0.5
        bg_alpha = 0.1 + (self.hover_brightness / 100.0) * 0.15
        
        self.setStyleSheet(f"""QPushButton {{
            background: rgba({r},{g},{b},{bg_alpha});
            color: rgb({min(255, int(r * 0.8 + self.hover_brightness))},{min(255, int(g * 0.8 + self.hover_brightness))},{min(255, int(b * 0.8 + self.hover_brightness))}); 
            border: 1.5px solid rgba({r},{g},{b},{border_alpha}); 
            border-radius: 8px;
            font-size: 16px;
            padding: 0px;
        }}
        QPushButton:pressed {{
            background: rgba({r},{g},{b},{bg_alpha + 0.1});
        }}""")
    
    def animate_hover(self):
        if self.is_hovered:
            self.hover_brightness = min(60.0, self.hover_brightness + 5.0)
        else:
            self.hover_brightness = max(0.0, self.hover_brightness - 5.0)
        self.update_style()


class FormatButton(QPushButton):
    """Кнопка выбора формата с плавной анимацией"""
    def __init__(self, fmt, parent=None):
        super().__init__(parent)
        self.fmt = fmt
        self.base_color = fmt.color
        self.text_brightness = 0.0
        self.border_brightness = 0.0
        self.is_hovered = False
        self.setFixedHeight(70)
        self.setCursor(Qt.PointingHandCursor)
        self.update_style()
        
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.animate_hover)
        self.hover_timer.start(20)
        
        # Создаём layout
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        
        r, g, b = self.base_color
        
        if fmt.icon:
            self.icon_label = QLabel(fmt.icon)
            self.icon_label.setStyleSheet(f"QLabel{{color:rgb({r},{g},{b});font-size:18px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
            layout.addWidget(self.icon_label)
        else:
            self.icon_label = None
        
        text_widget = QWidget()
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        self.name_label = QLabel(fmt.name)
        self.name_label.setStyleSheet(f"QLabel{{color:rgb({r},{g},{b});font-size:14px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        text_layout.addWidget(self.name_label)
        
        self.desc_label = QLabel(fmt.description)
        self.desc_label.setStyleSheet(f"QLabel{{color:#AAAAAA;font-size:12px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        text_layout.addWidget(self.desc_label)
        
        text_widget.setLayout(text_layout)
        layout.addWidget(text_widget, 1)
        
        self.setLayout(layout)
    
    def enterEvent(self, event):
        self.is_hovered = True
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.is_hovered = False
        super().leaveEvent(event)
    
    def update_style(self):
        r, g, b = self.base_color
        
        def clamp(v):
            return max(0, min(255, int(v)))
        
        # Базовые цвета рамки с учётом brightness
        br = clamp(r * 0.5 + self.border_brightness * 0.8)
        bg_c = clamp(g * 0.5 + self.border_brightness * 0.8)
        bb = clamp(b * 0.5 + self.border_brightness * 0.8)
        
        # Прозрачность рамки и фона
        border_alpha = min(1.0, 0.4 + (self.border_brightness / 100.0) * 0.6)
        bg_alpha = 0.1 + (self.border_brightness / 100.0) * 0.15
        
        self.setStyleSheet(f"""QPushButton {{
            background: rgba({r},{g},{b},{bg_alpha});
            border: 1.5px solid rgba({br},{bg_c},{bb},{border_alpha});
            border-radius: 10px;
            text-align: left;
            padding-left: 14px;
        }}
        QPushButton:pressed {{
            background: rgba({r},{g},{b},{bg_alpha + 0.1});
        }}""")
        
        # Обновляем цвет текста
        tr = clamp(r * 0.8 + self.text_brightness)
        tg = clamp(g * 0.8 + self.text_brightness)
        tb = clamp(b * 0.8 + self.text_brightness)
        
        if hasattr(self, 'name_label'):
            self.name_label.setStyleSheet(f"QLabel{{color:rgb({tr},{tg},{tb});font-size:14px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        if hasattr(self, 'icon_label') and self.icon_label:
            self.icon_label.setStyleSheet(f"QLabel{{color:rgb({tr},{tg},{tb});font-size:18px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
    
    def animate_hover(self):
        if self.is_hovered:
            self.text_brightness = min(80.0, self.text_brightness + 6.0)
            self.border_brightness = min(80.0, self.border_brightness + 6.0)
        else:
            self.text_brightness = max(0.0, self.text_brightness - 6.0)
            self.border_brightness = max(0.0, self.border_brightness - 6.0)
        self.update_style()


# ============================================================
# ПРОГРЕСС-БАР
# ============================================================

class AnimatedProgressBar(QWidget):
    def __init__(self, color=(34, 211, 238), parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setMinimumWidth(200)
        self._progress = 0.0
        self._target_progress = 0.0
        self._shimmer_pos = 0.0
        self._color = color
        self._status_text = ""
        self._speed_text = ""
        
        self._shimmer_enabled = True

        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(FPS_75)
    
    def set_shimmer(self, enabled: bool):
        self._shimmer_enabled = enabled
        if not enabled:
            self._shimmer_pos = 0.0
        self.update()

    def set_progress(self, value):
        self._target_progress = max(0.0, min(100.0, value))
    
    def set_status(self, text):
        self._status_text = text
        self.update()
    
    def set_speed(self, text):
        self._speed_text = text
        self.update()
    
    def _get_gradient_color(self, progress):
        # Градиент от красного (0%) к зелёному (100%)
        # Красный (приглушённый): (180, 80, 80) -> Зелёный: (100, 200, 120)
        red = (180, 80, 80)
        green = (100, 200, 120)
        
        if progress <= 0:
            return red
        if progress >= 100:
            return green
        
        # Плавный переход
        t = progress / 100.0
        r = int(red[0] + (green[0] - red[0]) * t)
        g = int(red[1] + (green[1] - red[1]) * t)
        b = int(red[2] + (green[2] - red[2]) * t)
        return (r, g, b)
    
    def _animate(self):
        diff = self._target_progress - self._progress
        self._progress = self._progress + diff * 0.12 if abs(diff) > 0.1 else self._target_progress
        if self._shimmer_enabled:
            self._shimmer_pos = (self._shimmer_pos + 0.025) if self._shimmer_pos <= 1.5 else -0.5
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h, r = self.width(), self.height(), self.height() / 2
        
        # Фон
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 35, 200))
        painter.drawRoundedRect(0, 0, w, h, r, r)
        
        # Рамка
        color = self._get_gradient_color(self._progress)
        painter.setPen(QPen(QColor(color[0], color[1], color[2], 100), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(1, 1, w-2, h-2, r, r)
        
        if self._progress > 0:
            pw = int((w - 4) * self._progress / 100)
            if pw > 0:
                grad = QLinearGradient(2, 0, 2 + pw, 0)
                grad.setColorAt(0, QColor(color[0], color[1], color[2], 200))
                grad.setColorAt(1, QColor(color[0], color[1], color[2], 255))
                painter.setPen(Qt.NoPen)
                painter.setBrush(grad)
                painter.drawRoundedRect(2, 2, pw, h-4, r-2, r-2)
                
                # Shimmer
                if self._shimmer_enabled:
                    shimmer_x = int(pw * self._shimmer_pos)
                    if 0 < shimmer_x < pw:
                        shimmer_grad = QLinearGradient(shimmer_x - 30, 0, shimmer_x + 30, 0)
                        shimmer_grad.setColorAt(0, QColor(255, 255, 255, 0))
                        shimmer_grad.setColorAt(0.5, QColor(255, 255, 255, 80))
                        shimmer_grad.setColorAt(1, QColor(255, 255, 255, 0))
                        painter.setBrush(shimmer_grad)
                        painter.drawRoundedRect(2, 2, pw, h-4, r-2, r-2)
        
        # Текст процента
        painter.setPen(QColor(255, 255, 255, 230))
        painter.setFont(QFont(MAIN_FONT, 11, QFont.Bold))
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, f"{int(self._progress)}%")
    
    def stop(self):
        self.timer.stop()


# ============================================================
# ПОЛОСА СТАТУСА СО SHIMMER
# ============================================================

class ShimmerStatusBar(QWidget):
    """Узкий shimmer-бар для отображения статуса (Merging, Converting...)"""
    def __init__(self, color=(255, 180, 50), parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._color = color
        self._shimmer_pos = -0.5
        self._text = ""
        self._active = False
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(FPS_75)

    def set_text(self, text):
        self._text = text
        self._active = bool(text)
        self.update()

    def _animate(self):
        if self._active:
            self._shimmer_pos += 0.025
            if self._shimmer_pos > 1.5:
                self._shimmer_pos = -0.5
        self.update()

    def paintEvent(self, event):
        from PySide6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rv = h / 2
        r, g, b = self._color

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 35, 180))
        painter.drawRoundedRect(0, 0, w, h, rv, rv)

        if self._active:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0,   QColor(r, g, b, 40))
            grad.setColorAt(0.5, QColor(r, g, b, 90))
            grad.setColorAt(1,   QColor(r, g, b, 40))
            painter.setBrush(grad)
            painter.drawRoundedRect(2, 2, w - 4, h - 4, rv - 2, rv - 2)

            sx = int(w * self._shimmer_pos)
            sg = QLinearGradient(sx - 80, 0, sx + 80, 0)
            sg.setColorAt(0,   QColor(255, 255, 255, 0))
            sg.setColorAt(0.5, QColor(255, 255, 255, 110))
            sg.setColorAt(1,   QColor(255, 255, 255, 0))
            painter.setBrush(sg)
            painter.drawRoundedRect(2, 2, w - 4, h - 4, rv - 2, rv - 2)

        border_a = 140 if self._active else 45
        painter.setPen(QPen(QColor(r, g, b, border_a), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(0, 0, w, h, rv, rv)

        if self._text:
            painter.setPen(QColor(255, 255, 255, 215))
            painter.setFont(QFont(MAIN_FONT, 10, QFont.Bold))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self._text)

    def stop(self):
        self.timer.stop()


# ============================================================
# КОНСОЛЬ
# ============================================================

class ConsoleMessage(QFrame):
    def __init__(self, text, msg_type="default", parent=None):
        super().__init__(parent)
        self.msg_type = msg_type
        self.type_config = {
            "success": {"icon": "●", "color": "#64DC82"},
            "error": {"icon": "●", "color": "#FF5050"},
            "warning": {"icon": "●", "color": "#FFB432"},
            "info": {"icon": "●", "color": "#22D3EE"},
            "default": {"icon": "›", "color": "#888888"},
            "cyan": {"icon": "●", "color": "#22D3EE"},
            "gray": {"icon": "›", "color": "#888888"},
            "yellow": {"icon": "●", "color": "#FFB432"},
            "magenta": {"icon": "●", "color": "#B478FF"},
            "green": {"icon": "●", "color": "#64DC82"},
        }
        config = self.type_config.get(msg_type, self.type_config["default"])
        self._config = config
        self._opacity = 0.0
        
        color = config['color']
        self._color_r, self._color_g, self._color_b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        self._update_style()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        self._icon_label = QLabel(config['icon'])
        self._icon_label.setFixedWidth(22)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._text_label = QLabel(text)
        self._text_label.setWordWrap(True)
        
        self._update_labels()
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label, 1)
        self.setLayout(layout)
        
        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._animate_fade)
        self._fade_timer.start(FPS_75)
    
    def _animate_fade(self):
        self._opacity = min(1.0, self._opacity + 0.06)
        self._update_style()
        self._update_labels()
        if self._opacity >= 1.0:
            self._fade_timer.stop()
    
    def _update_style(self):
        r, g, b = self._color_r, self._color_g, self._color_b
        bg_a = 0.08 * self._opacity
        self.setStyleSheet(f"QFrame{{background:rgba({r},{g},{b},{bg_a});border-left:3px solid rgba({r},{g},{b},{self._opacity});border-radius:12px;margin:1px 2px;}}")
    
    def _update_labels(self):
        r, g, b = self._color_r, self._color_g, self._color_b
        alpha = int(255 * self._opacity)
        self._icon_label.setStyleSheet(f"color:rgba({r},{g},{b},{alpha});font-size:16px;background:transparent;border:none;")
        self._text_label.setStyleSheet(f"color:rgba({r},{g},{b},{alpha});font-size:12px;font-weight:500;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;")


class ConsoleHeader(QFrame):
    def __init__(self, text, color="#22D3EE", parent=None):
        super().__init__(parent)
        self.color = color
        self._opacity = 0.0
        c = color.lstrip('#')
        self._color_r, self._color_g, self._color_b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        self._update_style()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(14, 10, 14, 10)
        self._text_label = QLabel(text)
        self._text_label.setAlignment(Qt.AlignCenter)
        self._update_label()
        layout.addStretch()
        layout.addWidget(self._text_label)
        layout.addStretch()
        self.setLayout(layout)
        
        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._animate_fade)
        self._fade_timer.start(FPS_75)
    
    def _animate_fade(self):
        self._opacity = min(1.0, self._opacity + 0.05)
        self._update_style()
        self._update_label()
        if self._opacity >= 1.0:
            self._fade_timer.stop()
    
    def _update_style(self):
        r, g, b = self._color_r, self._color_g, self._color_b
        bg1 = 0.15 * self._opacity
        bg2 = 0.05 * self._opacity
        self.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba({r},{g},{b},{bg1}),stop:1 rgba({r},{g},{b},{bg2}));border:1.5px solid rgba({r},{g},{b},{self._opacity});border-radius:8px;margin:4px 2px;}}")
    
    def _update_label(self):
        r, g, b = self._color_r, self._color_g, self._color_b
        self._text_label.setStyleSheet(f"color:rgba({r},{g},{b},{int(255*self._opacity)});font-size:13px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;")


class ConsoleSpinner(QWidget):
    def __init__(self, color="#22D3EE", size=16, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.color = QColor(color)
        self.angle = 0
        self._is_stopped = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        self.timer.start(FPS_75)
    
    def rotate(self):
        if not self._is_stopped:
            self.angle = (self.angle + 8) % 360
            self.update()
    
    def paintEvent(self, event):
        if self._is_stopped:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size = min(self.width(), self.height())
        center, radius = size / 2, size / 2 - 2
        painter.setPen(QPen(QColor(self.color.red(), self.color.green(), self.color.blue(), 50), 2))
        painter.drawEllipse(QRectF(2, 2, size-4, size-4))
        painter.setPen(QPen(self.color, 2, Qt.SolidLine, Qt.RoundCap))
        painter.translate(center, center)
        painter.rotate(self.angle)
        painter.drawArc(QRectF(-radius, -radius, radius*2, radius*2), 0, 90 * 16)
    
    def stop(self):
        self._is_stopped = True
        self.timer.stop()


class ConsoleLoadingMessage(QFrame):
    def __init__(self, text, color="#22D3EE", parent=None):
        super().__init__(parent)
        self.color = color
        self._opacity = 0.0
        self._is_stopped = False
        self._update_style()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        self.loader = ConsoleSpinner(color)
        layout.addWidget(self.loader)
        
        self.text_label = QLabel(text)
        self._update_label()
        layout.addWidget(self.text_label, 1)
        self.setLayout(layout)
        
        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._animate_fade)
        self._fade_timer.start(FPS_75)
    
    def _hex_rgb(self, c):
        c = c.lstrip('#')
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    
    def _update_style(self):
        r, g, b = self._hex_rgb(self.color)
        self.setStyleSheet(f"QFrame{{background:rgba({r},{g},{b},{0.1*self._opacity});border:1px solid rgba({r},{g},{b},{0.3*self._opacity});border-radius:12px;margin:2px;}}")
    
    def _update_label(self):
        r, g, b = self._hex_rgb(self.color)
        self.text_label.setStyleSheet(f"color:rgba({r},{g},{b},{int(255*self._opacity)});font-size:13px;font-weight:500;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;")
    
    def _animate_fade(self):
        if self._is_stopped:
            return
        self._opacity = min(1.0, self._opacity + 0.06)
        self._update_style()
        self._update_label()
        if self._opacity >= 1.0:
            self._fade_timer.stop()
    
    def set_text(self, text):
        self.text_label.setText(text)
    
    def stop(self):
        self._is_stopped = True
        self._fade_timer.stop()
        self.loader.stop()
    
    def remove_animated(self):
        self.stop()
        self.deleteLater()


class ModernConsole(QFrame):
    message_added = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []
        self.current_loading = None
        self._scroll_timer = None
        self._target_scroll = 0
        self.setup_ui()
    
    def setup_ui(self):
        self.setObjectName("console_main")
        self.setStyleSheet("""
            QFrame#console_main {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(10,10,12,0.98), stop:1 rgba(15,15,18,0.98));
                border: 2px solid rgba(34, 211, 238, 0.4);
                border-radius: 10px;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        
        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background:transparent;")
        self.messages_layout = QVBoxLayout()
        self.messages_layout.setContentsMargins(10, 10, 10, 10)
        self.messages_layout.setSpacing(3)
        self.messages_layout.addStretch()
        self.messages_container.setLayout(self.messages_layout)
        self.scroll_area.setWidget(self.messages_container)
        main_layout.addWidget(self.scroll_area, 1)
        self.setLayout(main_layout)
        
        self.message_added.connect(self.scroll_to_bottom)
    
    def add_message(self, text, msg_type="default"):
        msg = ConsoleMessage(text, msg_type)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, msg)
        self.messages.append(msg)
        self._cleanup()
        self.message_added.emit()
    
    def add_header(self, text, color="#22D3EE"):
        header = ConsoleHeader(text, color)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, header)
        self.messages.append(header)
        self._cleanup()
        self.message_added.emit()
    
    def _cleanup(self):
        while len(self.messages) > 20:
            old = self.messages.pop(0)
            self.messages_layout.removeWidget(old)
            old.deleteLater()
    
    def show_loading(self, text, color="#22D3EE"):
        self.hide_loading()
        self.current_loading = ConsoleLoadingMessage(text, color)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self.current_loading)
        self.message_added.emit()
        return self.current_loading
    
    def hide_loading(self):
        if self.current_loading:
            self.current_loading.remove_animated()
            self.current_loading = None
    
    def update_loading_text(self, text):
        if self.current_loading:
            self.current_loading.set_text(text)
    
    def clear(self):
        if self._scroll_timer:
            self._scroll_timer.stop()
            self._scroll_timer = None
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.messages = []
        self.current_loading = None
    
    def scroll_to_bottom(self):
        if self._scroll_timer:
            self._scroll_timer.stop()
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._do_scroll)
        self._scroll_timer.start(1000)
    
    def _do_scroll(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        self._target_scroll = scrollbar.maximum()
        self._animate_scroll_timer = QTimer()
        self._animate_scroll_timer.timeout.connect(self._animate_scroll)
        self._animate_scroll_timer.start(FPS_75)
    
    def _animate_scroll(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        current = scrollbar.value()
        diff = self._target_scroll - current
        if abs(diff) < 2:
            scrollbar.setValue(self._target_scroll)
            self._animate_scroll_timer.stop()
        else:
            scrollbar.setValue(int(current + diff * 0.1))


# ============================================================
# ИНДИКАТОР СТАТУСА
# ============================================================

class StatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.opacity = 1.0
        self._all_ready = False  # True = зелёный, False = красный
        self.pulse_direction = -1
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_pulse)
        self.timer.start(FPS_75)
    
    def set_status(self, all_ready):
        """Устанавливает статус: True - зелёный, False - красный"""
        self._all_ready = all_ready
        self.update()
    
    def animate_pulse(self):
        self.opacity += self.pulse_direction * 0.02
        if self.opacity <= 0.4:
            self.pulse_direction = 1
        elif self.opacity >= 1.0:
            self.pulse_direction = -1
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Зелёный если все компоненты установлены, красный если хоть один отсутствует
        if self._all_ready:
            r, g, b = 100, 220, 130  # Зелёный
        else:
            r, g, b = 255, 80, 80  # Красный
        color = QColor(r, g, b, int(255 * self.opacity))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(5, 5, 12, 12)


# ============================================================
# ДИАЛОГ ПОДТВЕРЖДЕНИЯ
# ============================================================

class ConfirmDialog(QDialog):
    def __init__(self, message, title_text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowIcon(get_app_icon())
        self.confirmed = False
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(18,18,22,0.98), stop:1 rgba(16,16,20,0.98));
                border: 2px solid rgba(100, 100, 100, 0.6);
                border-radius: 18px;
            }
        """)
        
        cl = QVBoxLayout()
        cl.setContentsMargins(35, 30, 35, 30)
        cl.setSpacing(22)
        
        icon = QLabel("?")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"""
            QLabel {{
                color: #22D3EE;
                font-size: 36px;
                font-weight: bold;
                font-family: {MONO_FONT_FAMILY};
                background: rgba(34, 211, 238, 0.15);
                border: 2px solid rgba(34, 211, 238, 0.4);
                border-radius: 28px;
                min-width: 56px;
                max-width: 56px;
                min-height: 56px;
                max-height: 56px;
            }}
        """)
        ic = QHBoxLayout()
        ic.addStretch()
        ic.addWidget(icon)
        ic.addStretch()
        
        title = QLabel(title_text)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"QLabel{{color:#22D3EE;font-size:18px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        
        msg = QLabel(message)
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"QLabel{{color:#E0E0E0;font-size:14px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;padding:12px;}}")
        
        bl = QHBoxLayout()
        bl.setSpacing(14)
        self.cancel_btn = GlowButton(get_text("btn_cancel"), (100, 220, 130))
        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = GlowButton("OK", (34, 211, 238))
        self.confirm_btn.clicked.connect(self.accept_dialog)
        bl.addWidget(self.cancel_btn)
        bl.addWidget(self.confirm_btn)
        
        cl.addLayout(ic)
        cl.addWidget(title)
        cl.addWidget(msg)
        cl.addLayout(bl)
        self.container.setLayout(cl)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        self.setFixedSize(400, 280)
    
    def accept_dialog(self):
        self.confirmed = True
        self.accept()


# ============================================================
# ДИАЛОГ АВТОУСТАНОВКИ КОМПОНЕНТОВ
# ============================================================

class AutoInstallDialog(QDialog):
    log_signal = Signal(str, str)
    ytdlp_progress_signal = Signal(float)
    ffmpeg_progress_signal = Signal(float)
    ytdlp_speed_signal = Signal(str)
    ffmpeg_speed_signal = Signal(str)
    ytdlp_status_signal = Signal(str)
    ffmpeg_status_signal = Signal(str)
    all_done_signal = Signal()
    failed_signal = Signal(str)

    def __init__(self, need_ytdlp, need_ffmpeg, parent=None):
        super().__init__(parent)
        self.need_ytdlp = need_ytdlp
        self.need_ffmpeg = need_ffmpeg
        self.ytdlp_path = ""
        self.ffmpeg_path_result = ""
        self._cancel = False
        self._installing = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(620, 520)
        # Сначала строим UI, потом подключаем сигналы
        self.ytdlp_bar = None; self.ffmpeg_bar = None
        self.ytdlp_status = None; self.ffmpeg_status = None
        self.ytdlp_speed = None; self.ffmpeg_speed = None
        self._build_ui()
        # Сигналы
        self.log_signal.connect(self._add_log)
        self.ytdlp_progress_signal.connect(lambda v: self.ytdlp_bar.set_progress(v) if self.ytdlp_bar else None)
        self.ffmpeg_progress_signal.connect(lambda v: self.ffmpeg_bar.set_progress(v) if self.ffmpeg_bar else None)
        self.ytdlp_speed_signal.connect(lambda t: self.ytdlp_speed.setText(t) if self.ytdlp_speed else None)
        self.ffmpeg_speed_signal.connect(lambda t: self.ffmpeg_speed.setText(t) if self.ffmpeg_speed else None)
        self.ytdlp_status_signal.connect(lambda t: self.ytdlp_status.setText(t) if self.ytdlp_status else None)
        self.ffmpeg_status_signal.connect(lambda t: self.ffmpeg_status.setText(t) if self.ffmpeg_status else None)
        self.all_done_signal.connect(self._on_done)
        self.failed_signal.connect(self._on_failed)

    def _build_ui(self):
        ml = QVBoxLayout(); ml.setContentsMargins(0,0,0,0)
        c = QFrame()
        c.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(15,15,18,0.99),stop:1 rgba(12,12,15,0.99));border:2px solid rgba(180,120,255,0.5);border-radius:18px;}")
        cl = QVBoxLayout(); cl.setContentsMargins(30,25,30,25); cl.setSpacing(16)
        # Title
        t = QLabel(get_text("auto_install_title"))
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"QLabel{{color:#B478FF;font-size:20px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        cl.addWidget(t)
        d = QLabel(get_text("auto_install_desc"))
        d.setAlignment(Qt.AlignCenter)
        d.setStyleSheet(f"QLabel{{color:#888;font-size:13px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        cl.addWidget(d)
        # yt-dlp section
        if self.need_ytdlp:
            cl.addLayout(self._make_section_header(get_text("auto_install_ytdlp"), "#64DC82"))
            self.ytdlp_bar = AnimatedProgressBar(color=(100,200,120)); cl.addWidget(self.ytdlp_bar)
            sr = QHBoxLayout()
            self.ytdlp_status = QLabel("⏳ " + get_text("status_ytdlp_missing"))
            self.ytdlp_status.setStyleSheet(f"QLabel{{color:#FF5050;font-size:11px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
            sr.addWidget(self.ytdlp_status)
            sr.addStretch()
            self.ytdlp_speed = QLabel("")
            self.ytdlp_speed.setStyleSheet(f"QLabel{{color:#888;font-size:11px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
            sr.addWidget(self.ytdlp_speed)
            cl.addLayout(sr)
        else:
            self.ytdlp_bar = None; self.ytdlp_status = None; self.ytdlp_speed = None
        # FFmpeg section
        if self.need_ffmpeg:
            cl.addLayout(self._make_section_header(get_text("auto_install_ffmpeg"), "#B478FF"))
            self.ffmpeg_bar = AnimatedProgressBar(color=(180,120,255)); cl.addWidget(self.ffmpeg_bar)
            sr2 = QHBoxLayout()
            self.ffmpeg_status = QLabel("⏳ " + get_text("status_ffmpeg_missing"))
            self.ffmpeg_status.setStyleSheet(f"QLabel{{color:#FF5050;font-size:11px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
            sr2.addWidget(self.ffmpeg_status)
            sr2.addStretch()
            self.ffmpeg_speed = QLabel("")
            self.ffmpeg_speed.setStyleSheet(f"QLabel{{color:#888;font-size:11px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
            sr2.addWidget(self.ffmpeg_speed)
            cl.addLayout(sr2)
        else:
            self.ffmpeg_bar = None; self.ffmpeg_status = None; self.ffmpeg_speed = None
        # Console
        self._console = ModernConsole(); self._console.setMinimumHeight(100)
        cl.addWidget(self._console, 1)
        # Buttons
        bl = QHBoxLayout(); bl.setSpacing(12)
        self.install_btn = GlowButton(get_text("auto_install_btn"), (100,220,130))
        self.install_btn.clicked.connect(self._start_install)
        bl.addWidget(self.install_btn)
        self.cancel_btn = GlowButton(get_text("btn_cancel"), (255,80,80))
        self.cancel_btn.clicked.connect(self._do_cancel)
        bl.addWidget(self.cancel_btn)
        cl.addLayout(bl)
        c.setLayout(cl); ml.addWidget(c); self.setLayout(ml)

    def _make_section_header(self, text, color):
        h = QHBoxLayout()
        l = QLabel(text)
        l.setStyleSheet(f"QLabel{{color:{color};font-size:13px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        h.addWidget(l); h.addStretch()
        return h

    def _add_log(self, text, msg_type):
        self._console.add_message(text, msg_type)

    def _do_cancel(self):
        self._cancel = True
        self.reject()

    def _start_install(self):
        if self._installing: return
        self._installing = True
        self.install_btn.setEnabled(False)
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _dl_file(self, url, dest, prog_signal, speed_signal, status_signal, name):
        """Скачивает файл с прогрессом, retry механизмом и fallback зеркалами"""
        # Определяем список зеркал на основе URL
        mirrors = [url]  # Основной URL всегда первый

        # Добавляем альтернативные зеркала
        if 'yt-dlp' in url:
            key = 'yt-dlp_windows' if platform.system() == 'Windows' else 'yt-dlp_linux'
            mirrors.extend([m for m in DOWNLOAD_MIRRORS.get(key, []) if m != url])
        elif 'ffmpeg' in url.lower() or 'FFmpeg' in url:
            key = 'ffmpeg_windows' if platform.system() == 'Windows' else 'ffmpeg_linux'
            mirrors.extend([m for m in DOWNLOAD_MIRRORS.get(key, []) if m != url])

        max_retries = 2  # Попытки для каждого зеркала

        # Пробуем каждое зеркало
        for mirror_idx, mirror_url in enumerate(mirrors):
            if mirror_idx > 0:
                self.log_signal.emit(f"[INFO] Trying alternative mirror #{mirror_idx}...", "info")

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        self.log_signal.emit(f"[INFO] Retry {attempt}/{max_retries} for {name}...", "info")
                        time.sleep(2)

                    status_signal.emit(f"⬇ Downloading {name}...")

                    # Создаем SSL контекст для обхода проблем с сертификатами
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

                    req = urllib.request.Request(
                        mirror_url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Accept': '*/*',
                            'Connection': 'keep-alive'
                        }
                    )

                    # Открываем соединение с таймаутом
                    resp = urllib.request.urlopen(req, timeout=30, context=ssl_context)
                    total = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    bs = 16384  # Увеличенный размер буфера
                    st = time.time()

                    self.log_signal.emit(f"[INFO] Downloading {name}: {total/(1024*1024):.1f} MB", "info")

                    with open(dest, 'wb') as f:
                        while True:
                            if self._cancel:
                                raise Exception("Cancelled")

                            buf = resp.read(bs)
                            if not buf:
                                break

                            f.write(buf)
                            downloaded += len(buf)

                            if total > 0:
                                prog_signal.emit((downloaded/total)*100)
                                el = time.time() - st
                                if el > 0:
                                    spd = downloaded / el
                                    spd_s = f"{spd/(1024*1024):.1f} MB/s" if spd >= 1048576 else f"{spd/1024:.1f} KB/s"
                                    rem = (total - downloaded) / spd if spd > 0 else 0
                                    eta = f"{int(rem//60)}:{int(rem%60):02d}" if rem >= 60 else f"{int(rem)}s"
                                    speed_signal.emit(f"{spd_s} • ETA: {eta}")

                    prog_signal.emit(100)
                    speed_signal.emit("✓")
                    status_signal.emit(f"✓ {name} installed!")
                    return  # Успешно скачали, выходим

                except Exception as e:
                    error_msg = str(e)
                    if attempt < max_retries - 1:
                        self.log_signal.emit(f"[WARN] Download failed: {error_msg}. Retrying...", "warning")
                    else:
                        # Последняя попытка для этого зеркала не удалась
                        if mirror_idx < len(mirrors) - 1:
                            self.log_signal.emit(f"[WARN] Mirror failed: {error_msg}. Trying next mirror...", "warning")
                        else:
                            # Все зеркала исчерпаны
                            self.log_signal.emit(f"[ERROR] Failed to download {name}: {error_msg}", "error")
                            raise Exception(f"Failed to download {name} from all mirrors: {error_msg}")

    def _install_worker(self):
        try:
            ee = '.exe' if platform.system() == 'Windows' else ''
            # yt-dlp
            if self.need_ytdlp:
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" if platform.system() == 'Windows' else "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                dest = os.path.join(BIN_FOLDER, f'yt-dlp{ee}')
                self._dl_file(url, dest, self.ytdlp_progress_signal, self.ytdlp_speed_signal, self.ytdlp_status_signal, "yt-dlp")
                if platform.system() != 'Windows': os.chmod(dest, 0o755)
                self.ytdlp_path = dest
                self.log_signal.emit("[SUCCESS] yt-dlp installed!", "success")
            # FFmpeg
            if self.need_ffmpeg and not self._cancel:
                url = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" if platform.system() == 'Windows' else "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
                ext = ".zip" if platform.system() == 'Windows' else ".tar.xz"
                td = tempfile.gettempdir()
                ap = os.path.join(td, f"ffmpeg{ext}"); ep = os.path.join(td, "ffmpeg_extract")
                self._dl_file(url, ap, self.ffmpeg_progress_signal, self.ffmpeg_speed_signal, self.ffmpeg_status_signal, "FFmpeg")
                self.ffmpeg_status_signal.emit("📦 Extracting...")
                self.ffmpeg_speed_signal.emit("")
                self.log_signal.emit("[INFO] Extracting FFmpeg...", "info")
                if os.path.exists(ep): shutil.rmtree(ep)
                if ext == ".zip":
                    with zipfile.ZipFile(ap, 'r') as zf: zf.extractall(ep)
                else:
                    import tarfile
                    with tarfile.open(ap, 'r:xz') as tf: tf.extractall(ep)
                for root, dirs, files in os.walk(ep):
                    for fn in files:
                        if fn in [f'ffmpeg{ee}', f'ffprobe{ee}']:
                            src = os.path.join(root, fn); dst = os.path.join(BIN_FOLDER, fn)
                            shutil.copy2(src, dst)
                            if platform.system() != 'Windows': os.chmod(dst, 0o755)
                os.remove(ap); shutil.rmtree(ep)
                self.ffmpeg_path_result = BIN_FOLDER
                self.ffmpeg_status_signal.emit("✓ FFmpeg installed!")
                self.log_signal.emit("[SUCCESS] FFmpeg installed!", "success")
            self.all_done_signal.emit()
        except Exception as e:
            if not self._cancel:
                self.failed_signal.emit(str(e))

    def _on_done(self):
        self.log_signal.emit(get_text("auto_install_complete"), "success")
        self.install_btn.setText("✓ " + get_text("auto_install_complete"))
        self.cancel_btn.setText(get_text("btn_home"))
        self.cancel_btn.base_color = (100,220,130)
        self.cancel_btn.update_style()
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)

    def _on_failed(self, err):
        self.log_signal.emit(f"[ERROR] {err}", "error")
        self.install_btn.setEnabled(True)
        self._installing = False


# ============================================================
# ДИАЛОГ ВЫБОРА ФОРМАТА
# ============================================================

class FormatSelectDialog(QDialog):
    def __init__(self, video_info, parent=None):
        super().__init__(parent)
        self.video_info = video_info
        self.selected_format = None
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowIcon(get_app_icon())
        self.setFixedSize(700, 620)  # Увеличенный размер окна
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(15,15,18,0.99), stop:1 rgba(12,12,15,0.99));
                border: 2px solid rgba(100, 100, 100, 0.5);
                border-radius: 18px;
            }
        """)
        
        cl = QVBoxLayout()
        cl.setContentsMargins(25, 25, 25, 25)
        cl.setSpacing(18)
        
        # Заголовок
        header = QLabel(get_text("select_quality"))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"QLabel{{color:#888888;font-size:22px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        cl.addWidget(header)
        
        # Информация о видео
        title = video_info.get('title', 'Unknown')[:60]
        if len(video_info.get('title', '')) > 60:
            title += "..."
        
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame{background:rgba(100,100,100,0.1);border:1.5px solid rgba(100,100,100,0.4);border-radius:14px;padding:12px;}")
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(14, 12, 14, 12)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"QLabel{{color:#FFFFFF;font-size:14px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        
        # Мета-информация
        channel = video_info.get('uploader', 'Unknown')
        duration = video_info.get('duration', 0)
        if duration:
            mins, secs = divmod(int(duration), 60)
            hours, mins = divmod(mins, 60)
            dur_str = f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"
        else:
            dur_str = "N/A"
        
        meta_label = QLabel(f"👤 {channel}  •  ⏱ {dur_str}")
        meta_label.setStyleSheet(f"QLabel{{color:#999999;font-size:12px;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        info_layout.addWidget(meta_label)
        
        info_frame.setLayout(info_layout)
        cl.addWidget(info_frame)
        
        # Скролл область с форматами
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background:transparent;")
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(14)
        
        # Видео форматы
        video_header = QLabel(get_text("video_formats"))
        video_header.setStyleSheet(f"QLabel{{color:#64C878;font-size:14px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;}}")
        scroll_layout.addWidget(video_header)
        
        video_grid = QGridLayout()
        video_grid.setSpacing(10)
        video_formats = [f for f in FORMATS if not f.is_audio]
        for i, fmt in enumerate(video_formats):
            btn = self._create_format_button(fmt)
            video_grid.addWidget(btn, i // 3, i % 3)
        scroll_layout.addLayout(video_grid)
        
        # Аудио форматы
        audio_header = QLabel(get_text("audio_formats"))
        audio_header.setStyleSheet(f"QLabel{{color:#B478FF;font-size:14px;font-weight:bold;font-family:{MONO_FONT_FAMILY};background:transparent;border:none;margin-top:12px;}}")
        scroll_layout.addWidget(audio_header)
        
        audio_grid = QGridLayout()
        audio_grid.setSpacing(10)
        audio_formats = [f for f in FORMATS if f.is_audio]
        for i, fmt in enumerate(audio_formats):
            btn = self._create_format_button(fmt)
            audio_grid.addWidget(btn, i // 3, i % 3)
        scroll_layout.addLayout(audio_grid)
        
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        cl.addWidget(scroll, 1)
        
        # Кнопка назад
        back_btn = GlowButton(get_text("btn_back"), (150, 150, 150))
        back_btn.clicked.connect(self.reject)
        cl.addWidget(back_btn)
        
        self.container.setLayout(cl)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
    
    def _create_format_button(self, fmt: FormatOption):
        btn = FormatButton(fmt)
        btn.clicked.connect(lambda: self._on_format_selected(fmt))
        return btn
    
    def _on_format_selected(self, fmt: FormatOption):
        self.selected_format = fmt
        self.accept()


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class VideoDownloaderApp(QMainWindow):
    log_signal = Signal(str, str)
    header_signal = Signal(str, str)
    status_signal = Signal(str)
    progress_signal = Signal(float)
    speed_signal = Signal(str)
    download_complete_signal = Signal()
    download_failed_signal = Signal(str)
    show_format_dialog_signal = Signal(dict, str)
    video_progress_signal = Signal(float)
    audio_progress_signal = Signal(float)
    merge_status_signal = Signal(str)
    # Сигналы для скачивания компонентов
    component_progress_signal = Signal(float)
    component_speed_signal = Signal(str)
    component_status_signal = Signal(str)
    
    def __init__(self):
        super().__init__()
        
        # Состояние
        self.download_folder = DEFAULT_DOWNLOAD_FOLDER
        self.ffmpeg_path = ""
        self.ytdlp_exe = ""
        self.has_ffmpeg = False
        self.current_video_info = None
        self._download_cancel = False
        self._current_screen = "home"
        
        # Создание системных папок (без download_folder - она создаётся после загрузки конфига)
        for folder in [APP_FOLDER, BIN_FOLDER]:
            os.makedirs(folder, exist_ok=True)
        
        # Загрузка конфигурации (может изменить download_folder)
        self._load_config()
        
        # Теперь создаём папку загрузок (уже с правильным путём из конфига)
        os.makedirs(self.download_folder, exist_ok=True)
        
        self._check_tools()
        
        # Сигналы
        self.log_signal.connect(self._write_console_safe)
        self.header_signal.connect(self._write_header_safe)
        self.status_signal.connect(self._update_status_safe)
        self.progress_signal.connect(self._update_progress_safe)
        self.speed_signal.connect(self._update_speed_safe)
        self.download_complete_signal.connect(self._on_download_complete)
        self.download_failed_signal.connect(self._on_download_failed)
        self.show_format_dialog_signal.connect(self._show_format_dialog)
        self.video_progress_signal.connect(self._update_video_progress_safe)
        self.audio_progress_signal.connect(self._update_audio_progress_safe)
        self.merge_status_signal.connect(self._update_merge_status_safe)
        # Сигналы для компонентов
        self.component_progress_signal.connect(self._update_component_progress_safe)
        self.component_speed_signal.connect(self._update_component_speed_safe)
        self.component_status_signal.connect(self._update_component_status_safe)
        
        # Инициализация переменных для загрузки
        self._loading_spinner = None
        
        self.setup_ui()
        self._show_home()
        
        # Автоустановка компонентов при первом запуске
        QTimer.singleShot(300, self._check_auto_install)
    
    def _load_config(self):
        try:
            if os.path.isfile(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if config.get('download_folder'):
                        self.download_folder = config['download_folder']
        except:
            pass
    
    def _save_config(self):
        try:
            os.makedirs(APP_FOLDER, exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'download_folder': self.download_folder}, f)
        except:
            pass
    
    def _check_tools(self):
        exe_ext = '.exe' if platform.system() == 'Windows' else ''
        # Сброс перед проверкой
        self.ytdlp_exe = ""
        self.ffmpeg_path = ""
        self.has_ffmpeg = False
        
        ytdlp_bin = os.path.join(BIN_FOLDER, f'yt-dlp{exe_ext}')
        if os.path.isfile(ytdlp_bin):
            self.ytdlp_exe = ytdlp_bin
        elif shutil.which('yt-dlp'):
            self.ytdlp_exe = shutil.which('yt-dlp')
        
        ffmpeg_bin = os.path.join(BIN_FOLDER, f'ffmpeg{exe_ext}')
        if os.path.isfile(ffmpeg_bin):
            self.ffmpeg_path = BIN_FOLDER
            self.has_ffmpeg = True
        elif shutil.which('ffmpeg'):
            self.ffmpeg_path = os.path.dirname(shutil.which('ffmpeg'))
            self.has_ffmpeg = True
    
    def setup_ui(self):
        self.setWindowTitle(get_text("window_title"))
        self.setFixedSize(1000, 880)  # Увеличенный размер окна
        
        # Установка иконки приложения
        self.setWindowIcon(get_app_icon())
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(18)
        
        # Верхняя панель
        top_layout = QHBoxLayout()
        
        # Заголовок
        title_widget = QWidget()
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)
        
        self.title_label = QLabel(get_text("app_title"))
        self.title_label.setFont(QFont(MAIN_FONT, 28, QFont.Bold))
        self.title_label.setStyleSheet("color: #888888; letter-spacing: 2px;")
        title_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel(get_text("subtitle"))
        self.subtitle_label.setStyleSheet(f"color: #888888; font-size: 14px; font-family: {MONO_FONT_FAMILY};")
        title_layout.addWidget(self.subtitle_label)
        
        title_widget.setLayout(title_layout)
        top_layout.addWidget(title_widget)
        top_layout.addStretch()
        
        # Переключатель языка
        self.lang_toggle = LanguageToggle()
        self.lang_toggle.language_changed.connect(self.update_language)
        top_layout.addWidget(self.lang_toggle, 0, Qt.AlignTop)
        
        main_layout.addLayout(top_layout)
        
        # Статус-бар
        self.status_frame = QFrame()
        self.status_frame.setFixedHeight(60)
        self.status_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(25,25,30,0.9), stop:1 rgba(30,30,35,0.9));
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 14px;
            }
        """)
        
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(18, 10, 18, 10)
        
        self.status_indicator = StatusIndicator()
        status_layout.addWidget(self.status_indicator)
        
        self.ytdlp_status = QLabel()
        self.ffmpeg_status = QLabel()
        self._update_tool_status()
        
        status_layout.addWidget(self.ytdlp_status)
        status_layout.addWidget(self.ffmpeg_status)
        status_layout.addStretch()
        
        # Навигационные кнопки с текстом
        self.nav_home_btn = NavButton("🏠", get_text("nav_home"), (100, 200, 120))
        self.nav_home_btn.clicked.connect(self._show_home)
        status_layout.addWidget(self.nav_home_btn)
        
        self.nav_components_btn = NavButton("⚙", get_text("nav_components"), (180, 120, 255))
        self.nav_components_btn.clicked.connect(self._show_components)
        status_layout.addWidget(self.nav_components_btn)
        
        self.nav_folder_btn = NavButton("📁", get_text("nav_folder"), (100, 220, 130))
        self.nav_folder_btn.clicked.connect(self._open_folder)
        status_layout.addWidget(self.nav_folder_btn)
        
        self.status_frame.setLayout(status_layout)
        main_layout.addWidget(self.status_frame)
        
        # Контент
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_frame.setLayout(self.content_layout)
        main_layout.addWidget(self.content_frame, 1)
        
        # Футер
        footer_layout = QVBoxLayout()
        footer_layout.setSpacing(2)
        
        # Верхняя строка футера
        footer_top = QHBoxLayout()
        
        self.copyright_label = QLabel(get_text("footer_copyright"))
        self.copyright_label.setStyleSheet(f"color: #555555; font-size: 10px; font-family: {MONO_FONT_FAMILY};")
        footer_top.addWidget(self.copyright_label)
        
        footer_top.addStretch()
        
        self.powered_label = QLabel(get_text("footer_powered"))
        self.powered_label.setStyleSheet(f"color: #555555; font-size: 10px; font-family: {MONO_FONT_FAMILY};")
        footer_top.addWidget(self.powered_label)
        
        footer_layout.addLayout(footer_top)
        
        # Нижняя строка — авторы
        self.authors_label = QLabel("By squezeebtw & on1felix")
        self.authors_label.setStyleSheet(f"color: #444444; font-size: 9px; font-family: {MONO_FONT_FAMILY};")
        footer_layout.addWidget(self.authors_label)
        
        main_layout.addLayout(footer_layout)
        
        central.setLayout(main_layout)
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d0d0d, stop:0.5 #141418, stop:1 #0f0f12);
            }}
            QLabel {{ 
                color: #FFFFFF; 
                font-family: {MONO_FONT_FAMILY};
            }}
        """)
    
    def _update_tool_status(self):
        if self.ytdlp_exe:
            self.ytdlp_status.setText(get_text("status_ytdlp_ready"))
            self.ytdlp_status.setStyleSheet(f"color: #64DC82; font-size: 12px; font-family: {MONO_FONT_FAMILY}; margin-left: 12px;")
        else:
            self.ytdlp_status.setText(get_text("status_ytdlp_missing"))
            self.ytdlp_status.setStyleSheet(f"color: #FF5050; font-size: 12px; font-family: {MONO_FONT_FAMILY}; margin-left: 12px;")
        
        if self.has_ffmpeg:
            self.ffmpeg_status.setText(get_text("status_ffmpeg_ready"))
            self.ffmpeg_status.setStyleSheet(f"color: #64DC82; font-size: 12px; font-family: {MONO_FONT_FAMILY}; margin-left: 18px;")
        else:
            self.ffmpeg_status.setText(get_text("status_ffmpeg_missing"))
            self.ffmpeg_status.setStyleSheet(f"color: #FFB432; font-size: 12px; font-family: {MONO_FONT_FAMILY}; margin-left: 18px;")
        
        # Обновляем индикатор статуса - зелёный если ВСЁ установлено, красный если хоть что-то отсутствует
        all_ready = bool(self.ytdlp_exe) and bool(self.has_ffmpeg)
        self.status_indicator.set_status(all_ready)
    
    def update_language(self, lang):
        set_current_language(lang)
        self.refresh_all_texts()
        if self._current_screen == "home":
            self._show_home()
        elif self._current_screen == "components":
            self._show_components()
    
    def refresh_all_texts(self):
        self.setWindowTitle(get_text("window_title"))
        self.title_label.setText(get_text("app_title"))
        self.subtitle_label.setText(get_text("subtitle"))
        self.copyright_label.setText(get_text("footer_copyright"))
        self.powered_label.setText(get_text("footer_powered"))
        self._update_tool_status()
    
    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _write_console_safe(self, text, msg_type):
        # Если мы на экране загрузки компонента - пишем в component_console
        if self._current_screen == "component_download" and hasattr(self, 'component_console'):
            self.component_console.add_message(text, msg_type)
        elif hasattr(self, 'console'):
            self.console.add_message(text, msg_type)
    
    def _write_header_safe(self, text, color):
        if hasattr(self, 'console'):
            self.console.add_header(text, color)
    
    def _update_status_safe(self, text):
        if hasattr(self, 'status_label'):
            self.status_label.setText(text)
    
    def _update_progress_safe(self, value):
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_progress(value)
    
    def _update_speed_safe(self, text):
        if hasattr(self, 'speed_label'):
            self.speed_label.setText(text)

    def _update_video_progress_safe(self, value):
        if hasattr(self, 'video_progress_bar') and self.video_progress_bar:
            self.video_progress_bar.set_progress(value)

    def _update_audio_progress_safe(self, value):
        if hasattr(self, 'audio_progress_bar') and self.audio_progress_bar:
            self.audio_progress_bar.set_progress(value)

    def _update_merge_status_safe(self, text):
        if hasattr(self, 'merge_bar') and self.merge_bar:
            self.merge_bar.set_text(text)
            # Если merge_bar активен — выключить шиммер у progress bars, и наоборот
            shimmer_on = not bool(text)
            if hasattr(self, 'video_progress_bar') and self.video_progress_bar:
                self.video_progress_bar.set_shimmer(shimmer_on)
            if hasattr(self, 'audio_progress_bar') and self.audio_progress_bar:
                self.audio_progress_bar.set_shimmer(shimmer_on)

    def _update_component_progress_safe(self, value):
        if hasattr(self, 'component_progress_bar') and self.component_progress_bar:
            self.component_progress_bar.set_progress(value)

    def _update_component_speed_safe(self, text):
        if hasattr(self, 'component_speed_label') and self.component_speed_label:
            self.component_speed_label.setText(text)

    def _update_component_status_safe(self, text):
        if hasattr(self, 'component_status_label') and self.component_status_label:
            self.component_status_label.setText(text)

    # ========================================
    # АВТОУСТАНОВКА
    # ========================================

    def _check_auto_install(self):
        """Проверяет компоненты и показывает диалог автоустановки"""
        need_ytdlp = not bool(self.ytdlp_exe)
        need_ffmpeg = not bool(self.has_ffmpeg)
        if need_ytdlp or need_ffmpeg:
            dialog = AutoInstallDialog(need_ytdlp, need_ffmpeg, self)
            result = dialog.exec()
            # Обновляем пути из диалога
            if dialog.ytdlp_path:
                self.ytdlp_exe = dialog.ytdlp_path
            if dialog.ffmpeg_path_result:
                self.ffmpeg_path = dialog.ffmpeg_path_result
                self.has_ffmpeg = True
            # Перепроверяем на случай если что-то было в PATH
            self._check_tools()
            self._update_tool_status()
            self._show_home()

    # ========================================
    # ГЛАВНЫЙ ЭКРАН
    # ========================================
    
    def _show_home(self):
        self._current_screen = "home"
        self._clear_content()
        
        # Обновляем информацию о компонентах при каждом показе домашнего экрана
        self._check_tools()
        self._update_tool_status()
        
        # URL ввод
        url_frame = QFrame()
        url_frame.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 16px;
            }
        """)
        
        url_layout = QVBoxLayout()
        url_layout.setContentsMargins(24, 22, 24, 22)
        url_layout.setSpacing(14)
        
        url_label = QLabel(get_text("enter_url"))
        url_label.setStyleSheet(f"color: #888888; font-size: 17px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        url_layout.addWidget(url_label)
        
        # Поле ввода
        input_layout = QHBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(get_text("url_placeholder"))
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(30, 30, 35, 0.9);
                border: 1.5px solid rgba(100, 200, 120, 0.3);
                border-radius: 10px;
                padding: 14px 18px;
                color: #FFFFFF;
                font-size: 14px;
                font-family: {MONO_FONT_FAMILY};
            }}
            QLineEdit:focus {{
                border: 1.5px solid rgba(100, 200, 120, 0.7);
            }}
        """)
        self.url_input.returnPressed.connect(self._search_video)
        input_layout.addWidget(self.url_input, 1)
        
        url_layout.addLayout(input_layout)
        
        # Кнопка поиска по центру
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_layout.addStretch()
        
        all_ready = bool(self.ytdlp_exe) and bool(self.has_ffmpeg)
        search_color = (100, 200, 120) if all_ready else (100, 100, 100)
        search_btn = GlowButton(f"  {get_text('btn_search')}", search_color)
        search_btn.setFixedWidth(200)
        search_btn.setEnabled(all_ready)
        search_btn.clicked.connect(self._search_video)
        btn_layout.addWidget(search_btn)
        
        btn_layout.addStretch()
        
        url_layout.addLayout(btn_layout)
        
        if not all_ready:
            warn = QLabel(get_text("error_no_components"))
            warn.setAlignment(Qt.AlignCenter)
            warn.setStyleSheet(f"color:#FF5050;font-size:12px;font-family:{MONO_FONT_FAMILY};margin-top:4px;")
            url_layout.addWidget(warn)
        
        url_frame.setLayout(url_layout)
        self.content_layout.addWidget(url_frame)
        
        # Поддерживаемые платформы
        platforms_label = QLabel(get_text("platforms"))
        platforms_label.setStyleSheet(f"color: #555555; font-size: 11px; font-family: {MONO_FONT_FAMILY}; margin-top: 12px;")
        platforms_label.setWordWrap(True)
        platforms_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(platforms_label)
        
        self.content_layout.addStretch()
    
    def _paste_url(self):
        clipboard = QApplication.clipboard()
        self.url_input.setText(clipboard.text())
    
    def _search_video(self):
        url = self.url_input.text().strip()
        if not url:
            self._show_error(get_text("error_empty_url"))
            return
        
        if not self.ytdlp_exe or not self.has_ffmpeg:
            self._show_error(get_text("error_no_components"))
            return
        
        self._show_loading_screen(get_text("fetching_info"))
        threading.Thread(target=self._fetch_video_info, args=(url,), daemon=True).start()
    
    def _fetch_video_info(self, url):
        try:
            result = subprocess.run(
                [self.ytdlp_exe, '--dump-json', '--no-playlist', url],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                info = json.loads(result.stdout)
                self.show_format_dialog_signal.emit(info, url)
            else:
                self.download_failed_signal.emit(get_text("error_fetch_failed"))
        except Exception as e:
            self.download_failed_signal.emit(str(e))
    
    def _show_format_dialog(self, info, url):
        # Останавливаем спиннер перед показом диалога
        self._stop_loading_spinner()
        self._show_home()
        self.current_video_info = info
        
        dialog = FormatSelectDialog(info, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_format:
            self._start_download(url, dialog.selected_format)
    
    def _stop_loading_spinner(self):
        """Останавливает все спиннеры на экране загрузки"""
        if hasattr(self, '_loading_spinner') and self._loading_spinner:
            self._loading_spinner.stop()
            self._loading_spinner = None
    
    def _show_loading_screen(self, message):
        self._clear_content()
        
        center_widget = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignCenter)
        
        self._loading_spinner = ConsoleSpinner("#22D3EE", 60)
        self._loading_spinner.setFixedSize(60, 60)
        center_layout.addWidget(self._loading_spinner, 0, Qt.AlignCenter)
        
        label = QLabel(message)
        label.setStyleSheet(f"color: #888888; font-size: 15px; font-family: {MONO_FONT_FAMILY}; margin-top: 18px;")
        label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(label)
        
        center_widget.setLayout(center_layout)
        self.content_layout.addStretch()
        self.content_layout.addWidget(center_widget)
        self.content_layout.addStretch()
    
    def _show_component_download_screen(self, component_name, message):
        """Показывает экран загрузки компонента с прогресс-баром"""
        self._current_screen = "component_download"
        self._clear_content()
        
        # Заголовок
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 16px;
            }
        """)
        
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(8)
        
        title_label = QLabel(f"⬇  {get_text('installing')} {component_name}")
        title_label.setStyleSheet(f"color: #B478FF; font-size: 18px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        header_layout.addWidget(title_label)
        
        desc_label = QLabel(message)
        desc_label.setStyleSheet(f"color: #888888; font-size: 13px; font-family: {MONO_FONT_FAMILY};")
        header_layout.addWidget(desc_label)
        
        header_frame.setLayout(header_layout)
        self.content_layout.addWidget(header_frame)
        
        # Прогресс
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 16px;
            }
        """)
        
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(24, 22, 24, 22)
        progress_layout.setSpacing(14)
        
        # Статус + скорость
        top_row = QHBoxLayout()
        self.component_status_label = QLabel(get_text("downloading"))
        self.component_status_label.setStyleSheet(f"color: #B478FF; font-size: 14px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        top_row.addWidget(self.component_status_label)
        top_row.addStretch()
        self.component_speed_label = QLabel("")
        self.component_speed_label.setStyleSheet(f"color: #888888; font-size: 13px; font-family: {MONO_FONT_FAMILY};")
        top_row.addWidget(self.component_speed_label)
        progress_layout.addLayout(top_row)
        
        # Прогресс-бар
        self.component_progress_bar = AnimatedProgressBar(color=(180, 120, 255))
        progress_layout.addWidget(self.component_progress_bar)
        
        # Детали загрузки
        details_row = QHBoxLayout()
        self.component_downloaded_label = QLabel("")
        self.component_downloaded_label.setStyleSheet(f"color: #666666; font-size: 12px; font-family: {MONO_FONT_FAMILY};")
        details_row.addWidget(self.component_downloaded_label)
        details_row.addStretch()
        self.component_eta_label = QLabel("")
        self.component_eta_label.setStyleSheet(f"color: #666666; font-size: 12px; font-family: {MONO_FONT_FAMILY};")
        details_row.addWidget(self.component_eta_label)
        progress_layout.addLayout(details_row)
        
        progress_frame.setLayout(progress_layout)
        self.content_layout.addWidget(progress_frame)
        
        # Консоль (опционально)
        self.component_console = ModernConsole()
        self.component_console.setMinimumHeight(150)
        self.content_layout.addWidget(self.component_console, 1)
        
        # Кнопка отмены
        cancel_btn = GlowButton(get_text("btn_cancel"), (255, 80, 80))
        cancel_btn.clicked.connect(self._cancel_component_download)
        self.content_layout.addWidget(cancel_btn)
        
        # Флаг отмены
        self._component_download_cancel = False
    
    def _cancel_component_download(self):
        self._component_download_cancel = True
        self._show_components()
    
    def _download_with_progress(self, url, dest):
        """Скачивает файл с отображением прогресса, retry механизмом и fallback зеркалами"""
        # Определяем список зеркал на основе URL
        mirrors = [url]  # Основной URL всегда первый

        # Добавляем альтернативные зеркала
        if 'yt-dlp' in url:
            key = 'yt-dlp_windows' if platform.system() == 'Windows' else 'yt-dlp_linux'
            mirrors.extend([m for m in DOWNLOAD_MIRRORS.get(key, []) if m != url])
        elif 'ffmpeg' in url.lower() or 'FFmpeg' in url:
            key = 'ffmpeg_windows' if platform.system() == 'Windows' else 'ffmpeg_linux'
            mirrors.extend([m for m in DOWNLOAD_MIRRORS.get(key, []) if m != url])

        max_retries = 2  # Попытки для каждого зеркала

        # Пробуем каждое зеркало
        for mirror_idx, mirror_url in enumerate(mirrors):
            if mirror_idx > 0:
                if hasattr(self, 'component_console'):
                    self.log_signal.emit(f"[INFO] Trying alternative mirror #{mirror_idx}...", "info")

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        if hasattr(self, 'component_console'):
                            self.log_signal.emit(f"[INFO] Retry {attempt}/{max_retries}...", "info")
                        time.sleep(2)

                    self._component_download_cancel = False

                    # Создаем SSL контекст
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

                    # Открываем соединение с таймаутом
                    request = urllib.request.Request(
                        mirror_url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Accept': '*/*',
                            'Connection': 'keep-alive'
                        }
                    )
                    response = urllib.request.urlopen(request, timeout=30, context=ssl_context)

                    # Получаем размер файла
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0
                    block_size = 16384  # Увеличенный размер буфера
                    start_time = time.time()

                    # Логируем начало
                    if hasattr(self, 'component_console'):
                        size_mb = total_size / (1024 * 1024)
                        self.log_signal.emit(f"[INFO] Starting download: {size_mb:.1f} MB", "info")

                    with open(dest, 'wb') as f:
                        while True:
                            if self._component_download_cancel:
                                f.close()
                                if os.path.exists(dest):
                                    os.remove(dest)
                                raise Exception("Download cancelled")

                            buffer = response.read(block_size)
                            if not buffer:
                                break

                            f.write(buffer)
                            downloaded += len(buffer)

                            # Вычисляем прогресс
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                self.component_progress_signal.emit(progress)

                                # Вычисляем скорость
                                elapsed = time.time() - start_time
                                if elapsed > 0:
                                    speed = downloaded / elapsed

                                    # Форматируем скорость
                                    if speed >= 1024 * 1024:
                                        speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                                    elif speed >= 1024:
                                        speed_str = f"{speed / 1024:.1f} KB/s"
                                    else:
                                        speed_str = f"{speed:.0f} B/s"

                                    # ETA
                                    remaining = total_size - downloaded
                                    if speed > 0:
                                        eta_seconds = remaining / speed
                                        if eta_seconds >= 60:
                                            eta_str = f"{int(eta_seconds // 60)}:{int(eta_seconds % 60):02d}"
                                        else:
                                            eta_str = f"{int(eta_seconds)}s"
                                    else:
                                        eta_str = "..."

                                    # Форматируем размеры
                                    downloaded_mb = downloaded / (1024 * 1024)
                                    total_mb = total_size / (1024 * 1024)

                                    self.component_speed_signal.emit(f"{get_text('speed')}: {speed_str}  •  ETA: {eta_str}")

                                    # Обновляем детали (через другие лейблы)
                                    if hasattr(self, 'component_downloaded_label'):
                                        QTimer.singleShot(0, lambda d=downloaded_mb, t=total_mb:
                                            self.component_downloaded_label.setText(f"{d:.1f} MB / {t:.1f} MB"))

                    self.component_progress_signal.emit(100)
                    self.component_speed_signal.emit("✓ Download complete")

                    if hasattr(self, 'component_console'):
                        self.log_signal.emit("[SUCCESS] Download completed!", "success")
                    return  # Успешно скачали, выходим

                except Exception as e:
                    error_msg = str(e)
                    if attempt < max_retries - 1:
                        if hasattr(self, 'component_console'):
                            self.log_signal.emit(f"[WARN] Download failed: {error_msg}. Retrying...", "warning")
                    else:
                        # Последняя попытка для этого зеркала не удалась
                        if mirror_idx < len(mirrors) - 1:
                            if hasattr(self, 'component_console'):
                                self.log_signal.emit(f"[WARN] Mirror failed: {error_msg}. Trying next mirror...", "warning")
                        else:
                            # Все зеркала исчерпаны
                            if hasattr(self, 'component_console'):
                                self.log_signal.emit(f"[ERROR] Download failed: {error_msg}", "error")
                            raise Exception(f"Failed to download after all mirrors: {error_msg}")
    
    def _show_error(self, message):
        dialog = ConfirmDialog(message, get_text("error"), self)
        dialog.cancel_btn.hide()
        dialog.exec()
    
    # ========================================
    # СКАЧИВАНИЕ
    # ========================================
    
    def _start_download(self, url: str, fmt: FormatOption):
        self._current_screen = "download"
        self._clear_content()
        self._download_cancel = False
        
        # Информация о видео
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 14px;
            }
        """)
        
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(24, 18, 24, 18)
        
        title = self.current_video_info.get('title', 'Video')[:60]
        title_label = QLabel(f"  {title}...")
        title_label.setStyleSheet(f"color: #FFFFFF; font-size: 15px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        
        format_label = QLabel(f"{get_text('select_quality')}: {fmt.name} ({fmt.description})")
        format_label.setStyleSheet(f"color: #888888; font-size: 13px; font-family: {MONO_FONT_FAMILY};")
        info_layout.addWidget(format_label)
        
        info_frame.setLayout(info_layout)
        self.content_layout.addWidget(info_frame)
        
        # Прогресс — три отдельных бара
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 14px;
            }
        """)

        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(24, 22, 24, 22)
        progress_layout.setSpacing(12)

        # Статус + скорость
        top_row = QHBoxLayout()
        self.status_label = QLabel(get_text("downloading"))
        self.status_label.setStyleSheet(f"color: #64C878; font-size: 14px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        top_row.addWidget(self.status_label)
        top_row.addStretch()
        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet(f"color: #888888; font-size: 13px; font-family: {MONO_FONT_FAMILY};")
        top_row.addWidget(self.speed_label)
        progress_layout.addLayout(top_row)

        is_audio_only = fmt.is_audio
        has_two_parts = not fmt.is_audio and fmt.needs_merge

        # ── Видео-бар
        if not is_audio_only:
            v_row = QHBoxLayout()
            v_lbl = QLabel("VIDEO")
            v_lbl.setStyleSheet(f"color: #64C878; font-size: 11px; font-weight: bold; font-family: {MONO_FONT_FAMILY}; letter-spacing: 1px;")
            v_row.addWidget(v_lbl)
            v_row.addStretch()
            progress_layout.addLayout(v_row)
            self.video_progress_bar = AnimatedProgressBar(color=(34, 211, 238))
            progress_layout.addWidget(self.video_progress_bar)
        else:
            self.video_progress_bar = None

        # ── Аудио-бар
        if is_audio_only or has_two_parts:
            a_row = QHBoxLayout()
            a_lbl = QLabel("AUDIO")
            a_lbl.setStyleSheet(f"color: #B478FF; font-size: 11px; font-weight: bold; font-family: {MONO_FONT_FAMILY}; letter-spacing: 1px;")
            a_row.addWidget(a_lbl)
            a_row.addStretch()
            progress_layout.addLayout(a_row)
            self.audio_progress_bar = AnimatedProgressBar(color=(180, 120, 255))
            progress_layout.addWidget(self.audio_progress_bar)
        else:
            self.audio_progress_bar = None

        # ── Shimmer-бар (Merging / Finalizing)
        if has_two_parts:
            self.merge_bar = ShimmerStatusBar(color=(255, 180, 50))
            progress_layout.addWidget(self.merge_bar)
        else:
            self.merge_bar = None

        progress_frame.setLayout(progress_layout)
        self.content_layout.addWidget(progress_frame)
        
        # Консоль
        self.console = ModernConsole()
        self.console.setMinimumHeight(220)
        self.content_layout.addWidget(self.console, 1)
        
        # Кнопка отмены
        cancel_btn = GlowButton(get_text("btn_cancel"), (255, 80, 80))
        cancel_btn.clicked.connect(self._cancel_download)
        self.content_layout.addWidget(cancel_btn)
        
        # Запуск скачивания
        threading.Thread(target=self._download_worker, args=(url, fmt), daemon=True).start()
    
    def _cancel_download(self):
        self._download_cancel = True
        self.log_signal.emit(get_text("download_cancelled"), "warning")
        QTimer.singleShot(500, self._show_home)
    
    def _download_worker(self, url: str, fmt: FormatOption):
        try:
            # Начальное сообщение
            self.log_signal.emit(f"[START] Starting download: {fmt.name} ({fmt.description})", "success")
            
            args = [self.ytdlp_exe, '--no-playlist', '--newline', '--progress']
            
            if fmt.is_audio:
                # Для аудио - извлекаем и конвертируем
                self.log_signal.emit(f"[INFO] Audio mode: {fmt.audio_codec.upper()} @ {fmt.audio_bitrate}kbps", "magenta")
                args.extend(['-x', '--audio-format', fmt.audio_codec])
                if fmt.audio_bitrate and fmt.audio_bitrate != "0":
                    args.extend(['--audio-quality', f'{fmt.audio_bitrate}K'])
            else:
                # Для видео - скачиваем лучшее видео + лучшее аудио отдельно и объединяем
                args.extend(['-f', fmt.format_str])
                
                if self.has_ffmpeg and fmt.needs_merge:
                    # Принудительное слияние в MP4 с перекодированием аудио в AAC
                    args.extend([
                        '--merge-output-format', 'mp4',
                        '--ppa', 'Merger:-c:v copy -c:a aac'
                    ])
                elif not self.has_ffmpeg:
                    # Без FFmpeg - скачиваем только видео с встроенным аудио
                    self.log_signal.emit("[WARNING] FFmpeg not found - downloading single stream", "warning")
                    args = [self.ytdlp_exe, '--no-playlist', '--newline', '--progress']
                    # Извлекаем высоту из description (например "1080p" -> 1080)
                    height_match = re.search(r'(\d+)p', fmt.description)
                    if height_match:
                        height = height_match.group(1)
                        args.extend(['-f', f'best[height<={height}]/best'])
                    else:
                        args.extend(['-f', 'best'])
            
            if self.ffmpeg_path:
                args.extend(['--ffmpeg-location', self.ffmpeg_path])
            
            # Качественный вывод
            output_template = os.path.join(self.download_folder, "%(title)s.%(ext)s")
            args.extend(['-o', output_template])
            
            # Добавляем URL в конец
            args.append(url)
            
            self.log_signal.emit(f"[CMD] {' '.join(args)}", "cyan")
            
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )
            
            current_part = 0
            total_parts = 2 if (not fmt.is_audio and fmt.needs_merge) else 1
            
            for line in process.stdout:
                if self._download_cancel:
                    process.terminate()
                    return
                
                line = line.strip()
                if not line:
                    continue
                
                # Парсинг прогресса: [download]  45.2% of  125.50MiB at  2.50MiB/s ETA 00:25
                # Проверяем, является ли это строкой с процентами (не логируем их, только парсим)
                m = re.search(r'\[download\]\s+(\d+\.?\d*)%', line)
                is_progress_line = m is not None
                
                # Логируем только важные сообщения (не прогресс-проценты)
                if not is_progress_line:
                    # Пропускаем известные предупреждения которые не критичны
                    skip_warnings = [
                        'No supported JavaScript runtime',
                        'YouTube extraction without a JS runtime',
                        'js-runtimes',
                        'EJS for details'
                    ]
                    if any(skip in line for skip in skip_warnings):
                        continue
                    
                    if '[download] Destination:' in line:
                        # Показываем куда скачивается
                        self.log_signal.emit(line, "cyan")
                    elif '[download]' in line and 'has already been downloaded' in line:
                        self.log_signal.emit("[INFO] File already exists, skipping...", "yellow")
                    elif '[download]' in line and '100%' in line:
                        # Показываем завершение скачивания части
                        self.log_signal.emit(line, "success")
                    elif '[Merger]' in line or '[ffmpeg]' in line:
                        self.log_signal.emit(line, "yellow")
                    elif 'error' in line.lower() and 'warning' not in line.lower():
                        self.log_signal.emit(line, "error")
                    elif '[ExtractAudio]' in line:
                        self.log_signal.emit(line, "magenta")
                    elif '[info]' in line.lower():
                        self.log_signal.emit(line, "info")
                    elif '[download]' not in line and 'WARNING' not in line:
                        # Другие сообщения (не download и не WARNING)
                        self.log_signal.emit(line, "gray")
                if m:
                    pct = float(m.group(1))
                    
                    speed = ""
                    eta = ""
                    size = ""
                    
                    # Парсим скорость
                    speed_m = re.search(r'at\s+([\d\.]+\s*\w+/s)', line)
                    if speed_m:
                        speed = speed_m.group(1)
                    
                    # Парсим ETA
                    eta_m = re.search(r'ETA\s+([\d:]+)', line)
                    if eta_m:
                        eta = eta_m.group(1)
                    
                    # Парсим размер
                    size_m = re.search(r'of\s+~?([\d\.]+\s*\w+)', line)
                    if size_m:
                        size = size_m.group(1)
                    
                    # Направляем прогресс в нужный бар
                    if fmt.is_audio:
                        self.audio_progress_signal.emit(pct)
                    elif total_parts == 2:
                        if current_part <= 1:
                            self.video_progress_signal.emit(pct)
                        else:
                            self.audio_progress_signal.emit(pct)
                    else:
                        self.video_progress_signal.emit(pct)
                    
                    # Формируем текст со скоростью
                    speed_parts = []
                    if speed:
                        speed_parts.append(f"{get_text('speed')}: {speed}")
                    if eta:
                        speed_parts.append(f"{get_text('eta')}: {eta}")
                    if size:
                        speed_parts.append(f"Size: {size}")
                    
                    if speed_parts:
                        self.speed_signal.emit("  •  ".join(speed_parts))
                
                # Новая часть - Destination означает начало скачивания файла
                if '[download] Destination:' in line:
                    current_part += 1
                    if current_part == 1:
                        if total_parts == 2:
                            self.status_signal.emit(f"{get_text('downloading_video')} (Part 1/2)")
                        else:
                            self.status_signal.emit(get_text("downloading_video"))
                    else:
                        self.status_signal.emit(f"{get_text('downloading_audio')} (Part 2/2)")
                
                # Файл уже существует или скачивается с продолжением
                if '[download]' in line and 'has already been downloaded' in line:
                    self.log_signal.emit("[INFO] File already exists, skipping...", "yellow")
                
                # Объединение видео и аудио
                if '[Merger]' in line or ('Merging' in line):
                    self.status_signal.emit(get_text("merging"))
                    self.merge_status_signal.emit(get_text("merging"))
                    self.speed_signal.emit("Processing...")
                
                # FFmpeg обработка
                if '[ffmpeg]' in line:
                    if 'Merging' in line:
                        self.status_signal.emit(get_text("merging"))
                        self.merge_status_signal.emit(get_text("merging"))
                    elif 'Destination' in line:
                        self.status_signal.emit("Finalizing...")
                        self.merge_status_signal.emit("Finalizing...")
                
                # Извлечение аудио
                if '[ExtractAudio]' in line:
                    self.status_signal.emit(get_text("extracting_audio"))
                    self.merge_status_signal.emit(get_text("extracting_audio"))

                # Конвертация
                if 'Converting' in line:
                    self.status_signal.emit("Converting...")
                    self.merge_status_signal.emit("Converting...")

                # Удаление временных файлов
                if 'Deleting original file' in line:
                    self.merge_status_signal.emit("Cleaning up...")
            
            process.wait()
            
            if process.returncode == 0 and not self._download_cancel:
                self.progress_signal.emit(100)
                self.status_signal.emit(get_text("download_complete"))
                self.speed_signal.emit("✓ Done!")
                self.download_complete_signal.emit()
            elif not self._download_cancel:
                self.download_failed_signal.emit(get_text("download_failed"))
        
        except Exception as e:
            self.log_signal.emit(f"[ERROR] {e}", "error")
            self.download_failed_signal.emit(str(e))
    
    def _on_download_complete(self):
        # Обновляем статус компонентов в реальном времени
        self._check_tools()
        self._update_tool_status()
        # Если мы на экране загрузки компонента - вернуться к компонентам
        if self._current_screen == "component_download":
            QTimer.singleShot(1000, self._show_components)
        else:
            QTimer.singleShot(1500, self._show_complete_screen)
    
    def _on_download_failed(self, error):
        self._stop_loading_spinner()
        self._show_error(error)
        self._show_home()
    
    def _show_complete_screen(self):
        self._clear_content()
        
        center_widget = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(24)
        
        # Иконка успеха
        icon = QLabel("✓")
        icon.setStyleSheet(f"""
            QLabel {{
                color: #64DC82;
                font-size: 72px;
                font-weight: bold;
                font-family: {MONO_FONT_FAMILY};
            }}
        """)
        icon.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(icon)
        
        # Заголовок
        title = QLabel(get_text("download_complete"))
        title.setStyleSheet(f"color: #64DC82; font-size: 24px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        title.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(title)
        
        # Путь
        path_label = QLabel(f"{get_text('saved_to')} {self.download_folder}")
        path_label.setStyleSheet(f"color: #888888; font-size: 13px; font-family: {MONO_FONT_FAMILY};")
        path_label.setAlignment(Qt.AlignCenter)
        path_label.setWordWrap(True)
        center_layout.addWidget(path_label)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(18)
        
        folder_btn = GlowButton(f"📁  {get_text('btn_open_folder')}", (34, 211, 238))
        folder_btn.clicked.connect(self._open_folder)
        btn_layout.addWidget(folder_btn)
        
        home_btn = GlowButton(f"🏠  {get_text('btn_home')}", (100, 220, 130))
        home_btn.clicked.connect(self._show_home)
        btn_layout.addWidget(home_btn)
        
        center_layout.addLayout(btn_layout)
        
        center_widget.setLayout(center_layout)
        self.content_layout.addStretch()
        self.content_layout.addWidget(center_widget)
        self.content_layout.addStretch()
    
    # ========================================
    # КОМПОНЕНТЫ
    # ========================================
    
    def _show_components(self):
        self._current_screen = "components"
        self._clear_content()
        
        # Обновляем статус компонентов
        self._check_tools()
        self._update_tool_status()
        
        # Заголовок
        header = QLabel(get_text("components_title"))
        header.setStyleSheet(f"color: #B478FF; font-size: 18px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        self.content_layout.addWidget(header)
        
        # yt-dlp
        self._create_component_card(
            "yt-dlp",
            "Core download engine",
            get_text("ytdlp_desc"),
            self.ytdlp_exe,
            self._install_ytdlp,
            self._uninstall_ytdlp
        )
        
        # ffmpeg
        self._create_component_card(
            "FFmpeg",
            "Media processing",
            get_text("ffmpeg_desc"),
            self.ffmpeg_path,
            self._install_ffmpeg,
            self._uninstall_ffmpeg
        )
        
        # Папка загрузок
        folder_frame = QFrame()
        folder_frame.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid rgba(100, 100, 100, 0.4);
                border-radius: 14px;
            }
        """)
        
        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(22, 18, 22, 18)
        
        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet("font-size: 28px;")
        folder_layout.addWidget(folder_icon)
        
        folder_info = QWidget()
        folder_info_layout = QVBoxLayout()
        folder_info_layout.setContentsMargins(12, 0, 0, 0)
        folder_info_layout.setSpacing(4)
        
        folder_name = QLabel(get_text("download_folder"))
        folder_name.setStyleSheet(f"color: #FFFFFF; font-size: 14px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        folder_info_layout.addWidget(folder_name)
        
        folder_path = QLabel(self.download_folder)
        folder_path.setStyleSheet(f"color: #888888; font-size: 12px; font-family: {MONO_FONT_FAMILY};")
        folder_path.setWordWrap(True)
        folder_info_layout.addWidget(folder_path)
        
        folder_info.setLayout(folder_info_layout)
        folder_layout.addWidget(folder_info, 1)
        
        change_btn = GlowButton(get_text("btn_change"), (34, 211, 238))
        change_btn.setFixedWidth(120)
        change_btn.clicked.connect(self._change_folder)
        folder_layout.addWidget(change_btn)
        
        folder_frame.setLayout(folder_layout)
        self.content_layout.addWidget(folder_frame)
        
        self.content_layout.addStretch()
    
    def _create_component_card(self, name, subtitle, description, path, install_cmd, uninstall_cmd):
        frame = QFrame()
        is_installed = bool(path)
        # Зелёные края если установлен, красные если нет
        if is_installed:
            border_color = "rgba(100, 220, 130, 0.5)"  # Зелёный
        else:
            border_color = "rgba(255, 80, 80, 0.5)"  # Красный
        
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(25, 25, 30, 0.9);
                border: 1.5px solid {border_color};
                border-radius: 14px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        
        # Заголовок
        header_layout = QHBoxLayout()
        
        icon = "✓" if is_installed else "○"
        icon_color = "#64DC82" if is_installed else "#FF5050"
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {icon_color}; font-size: 24px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        header_layout.addWidget(icon_label)
        
        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(12, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(f"color: #FFFFFF; font-size: 15px; font-weight: bold; font-family: {MONO_FONT_FAMILY};")
        info_layout.addWidget(name_label)
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: #888888; font-size: 12px; font-family: {MONO_FONT_FAMILY};")
        info_layout.addWidget(subtitle_label)
        
        info_widget.setLayout(info_layout)
        header_layout.addWidget(info_widget, 1)
        
        if is_installed:
            btn = GlowButton(get_text("btn_uninstall"), (255, 80, 80))
            btn.clicked.connect(uninstall_cmd)
        else:
            btn = GlowButton(get_text("btn_install"), (100, 220, 130))
            btn.clicked.connect(install_cmd)
        btn.setFixedWidth(130)
        header_layout.addWidget(btn)
        
        layout.addLayout(header_layout)
        
        # Описание
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"color: #666666; font-size: 12px; font-family: {MONO_FONT_FAMILY};")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Путь
        if is_installed and path:
            path_label = QLabel(f"Path: {path}")
            path_label.setStyleSheet(f"color: #555555; font-size: 11px; font-family: {MONO_FONT_FAMILY};")
            layout.addWidget(path_label)
        
        frame.setLayout(layout)
        self.content_layout.addWidget(frame)
    
    def _install_ytdlp(self):
        self._show_component_download_screen("yt-dlp", get_text("downloading_ytdlp"))
        threading.Thread(target=self._install_ytdlp_worker, daemon=True).start()
    
    def _install_ytdlp_worker(self):
        try:
            exe_ext = '.exe' if platform.system() == 'Windows' else ''
            if platform.system() == 'Windows':
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            else:
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
            
            dest = os.path.join(BIN_FOLDER, f'yt-dlp{exe_ext}')
            
            self.component_status_signal.emit(get_text("downloading_ytdlp"))
            self._download_with_progress(url, dest)
            
            if platform.system() != 'Windows':
                os.chmod(dest, 0o755)
            
            self.ytdlp_exe = dest
            self.component_status_signal.emit(get_text("install_success"))
            self.component_progress_signal.emit(100)
            self.download_complete_signal.emit()
        except Exception as e:
            self.download_failed_signal.emit(str(e))
    
    def _uninstall_ytdlp(self):
        dialog = ConfirmDialog(f"{get_text('uninstall_confirm')} yt-dlp?", "Uninstall", self)
        if dialog.exec() == QDialog.Accepted and dialog.confirmed:
            try:
                exe_ext = '.exe' if platform.system() == 'Windows' else ''
                path = os.path.join(BIN_FOLDER, f'yt-dlp{exe_ext}')
                if os.path.isfile(path):
                    os.remove(path)
                self.ytdlp_exe = ""
                self._show_components()
            except Exception as e:
                self._show_error(str(e))
    
    def _install_ffmpeg(self):
        self._show_component_download_screen("FFmpeg", get_text("downloading_ffmpeg"))
        threading.Thread(target=self._install_ffmpeg_worker, daemon=True).start()
    
    def _install_ffmpeg_worker(self):
        try:
            if platform.system() == 'Windows':
                url = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
                archive_ext = ".zip"
            else:
                url = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
                archive_ext = ".tar.xz"
            
            temp_dir = tempfile.gettempdir()
            archive_path = os.path.join(temp_dir, f"ffmpeg{archive_ext}")
            extract_path = os.path.join(temp_dir, "ffmpeg_extract")
            
            self.component_status_signal.emit(get_text("downloading_ffmpeg"))
            self._download_with_progress(url, archive_path)
            
            self.component_status_signal.emit("Extracting...")
            self.component_speed_signal.emit("Please wait...")
            
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
            
            if archive_ext == ".zip":
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(extract_path)
            else:
                import tarfile
                with tarfile.open(archive_path, 'r:xz') as tf:
                    tf.extractall(extract_path)
            
            self.component_status_signal.emit("Installing...")
            
            exe_ext = '.exe' if platform.system() == 'Windows' else ''
            for root, dirs, files in os.walk(extract_path):
                for f in files:
                    if f in [f'ffmpeg{exe_ext}', f'ffprobe{exe_ext}']:
                        src = os.path.join(root, f)
                        dst = os.path.join(BIN_FOLDER, f)
                        shutil.copy2(src, dst)
                        if platform.system() != 'Windows':
                            os.chmod(dst, 0o755)
            
            os.remove(archive_path)
            shutil.rmtree(extract_path)
            
            self.ffmpeg_path = BIN_FOLDER
            self.has_ffmpeg = True
            self.component_status_signal.emit(get_text("install_success"))
            self.component_progress_signal.emit(100)
            self.download_complete_signal.emit()
        except Exception as e:
            self.download_failed_signal.emit(str(e))
    
    def _uninstall_ffmpeg(self):
        dialog = ConfirmDialog(f"{get_text('uninstall_confirm')} FFmpeg?", "Uninstall", self)
        if dialog.exec() == QDialog.Accepted and dialog.confirmed:
            try:
                exe_ext = '.exe' if platform.system() == 'Windows' else ''
                for name in ['ffmpeg', 'ffprobe']:
                    path = os.path.join(BIN_FOLDER, f'{name}{exe_ext}')
                    if os.path.isfile(path):
                        os.remove(path)
                self.ffmpeg_path = ""
                self.has_ffmpeg = False
                self._show_components()
            except Exception as e:
                self._show_error(str(e))
    
    def _change_folder(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_folder)
        if folder:
            self.download_folder = folder
            self._save_config()
            self._show_components()
    
    def _open_folder(self):
        os.makedirs(self.download_folder, exist_ok=True)
        if platform.system() == 'Windows':
            os.startfile(self.download_folder)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', self.download_folder])
        else:
            subprocess.Popen(['xdg-open', self.download_folder])


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Установка иконки приложения
    app_icon = get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(13, 13, 13))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(20, 20, 24))
    palette.setColor(QPalette.Text, QColor(224, 224, 224))
    palette.setColor(QPalette.Button, QColor(30, 30, 35))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Link, QColor(34, 211, 238))
    palette.setColor(QPalette.Highlight, QColor(34, 211, 238))
    app.setPalette(palette)
    
    window = VideoDownloaderApp()
    window.show()
    sys.exit(app.exec())
