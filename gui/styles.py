DARK_STYLE = """
QFrame#LeftPanel {
    background: transparent;
    border: none;
}
QFrame#RightPanel {
    background-color: rgba(8, 8, 5, 0.94);
    border: none;
    border-radius: 12px;
}
QFrame#SettingsPanel {
    background-color: rgba(6, 6, 4, 0.96);
    border: none;
    border-radius: 12px;
}
QTextEdit#ChatHistory {
    background-color: transparent;
    color: #fffde7;
    border: none;
    font-size: 13px;
}
QLineEdit#InputField {
    background-color: #070705;
    color: #fffde7;
    border: 1px solid #78735f;
    border-radius: 8px;
    padding: 2px 10px 6px 10px;
    font-size: 13px;
}
QLineEdit#InputField:focus {
    border: 1px solid #9e9780;
    background-color: #090907;
}
QPushButton#SendButton {
    background-color: #dcd8cf;
    color: #0d0a05;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton#SendButton:hover {
    background-color: #ffffff;
}
QPushButton#AttachBtn {
    background-color: #070705;
    color: #ded7c4;
    font-size: 13px;
    border: 1px solid #78735f;
    border-radius: 8px;
    padding: 0px;
    outline: none;
}
QPushButton#AttachBtn:hover {
    background-color: #11110e;
    border: 1px solid #9e9780;
    color: #ffffff;
}
QLabel#FileLabel {
    color: #ded7c4;
    font-size: 11px;
    font-style: italic;
    background: transparent;
    padding-bottom: 4px;
}
QPushButton#TitleBtn {
    background-color: transparent;
    color: #78735f;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#TitleBtn:hover {
    background-color: rgba(120, 115, 95, 0.2);
    color: #ffffff;
}
QPushButton#MinBtn {
    background-color: transparent;
    color: #ffffff;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#MinBtn:hover {
    background-color: rgba(255, 255, 255, 0.15);
    color: #ffffff;
}
QPushButton#CloseBtn {
    background-color: transparent;
    color: #ffffff;
    font-size: 14px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#CloseBtn:hover {
    background-color: #ff5252;
    color: #ffffff;
}

QLabel#SettingsMainTitle {
    color: #fffde7;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

QFrame#SettingsCard {
    background-color: rgba(12, 11, 8, 0.70);
    border: 1px solid rgba(120, 115, 95, 0.25);
    border-radius: 10px;
}
QWidget#SettingsCard > QWidget:hover {
    background-color: rgba(158, 151, 128, 0.05);
    border-radius: 6px;
}

QLabel#CardHeader {
    color: #ded7c4;
    letter-spacing: 1.4px;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}

QLabel#ToggleLabel {
    color: #fffde7;
    font-size: 11px;
}

QLabel#FieldLabel {
    color: rgba(255, 253, 231, 0.75);
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

QLineEdit#SettingInput {
    background-color: rgba(7, 7, 5, 0.90);
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 6px;
    padding: 6px 10px;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-size: 11px;
}
QLineEdit#SettingInput:focus {
    border: 1px solid #9e9780;
    background-color: #090907;
}

QComboBox#SettingCombo {
    background-color: rgba(7, 7, 5, 0.90);
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 6px;
    padding: 4px 28px 4px 10px;
    font-size: 11px;
}
QComboBox#SettingCombo:focus {
    border: 1px solid #9e9780;
}
QComboBox#SettingCombo::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}
QComboBox#SettingCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView {
    background-color: #0c0b08;
    color: #ded7c4;
    selection-background-color: #2b2820;
    selection-color: #ffffff;
    border: 1px solid #78735f;
    border-radius: 6px;
    outline: none;
}

QSlider#VoiceSlider::groove:horizontal {
    height: 3px;
    background: rgba(120, 115, 95, 0.35);
    border-radius: 1px;
}
QSlider#VoiceSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #444034, stop:1 #ded7c4);
    border-radius: 1px;
}
QSlider#VoiceSlider::handle:horizontal {
    background: #ded7c4;
    border: 1px solid #ffffff;
    width: 12px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 6px;
}
QSlider#VoiceSlider::handle:horizontal:hover {
    background: #ffffff;
}

QPushButton#HintCircleBtn {
    background-color: #12100c;
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 8px;
    font-weight: bold;
    font-size: 9px;
    padding: 0px;
    outline: none;
}
QPushButton#HintCircleBtn:hover {
    background-color: #1e1b14;
    color: #ffffff;
    border: 1px solid #9e9780;
}

QPushButton#GuideCircleBtn {
    background-color: #12100c;
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 8px;
    font-size: 8px;
    font-weight: bold;
    letter-spacing: 0.5px;
    padding: 0px;
    outline: none;
}
QPushButton#GuideCircleBtn:hover {
    background-color: #1e1b14;
    color: #ffffff;
    border: 1px solid #9e9780;
}

QPushButton#SaveSettingsButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #121008;
    font-weight: bold;
    letter-spacing: 1px;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 11px;
    text-transform: uppercase;
}
QPushButton#SaveSettingsButton:hover {
    background: #ffffff;
}

QScrollArea#SettingsScroll {
    background: transparent;
    border: none;
}
QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 4px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(120, 115, 95, 0.45);
    min-height: 25px;
    border-radius: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #9e9780;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QPushButton#RemoveFileBtn {
    background-color: transparent;
    color: #ff5252;
    font-size: 11px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 0px;
}
QPushButton#RemoveFileBtn:hover {
    background-color: rgba(255, 82, 82, 0.2);
    color: #ff7b7b;
}

QTextEdit#GuideContent {
    background-color: rgba(14, 12, 7, 0.65);
    color: #fffde7;
    border: 1px solid rgba(120, 115, 95, 0.35);
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    line-height: 1.4;
}

QPushButton#GuideCloseBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #121008;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    letter-spacing: 0.5px;
}
QPushButton#GuideCloseBtn:hover {
    background: #ffffff;
}
QPushButton#ExitBtn {
    background-color: transparent;
    color: #ffffff;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#ExitBtn:hover {
    background-color: rgba(120, 115, 95, 0.2);
    color: #ffffff;
}

QProgressBar#UpdateProgressBar {
    background-color: rgba(5, 5, 3, 0.9);
    border: 1px solid rgba(120, 115, 95, 0.4);
    border-radius: 7px;
    text-align: center;
    color: #ded7c4;
    font-size: 10px;
    font-weight: bold;
    height: 20px;
}
QProgressBar#UpdateProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #444034, stop:1 #ded7c4);
    border-radius: 6px;
}

QPushButton#UpdateButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #0d0a05;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
QPushButton#UpdateButton:hover {
    background: #ffffff;
}

QPushButton#UpdateNotificationBadge {
    background-color: rgba(222, 215, 196, 0.12);
    color: #ded7c4;
    border: 1px solid rgba(222, 215, 196, 0.35);
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: bold;
    height: 20px;
}
QPushButton#UpdateNotificationBadge:hover {
    background-color: #ded7c4;
    color: #0d0a05;
    border: 1px solid #ffffff;
}
QLabel#AuthorLabel {
    color: rgba(255, 255, 255, 0.30);
    font-size: 9px;
    letter-spacing: 1px;
    padding-bottom: 2px;
    text-transform: uppercase;
}

QLabel#AuthDialogTitle {
    color: #ded7c4;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#AuthDialogDesc {
    color: #fffde7;
    line-height: 1.4;
}
QFrame#AuthCodeCard {
    background-color: rgba(14, 12, 7, 0.75);
    border: 1px solid rgba(120, 115, 95, 0.35);
    border-radius: 8px;
}
QLabel#AuthCodeLabel {
    color: #ded7c4;
    letter-spacing: 3px;
}
QLabel#AuthDialogStatus {
    color: rgba(255, 253, 231, 0.6);
}
QPushButton#AuthCopyBtn {
    background-color: rgba(120, 115, 95, 0.20);
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
QPushButton#AuthCopyBtn:hover {
    background-color: rgba(158, 151, 128, 0.25);
    border: 1px solid #9e9780;
    color: #ffffff;
}
QPushButton#AuthOpenBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #080805;
    border: none;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
QPushButton#AuthOpenBtn:hover {
    background: #ffffff;
}

QFrame#ModeItemCard {
    background-color: rgba(14, 12, 7, 0.75);
    border: 1px solid rgba(120, 115, 95, 0.25);
    border-radius: 8px;
}
QFrame#ModeItemCard:hover {
    border: 1px solid rgba(158, 151, 128, 0.45);
    background-color: rgba(20, 18, 14, 0.85);
}
QLabel#ModeItemTitle {
    color: #fffde7;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 0.5px;
}
QLabel#ModeItemPath {
    color: rgba(255, 253, 231, 0.45);
    font-size: 9px;
    font-family: 'Consolas', 'Segoe UI', monospace;
}

QFrame#IotCard {
    background-color: rgba(14, 12, 7, 0.75);
    border: 1px solid rgba(120, 115, 95, 0.35);
    border-radius: 8px;
}
QLabel#IotFieldLabel {
    color: rgba(255, 253, 231, 0.75);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#IotStatusLabel {
    color: rgba(255, 253, 231, 0.6);
}
QPushButton#IotAuthBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #080805;
    border: none;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
QPushButton#IotAuthBtn:hover {
    background: #ffffff;
}

QLabel#SpotifyDialogTitle {
    color: #ded7c4;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#SpotifyDialogDesc {
    color: #fffde7;
}
QFrame#SpotifyCard {
    background-color: rgba(14, 12, 7, 0.75);
    border: 1px solid rgba(120, 115, 95, 0.35);
    border-radius: 8px;
}
QLabel#SpotifyFieldLabel {
    color: rgba(255, 253, 231, 0.75);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#SpotifyStatusLabel {
    color: rgba(255, 253, 231, 0.6);
}
QPushButton#SpotifyAuthBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #080805;
    border: none;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
QPushButton#SpotifyAuthBtn:hover {
    background: #ffffff;
}

QLabel#GigaChatDialogTitle {
    color: #ded7c4;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#GigaChatDialogDesc {
    color: #fffde7;
}
QFrame#GigaChatCard {
    background-color: rgba(14, 12, 7, 0.75);
    border: 1px solid rgba(120, 115, 95, 0.35);
    border-radius: 8px;
}
QLabel#GigaChatFieldLabel {
    color: rgba(255, 253, 231, 0.75);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#GigaChatStatusLabel {
    color: rgba(255, 253, 231, 0.6);
}
QPushButton#GigaChatOpenBtn {
    background-color: rgba(120, 115, 95, 0.20);
    color: #ded7c4;
    border: 1px solid #78735f;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
QPushButton#GigaChatOpenBtn:hover {
    background-color: rgba(158, 151, 128, 0.25);
    border: 1px solid #9e9780;
    color: #ffffff;
}
QPushButton#GigaChatSaveBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #080805;
    border: none;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
QPushButton#GigaChatSaveBtn:hover {
    background: #ffffff;
}

QFrame#BentoCard {
    background-color: rgba(12, 11, 8, 0.72);
    border: 1px solid rgba(120, 115, 95, 0.28);
    border-radius: 12px;
}
QFrame#BentoCard:hover {
    border: 1px solid rgba(158, 151, 128, 0.45);
    background-color: rgba(16, 15, 11, 0.80);
}

QFrame#BentoCell {
    background-color: rgba(7, 7, 5, 0.65);
    border: 1px solid rgba(120, 115, 95, 0.22);
    border-radius: 9px;
}
QFrame#BentoCell:hover {
    background-color: rgba(20, 18, 14, 0.75);
    border: 1px solid rgba(158, 151, 128, 0.40);
}

QLabel#BentoSectionTitle {
    color: #ded7c4;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}

QLabel#BentoCellTitle {
    color: #fffde7;
    font-size: 11px;
    font-weight: bold;
}

QLabel#BentoCellDesc {
    color: rgba(255, 253, 231, 0.55);
    font-size: 9px;
}

QLabel#BentoStatusActive {
    color: #ded7c4;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 0.6px;
}

QLabel#BentoStatusIdle {
    color: rgba(255, 253, 231, 0.45);
    font-size: 9px;
    letter-spacing: 0.5px;
}

QPushButton#BentoActionBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #121008;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 9px;
    letter-spacing: 0.5px;
}
QPushButton#BentoActionBtn:hover {
    background: #ffffff;
}
QWidget#TitleBtnsWidget {
    background-color: rgba(14, 12, 7, 0.55);
    border: 1px solid rgba(120, 115, 95, 0.25);
    border-radius: 9px;
    padding: 1px 4px;
}
QPushButton#TitleBtn {
    background-color: transparent;
    border: none;
    padding: 3px;
    border-radius: 5px;
}
QPushButton#TitleBtn:hover {
    background-color: rgba(120, 115, 95, 0.22);
}
QPushButton#ExitBtn {
    background-color: transparent;
    border: none;
    padding: 3px;
    border-radius: 5px;
}
QPushButton#ExitBtn:hover {
    background-color: rgba(255, 82, 82, 0.22);
}
"""

LIGHT_STYLE = """
QFrame#LeftPanel {
    background: transparent;
    border: none;
}
QFrame#RightPanel {
    background-color: rgba(238, 242, 248, 0.82);
    border: none;
    border-radius: 12px;
}
QFrame#SettingsPanel {
    background-color: rgba(234, 238, 246, 0.85);
    border: none;
    border-radius: 12px;
}
QTextEdit#ChatHistory {
    background-color: transparent;
    color: #111318;
    border: none;
    font-size: 13px;
}
QLineEdit#InputField {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 8px;
    padding: 2px 10px 6px 10px;
    font-size: 13px;
}
QLineEdit#InputField:focus {
    border: 2px solid #000000;
    background-color: #ffffff;
}
QPushButton#SendButton {
    background-color: #111318;
    color: #ffffff;
    font-weight: bold;
    border: 1.5px solid #111318;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton#SendButton:hover {
    background-color: #2b313d;
    border-color: #2b313d;
}
QPushButton#AttachBtn {
    background-color: #ffffff;
    color: #111318;
    font-size: 13px;
    border: 1.5px solid #111318;
    border-radius: 8px;
    padding: 0px;
    outline: none;
}
QPushButton#AttachBtn:hover {
    background-color: #111318;
    color: #ffffff;
    border: 1.5px solid #111318;
}
QLabel#FileLabel {
    color: #2b313d;
    font-size: 11px;
    font-style: italic;
    background: transparent;
    padding-bottom: 4px;
}
QPushButton#TitleBtn {
    background-color: transparent;
    color: #111318;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#TitleBtn:hover {
    background-color: rgba(17, 19, 24, 0.12);
    color: #000000;
}
QPushButton#MinBtn {
    background-color: transparent;
    color: #111318;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#MinBtn:hover {
    background-color: rgba(17, 19, 24, 0.12);
    color: #000000;
}
QPushButton#CloseBtn {
    background-color: transparent;
    color: #111318;
    font-size: 14px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#CloseBtn:hover {
    background-color: #e53935;
    color: #ffffff;
}

QLabel#SettingsMainTitle {
    color: #111318;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

QFrame#SettingsCard {
    background-color: rgba(255, 255, 255, 0.85);
    border: 1.5px solid rgba(17, 19, 24, 0.18);
    border-radius: 10px;
}
QWidget#SettingsCard > QWidget:hover {
    background-color: rgba(17, 19, 24, 0.06);
    border-radius: 6px;
}

QLabel#CardHeader {
    color: #111318;
    letter-spacing: 1.4px;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}

QLabel#ToggleLabel {
    color: #111318;
    font-size: 11px;
}

QLabel#FieldLabel {
    color: rgba(17, 19, 24, 0.75);
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

QLineEdit#SettingInput {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 6px;
    padding: 6px 10px;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-size: 11px;
}
QLineEdit#SettingInput:focus {
    border: 2px solid #000000;
    background-color: #ffffff;
}

QComboBox#SettingCombo {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 6px;
    padding: 4px 28px 4px 10px;
    font-size: 11px;
}
QComboBox#SettingCombo:focus {
    border: 2px solid #000000;
}
QComboBox#SettingCombo::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}
QComboBox#SettingCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #111318;
    selection-background-color: #e2e8f0;
    selection-color: #000000;
    border: 1.5px solid #111318;
    border-radius: 6px;
    outline: none;
}

QSlider#VoiceSlider::groove:horizontal {
    height: 3px;
    background: rgba(17, 19, 24, 0.25);
    border-radius: 1px;
}
QSlider#VoiceSlider::sub-page:horizontal {
    background: #111318;
    border-radius: 1px;
}
QSlider#VoiceSlider::handle:horizontal {
    background: #111318;
    border: 1px solid #ffffff;
    width: 12px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 6px;
}
QSlider#VoiceSlider::handle:horizontal:hover {
    background: #000000;
}

QPushButton#HintCircleBtn {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 8px;
    font-weight: bold;
    font-size: 9px;
    padding: 0px;
    outline: none;
}
QPushButton#HintCircleBtn:hover {
    background-color: #111318;
    color: #ffffff;
}

QPushButton#GuideCircleBtn {
    background-color: #ffffff;
    color: #111318;
    border: 1.5px solid #111318;
    border-radius: 8px;
    font-size: 8px;
    font-weight: bold;
    letter-spacing: 0.5px;
    padding: 0px;
    outline: none;
}
QPushButton#GuideCircleBtn:hover {
    background-color: #111318;
    color: #ffffff;
}

QPushButton#SaveSettingsButton {
    background-color: #111318;
    color: #ffffff;
    font-weight: bold;
    letter-spacing: 1px;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 11px;
    text-transform: uppercase;
}
QPushButton#SaveSettingsButton:hover {
    background-color: #2b313d;
}

QScrollArea#SettingsScroll {
    background: transparent;
    border: none;
}
QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 4px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(17, 19, 24, 0.40);
    min-height: 25px;
    border-radius: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #111318;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QPushButton#RemoveFileBtn {
    background-color: transparent;
    color: #e53935;
    font-size: 11px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 0px;
}
QPushButton#RemoveFileBtn:hover {
    background-color: rgba(229, 57, 53, 0.15);
    color: #c62828;
}

QTextEdit#GuideContent {
    background-color: rgba(255, 255, 255, 0.92);
    color: #111318;
    border: 1.5px solid rgba(17, 19, 24, 0.25);
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    line-height: 1.4;
}

QPushButton#GuideCloseBtn {
    background-color: #111318;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    letter-spacing: 0.5px;
}
QPushButton#GuideCloseBtn:hover {
    background-color: #2b313d;
}
QPushButton#ExitBtn {
    background-color: transparent;
    color: #111318;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#ExitBtn:hover {
    background-color: rgba(17, 19, 24, 0.12);
    color: #000000;
}

QProgressBar#UpdateProgressBar {
    background-color: rgba(226, 232, 240, 0.9);
    border: 1.5px solid rgba(17, 19, 24, 0.25);
    border-radius: 7px;
    text-align: center;
    color: #111318;
    font-size: 10px;
    font-weight: bold;
    height: 20px;
}
QProgressBar#UpdateProgressBar::chunk {
    background-color: #111318;
    border-radius: 6px;
}

QPushButton#UpdateButton {
    background-color: #111318;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
QPushButton#UpdateButton:hover {
    background-color: #2b313d;
}

QPushButton#UpdateNotificationBadge {
    background-color: #111318;
    color: #ffffff;
    border: 1px solid #111318;
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: bold;
    height: 20px;
}
QPushButton#UpdateNotificationBadge:hover {
    background-color: #2b313d;
    border-color: #2b313d;
    color: #ffffff;
}
QLabel#AuthorLabel {
    color: #111318;
    font-size: 9px;
    letter-spacing: 1px;
    padding-bottom: 2px;
    text-transform: uppercase;
    font-weight: bold;
}

QFrame#BentoCard {
    background-color: rgba(255, 255, 255, 0.90);
    border: 1.5px solid rgba(17, 19, 24, 0.28);
    border-radius: 12px;
}
QFrame#BentoCard:hover {
    border: 1.5px solid #111318;
    background-color: #ffffff;
}

QFrame#BentoCell {
    background-color: rgba(238, 242, 248, 0.95);
    border: 1.2px solid rgba(17, 19, 24, 0.22);
    border-radius: 9px;
}
QFrame#BentoCell:hover {
    background-color: #ffffff;
    border: 1.2px solid #111318;
}

QLabel#BentoSectionTitle {
    color: #111318;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}

QLabel#BentoCellTitle {
    color: #111318;
    font-size: 11px;
    font-weight: bold;
}

QLabel#BentoCellDesc {
    color: #111318;
    font-size: 9px;
}

QLabel#BentoStatusActive {
    color: #111318;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 0.6px;
}

QLabel#BentoStatusIdle {
    color: #555e6d;
    font-size: 9px;
    letter-spacing: 0.5px;
}

QPushButton#BentoActionBtn {
    background-color: #111318;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 9px;
    letter-spacing: 0.5px;
}
QPushButton#BentoActionBtn:hover {
    background-color: #2b313d;
}
QWidget#TitleBtnsWidget {
    background-color: rgba(255, 255, 255, 0.75);
    border: 1px solid rgba(17, 19, 24, 0.15);
    border-radius: 9px;
    padding: 1px 4px;
}
QPushButton#TitleBtn {
    background-color: transparent;
    border: none;
    padding: 3px;
    border-radius: 5px;
}
QPushButton#TitleBtn:hover {
    background-color: rgba(17, 19, 24, 0.10);
}
QPushButton#ExitBtn {
    background-color: transparent;
    border: none;
    padding: 3px;
    border-radius: 5px;
}
QPushButton#ExitBtn:hover {
    background-color: rgba(229, 57, 53, 0.18);
}
"""


def get_main_style(theme: str = "dark") -> str:
    if theme == "light":
        return LIGHT_STYLE
    return DARK_STYLE


MAIN_STYLE = DARK_STYLE