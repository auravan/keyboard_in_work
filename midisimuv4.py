import mido
import time
from pynput import keyboard # 导入 pynput 的键盘模块

# MIDI 音符映射：将键盘字符映射到 MIDI 音高 (C4 八度)
# MIDI 音高 60 是 C4
# 这里我们映射到 C4 到 B4 的音高 (60 到 71)
key_to_midi_note = {
    'q': 60,  # C4
    'w': 61,  # C#4
    'e': 62,  # D4
    'r': 63,  # D#4
    't': 64,  # E4
    'y': 65,  # F4
    'u': 66,  # F#4
    'i': 67,  # G4
    'o': 68,  # G#4
    'p': 69,  # A4
    '[': 70,  # A#4
    ']': 71   # B4
    
}

# 存储当前正在发声的音符，用于在按键释放时关闭
active_notes = {} # 字典，键是 MIDI 音高，值是 True (表示正在发声)

# MIDI 通道和力度
midi_channel = 0
velocity = 100

midi_port = None # 全局变量，用于在不同函数中访问 MIDI 端口

def on_press(key):
    """当键盘键被按下时调用"""
    global midi_port, active_notes # 声明全局变量以便修改

    if midi_port is None or midi_port.closed:
        print("MIDI 端口未打开或已关闭。请检查启动时的错误。")
        return

    try:
        # 特殊按键，如 Esc 退出
        if key == keyboard.Key.esc:
            print("按下 'Esc' 键，退出 MIDI 键盘模拟。")
            return False # 返回 False 停止监听器

        # 处理普通字符键
        if hasattr(key, 'char') and key.char is not None:
            char_key = key.char.lower() # 将按键转换为小写

            if char_key in key_to_midi_note:
                note = key_to_midi_note[char_key]

                # 如果音符已经处于激活状态 (还在发声)，则不重复发送 Note On
                if note not in active_notes:
                    msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
                    midi_port.send(msg_on)
                    print(f"发送 Note On: {msg_on} (按键: '{char_key}')")
                    active_notes[note] = True # 标记此音符为激活状态
    except Exception as e:
        print(f"处理按键按下事件时出错: {e}")


def on_release(key):
    """当键盘键被释放时调用"""
    global midi_port, active_notes # 声明全局变量以便修改

    if midi_port is None or midi_port.closed:
        return

    try:
        # 处理普通字符键
        if hasattr(key, 'char') and key.char is not None:
            char_key = key.char.lower() # 将按键转换为小写

            if char_key in key_to_midi_note:
                note = key_to_midi_note[char_key]

                # 如果音符处于激活状态，则发送 Note Off
                if note in active_notes:
                    msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
                    midi_port.send(msg_off)
                    print(f"发送 Note Off: {msg_off}")
                    del active_notes[note] # 从激活列表中移除
    except Exception as e:
        print(f"处理按键释放事件时出错: {e}")

def start_midi_keyboard():
    global midi_port # 声明全局变量以便修改

    try:
        print("Available MIDI output ports:", mido.get_output_names())

        port_to_open_name = None
        for name in mido.get_output_names():
            if "loopmidi" in name.lower() or "python" in name.lower() or "rtmidi" in name.lower():
                port_to_open_name = name
                break
        
        if port_to_open_name:
            try:
                # 尝试打开一个已存在的虚拟端口（如 LoopMIDI 创建的）
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

        print("\n--- 实时 MIDI 键盘模拟 ---")
        print("使用 'q w e r t y u i o p [ ]' 演奏 C4 八度音符。")
        print("按 'Esc' 键退出。")
        print("--------------------------\n")

        # 创建键盘监听器
        # on_press 和 on_release 函数会在对应的键盘事件发生时被调用
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join() # 启动监听器并阻塞主线程，直到监听器停止

    except Exception as e:
        print(f"程序启动时发生错误: {e}")
    finally:
        if midi_port and not midi_port.closed:
            # 在程序退出前，确保关闭所有激活的音符
            for note in list(active_notes.keys()): # 遍历拷贝，因为可能会修改字典
                try:
                    msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
                    midi_port.send(msg_off)
                    print(f"发送 Note Off (清理): {msg_off}")
                except Exception as e:
                    print(f"关闭音符时出错: {e}")
            midi_port.close()
            print("MIDI 端口已关闭。")
        print("MIDI 模拟程序已退出。")

if __name__ == "__main__":
    start_midi_keyboard()