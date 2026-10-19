import json
import numpy as np
import sounddevice as sd
import vosk
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QFont, QGuiApplication
)
from core.utils.config import get_resource_path, load_config
from gui.styles import get_main_style


ENROLLMENT_PHRASES = [
    "Акира, подтверждаю калибровку моего голоса",
    "Сегодня отличный день для продуктивной работы",
    "Мой голос уникален и система меня узнаёт"
]


def _boost_audio_bytes(raw_bytes: bytes) -> bytes:
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
    samples = samples - np.mean(samples)
    peak = np.max(np.abs(samples))

    if peak > 10.0:
        target_peak = 20000.0
        gain = min(12.0, max(1.0, target_peak / max(peak, 1.0)))
        boosted = np.clip(samples * gain, -32768, 32767).astype(np.int16)
        return boosted.tobytes()
    return raw_bytes


class AudioRecorderThread(QThread):
    recording_finished = pyqtSignal(bytes)

    def __init__(self, duration=4.0, samplerate=16000, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.samplerate = samplerate
        self.is_recording = True

    def run(self):
        try:
            samples = int(self.duration * self.samplerate)
            audio = sd.rec(samples, samplerate=self.samplerate, channels=1, dtype='int16')
            sd.wait()
            if self.is_recording:
                boosted_bytes = _boost_audio_bytes(audio.tobytes())
                self.recording_finished.emit(boosted_bytes)
        except Exception as e:
            print(f"[Recorder Error]: {e}", flush=True)

    def stop(self):
        self.is_recording = False
        try:
            sd.stop()
        except Exception:
            pass


class QuickNameRecognizerThread(QThread):
    name_recognized = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samplerate = 16000
        self.duration = 2.5

    def run(self):
        try:
            samples = int(self.duration * self.samplerate)
            audio = sd.rec(samples, samplerate=self.samplerate, channels=1, dtype='int16')
            sd.wait()

            boosted_bytes = _boost_audio_bytes(audio.tobytes())

            model_path = get_resource_path("optimized_models", "model_vosk")
            vosk.SetLogLevel(-1)
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, self.samplerate)

            if rec.AcceptWaveform(boosted_bytes):
                res = json.loads(rec.Result())
            else:
                res = json.loads(rec.FinalResult())

            text = res.get("text", "").strip()
            if text:
                words = text.split()
                clean_name = words[-1].title()
                self.name_recognized.emit(clean_name)
            else:
                self.name_recognized.emit("")
        except Exception as e:
            print(f"[Name Recognition Error]: {e}", flush=True)
            self.name_recognized.emit("")


class VoiceEnrollmentDialog(QDialog):
    enrollment_completed = pyqtSignal()

    def __init__(self, verifier, is_owner=True, font_family="Arial", parent=None, theme: str = None):
        super().__init__(parent)
        self.verifier = verifier
        self.is_owner = is_owner
        self.font_family = font_family
        self.drag_position = QPoint()

        if theme:
            self.current_theme = theme
        elif parent and hasattr(parent, 'current_theme'):
            self.current_theme = parent.current_theme
        elif parent and hasattr(parent, 'window') and hasattr(parent.window(), 'current_theme'):
            self.current_theme = parent.window().current_theme
        else:
            cfg = load_config()
            self.current_theme = cfg.get("theme", "dark")

        self.step = 0 if not is_owner else 1
        self.current_phrase_idx = 0
        self.recorded_samples_count = 0

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 420)
        self.setStyleSheet(get_main_style(self.current_theme))

        self._center_on_screen(parent)

        self.recorder_thread = None
        self.name_thread = None

        self._set_background_stt_paused(True)

        self.init_ui()
        self._update_step_view()

    def _center_on_screen(self, parent=None):
        if parent and hasattr(parent, 'window') and parent.window() and parent.window().screen():
            screen = parent.window().screen().availableGeometry()
        else:
            screen = QGuiApplication.primaryScreen().availableGeometry()

        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _restore_parent_focus(self):
        if self.parent():
            top = self.parent().window()
            if top:
                top.activateWindow()
                top.raise_()
                top.setFocus()

    def _set_background_stt_paused(self, paused: bool):
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'stt_thread') and widget.stt_thread:
                widget.stt_thread.set_speaking(paused)
                return

        p = self.parent()
        while p:
            if hasattr(p, 'stt_thread') and p.stt_thread:
                p.stt_thread.set_speaking(paused)
                return
            p = p.parent()

    def closeEvent(self, event):
        self._set_background_stt_paused(False)
        self._restore_parent_focus()
        super().closeEvent(event)

    def reject(self):
        if self.recorder_thread and self.recorder_thread.isRunning():
            self.recorder_thread.stop()
        self._set_background_stt_paused(False)
        self._restore_parent_focus()
        super().reject()

    def accept(self):
        self._set_background_stt_paused(False)
        self._restore_parent_focus()
        super().accept()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        header_title = "Калибровка голоса создателя" if self.is_owner else "Добавление нового пользователя"
        self.title_lbl = QLabel(header_title)
        self.title_lbl.setFont(QFont(self.font_family, 13, QFont.Weight.Bold))
        title_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.title_lbl.setStyleSheet(f"color: {title_color}; letter-spacing: 0.5px; background: transparent; border: none;")
        header.addWidget(self.title_lbl)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.card = QFrame()
        self.card.setObjectName("EnrollmentCard")
        if self.current_theme == "light":
            self.card.setStyleSheet("""
                QFrame#EnrollmentCard {
                    background-color: rgba(255, 255, 255, 0.85);
                    border: 1.5px solid rgba(17, 19, 24, 0.22);
                    border-radius: 12px;
                }
                QLabel {
                    background: transparent;
                    border: none;
                }
            """)
        else:
            self.card.setStyleSheet("""
                QFrame#EnrollmentCard {
                    background-color: rgba(18, 15, 8, 0.75);
                    border: 1px solid #78735f;
                    border-radius: 12px;
                }
                QLabel {
                    background: transparent;
                    border: none;
                }
            """)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(22, 22, 22, 22)
        self.card_layout.setSpacing(14)

        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont(self.font_family, 13, QFont.Weight.Bold))
        status_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.status_lbl.setStyleSheet(f"color: {status_color};")
        self.status_lbl.setWordWrap(True)
        self.card_layout.addWidget(self.status_lbl)

        self.desc_lbl = QLabel("")
        self.desc_lbl.setFont(QFont(self.font_family, 11))
        desc_color = "rgba(17, 19, 24, 0.75)" if self.current_theme == "light" else "rgba(255, 253, 231, 0.85)"
        self.desc_lbl.setStyleSheet(f"color: {desc_color}; line-height: 1.45;")
        self.desc_lbl.setWordWrap(True)
        self.card_layout.addWidget(self.desc_lbl)

        self.name_container = QFrame()
        self.name_container.setObjectName("NameInputBox")
        if self.current_theme == "light":
            self.name_container.setStyleSheet("""
                QFrame#NameInputBox {
                    background-color: #ffffff;
                    border: 1.5px solid #111318;
                    border-radius: 8px;
                }
                QFrame#NameInputBox:hover {
                    border: 1.5px solid #000000;
                }
                QFrame#NameInputBox:focus-within {
                    border: 2px solid #000000;
                }
            """)
        else:
            self.name_container.setStyleSheet("""
                QFrame#NameInputBox {
                    background-color: rgba(6, 6, 4, 0.9);
                    border: 1.2px solid #78735f;
                    border-radius: 8px;
                }
                QFrame#NameInputBox:hover {
                    border: 1.2px solid #9e9780;
                }
                QFrame#NameInputBox:focus-within {
                    border: 1.2px solid #ded7c4;
                }
            """)
        name_layout = QHBoxLayout(self.name_container)
        name_layout.setContentsMargins(12, 4, 6, 4)
        name_layout.setSpacing(6)

        self.name_input = QLineEdit()
        self.name_input.setFont(QFont(self.font_family, 11))
        self.name_input.setFixedHeight(30)
        self.name_input.setPlaceholderText("Введи имя или назови вслух...")
        name_input_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {name_input_color};
            }}
        """)
        self.name_input.returnPressed.connect(self._on_action_clicked)
        name_layout.addWidget(self.name_input, 1)

        self.mic_name_btn = QPushButton("🎙")
        self.mic_name_btn.setFixedSize(30, 30)
        self.mic_name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.current_theme == "light":
            self.mic_name_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #111318;
                    font-size: 15px;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    color: #000000;
                    background-color: rgba(17, 19, 24, 0.1);
                }
            """)
        else:
            self.mic_name_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #78735f;
                    font-size: 15px;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    color: #ded7c4;
                    background-color: rgba(120, 115, 95, 0.2);
                }
            """)
        self.mic_name_btn.clicked.connect(self._start_listen_name)
        name_layout.addWidget(self.mic_name_btn)
        self.card_layout.addWidget(self.name_container)

        self.phrase_box = QFrame()
        self.phrase_box.setObjectName("PhraseBox")
        if self.current_theme == "light":
            self.phrase_box.setStyleSheet("""
                QFrame#PhraseBox {
                    background-color: rgba(238, 242, 248, 0.7);
                    border: 1.5px dashed rgba(17, 19, 24, 0.35);
                    border-radius: 8px;
                }
            """)
        else:
            self.phrase_box.setStyleSheet("""
                QFrame#PhraseBox {
                    background-color: rgba(6, 6, 4, 0.9);
                    border: 1px dashed #78735f;
                    border-radius: 8px;
                }
            """)
        phrase_layout = QVBoxLayout(self.phrase_box)
        phrase_layout.setContentsMargins(14, 14, 14, 14)

        self.phrase_text_lbl = QLabel("")
        self.phrase_text_lbl.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        phrase_color = "#111318" if self.current_theme == "light" else "#ded7c4"
        self.phrase_text_lbl.setStyleSheet(f"color: {phrase_color}; background: transparent; border: none;")
        self.phrase_text_lbl.setWordWrap(True)
        self.phrase_text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phrase_layout.addWidget(self.phrase_text_lbl)
        self.card_layout.addWidget(self.phrase_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("VoiceProgressBar")
        self.progress_bar.setRange(0, 3)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        if self.current_theme == "light":
            self.progress_bar.setStyleSheet("""
                QProgressBar#VoiceProgressBar {
                    background-color: rgba(17, 19, 24, 0.1);
                    border: none;
                    border-radius: 3px;
                }
                QProgressBar#VoiceProgressBar::chunk {
                    background-color: #111318;
                    border-radius: 3px;
                }
            """)
        else:
            self.progress_bar.setStyleSheet("""
                QProgressBar#VoiceProgressBar {
                    background-color: rgba(255, 255, 255, 0.08);
                    border: none;
                    border-radius: 3px;
                }
                QProgressBar#VoiceProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #444034, stop:1 #ded7c4);
                    border-radius: 3px;
                }
            """)
        self.card_layout.addWidget(self.progress_bar)
        self.card_layout.addStretch()

        layout.addWidget(self.card, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.action_btn = QPushButton("Начать запись")
        self.action_btn.setObjectName("VoiceActionBtn")
        self.action_btn.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setFixedHeight(36)
        self.action_btn.setFixedWidth(190)
        if self.current_theme == "light":
            self.action_btn.setStyleSheet("""
                QPushButton#VoiceActionBtn {
                    background-color: #111318;
                    color: #ffffff;
                    font-weight: bold;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 16px;
                }
                QPushButton#VoiceActionBtn:hover {
                    background-color: #2b313d;
                }
                QPushButton#VoiceActionBtn:disabled {
                    background-color: rgba(17, 19, 24, 0.35);
                    color: rgba(255, 255, 255, 0.6);
                }
            """)
        else:
            self.action_btn.setStyleSheet("""
                QPushButton#VoiceActionBtn {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                    color: #121008;
                    font-weight: bold;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 16px;
                }
                QPushButton#VoiceActionBtn:hover {
                    background: #ffffff;
                }
                QPushButton#VoiceActionBtn:disabled {
                    background: rgba(237, 232, 219, 0.35);
                    color: rgba(18, 16, 8, 0.45);
                }
            """)
        self.action_btn.clicked.connect(self._on_action_clicked)
        bottom_row.addWidget(self.action_btn)
        layout.addLayout(bottom_row)

    def _update_step_view(self):
        if self.step == 0:
            self.status_lbl.setText("Подтверждение создателя")
            self.desc_lbl.setText(
                "Добавить новый профиль может только владелец системы. Нажми 'Подтвердить' и произнеси фразу обычным голосом."
            )
            self.name_container.hide()
            self.phrase_box.hide()
            self.progress_bar.hide()
            self.action_btn.setText("Подтвердить")
        elif self.step == 1:
            self.status_lbl.setText("Знакомство")
            target = "своё имя" if self.is_owner else "имя пользователя"
            self.desc_lbl.setText(f"Укажи {target}. Можно напечатать в строке или нажать на микрофон и назвать имя вслух:")
            self.name_container.show()
            self.phrase_box.hide()
            self.progress_bar.hide()
            self.action_btn.setText("Перейти к записи →")
        elif self.step == 2:
            self.status_lbl.setText(f"Калибровка голоса ({self.current_phrase_idx + 1}/3) 🎙")
            self.desc_lbl.setText("Произнеси фразу четко в микрофон обычным тоном:")
            self.name_container.hide()
            self.phrase_box.show()
            self.phrase_text_lbl.setText(f"«{ENROLLMENT_PHRASES[self.current_phrase_idx]}»")
            self.progress_bar.show()
            self.progress_bar.setValue(self.current_phrase_idx)
            self.action_btn.setText("Записать фразу")

    def _start_listen_name(self):
        self.mic_name_btn.setEnabled(False)
        self.name_input.setPlaceholderText("Слушаю имя...")
        self.name_thread = QuickNameRecognizerThread(self)
        self.name_thread.name_recognized.connect(self._on_name_recognized)
        self.name_thread.start()

    def _on_name_recognized(self, name):
        self.mic_name_btn.setEnabled(True)
        self.name_input.setPlaceholderText("Введи имя или назови вслух...")
        if name:
            self.name_input.setText(name)
            self.name_input.setFocus()

    def _on_action_clicked(self):
        if self.step == 0:
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Слушаю владельца...")
            self.recorder_thread = AudioRecorderThread(duration=3.5, parent=self)
            self.recorder_thread.recording_finished.connect(self._verify_owner_recording)
            self.recorder_thread.start()

        elif self.step == 1:
            name = self.name_input.text().strip()
            if not name:
                self.name_input.setFocus()
                return
            self.user_name = name
            self.verifier.start_enrollment()
            self.step = 2
            self.current_phrase_idx = 0
            self._update_step_view()

        elif self.step == 2:
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Идёт запись...")
            self.recorder_thread = AudioRecorderThread(duration=4.0, parent=self)
            self.recorder_thread.recording_finished.connect(self._on_phrase_recorded)
            self.recorder_thread.start()

    def _verify_owner_recording(self, audio_data):
        self.action_btn.setEnabled(True)
        is_rec, name, score, is_owner = self.verifier.verify(audio_data)

        if is_rec and is_owner:
            self.step = 1
            self._update_step_view()
        else:
            self.status_lbl.setText("Голос не опознан")
            self.desc_lbl.setText("Верификация не пройдена. Пожалуйста, повтори попытку обычным голосом ближе к микрофону.")
            self.action_btn.setText("Попробовать снова")

    def _on_phrase_recorded(self, audio_data):
        ok, count = self.verifier.add_enrollment_sample(audio_data)
        self.action_btn.setEnabled(True)

        if ok:
            self.current_phrase_idx += 1
            if self.current_phrase_idx >= len(ENROLLMENT_PHRASES):
                self.verifier.commit_enrollment(self.user_name, is_owner=self.is_owner)
                self.enrollment_completed.emit()
                self.accept()
            else:
                self._update_step_view()
        else:
            self.desc_lbl.setText("Фраза получилась слишком тихой или неразборчивой. Давай повторим её ещё разок:")
            self.action_btn.setText("Повторить фразу")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = QPoint()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        if self.current_theme == "light":
            painter.fillPath(path, QColor(238, 242, 248, 252))
            pen_border = QPen(QColor("#111318"), 1.5)
        else:
            painter.fillPath(path, QColor(8, 8, 5, 248))
            pen_border = QPen(QColor("#78735f"), 1.4)

        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)