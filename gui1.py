import tkinter as tk
from tkinter import filedialog, messagebox
import mido
import time
from pynput import keyboard
import threading

# --- MIDI 和步进逻辑 (与上面保持一致) ---
# ... (所有 MIDI 配置、send_note_on/off、on_press/release 函数，以及全局变量) ...

# 自定义旋律序列（初始为空，由GUI填充）
custom_melody_sequence = []
# ----------------------------------------

class MidiSequencerApp:
    def __init__(self, master):
        self.master = master
        master.title("MIDI 序列器")

        # UI Elements
        self.melody_listbox = tk.Listbox(master, height=10, width=50)
        self.melody_listbox.pack()

        # Frame for adding notes/chords
        add_frame = tk.Frame(master)
        add_frame.pack()

        tk.Label(add_frame, text="音符/和弦 (MIDI音高,逗号分隔):").pack(side=tk.LEFT)
        self.note_entry = tk.Entry(add_frame, width=20)
        self.note_entry.pack(side=tk.LEFT)
        tk.Button(add_frame, text="添加", command=self.add_note_or_chord).pack(side=tk.LEFT)

        tk.Button(master, text="导入 MIDI 文件", command=self.import_midi).pack()
        tk.Button(master, text="保存序列", command=self.save_sequence).pack()
        tk.Button(master, text="加载序列", command=self.load_sequence).pack()

        # Step controls
        tk.Button(master, text="启动键盘步进", command=self.start_keyboard_listener).pack()
        tk.Button(master, text="停止所有音符", command=self.stop_all_notes).pack() # 用于紧急停止

        self.update_melody_listbox() # Initial display

    def add_note_or_chord(self):
        input_str = self.note_entry.get().strip()
        if not input_str:
            return

        try:
            if ',' in input_str:
                # 和弦
                notes = [int(n.strip()) for n in input_str.split(',')]
                custom_melody_sequence.append(notes)
            elif input_str.lower() == 'rest' or input_str == '[]':
                # 休止符
                custom_melody_sequence.append([])
            else:
                # 单个音符
                note = int(input_str)
                custom_melody_sequence.append(note)
            
            self.note_entry.delete(0, tk.END)
            self.update_melody_listbox()
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的MIDI音高（整数）或逗号分隔的和弦。")

    def update_melody_listbox(self):
        self.melody_listbox.delete(0, tk.END)
        for i, item in enumerate(custom_melody_sequence):
            if isinstance(item, int):
                self.melody_listbox.insert(tk.END, f"{i}: 音符 {item}")
            elif isinstance(item, list) and item:
                self.melody_listbox.insert(tk.END, f"{i}: 和弦 {item}")
            elif isinstance(item, list) and not item:
                self.melody_listbox.insert(tk.END, f"{i}: 休止符")

    def import_midi(self):
        filepath = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid")])
        if filepath:
            # 使用之前定义的 midi_file_to_sequence 函数
            new_sequence = midi_file_to_sequence(filepath) # track_index 和 quantization_level 可以作为参数
            if new_sequence:
                global custom_melody_sequence
                custom_melody_sequence = new_sequence
                self.update_melody_listbox()
                messagebox.showinfo("导入成功", f"从 {filepath} 导入了 {len(new_sequence)} 个元素。")

    def save_sequence(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filepath:
            import json
            try:
                with open(filepath, 'w') as f:
                    json.dump(custom_melody_sequence, f)
                messagebox.showinfo("保存成功", "序列已保存。")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存序列: {e}")

    def load_sequence(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filepath:
            import json
            try:
                with open(filepath, 'r') as f:
                    loaded_sequence = json.load(f)
                    # 简单验证一下加载的数据结构，防止错误格式
                    if all(isinstance(item, int) or (isinstance(item, list) and all(isinstance(n, int) for n in item)) for item in loaded_sequence):
                        global custom_melody_sequence
                        custom_melody_sequence = loaded_sequence
                        self.update_melody_listbox()
                        messagebox.showinfo("加载成功", "序列已加载。")
                    else:
                        messagebox.showerror("加载失败", "JSON 文件格式不正确。")
            except Exception as e:
                messagebox.showerror("加载失败", f"无法加载序列: {e}")

    def start_keyboard_listener(self):
        # 启动 MIDI 端口并开始监听键盘
        # 这部分逻辑需要从你的 start_midi_stepper 调整
        # listener.join() 会阻塞主线程，所以需要在一个新线程中启动
        # 或者使用非阻塞的 start() 方法
        global midi_port, current_sequence_index, last_notes_played, active_notes, current_pressed_keys

        if midi_port and not midi_port.closed:
            messagebox.showinfo("提示", "MIDI 监听器已在运行。")
            return

        try:
            print("尝试打开 MIDI 端口...")
            port_to_open_name = None
            for name in mido.get_output_names():
                if "loopmidi" in name.lower() or "python" in name.lower() or "rtmidi" in name.lower():
                    port_to_open_name = name
                    break
            
            if port_to_open_name:
                midi_port = mido.open_output(port_to_open_name)
                print(f"成功打开 MIDI 端口: '{port_to_open_name}'")
            else:
                messagebox.showerror("错误", "找不到 LoopMIDI 或其他合适的虚拟 MIDI 端口。\n请确保 LoopMIDI 正在运行并已创建虚拟端口。")
                return

            # 初始化步进状态
            current_sequence_index = 0
            last_notes_played = []
            active_notes = {}
            current_pressed_keys = set()

            # 启动键盘监听器在一个新线程中
            self.listener_thread = threading.Thread(target=self._run_listener)
            self.listener_thread.daemon = True # 设置为守护线程，主程序退出时它也会退出
            self.listener_thread.start()
            messagebox.showinfo("信息", "键盘监听器已启动。按 'Esc' 退出。")

        except Exception as e:
            messagebox.showerror("MIDI 端口错误", f"无法打开 MIDI 端口: {e}")

    def _run_listener(self):
        """在单独线程中运行键盘监听器"""
        with keyboard.Listener(on_press=self.on_listener_press, on_release=self.on_listener_release) as listener:
            listener.join()
        # 监听器停止后（例如按Esc），关闭MIDI端口
        self.stop_all_notes()
        print("键盘监听器线程已停止。")

    def on_listener_press(self, key):
        """pynput 回调，在监听器线程中运行"""
        # 这个函数将包含你之前 on_press 中的核心逻辑
        # 但需要确保它能访问 GUI 的更新方法（如果需要）
        global current_sequence_index, last_notes_played, active_notes, current_pressed_keys

        if key == keyboard.Key.esc:
            return False # 停止监听器

        # 忽略重复按键事件 (当按住键时，pynput 会持续触发 on_press)
        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key
        if key_identifier in current_pressed_keys:
            return
        current_pressed_keys.add(key_identifier)

        if not custom_melody_sequence:
            print("旋律序列为空，无法播放。")
            return

        # 关闭上一个播放的音符或和弦
        for note in last_notes_played:
            send_note_off(note)
        last_notes_played = []

        # 获取当前要播放的音符或和弦
        element_to_play = custom_melody_sequence[current_sequence_index]
        actual_notes_played = send_note_on(element_to_play)
        
        if actual_notes_played:
            print(f"播放: {element_to_play} (序列索引: {current_sequence_index})")
            last_notes_played = actual_notes_played
        else:
            print(f"播放休止符 (序列索引: {current_sequence_index})")

        # 更新索引
        current_sequence_index = (current_sequence_index + 1) % len(custom_melody_sequence)
        # 可以在这里更新GUI，例如高亮当前播放的序列元素
        # self.master.after(0, lambda: self.melody_listbox.select_clear(0, tk.END))
        # self.master.after(0, lambda: self.melody_listbox.select_set(current_sequence_index - 1)) # 高亮上一个
        # self.master.after(0, lambda: self.melody_listbox.see(current_sequence_index - 1))

    def on_listener_release(self, key):
        """pynput 回调，在监听器线程中运行"""
        global current_pressed_keys
        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key
        current_pressed_keys.discard(key_identifier)

    def stop_all_notes(self):
        global midi_port, active_notes
        if midi_port and not midi_port.closed:
            for note in list(active_notes.keys()):
                send_note_off(note)
            midi_port.close()
            print("MIDI 端口已关闭。")
            messagebox.showinfo("信息", "所有音符已停止，MIDI 端口已关闭。")
        else:
            print("MIDI 端口未打开。")
            messagebox.showinfo("信息", "MIDI 端口未打开。")

# 确保在主程序启动前初始化全局变量
global midi_port, current_sequence_index, last_notes_played, active_notes, current_pressed_keys
midi_port = None
current_sequence_index = 0
last_notes_played = []
active_notes = {}
current_pressed_keys = set()


# 主 GUI 循环
if __name__ == "__main__":
    root = tk.Tk()
    app = MidiSequencerApp(root)
    root.mainloop()