import mido
import time
from pynput import keyboard
import threading

# --- MIDI 配置 ---
midi_channel = 0
velocity = 90 # 默认力度

# --- 自定义旋律序列 ---
# 请在这里定义你的音符序列。
# 每个元素是一个 MIDI 音高。
# 示例旋律：dodososolalasofafamimireredo (假设 do=C4=60)
# 你可以根据需要修改这些音高来创建你自己的旋律。
# 注意：MIDI 音高 60 是 C4，61 是 C#4，以此类推。
custom_melody_sequence = [
    60, # do
    60, # do
    67, # sol
    67, # sol
    69, # la
    69, # la
    67, # sol
    65, # fa
    65, # fa
    64, # mi
    64, # mi
    62, # re
    62, # re
    60  # do
]

# --- 全局变量 ---
midi_port = None
current_note_index = 0 # 跟踪当前播放到旋律序列的哪个音符
last_note_played = None # 存储上一个播放的音符，用于在下一个音符播放前关闭
# active_notes 字典用于处理多音符同时按下的情况，但在这个“步进”模式下，
# 我们主要关注逐个音符的播放，所以它的作用更多是确保上一个音符被关闭。
active_notes = {}


# --- MIDI 消息发送函数 ---
def send_note_on(note):
    global active_notes
    if midi_port and not midi_port.closed:
        msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
        midi_port.send(msg_on)
        # print(f"发送 Note On: {msg_on}")
        active_notes[note] = True

def send_note_off(note):
    global active_notes
    if midi_port and not midi_port.closed:
        if note in active_notes:
            msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
            midi_port.send(msg_off)
            # print(f"发送 Note Off: {msg_off}")
            del active_notes[note]

# --- 键盘监听函数 ---
def on_press(key):
    """当键盘键被按下时调用"""
    global current_note_index, last_note_played

    if midi_port is None or midi_port.closed:
        print("MIDI 端口未打开或已关闭。")
        return

    try:
        # 按下 'Esc' 键退出
        if key == keyboard.Key.esc:
            print("按下 'Esc' 键，退出程序。")
            # 在退出前关闭所有可能还在响的音符
            for note in list(active_notes.keys()):
                send_note_off(note)
            return False # 返回 False 停止监听器

        # 忽略重复按键事件 (当按住键时，pynput 会持续触发 on_press)
        # 只处理第一次按键事件
        if key in active_notes: # 这里 active_notes 也可以用来跟踪按下的键，但我们更关心音符
            return

        # 任何按键触发下一个音符
        # 1. 首先关闭上一个音符（如果存在）
        if last_note_played is not None:
            send_note_off(last_note_played)

        # 2. 获取当前要播放的音符
        if not custom_melody_sequence:
            print("旋律序列为空，无法播放。")
            return

        note_to_play = custom_melody_sequence[current_note_index]
        send_note_on(note_to_play)
        print(f"播放音符: {note_to_play} (序列索引: {current_note_index})")

        # 3. 更新索引为下一个音符，如果到达末尾则循环回开头
        current_note_index = (current_note_index + 1) % len(custom_melody_sequence)
        last_note_played = note_to_play # 记住这个音符，以便下次按键时关闭它

    except Exception as e:
        print(f"处理按键按下事件时出错: {e}")

def on_release(key):
    """当键盘键被释放时调用"""
    # 在这个“步进”模式下，我们希望音符持续发声直到下一个键被按下，
    # 或者程序退出。所以这里不需要发送 Note Off。
    # Note Off 会在下一次按键时由 on_press 统一处理。
    pass


# --- 主程序启动函数 ---
def start_midi_stepper():
    global midi_port

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

        print("\n--- 键盘步进旋律播放器 ---")
        print(f"自定义旋律长度: {len(custom_melody_sequence)} 个音符。")
        print("按下键盘上的任意键，将播放旋律中的下一个音符。")
        print("音符将持续发声，直到你按下下一个键。")
        print("按 'Esc' 键退出程序。")
        print("----------------------------\n")

        # 创建键盘监听器
        # on_press 在键被按下时触发，on_release 在键被释放时触发
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join() # 启动监听器并阻塞主线程，直到监听器停止

    except Exception as e:
        print(f"程序启动时发生错误: {e}")
    finally:
        if midi_port and not midi_port.closed:
            # 程序退出前，确保关闭所有可能还在响的音符
            for note in list(active_notes.keys()):
                send_note_off(note)
            midi_port.close()
            print("MIDI 端口已关闭。")
        print("程序已退出。")

if __name__ == "__main__":
    start_midi_stepper()