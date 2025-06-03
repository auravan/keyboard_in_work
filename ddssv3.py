import mido
import time
from pynput import keyboard
import threading

# --- MIDI 配置 ---
midi_channel = 0
velocity = 90 # 默认力度

# --- 自定义旋律序列 ---
# 每个元素可以是：
# 1. 单个 MIDI 音高 (例如: 60 代表 C4)
# 2. 一个 MIDI 音高列表 (例如: [60, 64, 67] 代表 C大三和弦 C-E-G)
# 3. 如果需要休止符 (即不播放任何音符，只前进到下一个序列元素): 可以用 []
custom_melody_sequence = [
    60,           # C4 (do)
    55,           # G3 (sol)
    [60, 64, 67], # C大三和弦 (C4-E4-G4)
    67,           # G4 (sol)
    69,           # A4 (la)
    67,           # G4 (sol)
    [65, 69, 72], # F大三和弦 (F4-A4-C5)
    64,           # E4 (mi)
    62,           # D4 (re)
    62,           # D4 (re)
    60,           # C4 (do)
    [],           # 休止符 (不播放任何音符，只前进)
    [72, 67, 64]  # C5-G4-E4 (C大三和弦高把位)
]


# --- 全局变量 ---
midi_port = None
current_sequence_index = 0 # 跟踪当前播放到旋律序列的哪个元素
last_notes_played = []     # 存储上一个播放的音符/和弦，用于在下一个元素播放前关闭

# 修复：初始化 active_notes 字典
# 它应该在全局作用域或者 start_midi_stepper 函数内部作为全局变量声明
active_notes = {} 
current_pressed_keys = set() # 用于跟踪当前按下的键，避免重复触发 on_press


# --- MIDI 消息发送函数 ---
def send_note_on(note_or_chord):
    global active_notes # 确保函数能够修改全局的 active_notes
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
                # print(f"发送 Note On: {msg_on}")
                active_notes[note] = True # 标记为激活
        return notes_to_play # 返回实际发送的音符列表

def send_note_off(note_or_chord):
    global active_notes # 确保函数能够修改全局的 active_notes
    if midi_port and not midi_port.closed:
        notes_to_stop = []
        if isinstance(note_or_chord, int):
            notes_to_stop.append(note_or_chord)
        elif isinstance(note_or_chord, list) or isinstance(note_or_chord, tuple):
            notes_to_stop.extend(note_or_chord)
        
        for note in notes_to_stop:
            if note is not None and note in active_notes: # 确保不是 None 且在激活列表中
                msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
                midi_port.send(msg_off)
                # print(f"发送 Note Off: {msg_off}")
                del active_notes[note]


# --- 键盘监听函数 ---
def on_press(key):
    """当键盘键被按下时调用"""
    global current_sequence_index, last_notes_played, active_notes, current_pressed_keys # 确保所有全局变量都被声明

    if midi_port is None or midi_port.closed:
        print("MIDI 端口未打开或已关闭。")
        return

    try:
        # 按下 'Esc' 键退出
        if key == keyboard.Key.esc:
            print("按下 'Esc' 键，退出程序。")
            # 在退出前关闭所有可能还在响的音符
            for note in list(active_notes.keys()): # 遍历拷贝，因为可能会修改字典
                send_note_off(note)
            return False # 返回 False 停止监听器

        # 忽略重复按键事件 (当按住键时，pynput 会持续触发 on_press)
        # 记录当前按下的键，以便在下次按压时检查是否是重复按压
        key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key

        if key_identifier in current_pressed_keys:
            return # 如果这个键已经按下了，就忽略
        
        current_pressed_keys.add(key_identifier)


        # 1. 首先关闭上一个播放的音符或和弦
        if last_notes_played: # 检查列表是否为空
            # 这里的 last_notes_played 实际上是上一个元素中的所有音符
            for note in last_notes_played:
                send_note_off(note)
            last_notes_played = [] # 清空，防止下次重复关闭


        # 2. 获取当前要播放的音符或和弦
        if not custom_melody_sequence:
            print("旋律序列为空，无法播放。")
            return

        element_to_play = custom_melody_sequence[current_sequence_index]
        
        # 发送 Note On 消息，并获取实际播放的音符列表
        actual_notes_played = send_note_on(element_to_play)
        
        if actual_notes_played:
            print(f"播放: {element_to_play} (序列索引: {current_sequence_index})")
            last_notes_played = actual_notes_played # 记住实际播放的音符
        else:
            print(f"播放休止符 (序列索引: {current_sequence_index})")
            # 如果是休止符，last_notes_played 保持为空，不会有音符挂起


        # 3. 更新索引为下一个元素，如果到达末尾则循环回开头
        current_sequence_index = (current_sequence_index + 1) % len(custom_melody_sequence)

    except Exception as e:
        print(f"处理按键按下事件时出错: {e}")

def on_release(key):
    """当键盘键被释放时调用"""
    global current_pressed_keys # 确保能够修改全局变量
    # 移除被释放的键，以便再次按下时可以触发
    key_identifier = key.char.lower() if hasattr(key, 'char') and key.char is not None else key
    current_pressed_keys.discard(key_identifier)


# --- 主程序启动函数 ---
def start_midi_stepper():
    global midi_port, active_notes # 确保能够修改全局变量 active_notes

    # 再次强调：active_notes 在全局作用域已经初始化，这里只是为了代码清晰再次提及
    # 如果你在函数内部初始化它，就需要在 on_press/on_release 里面加 global active_notes

    try:
        print("Available MIDI output ports:", mido.get_output_names())

        port_to_open_name = None
        for name in mido.get_output_names():
            # 尝试匹配 LoopMIDI, Python 或 RtMidi 创建的端口
            if "loopmidi" in name.lower() or "python" in name.lower() or "rtmidi" in name.lower():
                port_to_open_name = name
                break
        
        if port_to_open_name:
            try:
                midi_port = mido.open_output(port_to_open_name)
                print(f"Successfully opened MIDI port: '{port_to_open_name}'")
            except Exception as e:
                print(f"Failed to open port '{port_to_open_name}': {e}")
                print("This might happen if the port is already in use by another application.")
                # 尝试打开第一个可用端口作为备用
                if mido.get_output_names():
                    midi_port = mido.open_output(mido.get_output_names()[0])
                    print(f"Opened first available port: '{mido.get_output_names()[0]}'")
                else:
                    print("No MIDI output ports found. Please ensure you have a MIDI driver (e.g., LoopMIDI) installed.")
                    return
        else:
            print("Could not find a LoopMIDI or other suitable virtual MIDI port.")
            print("Please ensure LoopMIDI is running and you have created a virtual port.")
            return

        print("\n--- 键盘步进旋律/和弦播放器 ---")
        print(f"自定义序列长度: {len(custom_melody_sequence)} 个元素。")
        print("按下键盘上的任意键，将播放序列中的下一个音符或和弦。")
        print("音符/和弦将持续发声，直到你按下下一个键。")
        print("按 'Esc' 键退出程序。")
        print("----------------------------\n")

        # 创建键盘监听器
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    except Exception as e:
        print(f"程序启动时发生错误: {e}")
    finally:
        if midi_port and not midi_port.closed:
            # 程序退出前，确保关闭所有可能还在响的音符
            for note in list(active_notes.keys()): # 遍历拷贝，因为可能会修改字典
                send_note_off(note)
            midi_port.close()
            print("MIDI 端口已关闭。")
        print("程序已退出。")

if __name__ == "__main__":
    start_midi_stepper()