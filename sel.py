import sys
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QBrush, QPen

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas # Corrected import
import sounddevice as sd
from scipy.fft import fft

# --- 1. 和弦合成器 ---
class ChordSynthesizer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.notes_freq = {
            'C3': 130.81, 'C#3': 138.59, 'D3': 146.83, 'D#3': 155.56, 'E3': 164.81, 'F3': 174.61,
            'F#3': 184.99, 'G3': 195.99, 'G#3': 207.65, 'A3': 220.00, 'A#3': 233.08, 'B3': 246.94,
            'C4': 261.63, 'C#4': 277.18, 'D4': 293.66, 'D#4': 311.13, 'E4': 329.63, 'F4': 349.23,
            'F#4': 369.99, 'G4': 392.00, 'G#4': 415.30, 'A4': 440.00, 'A#4': 466.16, 'B4': 493.88,
            'C5': 523.25, 'C#5': 554.37, 'D5': 587.33, 'D#5': 622.25, 'E5': 659.26, 'F5': 698.46,
            'F#5': 739.99, 'G5': 783.99, 'G#5': 830.61, 'A5': 880.00, 'A#5': 932.33, 'B5': 987.77,
        }
        # 只保留 C Major 和弦
        self.chords = {
            'C Major': ['C4', 'E4', 'G4'],
        }

    def get_chord_notes(self, chord_name):
        return [self.notes_freq[note] for note in self.chords.get(chord_name, []) if note in self.notes_freq]

    def generate_chord_audio(self, chord_name, duration=1.0, amplitude=0.5):
        frequencies = self.get_chord_notes(chord_name)
        if not frequencies:
            return np.zeros(int(self.sample_rate * duration))

        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint=False)
        audio_data = np.zeros_like(t)
        for freq in frequencies:
            audio_data += amplitude * np.sin(2 * np.pi * freq * t)

        # Normalize to prevent clipping
        audio_data = audio_data / np.max(np.abs(audio_data)) * 0.9 if np.max(np.abs(audio_data)) > 0 else audio_data
        return audio_data.astype(np.float32)

# --- 2. 钢琴卷帘小部件 (横向) ---
class PianoRollWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        # 横向滚动条，如果琴键太多，可能需要
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout = QVBoxLayout(self) # 内部布局仍是垂直，因为view是其唯一子部件
        layout.setContentsMargins(0,0,0,0) # 移除边距
        layout.addWidget(self.view)
        
        # 调整琴键尺寸，适应横向布局
        self.key_width = 40  # 每个琴键的横向宽度
        self.key_height = 100 # 每个琴键的纵向高度 (真实琴键高度)

        # 简化琴键范围，只显示 C4, D4, E4, F4, G4, A4, B4, C5
        self.white_keys_freq = [
            'C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5'
        ]
        self.black_keys_freq = [
            'C#4', 'D#4', 'F#4', 'G#4', 'A#4'
        ]
        self.note_to_x_pos = {} # Map note name to x position

        self.draw_piano_keys()
        # 确保视图尺寸适应内容
        self.view.setSceneRect(self.scene.itemsBoundingRect())
        
        # 设置视图的最小/最大尺寸，确保其高度固定，宽度可扩展
        self.view.setMinimumHeight(self.key_height + 5) # 稍微多一点空间
        self.view.setMaximumHeight(self.key_height + 5)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


    def draw_piano_keys(self):
        self.scene.clear() # 清除旧的琴键
        
        # 定义黑键的相对尺寸和位置
        black_key_visual_width = self.key_width * 0.6
        black_key_visual_height = self.key_height * 0.6
        # 黑键的横向偏移量，使其位于白键的右侧并略微重叠到下一个白键
        black_key_x_offset_from_white = self.key_width * 0.65 # 可调整此值以获得最佳视觉效果

        white_key_current_x = 0
        
        # 绘制白键
        for note in self.white_keys_freq:
            rect = QGraphicsRectItem(white_key_current_x, 0, self.key_width, self.key_height)
            rect.setBrush(QBrush(QColor(255, 255, 255))) # 白色琴键
            rect.setPen(QPen(QColor(0, 0, 0))) # 黑色边框
            self.scene.addItem(rect)
            self.note_to_x_pos[note] = white_key_current_x # 存储白键的起始X位置
            white_key_current_x += self.key_width

        # 绘制黑键 (在白键之上)
        for note_name in self.black_keys_freq:
            # 找到对应的白键作为基准
            base_white_key = ''
            if note_name.startswith('C#'): base_white_key = 'C' + note_name[2:]
            elif note_name.startswith('D#'): base_white_key = 'D' + note_name[2:]
            elif note_name.startswith('F#'): base_white_key = 'F' + note_name[2:]
            elif note_name.startswith('G#'): base_white_key = 'G' + note_name[2:]
            elif note_name.startswith('A#'): base_white_key = 'A' + note_name[2:]

            if base_white_key in self.note_to_x_pos:
                # 基于白键的X位置计算黑键的X位置
                white_key_x = self.note_to_x_pos[base_white_key]
                black_key_x = white_key_x + black_key_x_offset_from_white - (black_key_visual_width / 2) # 尝试使其居中于白键右侧

                rect = QGraphicsRectItem(black_key_x, 0, black_key_visual_width, black_key_visual_height)
                rect.setBrush(QBrush(QColor(0, 0, 0))) # 黑色琴键
                rect.setPen(QPen(QColor(0, 0, 0)))
                self.scene.addItem(rect)
                self.note_to_x_pos[note_name] = black_key_x # 存储黑键的起始X位置 (用于高亮)

        self.scene.setSceneRect(self.scene.itemsBoundingRect())


    def highlight_notes(self, notes):
        self.clear_highlights()
        for note_name in notes:
            if note_name in self.note_to_x_pos:
                x_pos = self.note_to_x_pos[note_name]
                color = QColor(255, 165, 0, 150) # 橙色，半透明

                # 根据是否是黑键，设置高亮矩形的尺寸
                if '#' in note_name: # 黑键高亮
                    width = self.key_width * 0.6
                    height = self.key_height * 0.6
                else: # 白键高亮
                    width = self.key_width
                    height = self.key_height
                
                rect = QGraphicsRectItem(x_pos, 0, width, height)
                rect.setBrush(QBrush(color))
                rect.setPen(QPen(Qt.PenStyle.NoPen)) # 无边框
                self.scene.addItem(rect)

    def clear_highlights(self):
        # 移除所有高亮矩形 (通过检查颜色透明度)
        items_to_remove = []
        for item in self.scene.items():
            if isinstance(item, QGraphicsRectItem) and item.brush().color().alpha() == 150:
                items_to_remove.append(item)
        for item in items_to_remove:
            self.scene.removeItem(item)

# --- 3. 频谱图小部件 ---
class SpectrogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Magnitude")
        self.ax.set_title("Audio Spectrum")
        self.ax.set_xlim(0, 1000) # 限制频率范围以便更好地可视化
        self.ax.set_ylim(0, 1) # 幅度范围

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def plot_spectrum(self, audio_data, sample_rate):
        if audio_data is None or len(audio_data) == 0:
            self.ax.clear()
            self.ax.set_xlabel("Frequency (Hz)")
            self.ax.set_ylabel("Magnitude")
            self.ax.set_title("Audio Spectrum (No data)")
            self.ax.set_xlim(0, 1000)
            self.ax.set_ylim(0, 1)
            self.canvas.draw()
            return

        N = len(audio_data)
        yf = fft(audio_data)
        xf = np.linspace(0.0, 1.0 / (2.0 * (1/sample_rate)), N // 2)

        self.ax.clear()
        self.ax.plot(xf, 2.0/N * np.abs(yf[0:N//2]))
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Magnitude")
        self.ax.set_title("Audio Spectrum")
        self.ax.set_xlim(0, 1000) # 限制频率范围以便更好地可视化
        # 动态调整 Y 轴上限
        max_magnitude = np.max(2.0/N * np.abs(yf[0:N//2]))
        self.ax.set_ylim(0, max_magnitude * 1.1 + 0.1 if max_magnitude > 0 else 1)
        self.canvas.draw()

# --- 4. 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chord Player and Spectrum Analyzer")
        self.setGeometry(100, 100, 1000, 600) # 初始窗口尺寸

        self.synthesizer = ChordSynthesizer()
        self.current_audio_data = None

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # 左侧面板 (和弦选择器)
        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        chord_label = QLabel("Select Chord:")
        left_panel.addWidget(chord_label)

        self.chord_selector = QComboBox()
        # 只添加 C Major
        self.chord_selector.addItems(sorted(self.synthesizer.chords.keys()))
        self.chord_selector.currentIndexChanged.connect(self.on_chord_selected)
        left_panel.addWidget(self.chord_selector)

        play_button = QPushButton("Play Chord")
        play_button.clicked.connect(self.play_selected_chord)
        left_panel.addWidget(play_button)

        main_layout.addLayout(left_panel, 1) # 左侧面板占 1 份宽度

        # 右侧面板 (频谱图和钢琴卷帘)
        right_panel = QVBoxLayout()

        # 频谱图 (右上)
        self.spectrogram_widget = SpectrogramWidget()
        right_panel.addWidget(self.spectrogram_widget, 2) # 频谱图占 2 份高度

        # 钢琴卷帘 (右下)
        self.piano_roll_widget = PianoRollWidget()
        right_panel.addWidget(self.piano_roll_widget, 1) # 钢琴卷帘占 1 份高度 (但其高度固定)

        main_layout.addLayout(right_panel, 3) # 右侧面板占 3 份宽度

        # 初始时显示 C Major 的高亮和空频谱图
        self.on_chord_selected(0) # 触发一次选中，显示C Major
        self.spectrogram_widget.plot_spectrum(None, self.synthesizer.sample_rate)


    def on_chord_selected(self, index):
        selected_chord_name = self.chord_selector.currentText()
        notes_in_chord = self.synthesizer.chords.get(selected_chord_name, [])
        self.piano_roll_widget.highlight_notes(notes_in_chord)

    def play_selected_chord(self):
        selected_chord_name = self.chord_selector.currentText()
        self.current_audio_data = self.synthesizer.generate_chord_audio(selected_chord_name, duration=1.5) # 播放 1.5 秒

        # 播放音频
        if self.current_audio_data is not None and len(self.current_audio_data) > 0:
            try:
                sd.play(self.current_audio_data, self.synthesizer.sample_rate)
                # 播放时显示频谱
                self.spectrogram_widget.plot_spectrum(self.current_audio_data, self.synthesizer.sample_rate)
                sd.wait() # 等待音频播放完成
                # 播放完成后清除频谱图和钢琴高亮
                QTimer.singleShot(500, lambda: self.spectrogram_widget.plot_spectrum(None, self.synthesizer.sample_rate))
                self.piano_roll_widget.clear_highlights()
                # 重新高亮选中的和弦
                self.on_chord_selected(self.chord_selector.currentIndex())
            except Exception as e:
                print(f"Error playing sound: {e}")
                self.spectrogram_widget.plot_spectrum(None, self.synthesizer.sample_rate)
                self.piano_roll_widget.clear_highlights()
                self.on_chord_selected(self.chord_selector.currentIndex())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())