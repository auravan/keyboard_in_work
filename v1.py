import re
from enum import Enum

class PitchClass(Enum):
    C = 0
    C_SHARP = 1  # 或 Db
    D = 2
    D_SHARP = 3  # 或 Eb
    E = 4
    F = 5
    F_SHARP = 6  # 或 Gb
    G = 7
    G_SHARP = 8  # 或 Ab
    A = 9
    A_SHARP = 10  # 或 Bb
    B = 11

def tokenize_chord(chord_str):
    """
    将和弦标记分解为根音和修饰部分
    例如 "Abm7" -> ('Ab', 'm7')
    """
    pattern = r'^([A-Ga-g][#b]?)(.*)$'
    match = re.match(pattern, chord_str)
    if not match:
        raise ValueError(f"无效的和弦标记: {chord_str}")
    root_note = match.group(1).upper()
    modifiers = match.group(2)
    return root_note, modifiers

def parse_pitch(note_str):
    """
    将音符字符串转换为PitchClass枚举值
    """
    note_str = note_str.upper()
    if len(note_str) == 1:
        base_note = note_str
        accidental = None
    else:
        base_note = note_str[0]
        accidental = note_str[1]
    
    # 基础音高映射
    base_map = {
        'C': PitchClass.C,
        'D': PitchClass.D,
        'E': PitchClass.E,
        'F': PitchClass.F,
        'G': PitchClass.G,
        'A': PitchClass.A,
        'B': PitchClass.B
    }
    
    if base_note not in base_map:
        raise ValueError(f"无效的音符: {note_str}")
    
    pitch = base_map[base_note]
    
    # 处理升降号
    if accidental == '#':
        pitch = PitchClass((pitch.value + 1) % 12)
    elif accidental == 'b':
        pitch = PitchClass((pitch.value - 1) % 12)
    elif accidental is not None:
        raise ValueError(f"无效的升降号: {accidental}")
    
    return pitch

if __name__ == "__main__":
    print("和弦解析器测试工具（输入'quit'退出）")
    print("--------------------------------")
    
    test_cases = [
        "C", "C#", "Db", "D", "D#", "Eb", "E", "F", 
        "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B",
        "Cm", "C#m7", "Dbmaj7", "Esus4", "F#dim", "Gaug"
    ]
    
    print("预设测试用例:")
    for i, case in enumerate(test_cases, 1):
        print(f"{i:2}. {case}")
    print()
    
    while True:
        user_input = input("请输入和弦名称（或'quit'退出）: ").strip()
        
        if user_input.lower() in ('quit', 'exit', 'q'):
            break
            
        if not user_input:
            continue
            
        try:
            root, modifiers = tokenize_chord(user_input)
            pitch = parse_pitch(root)
            
            print(f"解析结果:")
            print(f"  原始输入: {user_input}")
            print(f"  根音部分: {root}")
            print(f"  修饰部分: {modifiers}")
            print(f"  音高枚举: {pitch.name} (值: {pitch.value})")
            print("-" * 30)
            
        except ValueError as e:
            print(f"错误: {e}")
            print("-" * 30)