import mido
import time
from pynput import keyboard
import threading # 用于在单独线程中播放旋律，不阻塞键盘监听

# --- MIDI 配置 ---
midi_channel = 0
velocity = 90 # 默认力度

# --- 旋律定义 ---
# 将你的 dodososolalasofafamimireredo 转换为 MIDI 音高和时值
# 这里我们假设 'do' 是 C4 (MIDI 60)，'re' 是 D4 (MIDI 62)，以此类推。
# 每个元组是 (MIDI 音高, 时值_拍数)
# 时值 0.5 拍代表八分音符，1.0 拍代表四分音符
# 假设 1 拍 = 0.4 秒 (即 BPM 150)
BEAT_DURATION = 0.4 # 每拍的秒数 (决定速度，例如 0.5 秒/拍 = 120 BPM)

# 你的旋律：dodososolalasofafamimireredo
# 假设 'do' = C4 (60), 're' = D4 (62), 'mi' = E4 (64), 'fa' = F4 (65), 'sol' = G4 (67), 'la' = A4 (69)
# 简化示例，假设所有音符都是四分音符 (1.0 拍)
melody_notes = [
    (60, 1.0), # do
    (60, 1.0), # do
    (67, 1.0), # sol
    (67, 1.0), # sol
    (69, 1.0), # la
    (69, 1.0), # la
    (67, 1.0), # sol
    (65, 1.0), # fa
    (65, 1.0), # fa
    (64, 1.0), # mi
    (64, 1.0), # mi
    (62, 1.0), # re
    (62, 1.0), # re
    (60, 1.0)  # do
]

# --- 全局变量和标志 ---
midi_port = None
melody_playing = False # 标志，指示旋律是否正在播放

# --- 旋律播放函数 ---
def play_melody():
    global melody_playing
    if melody_playing: # 如果旋律正在播放，则不重复播放
        print("旋律正在播放中，请等待。")
        return

    melody_playing = True
    print("\n--- 正在播放旋律 ---")
    try:
        for note, duration_beats in melody_notes:
            if not melody_playing: # 如果在播放过程中被停止
                break

            # 发送 Note On
            msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
            midi_port.send(msg_on)
            # print(f"发送 Note On: {msg_on}")

            # 保持音符发声的时长
            time.sleep(duration_beats * BEAT_DURATION)

            # 发送 Note Off
            msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
            midi_port.send(msg_off)
            # print(f"发送 Note Off: {msg_off}")
        
        print("--- 旋律播放完毕 ---")

    except Exception as e:
        print(f"播放旋律时发生错误: {e}")
    finally:
        melody_playing = False # 播放结束或出错后重置标志

# --- 键盘监听函数 ---
def on_press(key):
    """当键盘键被按下时调用"""
    global melody_playing

    # 按下 'Esc' 键退出
    if key == keyboard.Key.esc:
        print("按下 'Esc' 键，退出程序。")
        # 如果旋律正在播放，尝试停止它（通过重置标志，线程会在下次循环检查）
        if melody_playing:
            melody_playing = False
        return False # 返回 False 停止监听器

    # 忽略重复按键事件 (当按住键时，pynput 会持续触发 on_press)
    # 并且只有当旋律不在播放时才触发新的播放
    if not melody_playing:
        # 创建一个新线程来播放旋律，这样键盘监听不会被阻塞
        melody_thread = threading.Thread(target=play_melody)
        melody_thread.start()
    
def on_release(key):
    # 对于这个应用场景，我们不需要在键释放时做任何事
    pass

# --- 主程序启动函数 ---
def start_midi_player():
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

        print("\n--- 旋律演奏器 ---")
        print("按下任意键开始播放预设旋律。")
        print("旋律播放期间，其他按键将被忽略。")
        print("按 'Esc' 键退出程序。")
        print("--------------------\n")

        # 创建键盘监听器
        # on_press 在键被按下时触发，on_release 在键被释放时触发
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join() # 启动监听器并阻塞主线程，直到监听器停止

    except Exception as e:
        print(f"程序启动时发生错误: {e}")
    finally:
        if midi_port and not midi_port.closed:
            # 在程序退出前，发送所有挂起音符的 Note Off (理论上 play_melody 会自行处理)
            # 但为了安全，这里可以再次清理
            try:
                # 假设旋律可能在播放中中断，清空所有理论上的激活音符
                for note, _ in melody_notes:
                    msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
                    midi_port.send(msg_off)
            except Exception as e:
                print(f"清理 MIDI 音符时出错: {e}")
            midi_port.close()
            print("MIDI 端口已关闭。")
        print("程序已退出。")

if __name__ == "__main__":
    start_midi_player()