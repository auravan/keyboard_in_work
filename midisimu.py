import rtmidi
import time

def send_midi_signal():
    try:
        # 创建一个 MidiOut 实例
        midiout = rtmidi.MidiOut()
        
        # 查找可用的 MIDI 端口
        available_ports = midiout.get_ports()
        
        # 打印可用端口
        print("Available MIDI ports:", available_ports)

        # 如果没有可用端口，尝试创建一个虚拟端口
        # 在某些操作系统（如 Windows）上，直接创建虚拟端口可能需要特定的驱动或配置
        # 在 Linux 上，通常可以很好地工作（需要安装 ALSA 的虚拟 MIDI 模块）
        # 在 macOS 上，也通常支持创建虚拟端口
        if not available_ports:
            print("No MIDI ports found. Attempting to open a virtual port.")
            # 创建一个虚拟 MIDI 端口，名为 "Python Virtual MIDI Out"
            # 注意：在某些系统上，这可能需要管理员权限或特定的配置
            # 如果创建失败，可能会抛出异常
            port_name = "Python Virtual MIDI Out"
            try:
                midiout.open_virtual_port(port_name)
                print(f"Successfully opened virtual port: '{port_name}'")
            except rtmidi.SystemError as e:
                print(f"Failed to open virtual port: {e}")
                print("Please ensure your system allows virtual MIDI ports or check permissions.")
                print("On Linux, you might need 'sudo modprobe snd-virmidi'.")
                return
        else:
            # 如果有可用端口，打开第一个输出端口
            # 实际应用中，你可能需要让用户选择一个端口
            print(f"Opening port: '{available_ports[0]}'")
            midiout.open_port(0) # 打开第一个输出端口

        # MIDI 通道 (0-15)
        midi_channel = 0 
        # 音符 C4 (MIDI 音符号 60)
        note_number = 60 
        # 速度 (0-127)
        velocity = 100  

        print(f"Sending MIDI Note On/Off for note {note_number} on channel {midi_channel}...")
        
        for i in range(50): # 发送 5 次音符
            # Note On 消息: [0x90 + channel, note_number, velocity]
            # 0x90 是 Note On 消息的起始字节，其中 0x90-0x9F 分别代表通道 0-15
            note_on = [0x90 + midi_channel, note_number, velocity]
            midiout.send_message(note_on)
            print(f"Sent Note On: {note_on}")
            time.sleep(0.5) # 保持音符开启 0.5 秒

            # Note Off 消息: [0x80 + channel, note_number, velocity]
            # 0x80 是 Note Off 消息的起始字节
            note_off = [0x80 + midi_channel, note_number, 0] # 速度通常设为 0
            midiout.send_message(note_off)
            print(f"Sent Note Off: {note_off}")
            time.sleep(0.5) # 等待 0.5 秒再发送下一个音符

            note_number += 2 # 每次提高两个半音

    except rtmidi.MidiOutError as e:
        print(f"MIDI Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'midiout' in locals() and midiout.is_port_open():
            midiout.close_port()
            print("MIDI port closed.")

if __name__ == "__main__":
    print("Starting MIDI simulation...")
    send_midi_signal()
    print("MIDI simulation finished.")