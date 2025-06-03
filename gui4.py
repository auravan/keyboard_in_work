import tkinter as tk
from tkinter import filedialog, messagebox
import mido
import time
from pynput import keyboard
import threading
import json

# --- MIDI Configuration ---
midi_channel = 0 # Default MIDI channel (0-15)
velocity = 90    # Default velocity
midi_program = 0 # Default MIDI program (0 for Acoustic Grand Piano)

# --- Global Variables ---
midi_port = None
current_sequence_index = 0
last_notes_played = []
active_notes = {}
current_pressed_keys = set()

custom_melody_sequence = []

# --- Note Name Conversion Helper ---
def midinote_to_name(midinote):
    """
    Converts MIDI note number to note name (e.g., 60 -> C4).
    C4 (Middle C) corresponds to MIDI note 60.
    """
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    
    if not (0 <= midinote <= 127):
        return "N/A"

    note_index = midinote % 12
    note_name = note_names[note_index]
    octave = (midinote // 12) - 1 # C4 = 60 corresponds to octave 4

    return f"{note_name}{octave}"

# --- MIDI Message Sending Helper Functions ---
def send_note_on(note_or_chord):
    """Sends Note On message(s)."""
    global active_notes
    if midi_port and not midi_port.closed:
        notes_to_play = []
        if isinstance(note_or_chord, int):
            notes_to_play.append(note_or_chord)
        elif isinstance(note_or_chord, list) or isinstance(note_or_chord, tuple):
            notes_to_play.extend(note_or_chord)
        else:
            return [] # Handle empty list as rest

        for note in notes_to_play:
            if note is not None:
                msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
                midi_port.send(msg_on)
                active_notes[note] = True
        return notes_to_play

def send_note_off(note):
    """Sends Note Off message."""
    global active_notes
    if midi_port and not midi_port.closed:
        if note is not None and note in active_notes:
            msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
            midi_port.send(msg_off)
            del active_notes[note]

def send_program_change(program_number):
    """Sends a Program Change message to change the instrument."""
    global midi_program
    if midi_port and not midi_port.closed:
        if 0 <= program_number <= 127: # MIDI program numbers are 0-127
            msg_pc = mido.Message('program_change', channel=midi_channel, program=program_number)
            midi_port.send(msg_pc)
            midi_program = program_number # Update the global program number
            print(f"Sent Program Change to instrument: {program_number}")
        else:
            print(f"Warning: Invalid MIDI program number {program_number}. Must be between 0 and 127.")

# --- MIDI File Conversion Function ---
def midi_file_to_sequence(midi_filepath, track_index=0, quantization_level=0.25):
    """
    Extracts note events from a MIDI file and converts them into the custom_melody_sequence format.
    Attempts to group simultaneously occurring notes into chords.
    """
    try:
        mid = mido.MidiFile(midi_filepath)
        
        if not mid.tracks:
            print("MIDI file contains no tracks.")
            return []

        if track_index >= len(mid.tracks):
            print(f"Warning: Track index {track_index} does not exist. Using the first track (index 0).")
            track_index = 0

        track = mid.tracks[track_index]
        ticks_per_beat = mid.ticks_per_beat
        current_tempo = mido.bpm2tempo(120) 

        for msg in mid.tracks[0]:
            if msg.type == 'set_tempo':
                current_tempo = msg.tempo
                break

        active_note_start_beats = {}
        note_events_in_beats = []
        
        current_time_ticks = 0

        for msg in track:
            current_time_ticks += msg.time
            current_time_beats = current_time_ticks / ticks_per_beat

            if msg.type == 'note_on' and msg.velocity > 0:
                active_note_start_beats[msg.note] = current_time_beats
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_note_start_beats:
                    start_beats = active_note_start_beats.pop(msg.note)
                    note_events_in_beats.append((start_beats, current_time_beats, msg.note))
        
        note_events_in_beats.sort(key=lambda x: x[0])

        sequence = []
        last_quantized_time_processed = -float('inf')
        notes_for_current_quantized_time = set()

        for start_beats, _, note in note_events_in_beats:
            quantized_start_beats = round(start_beats / quantization_level) * quantization_level

            if quantized_start_beats > last_quantized_time_processed:
                if notes_for_current_quantized_time:
                    if len(notes_for_current_quantized_time) == 1:
                        sequence.append(list(notes_for_current_quantized_time)[0])
                    else:
                        sequence.append(sorted(list(notes_for_current_quantized_time)))
                notes_for_current_quantized_time.clear()
                
            notes_for_current_quantized_time.add(note)
            last_quantized_time_processed = quantized_start_beats
        
        if notes_for_current_quantized_time:
            if len(notes_for_current_quantized_time) == 1:
                sequence.append(list(notes_for_current_quantized_time)[0])
            else:
                sequence.append(sorted(list(notes_for_current_quantized_time)))

        print(f"Successfully imported {len(sequence)} elements from '{midi_filepath}'.")
        return sequence

    except FileNotFoundError:
        messagebox.showerror("File Error", f"MIDI file '{midi_filepath}' not found.")
        return []
    except Exception as e:
        messagebox.showerror("MIDI Parsing Error", f"An error occurred while parsing the MIDI file: {e}")
        print(f"MIDI Parsing Error Details: {e}")
        return []

# --- GUI Application Class ---
class MidiSequencerApp:
    def __init__(self, master):
        self.master = master
        master.title("MIDI Sequencer")

        # UI Elements
        self.melody_listbox = tk.Listbox(master, height=15, width=60)
        self.melody_listbox.pack(pady=10)

        # Frame for adding notes/chords
        add_frame = tk.Frame(master)
        add_frame.pack(pady=5)

        tk.Label(add_frame, text="Note/Chord (e.g., 60 or 60,64,67 or rest):").pack(side=tk.LEFT)
        self.note_entry = tk.Entry(add_frame, width=25)
        self.note_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(add_frame, text="Add", command=self.add_note_or_chord).pack(side=tk.LEFT)
        tk.Button(add_frame, text="Delete Selected", command=self.delete_selected).pack(side=tk.LEFT, padx=5)

        # --- Instrument Control ---
        instrument_frame = tk.Frame(master)
        instrument_frame.pack(pady=5)
        tk.Label(instrument_frame, text="MIDI Instrument Program (0-127):").pack(side=tk.LEFT)
        self.instrument_entry = tk.Entry(instrument_frame, width=5)
        self.instrument_entry.insert(0, str(midi_program)) # Set default
        self.instrument_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(instrument_frame, text="Set Instrument", command=self.set_instrument_from_gui).pack(side=tk.LEFT)
        # --- End Instrument Control ---

        # File Operations
        file_frame = tk.Frame(master)
        file_frame.pack(pady=5)
        tk.Button(file_frame, text="Import MIDI File", command=self.import_midi).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="Save Sequence (JSON)", command=self.save_sequence).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="Load Sequence (JSON)", command=self.load_sequence).pack(side=tk.LEFT, padx=5)

        # Controls
        control_frame = tk.Frame(master)
        control_frame.pack(pady=10)
        self.start_button = tk.Button(control_frame, text="Start Keyboard Stepping", command=self.start_keyboard_listener)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(control_frame, text="Stop All Notes & Close MIDI", command=self.stop_all_notes)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Initial display
        self.update_melody_listbox()

    def add_note_or_chord(self):
        input_str = self.note_entry.get().strip()
        if not input_str:
            return

        try:
            if ',' in input_str:
                notes = [int(n.strip()) for n in input_str.split(',')]
                custom_melody_sequence.append(sorted(notes))
            elif input_str.lower() == 'rest' or input_str == '[]':
                custom_melody_sequence.append([])
            else:
                note = int(input_str)
                custom_melody_sequence.append(note)
            
            self.note_entry.delete(0, tk.END)
            self.update_melody_listbox()
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid MIDI pitch (integer), comma-separated chord (e.g., 60,64,67), or 'rest' / '[]' for a rest.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add: {e}")

    def delete_selected(self):
        selected_indices = self.melody_listbox.curselection()
        if not selected_indices:
            return
        
        for index in reversed(selected_indices):
            if 0 <= index < len(custom_melody_sequence):
                del custom_melody_sequence[index]
        
        self.update_melody_listbox()

    def update_melody_listbox(self):
        self.melody_listbox.delete(0, tk.END)
        if not custom_melody_sequence:
            self.melody_listbox.insert(tk.END, "Sequence is empty. Add notes/chords or import MIDI.")
            return
            
        for i, item in enumerate(custom_melody_sequence):
            display_text = ""
            if isinstance(item, int):
                display_text = f"Note: {item} ({midinote_to_name(item)})"
            elif isinstance(item, list) and item:
                chord_names = [midinote_to_name(n) for n in item]
                display_text = f"Chord: {item} ({', '.join(chord_names)})"
            elif isinstance(item, list) and not item:
                display_text = "Rest"
            self.melody_listbox.insert(tk.END, f"{i:03d} | {display_text}")

    # --- New Method to Set Instrument from GUI ---
    def set_instrument_from_gui(self):
        try:
            program_num = int(self.instrument_entry.get())
            if 0 <= program_num <= 127:
                global midi_program
                midi_program = program_num
                send_program_change(midi_program) # Send program change if MIDI port is open
                messagebox.showinfo("Instrument Set", f"Instrument set to program: {midi_program}")
            else:
                messagebox.showerror("Input Error", "MIDI program number must be between 0 and 127.")
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid integer for the instrument program.")

    def import_midi(self):
        filepath = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid")])
        if filepath:
            try:
                new_sequence = midi_file_to_sequence(filepath)
                if new_sequence is not None:
                    global custom_melody_sequence
                    custom_melody_sequence = new_sequence
                    self.update_melody_listbox()
                    messagebox.showinfo("Import Successful", f"Imported {len(new_sequence)} elements from {filepath}.")
            except Exception as e:
                messagebox.showerror("Import Failed", f"Could not import MIDI file: {e}")

    def save_sequence(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(custom_melody_sequence, f, indent=4)
                messagebox.showinfo("Save Successful", "Sequence saved.")
            except Exception as e:
                messagebox.showerror("Save Failed", f"Could not save sequence: {e}")

    def load_sequence(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    loaded_sequence = json.load(f)
                    if all(isinstance(item, int) or (isinstance(item, list) and all(isinstance(n, int) for n in item)) for item in loaded_sequence):
                        global custom_melody_sequence
                        custom_melody_sequence = loaded_sequence
                        self.update_melody_listbox()
                        messagebox.showinfo("Load Successful", "Sequence loaded.")
                    else:
                        messagebox.showerror("Load Failed", "JSON file has incorrect format or unexpected data types.")
            except json.JSONDecodeError:
                messagebox.showerror("Load Failed", "Not a valid JSON file.")
            except Exception as e:
                messagebox.showerror("Load Failed", f"Could not load sequence: {e}")

    def start_keyboard_listener(self):
        global midi_port, current_sequence_index, last_notes_played, active_notes, current_pressed_keys

        if midi_port and not midi_port.closed:
            messagebox.showinfo("Info", "MIDI listener is already running.")
            return

        if not custom_melody_sequence:
            messagebox.showwarning("Warning", "Melody sequence is empty, cannot start listener.")
            return

        try:
            print("Attempting to open MIDI port...")
            port_to_open_name = None
            for name in mido.get_output_names():
                if "loopmidi" in name.lower() or "python" in name.lower() or "rtmidi" in name.lower():
                    port_to_open_name = name
                    break
            
            if port_to_open_name:
                midi_port = mido.open_output(port_to_open_name)
                print(f"Successfully opened MIDI port: '{port_to_open_name}'")
                # --- Send initial program change when port opens ---
                send_program_change(midi_program) 
                # --- End send initial program change ---
            else:
                messagebox.showerror("Error", "Could not find LoopMIDI or another suitable virtual MIDI port.\nPlease ensure LoopMIDI is running and a virtual port is created.")
                return

            current_sequence_index = 0
            last_notes_played = []
            active_notes = {}
            current_pressed_keys = set()

            self.listener_thread = threading.Thread(target=self._run_listener, daemon=True)
            self.listener_thread.start()
            messagebox.showinfo("Info", "Keyboard listener started.\nPress any keyboard key in the program window to step through.\nPress 'Esc' to stop the listener.")

        except Exception as e:
            messagebox.showerror("MIDI Port Error", f"Could not open MIDI port: {e}")
            print(f"MIDI Port Error Details: {e}")

    def _run_listener(self):
        """Runs the keyboard listener in a separate thread."""
        print("Keyboard listener thread started...")
        with keyboard.Listener(on_press=self.on_listener_press, on_release=self.on_listener_release) as listener:
            listener.join()
        print("Keyboard listener thread stopped. Attempting to close MIDI port...")
        self.master.after(100, self.stop_all_notes)

    def on_listener_press(self, key):
        """pynput callback, runs in listener thread."""
        global current_sequence_index, last_notes_played, active_notes, current_pressed_keys

        if key == keyboard.Key.esc:
            self.master.after(0, lambda: messagebox.showinfo("Exiting", "Esc key detected, exiting keyboard listener."))
            return False

        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key
        if key_identifier in current_pressed_keys:
            return
        current_pressed_keys.add(key_identifier)

        if not custom_melody_sequence:
            self.master.after(0, lambda: print("Melody sequence is empty, cannot play."))
            return

        for note in last_notes_played:
            send_note_off(note)
        last_notes_played = []

        element_to_play = custom_melody_sequence[current_sequence_index]
        actual_notes_played = send_note_on(element_to_play)
        
        if actual_notes_played:
            log_message = f"Playing: {element_to_play} (Sequence Index: {current_sequence_index})"
            last_notes_played = actual_notes_played
        else:
            log_message = f"Playing rest (Sequence Index: {current_sequence_index})"

        current_sequence_index = (current_sequence_index + 1) % len(custom_melody_sequence)
        
        self.master.after(0, lambda: print(log_message))
        self.master.after(0, lambda: self.update_listbox_highlight(current_sequence_index - 1))

    def on_listener_release(self, key):
        """pynput callback, runs in listener thread."""
        global current_pressed_keys
        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key
        current_pressed_keys.discard(key_identifier)

    def update_listbox_highlight(self, index_to_highlight):
        """Updates the Listbox highlight in the GUI main thread."""
        self.melody_listbox.select_clear(0, tk.END)
        if custom_melody_sequence:
            display_index = index_to_highlight 
            if display_index < 0:
                display_index = len(custom_melody_sequence) - 1

            if 0 <= display_index < len(custom_melody_sequence):
                self.melody_listbox.select_set(display_index)
                self.melody_listbox.see(display_index)

    def stop_all_notes(self):
        """Stops all active notes and closes the MIDI port."""
        global midi_port, active_notes
        if midi_port and not midi_port.closed:
            print("Stopping all active notes and closing MIDI port...")
            for note in list(active_notes.keys()):
                send_note_off(note)
            midi_port.close()
            midi_port = None
            messagebox.showinfo("Info", "All notes stopped, MIDI port closed.")
        else:
            print("MIDI port not open or already closed.")
            messagebox.showinfo("Info", "MIDI port not open or already closed.")

if __name__ == "__main__":
    root = tk.Tk()
    app = MidiSequencerApp(root)
    root.mainloop()