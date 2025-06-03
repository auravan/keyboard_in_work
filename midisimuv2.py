import mido
import time
import sys

def send_midi_from_keyboard():
    # MIDI 音符映射：将键盘字符映射到 MIDI 音高 (C3 八度)
    # MIDI 音高 60 是 C4。C3 则是 48。
    # 这里我们映射到 C3 到 B3 的音高，也就是 48 到 59
    # 键 '1' 对应 C3 (48), '2' 对应 C#3 (49), ..., '=' 对应 B3 (59)
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

    # MIDI 通道和力度
    midi_channel = 0
    velocity = 100

    midi_port = None
    try:
        # 打印可用输出端口
        print("Available MIDI output ports:", mido.get_output_names())

        # 尝试打开一个虚拟端口
        port_name = "Python Keyboard MIDI Out"
        try:
            # open_output 尝试打开一个端口，如果不存在则创建
            midi_port = mido.open_output(port_name, virtual=True)
            print(f"Successfully opened virtual port: '{port_name}'")
        except Exception as e:
            print(f"Failed to open virtual port '{port_name}': {e}")
            print("Trying to open the first available non-virtual port instead.")
            output_ports = mido.get_output_names()
            if output_ports:
                midi_port = mido.open_output(output_ports[0])
                print(f"Opened existing port: '{output_ports[0]}'")
            else:
                print("No MIDI output ports found. Please ensure you have a MIDI driver (e.g., LoopMIDI) installed.")
                return

        print("\n--- MIDI 键盘模拟 ---")
        print("按 '1' 到 '=' 发送 MIDI 音符 (C3 到 B3)。")
        print("按 'q' 退出。")
        print("---------------------\n")

        while True:
            # 实时读取单个字符输入在标准 Python 中较难跨平台实现，
            # 这里我们使用 input()，每次按回车后读取字符。
            # 如果需要实时按键，你需要使用特定的终端库 (如 msvcrt, termios/tty)
            # 或更高级的 pynput 库。
            key_input = input("输入键 (1-9,0,-,= 或 q 退出): ").strip().lower()

            if key_input == 'q':
                print("退出 MIDI 键盘模拟。")
                break
            elif key_input in key_to_midi_note:
                note = key_to_midi_note[key_input]

                # 发送 Note On
                msg_on = mido.Message('note_on', channel=midi_channel, note=note, velocity=velocity)
                midi_port.send(msg_on)
                print(f"发送 Note On: {msg_on} (按键: '{key_input}')")

                # 为了模拟按键的持续时间，这里我们简单地等待一小段时间
                # 在实际应用中，你可能希望按住按键就持续发声，松开按键才发 Note Off
                # 这需要更复杂的实时键盘监听逻辑
                time.sleep(0.5) # 音符持续 0.5 秒

                # 发送 Note Off
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
## 如何运行和测试

# 1.  **安装 `mido`：**
#     ```bash
#     pip install mido
#     ```

# 2.  **安装虚拟 MIDI 驱动（Windows 用户必看）：**
#     如果你是 Windows 用户，为了让其他音乐软件（如 DAW 或软音源）能“看到”你的 Python 虚拟 MIDI 设备，你几乎肯定需要安装一个虚拟 MIDI 驱动。推荐使用免费的 **LoopMIDI**：
#     [https://www.tobias-erichsen.de/software/loopmidi.html](https://www.tobias-erichsen.de/software/loopmidi.html)
#     安装 LoopMIDI 后，创建一个或多个虚拟端口。你的 Python 脚本会尝试连接到这些端口。

# 3.  **运行 Python 脚本：**
#     将上述代码保存为 `.py` 文件（例如 `keyboard_midi.py`），然后在终端运行：
#     ```bash
#     python keyboard_midi.py
#     ```

# 4.  **连接到你的软音源或 DAW：**
#     * **打开你的软音源或 DAW (数字音频工作站)。**
#     * **查找 MIDI 输入设置：** 在你的软件的 MIDI 设置中，你会看到一个名为 **"Python Keyboard MIDI Out"**（如果你成功创建了虚拟端口）或 LoopMIDI 创建的端口名称。
#     * **选择该端口作为 MIDI 输入。**
#     * **加载一个钢琴音色。**
#     * **在终端中输入数字或符号：** 当你在终端中输入 '1' 到 '=' 并按回车时，你的软音源应该会发出对应的钢琴音符。

# ---

# ## 注意事项和进阶：

# * **实时按键响应：**
#     当前代码使用 `input()`，这意味着你每次输入字符后需要按回车。如果你希望实现 **实时按键响应**（即按下键立即发声，松开键立即停止），这需要更高级的键盘监听库：
#     * **`pynput` (推荐，跨平台)：** 这是一个功能强大的库，可以监听键盘和鼠标事件。你可以监听 `on_press` 和 `on_release` 事件来发送 Note On 和 Note Off。安装：`pip install pynput`。
#     * **`msvcrt` (Windows only)：** `msvcrt.getch()` 可以读取单个字符而无需回车。
#     * **`termios` / `tty` (Linux/macOS only)：** 允许你在 Unix-like 系统上进行原始终端输入。

#     使用 `pynput` 实现实时按键会使代码更复杂，因为你需要管理多线程（键盘监听通常在一个单独的线程中运行）以及跟踪当前按下的音符，以便在按键释放时发送 Note Off。

# * **八度选择：**
#     当前代码只在一个八度内发送音符。你可以扩展 `key_to_midi_note` 字典，或者添加额外的按键（例如 'z', 'x'）来切换八度。

# * **力度变化：**
#     目前的力度是固定的 (`velocity = 100`)。你可以根据需要调整它，或者甚至实现更复杂的逻辑，例如根据输入字符的重复次数或其他方式来模拟不同的力度。

# 这个方案提供了一个坚实的基础，让你通过键盘控制 MIDI 信号。如果你需要更高级的实时交互，可以考虑投入时间学习 `pynput` 库。