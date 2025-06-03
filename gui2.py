import tkinter as tk
from tkinter import filedialog, messagebox
import mido
import time
from pynput import keyboard
import threading
import json # 用于保存/加载序列

# --- MIDI 配置 ---
midi_channel = 0
velocity = 90 # 默认力度

# --- 全局变量（在任何函数或类定义之前初始化） ---
midi_port = None
current_sequence_index = 0
last_notes_played = [] # 存储上一个播放的音符/和弦，用于在下一个元素播放前关闭
active_notes = {} # 跟踪当前正在发声的音符，确保 Note Off
current_pressed_keys = set() # 用于跟踪当前按下的键，避免重复触发 on_press

# 自定义旋律序列（初始为空，由GUI填充）
custom_melody_sequence = []

# --- MIDI 消息发送辅助函数 ---
def send_note_on(note_or_chord):
    """发送 Note On 消息。如果是和弦，发送所有音符的 Note On。"""
    global active_notes
    if midi_port and not midi_port.closed:
        notes_to_play = []
        if isinstance(note_or_chord, int): # 如果是单个音符
            notes_to_play.append(note_or_chord)
        elif isinstance(note_or_chord, list) or isinstance(note_or_chord, tuple): # 如果是和弦
            notes_to_play.extend(note_or_chord)
        else: # 处理 [] (作为休止符)
            return [] # 不播放任何音符，返回空列表

        for note in notes_to_play:
            if note is not None: # 确保不是 None
                msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
                midi_port.send(msg_on)
                # print(f"发送 Note On: {msg_on}") # 可以取消注释用于调试
                active_notes[note] = True # 标记为激活
        return notes_to_play # 返回实际发送的音符列表

def send_note_off(note):
    """发送 Note Off 消息。注意：这里只处理单个音符，因为 active_notes 存储的是单个音符。"""
    global active_notes
    if midi_port and not midi_port.closed:
        if note is not None and note in active_notes: # 确保不是 None 且在激活列表中
            msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
            midi_port.send(msg_off)
            # print(f"发送 Note Off: {msg_off}") # 可以取消注释用于调试
            del active_notes[note]

# --- MIDI 文件转换函数 ---
def midi_file_to_sequence(midi_filepath, track_index=0, quantization_level=0.25):
    """
    从 MIDI 文件中提取音符事件，并将其转换为 custom_melody_sequence 格式。
    尝试将同时发生的音符组合成和弦。

    Args:
        midi_filepath (str): MIDI 文件的路径。
        track_index (int): 要提取音符的 MIDI 轨道索引 (通常为 0)。
        quantization_level (float): 量化级别 (以拍为单位)。
                                    例如，0.25 意味着所有音符都量化到十六分音符的网格上。
                                    用于判断同时发生的音符。

    Returns:
        list: 包含单个音符 (int) 或和弦 (list of int) 的序列。
    """
    try:
        mid = mido.MidiFile(midi_filepath)
        
        # 确保有轨道
        if not mid.tracks:
            print("MIDI 文件不包含任何轨道。")
            return []

        # 确保轨道索引有效
        if track_index >= len(mid.tracks):
            print(f"警告: 轨道索引 {track_index} 不存在。使用第一个轨道 (索引 0)。")
            track_index = 0

        track = mid.tracks[track_index]
        
        # 获取 MIDI 文件的 BPM (如果存在)
        tempo = mido.bpm2tempo(120) # 默认 120 BPM
        for msg in mid.tracks[0]: # 通常 tempo 消息在第一个轨道
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
        
        ticks_per_beat = mid.ticks_per_beat

        # 用于跟踪当前时间点和同时发生的音符
        current_time_ticks = 0 # 累积的 tick 数
        notes_on_start_ticks = {} # {midi_note: start_ticks}
        
        # 用于收集在同一量化时间点开始的所有音符
        # {quantized_time_beats: {midi_note_number: start_ticks}}
        # 我们需要先收集所有音符的开始和结束，再进行排序和组合
        note_events = [] # 存储 (start_ticks, end_ticks, note)

        for msg in track:
            current_time_ticks += msg.time # 累积 delta time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                notes_on_start_ticks[msg.note] = current_time_ticks
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in notes_on_start_ticks:
                    start_ticks = notes_on_start_ticks.pop(msg.note)
                    note_events.append((start_ticks, current_time_ticks, msg.note))
        
        # 按开始时间排序所有音符事件
        note_events.sort(key=lambda x: x[0])

        sequence = []
        last_quantized_beat = -float('inf') # 记录上一个处理的量化拍
        current_chord_notes = set() # 用于构建和弦，存储当前拍正在等待的音符

        for start_ticks, end_ticks, note in note_events:
            # 将 ticks 转换为 beats
            start_beats = mido.tick2beats(start_ticks, ticks_per_beat, tempo)
            end_beats = mido.tick2beats(end_ticks, ticks_per_beat, tempo)

            # 量化到最近的网格
            quantized_start_beat = round(start_beats / quantization_level) * quantization_level

            # 如果新的量化拍与上一个不同，则处理上一拍收集到的和弦
            if quantized_start_beat > last_quantized_beat:
                if current_chord_notes: # 如果有音符收集到了
                    if len(current_chord_notes) == 1:
                        sequence.append(list(current_chord_notes)[0])
                    else:
                        sequence.append(sorted(list(current_chord_notes)))
                current_chord_notes.clear() # 清空为新拍

            # 添加当前音符到当前拍的和弦
            current_chord_notes.add(note)
            last_quantized_beat = quantized_start_beat
        
        # 处理最后一个和弦
        if current_chord_notes:
            if len(current_chord_notes) == 1:
                sequence.append(list(current_chord_notes)[0])
            else:
                sequence.append(sorted(list(current_chord_notes)))

        # 检查并添加休止符：如果连续的量化时间之间有空隙
        final_sequence = []
        if sequence:
            last_added_element_time = -float('inf')
            # 重新遍历 note_events 来更准确地插入休止符
            # 这是一个更复杂的任务，暂时简化处理，只关注音符/和弦的添加
            # 如果需要精确的休止符，需要基于量化网格来遍历时间而非事件
            
            # 简单添加：如果在两个有效音符/和弦之间存在一个或多个量化单位的空白
            # 这个逻辑会比较复杂，需要对比 sorted_times 的相邻元素
            # 暂时先不自动插入大量休止符，让用户手动添加 []
            final_sequence = sequence

        print(f"成功从 '{midi_filepath}' 导入 {len(final_sequence)} 个元素。")
        return final_sequence

    except FileNotFoundError:
        messagebox.showerror("文件错误", f"找不到 MIDI 文件 '{midi_filepath}'。")
        return []
    except Exception as e:
        messagebox.showerror("MIDI 解析错误", f"解析 MIDI 文件时发生错误: {e}")
        print(f"MIDI 解析错误细节: {e}")
        return []


# --- GUI 应用程序类 ---
class MidiSequencerApp:
    def __init__(self, master):
        self.master = master
        master.title("MIDI 序列器")

        # UI Elements
        self.melody_listbox = tk.Listbox(master, height=15, width=60)
        self.melody_listbox.pack(pady=10)

        # Frame for adding notes/chords
        add_frame = tk.Frame(master)
        add_frame.pack(pady=5)

        tk.Label(add_frame, text="音符/和弦 (如: 60 或 60,64,67 或 rest):").pack(side=tk.LEFT)
        self.note_entry = tk.Entry(add_frame, width=25)
        self.note_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(add_frame, text="添加", command=self.add_note_or_chord).pack(side=tk.LEFT)
        tk.Button(add_frame, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT, padx=5)


        # File Operations
        file_frame = tk.Frame(master)
        file_frame.pack(pady=5)
        tk.Button(file_frame, text="导入 MIDI 文件", command=self.import_midi).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="保存序列 (JSON)", command=self.save_sequence).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="加载序列 (JSON)", command=self.load_sequence).pack(side=tk.LEFT, padx=5)


        # Controls
        control_frame = tk.Frame(master)
        control_frame.pack(pady=10)
        self.start_button = tk.Button(control_frame, text="启动键盘步进", command=self.start_keyboard_listener)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(control_frame, text="停止所有音符并关闭MIDI", command=self.stop_all_notes)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Initial display
        self.update_melody_listbox()

    def add_note_or_chord(self):
        input_str = self.note_entry.get().strip()
        if not input_str:
            return

        try:
            if ',' in input_str:
                # 和弦
                notes = [int(n.strip()) for n in input_str.split(',')]
                custom_melody_sequence.append(sorted(notes)) # 确保和弦内部音符有序
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
            messagebox.showerror("输入错误", "请输入有效的MIDI音高（整数），逗号分隔的和弦（如 60,64,67），或 'rest' / '[]' 表示休止符。")
        except Exception as e:
            messagebox.showerror("错误", f"添加失败: {e}")

    def delete_selected(self):
        selected_indices = self.melody_listbox.curselection()
        if not selected_indices:
            return
        
        # 从后往前删除，避免索引变化问题
        for index in reversed(selected_indices):
            if 0 <= index < len(custom_melody_sequence):
                del custom_melody_sequence[index]
        
        self.update_melody_listbox()


    def update_melody_listbox(self):
        self.melody_listbox.delete(0, tk.END)
        if not custom_melody_sequence:
            self.melody_listbox.insert(tk.END, "序列为空，请添加音符/和弦或导入MIDI。")
            return
            
        for i, item in enumerate(custom_melody_sequence):
            display_text = ""
            if isinstance(item, int):
                display_text = f"音符: {item} ({mido.midinote_to_name(item)})"
            elif isinstance(item, list) and item:
                chord_names = [mido.midinote_to_name(n) for n in item]
                display_text = f"和弦: {item} ({', '.join(chord_names)})"
            elif isinstance(item, list) and not item:
                display_text = "休止符"
            self.melody_listbox.insert(tk.END, f"{i:03d} | {display_text}")

    def import_midi(self):
        filepath = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid")])
        if filepath:
            try:
                new_sequence = midi_file_to_sequence(filepath) # track_index 和 quantization_level 可以作为参数
                if new_sequence is not None: # midi_file_to_sequence 可能返回 []
                    global custom_melody_sequence
                    custom_melody_sequence = new_sequence
                    self.update_melody_listbox()
                    messagebox.showinfo("导入成功", f"从 {filepath} 导入了 {len(new_sequence)} 个元素。")
            except Exception as e:
                messagebox.showerror("导入失败", f"无法导入 MIDI 文件: {e}")

    def save_sequence(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(custom_melody_sequence, f, indent=4) # indent=4 for pretty printing
                messagebox.showinfo("保存成功", "序列已保存。")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存序列: {e}")

    def load_sequence(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    loaded_sequence = json.load(f)
                    # 简单验证一下加载的数据结构，防止错误格式
                    # 允许 int, list of int
                    if all(isinstance(item, int) or (isinstance(item, list) and all(isinstance(n, int) for n in item)) for item in loaded_sequence):
                        global custom_melody_sequence
                        custom_melody_sequence = loaded_sequence
                        self.update_melody_listbox()
                        messagebox.showinfo("加载成功", "序列已加载。")
                    else:
                        messagebox.showerror("加载失败", "JSON 文件格式不正确或包含非预期数据类型。")
            except json.JSONDecodeError:
                messagebox.showerror("加载失败", "不是有效的 JSON 文件。")
            except Exception as e:
                messagebox.showerror("加载失败", f"无法加载序列: {e}")

    def start_keyboard_listener(self):
        global midi_port, current_sequence_index, last_notes_played, active_notes, current_pressed_keys

        if midi_port and not midi_port.closed:
            messagebox.showinfo("提示", "MIDI 监听器已在运行。")
            return

        if not custom_melody_sequence:
            messagebox.showwarning("警告", "旋律序列为空，无法启动监听器。")
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
            current_pressed_keys = set() # 确保在启动时清空

            # 启动键盘监听器在一个新线程中
            self.listener_thread = threading.Thread(target=self._run_listener, daemon=True)
            self.listener_thread.start()
            messagebox.showinfo("信息", "键盘监听器已启动。\n在程序窗口中，按下任意键盘键开始步进。\n按 'Esc' 键停止监听。")

        except Exception as e:
            messagebox.showerror("MIDI 端口错误", f"无法打开 MIDI 端口: {e}")
            print(f"MIDI 端口错误细节: {e}")

    def _run_listener(self):
        """在单独线程中运行键盘监听器"""
        print("键盘监听器线程已启动...")
        with keyboard.Listener(on_press=self.on_listener_press, on_release=self.on_listener_release) as listener:
            listener.join()
        # 监听器停止后（例如按Esc），关闭MIDI端口
        print("键盘监听器线程已停止。尝试关闭MIDI端口...")
        self.master.after(100, self.stop_all_notes) # 在GUI主线程中安全调用

    def on_listener_press(self, key):
        """pynput 回调，在监听器线程中运行"""
        global current_sequence_index, last_notes_played, active_notes, current_pressed_keys

        if key == keyboard.Key.esc:
            self.master.after(0, lambda: messagebox.showinfo("退出", "已检测到 'Esc' 键，正在退出键盘监听。"))
            return False # 停止监听器

        # 忽略重复按键事件 (当按住键时，pynput 会持续触发 on_press)
        # 对于字符键，使用 .char，对于特殊键，直接使用 key 对象
        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key

        if key_identifier in current_pressed_keys:
            return # 如果这个键已经按下了，就忽略
        current_pressed_keys.add(key_identifier)

        if not custom_melody_sequence:
            self.master.after(0, lambda: print("旋律序列为空，无法播放。"))
            return

        # 关闭上一个播放的音符或和弦
        for note in last_notes_played:
            send_note_off(note)
        last_notes_played = [] # 清空上一个音符列表

        # 获取当前要播放的音符或和弦
        element_to_play = custom_melody_sequence[current_sequence_index]
        actual_notes_played = send_note_on(element_to_play)
        
        if actual_notes_played:
            log_message = f"播放: {element_to_play} (序列索引: {current_sequence_index})"
            last_notes_played = actual_notes_played # 记住实际播放的音符
        else:
            log_message = f"播放休止符 (序列索引: {current_sequence_index})"

        # 更新索引
        current_sequence_index = (current_sequence_index + 1) % len(custom_melody_sequence)
        
        # 在GUI主线程中更新UI或打印到控制台
        self.master.after(0, lambda: print(log_message))
        self.master.after(0, lambda: self.update_listbox_highlight(current_sequence_index - 1)) # 高亮上一个播放的


    def on_listener_release(self, key):
        """pynput 回调，在监听器线程中运行"""
        global current_pressed_keys
        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key
        current_pressed_keys.discard(key_identifier)

    def update_listbox_highlight(self, index_to_highlight):
        """在GUI主线程中更新Listbox的高亮显示"""
        self.melody_listbox.select_clear(0, tk.END) # 清除所有高亮
        if custom_melody_sequence: # 确保序列不为空
            # 索引可能在模运算后回到开头，所以需要处理
            display_index = index_to_highlight 
            if display_index < 0: # 如果是 -1，表示刚刚从最后一个音符回到 0
                display_index = len(custom_melody_sequence) - 1

            if 0 <= display_index < len(custom_melody_sequence):
                self.melody_listbox.select_set(display_index) # 设置新的高亮
                self.melody_listbox.see(display_index) # 确保高亮项可见


    def stop_all_notes(self):
        """停止所有正在发声的音符并关闭 MIDI 端口"""
        global midi_port, active_notes
        if midi_port and not midi_port.closed:
            print("正在停止所有激活音符并关闭MIDI端口...")
            for note in list(active_notes.keys()): # 遍历拷贝，因为可能会修改字典
                send_note_off(note)
            midi_port.close()
            midi_port = None # 清除端口引用
            messagebox.showinfo("信息", "所有音符已停止，MIDI 端口已关闭。")
        else:
            print("MIDI 端口未打开或已关闭。")
            messagebox.showinfo("信息", "MIDI 端口未打开或已关闭。")

# 主 GUI 循环
if __name__ == "__main__":
    root = tk.Tk()
    app = MidiSequencerApp(root)
    root.mainloop()