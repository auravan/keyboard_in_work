import mido
import time
import sys

def send_midi_from_keyboard():
    key_to_midi_note = {
        '1': 48,  # C3
        '2': 49,  # C#3
        '3': 50,  # D3
        '4': 51,  # D#3
        '5': 52,  # E3
        '6': 53,  # F3
        '7': 54,  # F#3
        '8': 55,  # G3
        '9': 56,  # G#3
        '0': 57,  # A3
        '-': 58,  # A#3
        '=': 59   # B3
    }

    midi_channel = 0
    velocity = 100

    midi_port = None
    try:
        # 1. 打印所有可用的 MIDI 输出端口
        print("Available MIDI output ports:", mido.get_output_names())

        # 2. 确定你的 LoopMIDI 端口名称
        #    在 LoopMIDI 界面中查看你创建的端口名称，例如 'loopMIDI Port'
        #    将下面的 port_to_open_name 替换为你实际的端口名称
        port_to_open_name = None
        for name in mido.get_output_names():
            if "loopmidi" in name.lower() or "python" in name.lower(): # 尝试匹配包含 "loopmidi" 或 "python" 的端口名
                port_to_open_name = name
                break

        if port_to_open_name:
            try:
                midi_port = mido.open_output(port_to_open_name)
                print(f"Successfully opened MIDI port: '{port_to_open_name}'")
            except Exception as e:
                print(f"Failed to open port '{port_to_open_name}': {e}")
                print("This might happen if the port is already in use by another application.")
                return
        else:
            print("Could not find a LoopMIDI port or any suitable port.")
            print("Please ensure LoopMIDI is running and you have created a virtual port.")
            return

        print("\n--- MIDI 键盘模拟 ---")
        print("按 '1' 到 '=' 发送 MIDI 音符 (C3 到 B3)。")
        print("按 'q' 退出。")
        print("---------------------\n")

        while True:
            key_input = input("输入键 (1-9,0,-,= 或 q 退出): ").strip().lower()

            if key_input == 'q':
                print("退出 MIDI 键盘模拟。")
                break
            elif key_input in key_to_midi_note:
                note = key_to_midi_note[key_input]

                msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
                midi_port.send(msg_on)
                print(f"发送 Note On: {msg_on} (按键: '{key_input}')")

                time.sleep(0.5)

                msg_off = mido.Message('note_off', channel=midi_channel, note=note, velocity=0)
                midi_port.send(msg_off)
                print(f"发送 Note Off: {msg_off}")
            else:
                print("无效输入。请按 '1' 到 '=' 或 'q' 退出。")

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if midi_port and not midi_port.closed:
            midi_port.close()
            print("MIDI 端口已关闭。")

if __name__ == "__main__":
    print("Starting MIDI simulation with mido...")
    send_midi_from_keyboard()
    print("MIDI simulation finished.")