import argparse
import os
from mido import MidiFile, MidiTrack, Message

def analyze_midi(midi_file_path):
    """
    解析MIDI文件并显示基本信息。
    """
    try:
        mid = MidiFile(midi_file_path)
        print(f"分析 MIDI 文件: {midi_file_path}")
        print(f"  轨道数量: {len(mid.tracks)}")
        print(f"  文件类型 (format): {mid.type}")
        print(f"  每拍刻度 (ticks_per_beat): {mid.ticks_per_beat}")

        print("\n  轨道信息:")
        for i, track in enumerate(mid.tracks):
            print(f"    轨道 {i}: 长度 {len(track)} 事件")
            program_changes = []
            for msg in track:
                if msg.type == 'program_change':
                    program_changes.append(f"  通道 {msg.channel}, 乐器 {msg.program}")
            if program_changes:
                print(f"      检测到的乐器变化: {', '.join(program_changes)}")
            else:
                print("      未检测到 Program Change 消息")

    except Exception as e:
        print(f"错误: 无法解析 MIDI 文件 {midi_file_path} - {e}")

def separate_midi_by_instrument(midi_file_path, output_dir="separated_midi"):
    """
    将MIDI文件按乐器分离到不同的轨道并导出为独立的MIDI文件。
    """
    try:
        mid = MidiFile(midi_file_path)
        
        # 存储按乐器分离的轨道
        instrument_tracks = {} # key: (channel, program), value: MidiTrack

        for track in mid.tracks:
            current_program = {} # key: channel, value: program
            for msg in track:
                if msg.type == 'program_change':
                    current_program[msg.channel] = msg.program
                
                # 如果是音符事件或其他需要分离的事件
                if msg.type in ['note_on', 'note_off', 'control_change', 'pitchwheel'] and msg.channel in current_program:
                    key = (msg.channel, current_program[msg.channel])
                    if key not in instrument_tracks:
                        instrument_tracks[key] = MidiTrack()
                        # 添加 Program Change 消息到新轨道的开头
                        instrument_tracks[key].append(Message('program_change', channel=msg.channel, program=current_program[msg.channel], time=0))
                    instrument_tracks[key].append(msg)
                elif msg.type == 'set_tempo': # 通常在第一个轨道，需要保留
                    if (0,0) not in instrument_tracks: # 假设通用事件可以放到一个默认轨道
                        instrument_tracks[(0,0)] = MidiTrack()
                    instrument_tracks[(0,0)].append(msg)
                elif msg.is_meta: # 元事件，如时间签名，文本事件等，也放到一个默认轨道
                    if (0,0) not in instrument_tracks:
                        instrument_tracks[(0,0)] = MidiTrack()
                    instrument_tracks[(0,0)].append(msg)
                
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        base_name = os.path.splitext(os.path.basename(midi_file_path))[0]
        
        for (channel, program), track in instrument_tracks.items():
            new_mid = MidiFile()
            new_mid.type = mid.type # 保持文件类型
            new_mid.ticks_per_beat = mid.ticks_per_beat # 保持每拍刻度
            new_mid.tracks.append(track)
            
            output_file_name = os.path.join(output_dir, f"{base_name}_channel{channel}_instrument{program}.mid")
            new_mid.save(output_file_name)
            print(f"导出乐器轨道 (通道: {channel}, 乐器: {program}) 到: {output_file_name}")

    except Exception as e:
        print(f"错误: 无法分离 MIDI 文件 {midi_file_path} - {e}")

def main():
    parser = argparse.ArgumentParser(description="一个用于解析和编辑 MIDI 文件的命令行工具。")
    parser.add_argument("command", choices=["analyze", "separate"], help="要执行的命令 ('analyze' 或 'separate').")
    parser.add_argument("midi_file", help="要处理的 MIDI 文件路径。")
    parser.add_argument("--output_dir", default="separated_midi", help="分离MIDI文件时的输出目录 (默认为 'separated_midi').")

    args = parser.parse_args()

    if args.command == "analyze":
        analyze_midi(args.midi_file)
    elif args.command == "separate":
        separate_midi_by_instrument(args.midi_file, args.output_dir)

if __name__ == "__main__":
    main()