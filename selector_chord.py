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
#from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
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
        self.chords = {
            'C Major': ['C4', 'E4', 'G4'],
            'G Major': ['G4', 'B4', 'D5'],
            'A Minor': ['A4', 'C5', 'E5'],
            'F Major': ['F4', 'A4', 'C5'],
            'D Major': ['D4', 'F#4', 'A4'],
            'E Minor': ['E4', 'G4', 'B4'],
            'Bb Major': ['A#4', 'D5', 'F5'],
            'C7': ['C4', 'E4', 'G4', 'A#4']
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

# --- 2. 钢琴卷帘小部件 ---
class PianoRollWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)

        self.key_height = 20
        self.key_width = 80
        self.white_keys_freq = [
            'C3', 'D3', 'E3', 'F3', 'G3', 'A3', 'B3',
            'C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4',
            'C5', 'D5', 'E5', 'F5', 'G5', 'A5', 'B5',
        ]
        self.black_keys_freq = [
            'C#3', 'D#3', 'F#3', 'G#3', 'A#3',
            'C#4', 'D#4', 'F#4', 'G#4', 'A#4',
            'C#5', 'D#5', 'F#5', 'G#5', 'A#5',
        ]
        self.note_to_y_pos = {} # Map note name to y position

        self.draw_piano_keys()
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def draw_piano_keys(self):
        y_pos = 0
        white_key_index = 0
        for i, note in enumerate(self.white_keys_freq):
            rect = QGraphicsRectItem(0, y_pos, self.key_width, self.key_height)
            rect.setBrush(QBrush(QColor(255, 255, 255))) # White keys
            rect.setPen(QPen(QColor(0, 0, 0))) # Black border
            self.scene.addItem(rect)
            self.note_to_y_pos[note] = y_pos
            y_pos += self.key_height
            white_key_index += 1

        # Draw black keys over white keys
        y_pos = 0
        white_key_count_iter = 0
        for i, note in enumerate(self.white_keys_freq):
            if note in ['C3', 'D3', 'F3', 'G3', 'A3',
                        'C4', 'D4', 'F4', 'G4', 'A4',
                        'C5', 'D5', 'F5', 'G5', 'A5']: # Notes that have a sharp
                if note == 'C3':
                    black_key_y = self.note_to_y_pos['C3'] + self.key_height - (self.key_height * 0.7)
                elif note == 'D3':
                    black_key_y = self.note_to_y_pos['D3'] + self.key_height - (self.key_height * 0.7)
                elif note == 'F3':
                    black_key_y = self.note_to_y_pos['F3'] + self.key_height - (self.key_height * 0.7)
                elif note == 'G3':
                    black_key_y = self.note_to_y_pos['G3'] + self.key_height - (self.key_height * 0.7)
                elif note == 'A3':
                    black_key_y = self.note_to_y_pos['A3'] + self.key_height - (self.key_height * 0.7)
                elif note == 'C4':
                    black_key_y = self.note_to_y_pos['C4'] + self.key_height - (self.key_height * 0.7)
                elif note == 'D4':
                    black_key_y = self.note_to_y_pos['D4'] + self.key_height - (self.key_height * 0.7)
                elif note == 'F4':
                    black_key_y = self.note_to_y_pos['F4'] + self.key_height - (self.key_height * 0.7)
                elif note == 'G4':
                    black_key_y = self.note_to_y_pos['G4'] + self.key_height - (self.key_height * 0.7)
                elif note == 'A4':
                    black_key_y = self.note_to_y_pos['A4'] + self.key_height - (self.key_height * 0.7)
                elif note == 'C5':
                    black_key_y = self.note_to_y_pos['C5'] + self.key_height - (self.key_height * 0.7)
                elif note == 'D5':
                    black_key_y = self.note_to_y_pos['D5'] + self.key_height - (self.key_height * 0.7)
                elif note == 'F5':
                    black_key_y = self.note_to_y_pos['F5'] + self.key_height - (self.key_height * 0.7)
                elif note == 'G5':
                    black_key_y = self.note_to_y_pos['G5'] + self.key_height - (self.key_height * 0.7)
                elif note == 'A5':
                    black_key_y = self.note_to_y_pos['A5'] + self.key_height - (self.key_height * 0.7)
                else:
                    continue # No black key for E and B

                # Find the corresponding black key note name
                black_note_name = ''
                if note == 'C3': black_note_name = 'C#3'
                elif note == 'D3': black_note_name = 'D#3'
                elif note == 'F3': black_note_name = 'F#3'
                elif note == 'G3': black_note_name = 'G#3'
                elif note == 'A3': black_note_name = 'A#3'
                elif note == 'C4': black_note_name = 'C#4'
                elif note == 'D4': black_note_name = 'D#4'
                elif note == 'F4': black_note_name = 'F#4'
                elif note == 'G4': black_note_name = 'G#4'
                elif note == 'A4': black_note_name = 'A#4'
                elif note == 'C5': black_note_name = 'C#5'
                elif note == 'D5': black_note_name = 'D#5'
                elif note == 'F5': black_note_name = 'F#5'
                elif note == 'G5': black_note_name = 'G#5'
                elif note == 'A5': black_note_name = 'A#5'

                if black_note_name:
                    rect = QGraphicsRectItem(0, black_key_y, self.key_width * 0.6, self.key_height * 0.6) # Shorter and narrower
                    rect.setBrush(QBrush(QColor(0, 0, 0))) # Black keys
                    rect.setPen(QPen(QColor(0, 0, 0)))
                    self.scene.addItem(rect)
                    self.note_to_y_pos[black_note_name] = black_key_y


    def highlight_notes(self, notes):
        self.clear_highlights()
        for note_name in notes:
            if note_name in self.note_to_y_pos:
                y_pos = self.note_to_y_pos[note_name]
                color = QColor(255, 165, 0, 150) # Orange, semi-transparent
                if '#' in note_name: # Black key highlight
                    rect = QGraphicsRectItem(0, y_pos, self.key_width * 0.6, self.key_height * 0.6)
                else: # White key highlight
                    rect = QGraphicsRectItem(0, y_pos, self.key_width, self.key_height)
                rect.setBrush(QBrush(color))
                rect.setPen(QPen(Qt.PenStyle.NoPen))
                self.scene.addItem(rect)

    def clear_highlights(self):
        # Remove all but the original piano key rects
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
        self.ax.set_xlim(0, 1000) # Limit frequency range for better visualization
        self.ax.set_ylim(0, 1) # Magnitude range

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
        self.ax.set_xlim(0, 1000) # Limit frequency range for better visualization
        self.ax.set_ylim(0, np.max(2.0/N * np.abs(yf[0:N//2])) * 1.1 + 0.1) if np.max(2.0/N * np.abs(yf[0:N//2])) > 0 else self.ax.set_ylim(0, 1)
        self.canvas.draw()

# --- 4. 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chord Player and Spectrum Analyzer")
        self.setGeometry(100, 100, 1000, 700) # Initial window size

        self.synthesizer = ChordSynthesizer()
        self.current_audio_data = None

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left Panel (Chord Selector)
        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        chord_label = QLabel("Select Chord:")
        left_panel.addWidget(chord_label)

        self.chord_selector = QComboBox()
        self.chord_selector.addItems(sorted(self.synthesizer.chords.keys()))
        self.chord_selector.currentIndexChanged.connect(self.on_chord_selected)
        left_panel.addWidget(self.chord_selector)

        play_button = QPushButton("Play Chord")
        play_button.clicked.connect(self.play_selected_chord)
        left_panel.addWidget(play_button)

        main_layout.addLayout(left_panel, 1) # Stretch factor for left panel

        # Right Panel (Spectrogram and Piano Roll)
        right_panel = QVBoxLayout()

        # Spectrogram (Top-Right)
        self.spectrogram_widget = SpectrogramWidget()
        right_panel.addWidget(self.spectrogram_widget, 2) # Spectrogram takes 2/3 of height

        # Piano Roll (Bottom-Right)
        self.piano_roll_widget = PianoRollWidget()
        right_panel.addWidget(self.piano_roll_widget, 1) # Piano roll takes 1/3 of height
        self.piano_roll_widget.view.setMinimumHeight(self.piano_roll_widget.key_height * len(self.piano_roll_widget.white_keys_freq))


        main_layout.addLayout(right_panel, 3) # Stretch factor for right panel

        # Initial plot for spectrogram
        self.spectrogram_widget.plot_spectrum(None, self.synthesizer.sample_rate)

    def on_chord_selected(self, index):
        selected_chord_name = self.chord_selector.currentText()
        notes_in_chord = self.synthesizer.chords.get(selected_chord_name, [])
        self.piano_roll_widget.highlight_notes(notes_in_chord)

    def play_selected_chord(self):
        selected_chord_name = self.chord_selector.currentText()
        self.current_audio_data = self.synthesizer.generate_chord_audio(selected_chord_name, duration=1.5) # Play for 1.5 seconds

        # Play audio
        if self.current_audio_data is not None and len(self.current_audio_data) > 0:
            try:
                sd.play(self.current_audio_data, self.synthesizer.sample_rate)
                # Update spectrogram after a short delay to ensure audio is playing
                QTimer.singleShot(100, lambda: self.spectrogram_widget.plot_spectrum(self.current_audio_data, self.synthesizer.sample_rate))
                sd.wait() # Wait for the audio to finish playing
                # Clear spectrogram after playing
                QTimer.singleShot(500, lambda: self.spectrogram_widget.plot_spectrum(None, self.synthesizer.sample_rate))
                self.piano_roll_widget.clear_highlights()
            except Exception as e:
                print(f"Error playing sound: {e}")
                self.spectrogram_widget.plot_spectrum(None, self.synthesizer.sample_rate)
                self.piano_roll_widget.clear_highlights()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())