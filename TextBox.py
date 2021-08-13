import Messages
from SettingsList import setting_infos

# Least common multiple of all possible character widths. A line wrap must occur when the combined widths of all of the
# characters on a line reach this value.
NORMAL_LINE_WIDTH = 1801800

# Attempting to display more lines in a single text box will cause additional lines to bleed past the bottom of the box.
LINES_PER_BOX = 4

# Attempting to display more characters in a single text box will cause buffer overflows. First, visual artifacts will
# appear in lower areas of the text box. Eventually, the text box will become uncloseable.
MAX_CHARACTERS_PER_BOX = 200

if settings.default_language == 'english':
    CONTROL_CHARS = {
        'LINE_BREAK':   ['&', '\x01'],
        'BOX_BREAK':    ['^', '\x04'],
        'NAME':         ['@', '\x0F'],
        'COLOR':        ['#', '\x05\x00'],
    }
    TEXT_END   = '\x02'
else:
    CONTROL_CHARS = {
        'LINE_BREAK':   ['&', '\x000A'],
        'BOX_BREAK':    ['^', '\x81A5'],
        'NAME':         ['@', '\x874F'],
        'COLOR':        ['#', '\x000B\x0000'],
    }
    TEXT_END   = '\x8170'


def line_wrap(text, strip_existing_lines=False, strip_existing_boxes=False, replace_control_chars=True):
    # Replace stand-in characters with their actual control code.
    if replace_control_chars:
        for char in CONTROL_CHARS.values():
            text = text.replace(char[0], char[1])

    # Parse the text into a list of control codes.
    text_codes = Messages.parse_control_codes(text)

    # Existing line/box break codes to strip.
    strip_codes = []
    if strip_existing_boxes:
        strip_codes.append(0x04)
    if strip_existing_lines:
        strip_codes.append(0x01)

    # Replace stripped codes with a space.
    if strip_codes:
        index = 0
        while index < len(text_codes):
            text_code = text_codes[index]
            if text_code.code in strip_codes:
                # Check for existing whitespace near this control code.
                # If one is found, simply remove this text code.
                if index > 0 and text_codes[index-1].code == 0x20:
                    text_codes.pop(index)
                    continue
                if index + 1 < len(text_codes) and text_codes[index+1].code == 0x20:
                    text_codes.pop(index)
                    continue
                # Replace this text code with a space.
                text_codes[index] = Messages.Text_Code(0x20, 0)
            index += 1

    # Split the text codes by current box breaks.
    boxes = []
    start_index = 0
    end_index = 0
    for text_code in text_codes:
        end_index += 1
        if text_code.code == 0x04:
            boxes.append(text_codes[start_index:end_index])
            start_index = end_index
    boxes.append(text_codes[start_index:end_index])

    # Split the boxes into lines and words.
    processed_boxes = []
    for box_codes in boxes:
        line_width = NORMAL_LINE_WIDTH
        icon_code = None
        words = []

        # Group the text codes into words.
        index = 0
        while index < len(box_codes):
            text_code = box_codes[index]
            index += 1

            # Check for an icon code and lower the width of this box if one is found.
            if text_code.code == 0x13:
                line_width = 1441440
                icon_code = text_code

            # Find us a whole word.
            if text_code.code in [0x01, 0x04, 0x20]:
                if index > 1:
                    words.append(box_codes[0:index-1])
                if text_code.code in [0x01, 0x04]:
                    # If we have ran into a line or box break, add it as a "word" as well.
                    words.append([box_codes[index-1]])
                box_codes = box_codes[index:]
                index = 0
            if index > 0 and index == len(box_codes):
                words.append(box_codes)
                box_codes = []

        # Arrange our words into lines.
        lines = []
        start_index = 0
        end_index = 0
        box_count = 1
        while end_index < len(words):
            # Our current confirmed line.
            end_index += 1
            line = words[start_index:end_index]

            # If this word is a line/box break, trim our line back a word and deal with it later.
            break_char = False
            if words[end_index-1][0].code in [0x01, 0x04]:
                line = words[start_index:end_index-1]
                break_char = True

            # Check the width of the line after adding one more word.
            if end_index == len(words) or break_char or calculate_width(words[start_index:end_index+1]) > line_width:
                if line or lines:
                    lines.append(line)
                start_index = end_index

            # If we've reached the end of the box, finalize it.
            if end_index == len(words) or words[end_index-1][0].code == 0x04 or len(lines) == LINES_PER_BOX:
                # Append the same icon to any wrapped boxes.
                if icon_code and box_count > 1:
                    lines[0][0] = [icon_code] + lines[0][0]
                processed_boxes.append(lines)
                lines = []
                box_count += 1

    # Construct our final string.
    # This is a hideous level of list comprehension. Sorry.
    return '\x04'.join(['\x01'.join([' '.join([''.join([code.get_string() for code in word]) for word in line]) for line in box]) for box in processed_boxes])


def calculate_width(words):
    words_width = 0
    for word in words:
        index = 0
        while index < len(word):
            character = word[index]
            index += 1
            if character.code in Messages.CONTROL_CODES:
                if character.code == 0x06:
                    words_width += character.data
            words_width += get_character_width(chr(character.code))
    spaces_width = get_character_width(' ') * (len(words) - 1)

    return words_width + spaces_width


def get_character_width(character):
    if settings.default_language == 'english':
        try:
            return character_table[character]
        except KeyError:
            if ord(character) < 0x20:
                if character in control_code_width:
                    return sum([character_table[c] for c in control_code_width[character]])
                else:
                    return 0
            else:
                # A sane default with the most common character width
                return character_table[' ']
    else:
        try:
            return character_table_JP[character]
        except KeyError:
            if ord(character) < 0x87A0:
                if character in control_code_width_JP:
                    return sum([character_table_JP[c] for c in control_code_width[character]])
                else:
                    return character_table_JP[' ']
            else:
                # A sane default with the most common character width
                return character_table_JP[' ']
control_code_width = {
    '\x0F': '00000000',
    '\x16': '00\'00"',
    '\x17': '00\'00"',
    '\x18': '00000',
    '\x19': '100',
    '\x1D': '00',
    '\x1E': '00000',
    '\x1F': '00\'00"',
}
control_code_width_JP = {
    '\x874F': '00000000',
    '\x8791': '00\:00',
    '\x8792': '00\:00',
    '\x879B': '00000',
    '\x86A3': '100',
    '\x86A4': '00',
    '\x869F': '00000',
    '\x81A1': '00\:00',
}


# Tediously measured by filling a full line of a gossip stone's text box with one character until it is reasonably full
# (with a right margin) and counting how many characters fit. OoT does not appear to use any kerning, but, if it does,
# it will only make the characters more space-efficient, so this is an underestimate of the number of letters per line,
# at worst. This ensures that we will never bleed text out of the text box while line wrapping.
# Larger numbers in the denominator mean more of that character fits on a line; conversely, larger values in this table
# mean the character is wider and can't fit as many on one line.
character_table = {
    '\x0F': 655200,
    '\x16': 292215,
    '\x17': 292215,
    '\x18': 300300,
    '\x19': 145860,
    '\x1D': 85800,
    '\x1E': 300300,
    '\x1F': 265980,
    'a':  51480, # LINE_WIDTH /  35
    'b':  51480, # LINE_WIDTH /  35
    'c':  51480, # LINE_WIDTH /  35
    'd':  51480, # LINE_WIDTH /  35
    'e':  51480, # LINE_WIDTH /  35
    'f':  34650, # LINE_WIDTH /  52
    'g':  51480, # LINE_WIDTH /  35
    'h':  51480, # LINE_WIDTH /  35
    'i':  25740, # LINE_WIDTH /  70
    'j':  34650, # LINE_WIDTH /  52
    'k':  51480, # LINE_WIDTH /  35
    'l':  25740, # LINE_WIDTH /  70
    'm':  81900, # LINE_WIDTH /  22
    'n':  51480, # LINE_WIDTH /  35
    'o':  51480, # LINE_WIDTH /  35
    'p':  51480, # LINE_WIDTH /  35
    'q':  51480, # LINE_WIDTH /  35
    'r':  42900, # LINE_WIDTH /  42
    's':  51480, # LINE_WIDTH /  35
    't':  42900, # LINE_WIDTH /  42
    'u':  51480, # LINE_WIDTH /  35
    'v':  51480, # LINE_WIDTH /  35
    'w':  81900, # LINE_WIDTH /  22
    'x':  51480, # LINE_WIDTH /  35
    'y':  51480, # LINE_WIDTH /  35
    'z':  51480, # LINE_WIDTH /  35
    'A':  81900, # LINE_WIDTH /  22
    'B':  51480, # LINE_WIDTH /  35
    'C':  72072, # LINE_WIDTH /  25
    'D':  72072, # LINE_WIDTH /  25
    'E':  51480, # LINE_WIDTH /  35
    'F':  51480, # LINE_WIDTH /  35
    'G':  81900, # LINE_WIDTH /  22
    'H':  60060, # LINE_WIDTH /  30
    'I':  25740, # LINE_WIDTH /  70
    'J':  51480, # LINE_WIDTH /  35
    'K':  60060, # LINE_WIDTH /  30
    'L':  51480, # LINE_WIDTH /  35
    'M':  81900, # LINE_WIDTH /  22
    'N':  72072, # LINE_WIDTH /  25
    'O':  81900, # LINE_WIDTH /  22
    'P':  51480, # LINE_WIDTH /  35
    'Q':  81900, # LINE_WIDTH /  22
    'R':  60060, # LINE_WIDTH /  30
    'S':  60060, # LINE_WIDTH /  30
    'T':  51480, # LINE_WIDTH /  35
    'U':  60060, # LINE_WIDTH /  30
    'V':  72072, # LINE_WIDTH /  25
    'W': 100100, # LINE_WIDTH /  18
    'X':  72072, # LINE_WIDTH /  25
    'Y':  60060, # LINE_WIDTH /  30
    'Z':  60060, # LINE_WIDTH /  30
    ' ':  51480, # LINE_WIDTH /  35
    '1':  25740, # LINE_WIDTH /  70
    '2':  51480, # LINE_WIDTH /  35
    '3':  51480, # LINE_WIDTH /  35
    '4':  60060, # LINE_WIDTH /  30
    '5':  51480, # LINE_WIDTH /  35
    '6':  51480, # LINE_WIDTH /  35
    '7':  51480, # LINE_WIDTH /  35
    '8':  51480, # LINE_WIDTH /  35
    '9':  51480, # LINE_WIDTH /  35
    '0':  60060, # LINE_WIDTH /  30
    '!':  51480, # LINE_WIDTH /  35
    '?':  72072, # LINE_WIDTH /  25
    '\'': 17325, # LINE_WIDTH / 104
    '"':  34650, # LINE_WIDTH /  52
    '.':  25740, # LINE_WIDTH /  70
    ',':  25740, # LINE_WIDTH /  70
    '/':  51480, # LINE_WIDTH /  35
    '-':  34650, # LINE_WIDTH /  52
    '_':  51480, # LINE_WIDTH /  35
    '(':  42900, # LINE_WIDTH /  42
    ')':  42900, # LINE_WIDTH /  42
    '$':  51480  # LINE_WIDTH /  35
}
character_table_JP = {
    '\x874F': 655200,
    '\x8791': 292215,
    '\x8792': 292215,
    '\x879B': 300300,
    '\x86A3': 145860,
    '\x86A4': 85800,
    '\x869F': 300300,
    '\x81A1': 265980,
    '1':  25740, # LINE_WIDTH /  70
    '2':  51480, # LINE_WIDTH /  35
    '3':  51480, # LINE_WIDTH /  35
    '4':  60060, # LINE_WIDTH /  30
    '5':  51480, # LINE_WIDTH /  35
    '6':  51480, # LINE_WIDTH /  35
    '7':  51480, # LINE_WIDTH /  35
    '8':  51480, # LINE_WIDTH /  35
    '9':  51480, # LINE_WIDTH /  35
    '0':  60060, # LINE_WIDTH /  30
    ' ':  51480, # LINE_WIDTH /  35
    '!':  51480, # LINE_WIDTH /  35
    ':':  51480, # LINE_WIDTH /  35
    '?':  72072, # LINE_WIDTH /  25
    '\'': 17325, # LINE_WIDTH / 104
    '"':  34650, # LINE_WIDTH /  52
    '。':  25740, # LINE_WIDTH /  70
    '、':  25740, # LINE_WIDTH /  70
    '/':  51480, # LINE_WIDTH /  35
    '-':  34650, # LINE_WIDTH /  52
    '~':  34650, # LINE_WIDTH /  52
    '_':  51480, # LINE_WIDTH /  35
    '(':  42900, # LINE_WIDTH /  42
    ')':  42900, # LINE_WIDTH /  42
    '¥':  51480, # LINE_WIDTH /  35
    '.':  25740, # LINE_WIDTH /  70
    ',':  25740, # LINE_WIDTH /  70
    'ぁ' :  81900, # LINE_WIDTH /  22 
    'あ' :  81900, # LINE_WIDTH /  22 
    'ぃ' :  81900, # LINE_WIDTH /  22 
    'い' :  81900, # LINE_WIDTH /  22 
    'ぅ' :  81900, # LINE_WIDTH /  22 
    'う' :  81900, # LINE_WIDTH /  22 
    'ぇ' :  81900, # LINE_WIDTH /  22 
    'え' :  81900, # LINE_WIDTH /  22 
    'ぉ' :  81900, # LINE_WIDTH /  22 
    'お' :  81900, # LINE_WIDTH /  22 
    'か' :  81900, # LINE_WIDTH /  22 
    'が' :  81900, # LINE_WIDTH /  22 
    'き' :  81900, # LINE_WIDTH /  22 
    'ぎ' :  81900, # LINE_WIDTH /  22 
    'く' :  81900, # LINE_WIDTH /  22 
    'ぐ' :  81900, # LINE_WIDTH /  22 
    'け' :  81900, # LINE_WIDTH /  22 
    'げ' :  81900, # LINE_WIDTH /  22 
    'こ' :  81900, # LINE_WIDTH /  22 
    'ご' :  81900, # LINE_WIDTH /  22 
    'さ' :  81900, # LINE_WIDTH /  22 
    'ざ' :  81900, # LINE_WIDTH /  22 
    'し' :  81900, # LINE_WIDTH /  22 
    'じ' :  81900, # LINE_WIDTH /  22 
    'す' :  81900, # LINE_WIDTH /  22 
    'ず' :  81900, # LINE_WIDTH /  22 
    'せ' :  81900, # LINE_WIDTH /  22 
    'ぜ' :  81900, # LINE_WIDTH /  22 
    'そ' :  81900, # LINE_WIDTH /  22 
    'ぞ' :  81900, # LINE_WIDTH /  22 
    'た' :  81900, # LINE_WIDTH /  22 
    'だ' :  81900, # LINE_WIDTH /  22 
    'ち' :  81900, # LINE_WIDTH /  22 
    'ぢ' :  81900, # LINE_WIDTH /  22 
    'っ' :  81900, # LINE_WIDTH /  22 
    'つ' :  81900, # LINE_WIDTH /  22 
    'づ' :  81900, # LINE_WIDTH /  22 
    'て' :  81900, # LINE_WIDTH /  22 
    'で' :  81900, # LINE_WIDTH /  22 
    'と' :  81900, # LINE_WIDTH /  22 
    'ど' :  81900, # LINE_WIDTH /  22 
    'な' :  81900, # LINE_WIDTH /  22 
    'に' :  81900, # LINE_WIDTH /  22 
    'ぬ' :  81900, # LINE_WIDTH /  22 
    'ね' :  81900, # LINE_WIDTH /  22 
    'の' :  81900, # LINE_WIDTH /  22 
    'は' :  81900, # LINE_WIDTH /  22 
    'ば' :  81900, # LINE_WIDTH /  22 
    'ぱ' :  81900, # LINE_WIDTH /  22 
    'ひ' :  81900, # LINE_WIDTH /  22 
    'び' :  81900, # LINE_WIDTH /  22 
    'ぴ' :  81900, # LINE_WIDTH /  22 
    'ふ' :  81900, # LINE_WIDTH /  22 
    'ぶ' :  81900, # LINE_WIDTH /  22 
    'ぷ' :  81900, # LINE_WIDTH /  22 
    'へ' :  81900, # LINE_WIDTH /  22 
    'べ' :  81900, # LINE_WIDTH /  22 
    'ぺ' :  81900, # LINE_WIDTH /  22 
    'ほ' :  81900, # LINE_WIDTH /  22 
    'ぼ' :  81900, # LINE_WIDTH /  22 
    'ぽ' :  81900, # LINE_WIDTH /  22 
    'ま' :  81900, # LINE_WIDTH /  22 
    'み' :  81900, # LINE_WIDTH /  22 
    'む' :  81900, # LINE_WIDTH /  22 
    'め' :  81900, # LINE_WIDTH /  22 
    'も' :  81900, # LINE_WIDTH /  22 
    'ゃ' :  81900, # LINE_WIDTH /  22 
    'や' :  81900, # LINE_WIDTH /  22 
    'ゅ' :  81900, # LINE_WIDTH /  22 
    'ゆ' :  81900, # LINE_WIDTH /  22 
    'ょ' :  81900, # LINE_WIDTH /  22 
    'よ' :  81900, # LINE_WIDTH /  22 
    'ら' :  81900, # LINE_WIDTH /  22 
    'り' :  81900, # LINE_WIDTH /  22 
    'る' :  81900, # LINE_WIDTH /  22 
    'れ' :  81900, # LINE_WIDTH /  22 
    'ろ' :  81900, # LINE_WIDTH /  22 
    'ゎ' :  81900, # LINE_WIDTH /  22 
    'わ' :  81900, # LINE_WIDTH /  22 
    'ゐ' :  81900, # LINE_WIDTH /  22 
    'ゑ' :  81900, # LINE_WIDTH /  22 
    'を' :  81900, # LINE_WIDTH /  22 
    'ん' :  81900, # LINE_WIDTH /  22 
    'ゔ' :  81900, # LINE_WIDTH /  22 
    'ゕ' :  81900, # LINE_WIDTH /  22 
    'ゖ' :  81900, # LINE_WIDTH /  22
    'ァ' :  81900, # LINE_WIDTH /  22 
    'ア' :  81900, # LINE_WIDTH /  22 
    'ィ' :  81900, # LINE_WIDTH /  22 
    'イ' :  81900, # LINE_WIDTH /  22 
    'ゥ' :  81900, # LINE_WIDTH /  22 
    'ウ' :  81900, # LINE_WIDTH /  22 
    'ェ' :  81900, # LINE_WIDTH /  22 
    'エ' :  81900, # LINE_WIDTH /  22 
    'ォ' :  81900, # LINE_WIDTH /  22 
    'オ' :  81900, # LINE_WIDTH /  22 
    'カ' :  81900, # LINE_WIDTH /  22 
    'ガ' :  81900, # LINE_WIDTH /  22 
    'キ' :  81900, # LINE_WIDTH /  22 
    'ギ' :  81900, # LINE_WIDTH /  22 
    'ク' :  81900, # LINE_WIDTH /  22 
    'グ' :  81900, # LINE_WIDTH /  22 
    'ケ' :  81900, # LINE_WIDTH /  22 
    'ゲ' :  81900, # LINE_WIDTH /  22 
    'コ' :  81900, # LINE_WIDTH /  22 
    'ゴ' :  81900, # LINE_WIDTH /  22 
    'サ' :  81900, # LINE_WIDTH /  22 
    'ザ' :  81900, # LINE_WIDTH /  22 
    'シ' :  81900, # LINE_WIDTH /  22 
    'ジ' :  81900, # LINE_WIDTH /  22 
    'ス' :  81900, # LINE_WIDTH /  22 
    'ズ' :  81900, # LINE_WIDTH /  22 
    'セ' :  81900, # LINE_WIDTH /  22 
    'ゼ' :  81900, # LINE_WIDTH /  22 
    'ソ' :  81900, # LINE_WIDTH /  22 
    'ゾ' :  81900, # LINE_WIDTH /  22 
    'タ' :  81900, # LINE_WIDTH /  22 
    'ダ' :  81900, # LINE_WIDTH /  22 
    'チ' :  81900, # LINE_WIDTH /  22 
    'ヂ' :  81900, # LINE_WIDTH /  22 
    'ッ' :  81900, # LINE_WIDTH /  22 
    'ツ' :  81900, # LINE_WIDTH /  22 
    'ヅ' :  81900, # LINE_WIDTH /  22 
    'テ' :  81900, # LINE_WIDTH /  22 
    'デ' :  81900, # LINE_WIDTH /  22 
    'ト' :  81900, # LINE_WIDTH /  22 
    'ド' :  81900, # LINE_WIDTH /  22 
    'ナ' :  81900, # LINE_WIDTH /  22 
    'ニ' :  81900, # LINE_WIDTH /  22 
    'ヌ' :  81900, # LINE_WIDTH /  22 
    'ネ' :  81900, # LINE_WIDTH /  22 
    'ノ' :  81900, # LINE_WIDTH /  22 
    'ハ' :  81900, # LINE_WIDTH /  22 
    'バ' :  81900, # LINE_WIDTH /  22 
    'パ' :  81900, # LINE_WIDTH /  22 
    'ヒ' :  81900, # LINE_WIDTH /  22 
    'ビ' :  81900, # LINE_WIDTH /  22 
    'ピ' :  81900, # LINE_WIDTH /  22 
    'フ' :  81900, # LINE_WIDTH /  22 
    'ブ' :  81900, # LINE_WIDTH /  22 
    'プ' :  81900, # LINE_WIDTH /  22 
    'ヘ' :  81900, # LINE_WIDTH /  22 
    'ベ' :  81900, # LINE_WIDTH /  22 
    'ペ' :  81900, # LINE_WIDTH /  22 
    'ホ' :  81900, # LINE_WIDTH /  22 
    'ボ' :  81900, # LINE_WIDTH /  22 
    'ポ' :  81900, # LINE_WIDTH /  22 
    'マ' :  81900, # LINE_WIDTH /  22 
    'ミ' :  81900, # LINE_WIDTH /  22 
    'ム' :  81900, # LINE_WIDTH /  22 
    'メ' :  81900, # LINE_WIDTH /  22 
    'モ' :  81900, # LINE_WIDTH /  22 
    'ャ' :  81900, # LINE_WIDTH /  22 
    'ヤ' :  81900, # LINE_WIDTH /  22 
    'ュ' :  81900, # LINE_WIDTH /  22 
    'ユ' :  81900, # LINE_WIDTH /  22 
    'ョ' :  81900, # LINE_WIDTH /  22 
    'ヨ' :  81900, # LINE_WIDTH /  22 
    'ラ' :  81900, # LINE_WIDTH /  22 
    'リ' :  81900, # LINE_WIDTH /  22 
    'ル' :  81900, # LINE_WIDTH /  22 
    'レ' :  81900, # LINE_WIDTH /  22 
    'ロ' :  81900, # LINE_WIDTH /  22 
    'ヮ' :  81900, # LINE_WIDTH /  22 
    'ワ' :  81900, # LINE_WIDTH /  22 
    'ヰ' :  81900, # LINE_WIDTH /  22 
    'ヱ' :  81900, # LINE_WIDTH /  22 
    'ヲ' :  81900, # LINE_WIDTH /  22 
    'ン' :  81900, # LINE_WIDTH /  22 
    'ヴ' :  81900, # LINE_WIDTH /  22 
    'ヵ' :  81900, # LINE_WIDTH /  22 
    'ヶ' :  81900, # LINE_WIDTH /  22
    '亜' :  81900, # LINE_WIDTH /  22 
    '唖' :  81900, # LINE_WIDTH /  22 
    '娃' :  81900, # LINE_WIDTH /  22 
    '阿' :  81900, # LINE_WIDTH /  22 
    '哀' :  81900, # LINE_WIDTH /  22 
    '愛' :  81900, # LINE_WIDTH /  22 
    '挨' :  81900, # LINE_WIDTH /  22 
    '姶' :  81900, # LINE_WIDTH /  22 
    '逢' :  81900, # LINE_WIDTH /  22 
    '葵' :  81900, # LINE_WIDTH /  22 
    '茜' :  81900, # LINE_WIDTH /  22 
    '穐' :  81900, # LINE_WIDTH /  22 
    '悪' :  81900, # LINE_WIDTH /  22 
    '握' :  81900, # LINE_WIDTH /  22 
    '渥' :  81900, # LINE_WIDTH /  22 
    '旭' :  81900, # LINE_WIDTH /  22 
    '葦' :  81900, # LINE_WIDTH /  22 
    '芦' :  81900, # LINE_WIDTH /  22 
    '鯵' :  81900, # LINE_WIDTH /  22 
    '梓' :  81900, # LINE_WIDTH /  22 
    '圧' :  81900, # LINE_WIDTH /  22 
    '斡' :  81900, # LINE_WIDTH /  22 
    '扱' :  81900, # LINE_WIDTH /  22 
    '宛' :  81900, # LINE_WIDTH /  22 
    '姐' :  81900, # LINE_WIDTH /  22 
    '虻' :  81900, # LINE_WIDTH /  22 
    '飴' :  81900, # LINE_WIDTH /  22 
    '絢' :  81900, # LINE_WIDTH /  22 
    '綾' :  81900, # LINE_WIDTH /  22 
    '鮎' :  81900, # LINE_WIDTH /  22 
    '或' :  81900, # LINE_WIDTH /  22 
    '粟' :  81900, # LINE_WIDTH /  22 
    '袷' :  81900, # LINE_WIDTH /  22 
    '安' :  81900, # LINE_WIDTH /  22 
    '庵' :  81900, # LINE_WIDTH /  22 
    '按' :  81900, # LINE_WIDTH /  22 
    '暗' :  81900, # LINE_WIDTH /  22 
    '案' :  81900, # LINE_WIDTH /  22 
    '闇' :  81900, # LINE_WIDTH /  22 
    '鞍' :  81900, # LINE_WIDTH /  22 
    '杏' :  81900, # LINE_WIDTH /  22 
    '以' :  81900, # LINE_WIDTH /  22 
    '伊' :  81900, # LINE_WIDTH /  22 
    '位' :  81900, # LINE_WIDTH /  22 
    '依' :  81900, # LINE_WIDTH /  22 
    '偉' :  81900, # LINE_WIDTH /  22 
    '囲' :  81900, # LINE_WIDTH /  22 
    '夷' :  81900, # LINE_WIDTH /  22 
    '委' :  81900, # LINE_WIDTH /  22 
    '威' :  81900, # LINE_WIDTH /  22 
    '尉' :  81900, # LINE_WIDTH /  22 
    '惟' :  81900, # LINE_WIDTH /  22 
    '意' :  81900, # LINE_WIDTH /  22 
    '慰' :  81900, # LINE_WIDTH /  22 
    '易' :  81900, # LINE_WIDTH /  22 
    '椅' :  81900, # LINE_WIDTH /  22 
    '為' :  81900, # LINE_WIDTH /  22 
    '畏' :  81900, # LINE_WIDTH /  22 
    '異' :  81900, # LINE_WIDTH /  22 
    '移' :  81900, # LINE_WIDTH /  22 
    '維' :  81900, # LINE_WIDTH /  22 
    '緯' :  81900, # LINE_WIDTH /  22 
    '胃' :  81900, # LINE_WIDTH /  22 
    '萎' :  81900, # LINE_WIDTH /  22 
    '衣' :  81900, # LINE_WIDTH /  22 
    '謂' :  81900, # LINE_WIDTH /  22 
    '違' :  81900, # LINE_WIDTH /  22 
    '遺' :  81900, # LINE_WIDTH /  22 
    '医' :  81900, # LINE_WIDTH /  22 
    '井' :  81900, # LINE_WIDTH /  22 
    '亥' :  81900, # LINE_WIDTH /  22 
    '域' :  81900, # LINE_WIDTH /  22 
    '育' :  81900, # LINE_WIDTH /  22 
    '郁' :  81900, # LINE_WIDTH /  22 
    '磯' :  81900, # LINE_WIDTH /  22 
    '一' :  81900, # LINE_WIDTH /  22 
    '壱' :  81900, # LINE_WIDTH /  22 
    '溢' :  81900, # LINE_WIDTH /  22 
    '逸' :  81900, # LINE_WIDTH /  22 
    '稲' :  81900, # LINE_WIDTH /  22 
    '茨' :  81900, # LINE_WIDTH /  22 
    '芋' :  81900, # LINE_WIDTH /  22 
    '鰯' :  81900, # LINE_WIDTH /  22 
    '允' :  81900, # LINE_WIDTH /  22 
    '印' :  81900, # LINE_WIDTH /  22 
    '咽' :  81900, # LINE_WIDTH /  22 
    '員' :  81900, # LINE_WIDTH /  22 
    '因' :  81900, # LINE_WIDTH /  22 
    '姻' :  81900, # LINE_WIDTH /  22 
    '引' :  81900, # LINE_WIDTH /  22 
    '飲' :  81900, # LINE_WIDTH /  22 
    '淫' :  81900, # LINE_WIDTH /  22 
    '胤' :  81900, # LINE_WIDTH /  22 
    '蔭' :  81900, # LINE_WIDTH /  22 
    '院' :  81900, # LINE_WIDTH /  22 
    '陰' :  81900, # LINE_WIDTH /  22 
    '隠' :  81900, # LINE_WIDTH /  22 
    '韻' :  81900, # LINE_WIDTH /  22 
    '吋' :  81900, # LINE_WIDTH /  22 
    '右' :  81900, # LINE_WIDTH /  22 
    '宇' :  81900, # LINE_WIDTH /  22 
    '烏' :  81900, # LINE_WIDTH /  22 
    '羽' :  81900, # LINE_WIDTH /  22 
    '迂' :  81900, # LINE_WIDTH /  22 
    '雨' :  81900, # LINE_WIDTH /  22 
    '卯' :  81900, # LINE_WIDTH /  22 
    '鵜' :  81900, # LINE_WIDTH /  22 
    '窺' :  81900, # LINE_WIDTH /  22 
    '丑' :  81900, # LINE_WIDTH /  22 
    '碓' :  81900, # LINE_WIDTH /  22 
    '臼' :  81900, # LINE_WIDTH /  22 
    '渦' :  81900, # LINE_WIDTH /  22 
    '嘘' :  81900, # LINE_WIDTH /  22 
    '唄' :  81900, # LINE_WIDTH /  22 
    '欝' :  81900, # LINE_WIDTH /  22 
    '蔚' :  81900, # LINE_WIDTH /  22 
    '鰻' :  81900, # LINE_WIDTH /  22 
    '姥' :  81900, # LINE_WIDTH /  22 
    '厩' :  81900, # LINE_WIDTH /  22 
    '浦' :  81900, # LINE_WIDTH /  22 
    '瓜' :  81900, # LINE_WIDTH /  22 
    '閏' :  81900, # LINE_WIDTH /  22 
    '噂' :  81900, # LINE_WIDTH /  22 
    '云' :  81900, # LINE_WIDTH /  22 
    '運' :  81900, # LINE_WIDTH /  22 
    '雲' :  81900, # LINE_WIDTH /  22 
    '荏' :  81900, # LINE_WIDTH /  22 
    '餌' :  81900, # LINE_WIDTH /  22 
    '叡' :  81900, # LINE_WIDTH /  22 
    '営' :  81900, # LINE_WIDTH /  22 
    '嬰' :  81900, # LINE_WIDTH /  22 
    '影' :  81900, # LINE_WIDTH /  22 
    '映' :  81900, # LINE_WIDTH /  22 
    '曳' :  81900, # LINE_WIDTH /  22 
    '栄' :  81900, # LINE_WIDTH /  22 
    '永' :  81900, # LINE_WIDTH /  22 
    '泳' :  81900, # LINE_WIDTH /  22 
    '洩' :  81900, # LINE_WIDTH /  22 
    '瑛' :  81900, # LINE_WIDTH /  22 
    '盈' :  81900, # LINE_WIDTH /  22 
    '穎' :  81900, # LINE_WIDTH /  22 
    '頴' :  81900, # LINE_WIDTH /  22 
    '英' :  81900, # LINE_WIDTH /  22 
    '衛' :  81900, # LINE_WIDTH /  22 
    '詠' :  81900, # LINE_WIDTH /  22 
    '鋭' :  81900, # LINE_WIDTH /  22 
    '液' :  81900, # LINE_WIDTH /  22 
    '疫' :  81900, # LINE_WIDTH /  22 
    '益' :  81900, # LINE_WIDTH /  22 
    '駅' :  81900, # LINE_WIDTH /  22 
    '悦' :  81900, # LINE_WIDTH /  22 
    '謁' :  81900, # LINE_WIDTH /  22 
    '越' :  81900, # LINE_WIDTH /  22 
    '閲' :  81900, # LINE_WIDTH /  22 
    '榎' :  81900, # LINE_WIDTH /  22 
    '厭' :  81900, # LINE_WIDTH /  22 
    '円' :  81900, # LINE_WIDTH /  22 
    '園' :  81900, # LINE_WIDTH /  22 
    '堰' :  81900, # LINE_WIDTH /  22 
    '奄' :  81900, # LINE_WIDTH /  22 
    '宴' :  81900, # LINE_WIDTH /  22 
    '延' :  81900, # LINE_WIDTH /  22 
    '怨' :  81900, # LINE_WIDTH /  22 
    '掩' :  81900, # LINE_WIDTH /  22 
    '援' :  81900, # LINE_WIDTH /  22 
    '沿' :  81900, # LINE_WIDTH /  22 
    '演' :  81900, # LINE_WIDTH /  22 
    '炎' :  81900, # LINE_WIDTH /  22 
    '焔' :  81900, # LINE_WIDTH /  22 
    '煙' :  81900, # LINE_WIDTH /  22 
    '燕' :  81900, # LINE_WIDTH /  22 
    '猿' :  81900, # LINE_WIDTH /  22 
    '縁' :  81900, # LINE_WIDTH /  22 
    '艶' :  81900, # LINE_WIDTH /  22 
    '苑' :  81900, # LINE_WIDTH /  22 
    '薗' :  81900, # LINE_WIDTH /  22 
    '遠' :  81900, # LINE_WIDTH /  22 
    '鉛' :  81900, # LINE_WIDTH /  22 
    '鴛' :  81900, # LINE_WIDTH /  22 
    '塩' :  81900, # LINE_WIDTH /  22 
    '於' :  81900, # LINE_WIDTH /  22 
    '汚' :  81900, # LINE_WIDTH /  22 
    '甥' :  81900, # LINE_WIDTH /  22 
    '凹' :  81900, # LINE_WIDTH /  22 
    '央' :  81900, # LINE_WIDTH /  22 
    '奥' :  81900, # LINE_WIDTH /  22 
    '往' :  81900, # LINE_WIDTH /  22 
    '応' :  81900, # LINE_WIDTH /  22 
    '押' :  81900, # LINE_WIDTH /  22 
    '旺' :  81900, # LINE_WIDTH /  22 
    '横' :  81900, # LINE_WIDTH /  22 
    '欧' :  81900, # LINE_WIDTH /  22 
    '殴' :  81900, # LINE_WIDTH /  22 
    '王' :  81900, # LINE_WIDTH /  22 
    '翁' :  81900, # LINE_WIDTH /  22 
    '襖' :  81900, # LINE_WIDTH /  22 
    '鴬' :  81900, # LINE_WIDTH /  22 
    '鴎' :  81900, # LINE_WIDTH /  22 
    '黄' :  81900, # LINE_WIDTH /  22 
    '岡' :  81900, # LINE_WIDTH /  22 
    '沖' :  81900, # LINE_WIDTH /  22 
    '荻' :  81900, # LINE_WIDTH /  22 
    '億' :  81900, # LINE_WIDTH /  22 
    '屋' :  81900, # LINE_WIDTH /  22 
    '憶' :  81900, # LINE_WIDTH /  22 
    '臆' :  81900, # LINE_WIDTH /  22 
    '桶' :  81900, # LINE_WIDTH /  22 
    '牡' :  81900, # LINE_WIDTH /  22 
    '乙' :  81900, # LINE_WIDTH /  22 
    '俺' :  81900, # LINE_WIDTH /  22 
    '卸' :  81900, # LINE_WIDTH /  22 
    '恩' :  81900, # LINE_WIDTH /  22 
    '温' :  81900, # LINE_WIDTH /  22 
    '穏' :  81900, # LINE_WIDTH /  22 
    '音' :  81900, # LINE_WIDTH /  22 
    '下' :  81900, # LINE_WIDTH /  22 
    '化' :  81900, # LINE_WIDTH /  22 
    '仮' :  81900, # LINE_WIDTH /  22 
    '何' :  81900, # LINE_WIDTH /  22 
    '伽' :  81900, # LINE_WIDTH /  22 
    '価' :  81900, # LINE_WIDTH /  22 
    '佳' :  81900, # LINE_WIDTH /  22 
    '加' :  81900, # LINE_WIDTH /  22 
    '可' :  81900, # LINE_WIDTH /  22 
    '嘉' :  81900, # LINE_WIDTH /  22 
    '夏' :  81900, # LINE_WIDTH /  22 
    '嫁' :  81900, # LINE_WIDTH /  22 
    '家' :  81900, # LINE_WIDTH /  22 
    '寡' :  81900, # LINE_WIDTH /  22 
    '科' :  81900, # LINE_WIDTH /  22 
    '暇' :  81900, # LINE_WIDTH /  22 
    '果' :  81900, # LINE_WIDTH /  22 
    '架' :  81900, # LINE_WIDTH /  22 
    '歌' :  81900, # LINE_WIDTH /  22 
    '河' :  81900, # LINE_WIDTH /  22 
    '火' :  81900, # LINE_WIDTH /  22 
    '珂' :  81900, # LINE_WIDTH /  22 
    '禍' :  81900, # LINE_WIDTH /  22 
    '禾' :  81900, # LINE_WIDTH /  22 
    '稼' :  81900, # LINE_WIDTH /  22 
    '箇' :  81900, # LINE_WIDTH /  22 
    '花' :  81900, # LINE_WIDTH /  22 
    '苛' :  81900, # LINE_WIDTH /  22 
    '茄' :  81900, # LINE_WIDTH /  22 
    '荷' :  81900, # LINE_WIDTH /  22 
    '華' :  81900, # LINE_WIDTH /  22 
    '菓' :  81900, # LINE_WIDTH /  22 
    '蝦' :  81900, # LINE_WIDTH /  22 
    '課' :  81900, # LINE_WIDTH /  22 
    '嘩' :  81900, # LINE_WIDTH /  22 
    '貨' :  81900, # LINE_WIDTH /  22 
    '迦' :  81900, # LINE_WIDTH /  22 
    '過' :  81900, # LINE_WIDTH /  22 
    '霞' :  81900, # LINE_WIDTH /  22 
    '蚊' :  81900, # LINE_WIDTH /  22 
    '俄' :  81900, # LINE_WIDTH /  22 
    '峨' :  81900, # LINE_WIDTH /  22 
    '我' :  81900, # LINE_WIDTH /  22 
    '牙' :  81900, # LINE_WIDTH /  22 
    '画' :  81900, # LINE_WIDTH /  22 
    '臥' :  81900, # LINE_WIDTH /  22 
    '芽' :  81900, # LINE_WIDTH /  22 
    '蛾' :  81900, # LINE_WIDTH /  22 
    '賀' :  81900, # LINE_WIDTH /  22 
    '雅' :  81900, # LINE_WIDTH /  22 
    '餓' :  81900, # LINE_WIDTH /  22 
    '駕' :  81900, # LINE_WIDTH /  22 
    '介' :  81900, # LINE_WIDTH /  22 
    '会' :  81900, # LINE_WIDTH /  22 
    '解' :  81900, # LINE_WIDTH /  22 
    '回' :  81900, # LINE_WIDTH /  22 
    '塊' :  81900, # LINE_WIDTH /  22 
    '壊' :  81900, # LINE_WIDTH /  22 
    '廻' :  81900, # LINE_WIDTH /  22 
    '快' :  81900, # LINE_WIDTH /  22 
    '怪' :  81900, # LINE_WIDTH /  22 
    '悔' :  81900, # LINE_WIDTH /  22 
    '恢' :  81900, # LINE_WIDTH /  22 
    '懐' :  81900, # LINE_WIDTH /  22 
    '戒' :  81900, # LINE_WIDTH /  22 
    '拐' :  81900, # LINE_WIDTH /  22 
    '改' :  81900, # LINE_WIDTH /  22 
    '魁' :  81900, # LINE_WIDTH /  22 
    '晦' :  81900, # LINE_WIDTH /  22 
    '械' :  81900, # LINE_WIDTH /  22 
    '海' :  81900, # LINE_WIDTH /  22 
    '灰' :  81900, # LINE_WIDTH /  22 
    '界' :  81900, # LINE_WIDTH /  22 
    '皆' :  81900, # LINE_WIDTH /  22 
    '絵' :  81900, # LINE_WIDTH /  22 
    '芥' :  81900, # LINE_WIDTH /  22 
    '蟹' :  81900, # LINE_WIDTH /  22 
    '開' :  81900, # LINE_WIDTH /  22 
    '階' :  81900, # LINE_WIDTH /  22 
    '貝' :  81900, # LINE_WIDTH /  22 
    '凱' :  81900, # LINE_WIDTH /  22 
    '劾' :  81900, # LINE_WIDTH /  22 
    '外' :  81900, # LINE_WIDTH /  22 
    '咳' :  81900, # LINE_WIDTH /  22 
    '害' :  81900, # LINE_WIDTH /  22 
    '崖' :  81900, # LINE_WIDTH /  22 
    '慨' :  81900, # LINE_WIDTH /  22 
    '概' :  81900, # LINE_WIDTH /  22 
    '涯' :  81900, # LINE_WIDTH /  22 
    '碍' :  81900, # LINE_WIDTH /  22 
    '蓋' :  81900, # LINE_WIDTH /  22 
    '街' :  81900, # LINE_WIDTH /  22 
    '該' :  81900, # LINE_WIDTH /  22 
    '鎧' :  81900, # LINE_WIDTH /  22 
    '骸' :  81900, # LINE_WIDTH /  22 
    '浬' :  81900, # LINE_WIDTH /  22 
    '馨' :  81900, # LINE_WIDTH /  22 
    '蛙' :  81900, # LINE_WIDTH /  22 
    '垣' :  81900, # LINE_WIDTH /  22 
    '柿' :  81900, # LINE_WIDTH /  22 
    '蛎' :  81900, # LINE_WIDTH /  22 
    '鈎' :  81900, # LINE_WIDTH /  22 
    '劃' :  81900, # LINE_WIDTH /  22 
    '嚇' :  81900, # LINE_WIDTH /  22 
    '各' :  81900, # LINE_WIDTH /  22 
    '廓' :  81900, # LINE_WIDTH /  22 
    '拡' :  81900, # LINE_WIDTH /  22 
    '撹' :  81900, # LINE_WIDTH /  22 
    '格' :  81900, # LINE_WIDTH /  22 
    '核' :  81900, # LINE_WIDTH /  22 
    '殻' :  81900, # LINE_WIDTH /  22 
    '獲' :  81900, # LINE_WIDTH /  22 
    '確' :  81900, # LINE_WIDTH /  22 
    '穫' :  81900, # LINE_WIDTH /  22 
    '覚' :  81900, # LINE_WIDTH /  22 
    '角' :  81900, # LINE_WIDTH /  22 
    '赫' :  81900, # LINE_WIDTH /  22 
    '較' :  81900, # LINE_WIDTH /  22 
    '郭' :  81900, # LINE_WIDTH /  22 
    '閣' :  81900, # LINE_WIDTH /  22 
    '隔' :  81900, # LINE_WIDTH /  22 
    '革' :  81900, # LINE_WIDTH /  22 
    '学' :  81900, # LINE_WIDTH /  22 
    '岳' :  81900, # LINE_WIDTH /  22 
    '楽' :  81900, # LINE_WIDTH /  22 
    '額' :  81900, # LINE_WIDTH /  22 
    '顎' :  81900, # LINE_WIDTH /  22 
    '掛' :  81900, # LINE_WIDTH /  22 
    '笠' :  81900, # LINE_WIDTH /  22 
    '樫' :  81900, # LINE_WIDTH /  22 
    '橿' :  81900, # LINE_WIDTH /  22 
    '梶' :  81900, # LINE_WIDTH /  22 
    '鰍' :  81900, # LINE_WIDTH /  22 
    '潟' :  81900, # LINE_WIDTH /  22 
    '割' :  81900, # LINE_WIDTH /  22 
    '喝' :  81900, # LINE_WIDTH /  22 
    '恰' :  81900, # LINE_WIDTH /  22 
    '括' :  81900, # LINE_WIDTH /  22 
    '活' :  81900, # LINE_WIDTH /  22 
    '渇' :  81900, # LINE_WIDTH /  22 
    '滑' :  81900, # LINE_WIDTH /  22 
    '葛' :  81900, # LINE_WIDTH /  22 
    '褐' :  81900, # LINE_WIDTH /  22 
    '轄' :  81900, # LINE_WIDTH /  22 
    '且' :  81900, # LINE_WIDTH /  22 
    '鰹' :  81900, # LINE_WIDTH /  22 
    '叶' :  81900, # LINE_WIDTH /  22 
    '椛' :  81900, # LINE_WIDTH /  22 
    '樺' :  81900, # LINE_WIDTH /  22 
    '鞄' :  81900, # LINE_WIDTH /  22 
    '株' :  81900, # LINE_WIDTH /  22 
    '兜' :  81900, # LINE_WIDTH /  22 
    '竃' :  81900, # LINE_WIDTH /  22 
    '蒲' :  81900, # LINE_WIDTH /  22 
    '釜' :  81900, # LINE_WIDTH /  22 
    '鎌' :  81900, # LINE_WIDTH /  22 
    '噛' :  81900, # LINE_WIDTH /  22 
    '鴨' :  81900, # LINE_WIDTH /  22 
    '栢' :  81900, # LINE_WIDTH /  22 
    '茅' :  81900, # LINE_WIDTH /  22 
    '萱' :  81900, # LINE_WIDTH /  22 
    '粥' :  81900, # LINE_WIDTH /  22 
    '刈' :  81900, # LINE_WIDTH /  22 
    '苅' :  81900, # LINE_WIDTH /  22 
    '瓦' :  81900, # LINE_WIDTH /  22 
    '乾' :  81900, # LINE_WIDTH /  22 
    '侃' :  81900, # LINE_WIDTH /  22 
    '冠' :  81900, # LINE_WIDTH /  22 
    '寒' :  81900, # LINE_WIDTH /  22 
    '刊' :  81900, # LINE_WIDTH /  22 
    '勘' :  81900, # LINE_WIDTH /  22 
    '勧' :  81900, # LINE_WIDTH /  22 
    '巻' :  81900, # LINE_WIDTH /  22 
    '喚' :  81900, # LINE_WIDTH /  22 
    '堪' :  81900, # LINE_WIDTH /  22 
    '姦' :  81900, # LINE_WIDTH /  22 
    '完' :  81900, # LINE_WIDTH /  22 
    '官' :  81900, # LINE_WIDTH /  22 
    '寛' :  81900, # LINE_WIDTH /  22 
    '干' :  81900, # LINE_WIDTH /  22 
    '幹' :  81900, # LINE_WIDTH /  22 
    '患' :  81900, # LINE_WIDTH /  22 
    '感' :  81900, # LINE_WIDTH /  22 
    '慣' :  81900, # LINE_WIDTH /  22 
    '憾' :  81900, # LINE_WIDTH /  22 
    '換' :  81900, # LINE_WIDTH /  22 
    '敢' :  81900, # LINE_WIDTH /  22 
    '柑' :  81900, # LINE_WIDTH /  22 
    '桓' :  81900, # LINE_WIDTH /  22 
    '棺' :  81900, # LINE_WIDTH /  22 
    '款' :  81900, # LINE_WIDTH /  22 
    '歓' :  81900, # LINE_WIDTH /  22 
    '汗' :  81900, # LINE_WIDTH /  22 
    '漢' :  81900, # LINE_WIDTH /  22 
    '澗' :  81900, # LINE_WIDTH /  22 
    '潅' :  81900, # LINE_WIDTH /  22 
    '環' :  81900, # LINE_WIDTH /  22 
    '甘' :  81900, # LINE_WIDTH /  22 
    '監' :  81900, # LINE_WIDTH /  22 
    '看' :  81900, # LINE_WIDTH /  22 
    '竿' :  81900, # LINE_WIDTH /  22 
    '管' :  81900, # LINE_WIDTH /  22 
    '簡' :  81900, # LINE_WIDTH /  22 
    '緩' :  81900, # LINE_WIDTH /  22 
    '缶' :  81900, # LINE_WIDTH /  22 
    '翰' :  81900, # LINE_WIDTH /  22 
    '肝' :  81900, # LINE_WIDTH /  22 
    '艦' :  81900, # LINE_WIDTH /  22 
    '莞' :  81900, # LINE_WIDTH /  22 
    '観' :  81900, # LINE_WIDTH /  22 
    '諌' :  81900, # LINE_WIDTH /  22 
    '貫' :  81900, # LINE_WIDTH /  22 
    '還' :  81900, # LINE_WIDTH /  22 
    '鑑' :  81900, # LINE_WIDTH /  22 
    '間' :  81900, # LINE_WIDTH /  22 
    '閑' :  81900, # LINE_WIDTH /  22 
    '関' :  81900, # LINE_WIDTH /  22 
    '陥' :  81900, # LINE_WIDTH /  22 
    '韓' :  81900, # LINE_WIDTH /  22 
    '館' :  81900, # LINE_WIDTH /  22 
    '舘' :  81900, # LINE_WIDTH /  22 
    '丸' :  81900, # LINE_WIDTH /  22 
    '含' :  81900, # LINE_WIDTH /  22 
    '岸' :  81900, # LINE_WIDTH /  22 
    '巌' :  81900, # LINE_WIDTH /  22 
    '玩' :  81900, # LINE_WIDTH /  22 
    '癌' :  81900, # LINE_WIDTH /  22 
    '眼' :  81900, # LINE_WIDTH /  22 
    '岩' :  81900, # LINE_WIDTH /  22 
    '翫' :  81900, # LINE_WIDTH /  22 
    '贋' :  81900, # LINE_WIDTH /  22 
    '雁' :  81900, # LINE_WIDTH /  22 
    '頑' :  81900, # LINE_WIDTH /  22 
    '顔' :  81900, # LINE_WIDTH /  22 
    '願' :  81900, # LINE_WIDTH /  22 
    '企' :  81900, # LINE_WIDTH /  22 
    '伎' :  81900, # LINE_WIDTH /  22 
    '危' :  81900, # LINE_WIDTH /  22 
    '喜' :  81900, # LINE_WIDTH /  22 
    '器' :  81900, # LINE_WIDTH /  22 
    '基' :  81900, # LINE_WIDTH /  22 
    '奇' :  81900, # LINE_WIDTH /  22 
    '嬉' :  81900, # LINE_WIDTH /  22 
    '寄' :  81900, # LINE_WIDTH /  22 
    '岐' :  81900, # LINE_WIDTH /  22 
    '希' :  81900, # LINE_WIDTH /  22 
    '幾' :  81900, # LINE_WIDTH /  22 
    '忌' :  81900, # LINE_WIDTH /  22 
    '揮' :  81900, # LINE_WIDTH /  22 
    '机' :  81900, # LINE_WIDTH /  22 
    '旗' :  81900, # LINE_WIDTH /  22 
    '既' :  81900, # LINE_WIDTH /  22 
    '期' :  81900, # LINE_WIDTH /  22 
    '棋' :  81900, # LINE_WIDTH /  22 
    '棄' :  81900, # LINE_WIDTH /  22 
    '機' :  81900, # LINE_WIDTH /  22 
    '帰' :  81900, # LINE_WIDTH /  22 
    '毅' :  81900, # LINE_WIDTH /  22 
    '気' :  81900, # LINE_WIDTH /  22 
    '汽' :  81900, # LINE_WIDTH /  22 
    '畿' :  81900, # LINE_WIDTH /  22 
    '祈' :  81900, # LINE_WIDTH /  22 
    '季' :  81900, # LINE_WIDTH /  22 
    '稀' :  81900, # LINE_WIDTH /  22 
    '紀' :  81900, # LINE_WIDTH /  22 
    '徽' :  81900, # LINE_WIDTH /  22 
    '規' :  81900, # LINE_WIDTH /  22 
    '記' :  81900, # LINE_WIDTH /  22 
    '貴' :  81900, # LINE_WIDTH /  22 
    '起' :  81900, # LINE_WIDTH /  22 
    '軌' :  81900, # LINE_WIDTH /  22 
    '輝' :  81900, # LINE_WIDTH /  22 
    '飢' :  81900, # LINE_WIDTH /  22 
    '騎' :  81900, # LINE_WIDTH /  22 
    '鬼' :  81900, # LINE_WIDTH /  22 
    '亀' :  81900, # LINE_WIDTH /  22 
    '偽' :  81900, # LINE_WIDTH /  22 
    '儀' :  81900, # LINE_WIDTH /  22 
    '妓' :  81900, # LINE_WIDTH /  22 
    '宜' :  81900, # LINE_WIDTH /  22 
    '戯' :  81900, # LINE_WIDTH /  22 
    '技' :  81900, # LINE_WIDTH /  22 
    '擬' :  81900, # LINE_WIDTH /  22 
    '欺' :  81900, # LINE_WIDTH /  22 
    '犠' :  81900, # LINE_WIDTH /  22 
    '疑' :  81900, # LINE_WIDTH /  22 
    '祇' :  81900, # LINE_WIDTH /  22 
    '義' :  81900, # LINE_WIDTH /  22 
    '蟻' :  81900, # LINE_WIDTH /  22 
    '誼' :  81900, # LINE_WIDTH /  22 
    '議' :  81900, # LINE_WIDTH /  22 
    '掬' :  81900, # LINE_WIDTH /  22 
    '菊' :  81900, # LINE_WIDTH /  22 
    '鞠' :  81900, # LINE_WIDTH /  22 
    '吉' :  81900, # LINE_WIDTH /  22 
    '吃' :  81900, # LINE_WIDTH /  22 
    '喫' :  81900, # LINE_WIDTH /  22 
    '桔' :  81900, # LINE_WIDTH /  22 
    '橘' :  81900, # LINE_WIDTH /  22 
    '詰' :  81900, # LINE_WIDTH /  22 
    '砧' :  81900, # LINE_WIDTH /  22 
    '杵' :  81900, # LINE_WIDTH /  22 
    '黍' :  81900, # LINE_WIDTH /  22 
    '却' :  81900, # LINE_WIDTH /  22 
    '客' :  81900, # LINE_WIDTH /  22 
    '脚' :  81900, # LINE_WIDTH /  22 
    '虐' :  81900, # LINE_WIDTH /  22 
    '逆' :  81900, # LINE_WIDTH /  22 
    '丘' :  81900, # LINE_WIDTH /  22 
    '久' :  81900, # LINE_WIDTH /  22 
    '仇' :  81900, # LINE_WIDTH /  22 
    '休' :  81900, # LINE_WIDTH /  22 
    '及' :  81900, # LINE_WIDTH /  22 
    '吸' :  81900, # LINE_WIDTH /  22 
    '宮' :  81900, # LINE_WIDTH /  22 
    '弓' :  81900, # LINE_WIDTH /  22 
    '急' :  81900, # LINE_WIDTH /  22 
    '救' :  81900, # LINE_WIDTH /  22 
    '朽' :  81900, # LINE_WIDTH /  22 
    '求' :  81900, # LINE_WIDTH /  22 
    '汲' :  81900, # LINE_WIDTH /  22 
    '泣' :  81900, # LINE_WIDTH /  22 
    '灸' :  81900, # LINE_WIDTH /  22 
    '球' :  81900, # LINE_WIDTH /  22 
    '究' :  81900, # LINE_WIDTH /  22 
    '窮' :  81900, # LINE_WIDTH /  22 
    '笈' :  81900, # LINE_WIDTH /  22 
    '級' :  81900, # LINE_WIDTH /  22 
    '糾' :  81900, # LINE_WIDTH /  22 
    '給' :  81900, # LINE_WIDTH /  22 
    '旧' :  81900, # LINE_WIDTH /  22 
    '牛' :  81900, # LINE_WIDTH /  22 
    '去' :  81900, # LINE_WIDTH /  22 
    '居' :  81900, # LINE_WIDTH /  22 
    '巨' :  81900, # LINE_WIDTH /  22 
    '拒' :  81900, # LINE_WIDTH /  22 
    '拠' :  81900, # LINE_WIDTH /  22 
    '挙' :  81900, # LINE_WIDTH /  22 
    '渠' :  81900, # LINE_WIDTH /  22 
    '虚' :  81900, # LINE_WIDTH /  22 
    '許' :  81900, # LINE_WIDTH /  22 
    '距' :  81900, # LINE_WIDTH /  22 
    '鋸' :  81900, # LINE_WIDTH /  22 
    '漁' :  81900, # LINE_WIDTH /  22 
    '禦' :  81900, # LINE_WIDTH /  22 
    '魚' :  81900, # LINE_WIDTH /  22 
    '亨' :  81900, # LINE_WIDTH /  22 
    '享' :  81900, # LINE_WIDTH /  22 
    '京' :  81900, # LINE_WIDTH /  22 
    '供' :  81900, # LINE_WIDTH /  22 
    '侠' :  81900, # LINE_WIDTH /  22 
    '僑' :  81900, # LINE_WIDTH /  22 
    '兇' :  81900, # LINE_WIDTH /  22 
    '競' :  81900, # LINE_WIDTH /  22 
    '共' :  81900, # LINE_WIDTH /  22 
    '凶' :  81900, # LINE_WIDTH /  22 
    '協' :  81900, # LINE_WIDTH /  22 
    '匡' :  81900, # LINE_WIDTH /  22 
    '卿' :  81900, # LINE_WIDTH /  22 
    '叫' :  81900, # LINE_WIDTH /  22 
    '喬' :  81900, # LINE_WIDTH /  22 
    '境' :  81900, # LINE_WIDTH /  22 
    '峡' :  81900, # LINE_WIDTH /  22 
    '強' :  81900, # LINE_WIDTH /  22 
    '彊' :  81900, # LINE_WIDTH /  22 
    '怯' :  81900, # LINE_WIDTH /  22 
    '恐' :  81900, # LINE_WIDTH /  22 
    '恭' :  81900, # LINE_WIDTH /  22 
    '挟' :  81900, # LINE_WIDTH /  22 
    '教' :  81900, # LINE_WIDTH /  22 
    '橋' :  81900, # LINE_WIDTH /  22 
    '況' :  81900, # LINE_WIDTH /  22 
    '狂' :  81900, # LINE_WIDTH /  22 
    '狭' :  81900, # LINE_WIDTH /  22 
    '矯' :  81900, # LINE_WIDTH /  22 
    '胸' :  81900, # LINE_WIDTH /  22 
    '脅' :  81900, # LINE_WIDTH /  22 
    '興' :  81900, # LINE_WIDTH /  22 
    '蕎' :  81900, # LINE_WIDTH /  22 
    '郷' :  81900, # LINE_WIDTH /  22 
    '鏡' :  81900, # LINE_WIDTH /  22 
    '響' :  81900, # LINE_WIDTH /  22 
    '饗' :  81900, # LINE_WIDTH /  22 
    '驚' :  81900, # LINE_WIDTH /  22 
    '仰' :  81900, # LINE_WIDTH /  22 
    '凝' :  81900, # LINE_WIDTH /  22 
    '尭' :  81900, # LINE_WIDTH /  22 
    '暁' :  81900, # LINE_WIDTH /  22 
    '業' :  81900, # LINE_WIDTH /  22 
    '局' :  81900, # LINE_WIDTH /  22 
    '曲' :  81900, # LINE_WIDTH /  22 
    '極' :  81900, # LINE_WIDTH /  22 
    '玉' :  81900, # LINE_WIDTH /  22 
    '桐' :  81900, # LINE_WIDTH /  22 
    '粁' :  81900, # LINE_WIDTH /  22 
    '僅' :  81900, # LINE_WIDTH /  22 
    '勤' :  81900, # LINE_WIDTH /  22 
    '均' :  81900, # LINE_WIDTH /  22 
    '巾' :  81900, # LINE_WIDTH /  22 
    '錦' :  81900, # LINE_WIDTH /  22 
    '斤' :  81900, # LINE_WIDTH /  22 
    '欣' :  81900, # LINE_WIDTH /  22 
    '欽' :  81900, # LINE_WIDTH /  22 
    '琴' :  81900, # LINE_WIDTH /  22 
    '禁' :  81900, # LINE_WIDTH /  22 
    '禽' :  81900, # LINE_WIDTH /  22 
    '筋' :  81900, # LINE_WIDTH /  22 
    '緊' :  81900, # LINE_WIDTH /  22 
    '芹' :  81900, # LINE_WIDTH /  22 
    '菌' :  81900, # LINE_WIDTH /  22 
    '衿' :  81900, # LINE_WIDTH /  22 
    '襟' :  81900, # LINE_WIDTH /  22 
    '謹' :  81900, # LINE_WIDTH /  22 
    '近' :  81900, # LINE_WIDTH /  22 
    '金' :  81900, # LINE_WIDTH /  22 
    '吟' :  81900, # LINE_WIDTH /  22 
    '銀' :  81900, # LINE_WIDTH /  22 
    '九' :  81900, # LINE_WIDTH /  22 
    '倶' :  81900, # LINE_WIDTH /  22 
    '句' :  81900, # LINE_WIDTH /  22 
    '区' :  81900, # LINE_WIDTH /  22 
    '狗' :  81900, # LINE_WIDTH /  22 
    '玖' :  81900, # LINE_WIDTH /  22 
    '矩' :  81900, # LINE_WIDTH /  22 
    '苦' :  81900, # LINE_WIDTH /  22 
    '躯' :  81900, # LINE_WIDTH /  22 
    '駆' :  81900, # LINE_WIDTH /  22 
    '駈' :  81900, # LINE_WIDTH /  22 
    '駒' :  81900, # LINE_WIDTH /  22 
    '具' :  81900, # LINE_WIDTH /  22 
    '愚' :  81900, # LINE_WIDTH /  22 
    '虞' :  81900, # LINE_WIDTH /  22 
    '喰' :  81900, # LINE_WIDTH /  22 
    '空' :  81900, # LINE_WIDTH /  22 
    '偶' :  81900, # LINE_WIDTH /  22 
    '寓' :  81900, # LINE_WIDTH /  22 
    '遇' :  81900, # LINE_WIDTH /  22 
    '隅' :  81900, # LINE_WIDTH /  22 
    '串' :  81900, # LINE_WIDTH /  22 
    '櫛' :  81900, # LINE_WIDTH /  22 
    '釧' :  81900, # LINE_WIDTH /  22 
    '屑' :  81900, # LINE_WIDTH /  22 
    '屈' :  81900, # LINE_WIDTH /  22 
    '掘' :  81900, # LINE_WIDTH /  22 
    '窟' :  81900, # LINE_WIDTH /  22 
    '沓' :  81900, # LINE_WIDTH /  22 
    '靴' :  81900, # LINE_WIDTH /  22 
    '轡' :  81900, # LINE_WIDTH /  22 
    '窪' :  81900, # LINE_WIDTH /  22 
    '熊' :  81900, # LINE_WIDTH /  22 
    '隈' :  81900, # LINE_WIDTH /  22 
    '粂' :  81900, # LINE_WIDTH /  22 
    '栗' :  81900, # LINE_WIDTH /  22 
    '繰' :  81900, # LINE_WIDTH /  22 
    '桑' :  81900, # LINE_WIDTH /  22 
    '鍬' :  81900, # LINE_WIDTH /  22 
    '勲' :  81900, # LINE_WIDTH /  22 
    '君' :  81900, # LINE_WIDTH /  22 
    '薫' :  81900, # LINE_WIDTH /  22 
    '訓' :  81900, # LINE_WIDTH /  22 
    '群' :  81900, # LINE_WIDTH /  22 
    '軍' :  81900, # LINE_WIDTH /  22 
    '郡' :  81900, # LINE_WIDTH /  22 
    '卦' :  81900, # LINE_WIDTH /  22 
    '袈' :  81900, # LINE_WIDTH /  22 
    '祁' :  81900, # LINE_WIDTH /  22 
    '係' :  81900, # LINE_WIDTH /  22 
    '傾' :  81900, # LINE_WIDTH /  22 
    '刑' :  81900, # LINE_WIDTH /  22 
    '兄' :  81900, # LINE_WIDTH /  22 
    '啓' :  81900, # LINE_WIDTH /  22 
    '圭' :  81900, # LINE_WIDTH /  22 
    '珪' :  81900, # LINE_WIDTH /  22 
    '型' :  81900, # LINE_WIDTH /  22 
    '契' :  81900, # LINE_WIDTH /  22 
    '形' :  81900, # LINE_WIDTH /  22 
    '径' :  81900, # LINE_WIDTH /  22 
    '恵' :  81900, # LINE_WIDTH /  22 
    '慶' :  81900, # LINE_WIDTH /  22 
    '慧' :  81900, # LINE_WIDTH /  22 
    '憩' :  81900, # LINE_WIDTH /  22 
    '掲' :  81900, # LINE_WIDTH /  22 
    '携' :  81900, # LINE_WIDTH /  22 
    '敬' :  81900, # LINE_WIDTH /  22 
    '景' :  81900, # LINE_WIDTH /  22 
    '桂' :  81900, # LINE_WIDTH /  22 
    '渓' :  81900, # LINE_WIDTH /  22 
    '畦' :  81900, # LINE_WIDTH /  22 
    '稽' :  81900, # LINE_WIDTH /  22 
    '系' :  81900, # LINE_WIDTH /  22 
    '経' :  81900, # LINE_WIDTH /  22 
    '継' :  81900, # LINE_WIDTH /  22 
    '繋' :  81900, # LINE_WIDTH /  22 
    '罫' :  81900, # LINE_WIDTH /  22 
    '茎' :  81900, # LINE_WIDTH /  22 
    '荊' :  81900, # LINE_WIDTH /  22 
    '蛍' :  81900, # LINE_WIDTH /  22 
    '計' :  81900, # LINE_WIDTH /  22 
    '詣' :  81900, # LINE_WIDTH /  22 
    '警' :  81900, # LINE_WIDTH /  22 
    '軽' :  81900, # LINE_WIDTH /  22 
    '頚' :  81900, # LINE_WIDTH /  22 
    '鶏' :  81900, # LINE_WIDTH /  22 
    '芸' :  81900, # LINE_WIDTH /  22 
    '迎' :  81900, # LINE_WIDTH /  22 
    '鯨' :  81900, # LINE_WIDTH /  22 
    '劇' :  81900, # LINE_WIDTH /  22 
    '戟' :  81900, # LINE_WIDTH /  22 
    '撃' :  81900, # LINE_WIDTH /  22 
    '激' :  81900, # LINE_WIDTH /  22 
    '隙' :  81900, # LINE_WIDTH /  22 
    '桁' :  81900, # LINE_WIDTH /  22 
    '傑' :  81900, # LINE_WIDTH /  22 
    '欠' :  81900, # LINE_WIDTH /  22 
    '決' :  81900, # LINE_WIDTH /  22 
    '潔' :  81900, # LINE_WIDTH /  22 
    '穴' :  81900, # LINE_WIDTH /  22 
    '結' :  81900, # LINE_WIDTH /  22 
    '血' :  81900, # LINE_WIDTH /  22 
    '訣' :  81900, # LINE_WIDTH /  22 
    '月' :  81900, # LINE_WIDTH /  22 
    '件' :  81900, # LINE_WIDTH /  22 
    '倹' :  81900, # LINE_WIDTH /  22 
    '倦' :  81900, # LINE_WIDTH /  22 
    '健' :  81900, # LINE_WIDTH /  22 
    '兼' :  81900, # LINE_WIDTH /  22 
    '券' :  81900, # LINE_WIDTH /  22 
    '剣' :  81900, # LINE_WIDTH /  22 
    '喧' :  81900, # LINE_WIDTH /  22 
    '圏' :  81900, # LINE_WIDTH /  22 
    '堅' :  81900, # LINE_WIDTH /  22 
    '嫌' :  81900, # LINE_WIDTH /  22 
    '建' :  81900, # LINE_WIDTH /  22 
    '憲' :  81900, # LINE_WIDTH /  22 
    '懸' :  81900, # LINE_WIDTH /  22 
    '拳' :  81900, # LINE_WIDTH /  22 
    '捲' :  81900, # LINE_WIDTH /  22 
    '検' :  81900, # LINE_WIDTH /  22 
    '権' :  81900, # LINE_WIDTH /  22 
    '牽' :  81900, # LINE_WIDTH /  22 
    '犬' :  81900, # LINE_WIDTH /  22 
    '献' :  81900, # LINE_WIDTH /  22 
    '研' :  81900, # LINE_WIDTH /  22 
    '硯' :  81900, # LINE_WIDTH /  22 
    '絹' :  81900, # LINE_WIDTH /  22 
    '県' :  81900, # LINE_WIDTH /  22 
    '肩' :  81900, # LINE_WIDTH /  22 
    '見' :  81900, # LINE_WIDTH /  22 
    '謙' :  81900, # LINE_WIDTH /  22 
    '賢' :  81900, # LINE_WIDTH /  22 
    '軒' :  81900, # LINE_WIDTH /  22 
    '遣' :  81900, # LINE_WIDTH /  22 
    '鍵' :  81900, # LINE_WIDTH /  22 
    '険' :  81900, # LINE_WIDTH /  22 
    '顕' :  81900, # LINE_WIDTH /  22 
    '験' :  81900, # LINE_WIDTH /  22 
    '鹸' :  81900, # LINE_WIDTH /  22 
    '元' :  81900, # LINE_WIDTH /  22 
    '原' :  81900, # LINE_WIDTH /  22 
    '厳' :  81900, # LINE_WIDTH /  22 
    '幻' :  81900, # LINE_WIDTH /  22 
    '弦' :  81900, # LINE_WIDTH /  22 
    '減' :  81900, # LINE_WIDTH /  22 
    '源' :  81900, # LINE_WIDTH /  22 
    '玄' :  81900, # LINE_WIDTH /  22 
    '現' :  81900, # LINE_WIDTH /  22 
    '絃' :  81900, # LINE_WIDTH /  22 
    '舷' :  81900, # LINE_WIDTH /  22 
    '言' :  81900, # LINE_WIDTH /  22 
    '諺' :  81900, # LINE_WIDTH /  22 
    '限' :  81900, # LINE_WIDTH /  22 
    '乎' :  81900, # LINE_WIDTH /  22 
    '個' :  81900, # LINE_WIDTH /  22 
    '古' :  81900, # LINE_WIDTH /  22 
    '呼' :  81900, # LINE_WIDTH /  22 
    '固' :  81900, # LINE_WIDTH /  22 
    '姑' :  81900, # LINE_WIDTH /  22 
    '孤' :  81900, # LINE_WIDTH /  22 
    '己' :  81900, # LINE_WIDTH /  22 
    '庫' :  81900, # LINE_WIDTH /  22 
    '弧' :  81900, # LINE_WIDTH /  22 
    '戸' :  81900, # LINE_WIDTH /  22 
    '故' :  81900, # LINE_WIDTH /  22 
    '枯' :  81900, # LINE_WIDTH /  22 
    '湖' :  81900, # LINE_WIDTH /  22 
    '狐' :  81900, # LINE_WIDTH /  22 
    '糊' :  81900, # LINE_WIDTH /  22 
    '袴' :  81900, # LINE_WIDTH /  22 
    '股' :  81900, # LINE_WIDTH /  22 
    '胡' :  81900, # LINE_WIDTH /  22 
    '菰' :  81900, # LINE_WIDTH /  22 
    '虎' :  81900, # LINE_WIDTH /  22 
    '誇' :  81900, # LINE_WIDTH /  22 
    '跨' :  81900, # LINE_WIDTH /  22 
    '鈷' :  81900, # LINE_WIDTH /  22 
    '雇' :  81900, # LINE_WIDTH /  22 
    '顧' :  81900, # LINE_WIDTH /  22 
    '鼓' :  81900, # LINE_WIDTH /  22 
    '五' :  81900, # LINE_WIDTH /  22 
    '互' :  81900, # LINE_WIDTH /  22 
    '伍' :  81900, # LINE_WIDTH /  22 
    '午' :  81900, # LINE_WIDTH /  22 
    '呉' :  81900, # LINE_WIDTH /  22 
    '吾' :  81900, # LINE_WIDTH /  22 
    '娯' :  81900, # LINE_WIDTH /  22 
    '後' :  81900, # LINE_WIDTH /  22 
    '御' :  81900, # LINE_WIDTH /  22 
    '悟' :  81900, # LINE_WIDTH /  22 
    '梧' :  81900, # LINE_WIDTH /  22 
    '檎' :  81900, # LINE_WIDTH /  22 
    '瑚' :  81900, # LINE_WIDTH /  22 
    '碁' :  81900, # LINE_WIDTH /  22 
    '語' :  81900, # LINE_WIDTH /  22 
    '誤' :  81900, # LINE_WIDTH /  22 
    '護' :  81900, # LINE_WIDTH /  22 
    '醐' :  81900, # LINE_WIDTH /  22 
    '乞' :  81900, # LINE_WIDTH /  22 
    '鯉' :  81900, # LINE_WIDTH /  22 
    '交' :  81900, # LINE_WIDTH /  22 
    '佼' :  81900, # LINE_WIDTH /  22 
    '侯' :  81900, # LINE_WIDTH /  22 
    '候' :  81900, # LINE_WIDTH /  22 
    '倖' :  81900, # LINE_WIDTH /  22 
    '光' :  81900, # LINE_WIDTH /  22 
    '公' :  81900, # LINE_WIDTH /  22 
    '功' :  81900, # LINE_WIDTH /  22 
    '効' :  81900, # LINE_WIDTH /  22 
    '勾' :  81900, # LINE_WIDTH /  22 
    '厚' :  81900, # LINE_WIDTH /  22 
    '口' :  81900, # LINE_WIDTH /  22 
    '向' :  81900, # LINE_WIDTH /  22 
    '后' :  81900, # LINE_WIDTH /  22 
    '喉' :  81900, # LINE_WIDTH /  22 
    '坑' :  81900, # LINE_WIDTH /  22 
    '垢' :  81900, # LINE_WIDTH /  22 
    '好' :  81900, # LINE_WIDTH /  22 
    '孔' :  81900, # LINE_WIDTH /  22 
    '孝' :  81900, # LINE_WIDTH /  22 
    '宏' :  81900, # LINE_WIDTH /  22 
    '工' :  81900, # LINE_WIDTH /  22 
    '巧' :  81900, # LINE_WIDTH /  22 
    '巷' :  81900, # LINE_WIDTH /  22 
    '幸' :  81900, # LINE_WIDTH /  22 
    '広' :  81900, # LINE_WIDTH /  22 
    '庚' :  81900, # LINE_WIDTH /  22 
    '康' :  81900, # LINE_WIDTH /  22 
    '弘' :  81900, # LINE_WIDTH /  22 
    '恒' :  81900, # LINE_WIDTH /  22 
    '慌' :  81900, # LINE_WIDTH /  22 
    '抗' :  81900, # LINE_WIDTH /  22 
    '拘' :  81900, # LINE_WIDTH /  22 
    '控' :  81900, # LINE_WIDTH /  22 
    '攻' :  81900, # LINE_WIDTH /  22 
    '昂' :  81900, # LINE_WIDTH /  22 
    '晃' :  81900, # LINE_WIDTH /  22 
    '更' :  81900, # LINE_WIDTH /  22 
    '杭' :  81900, # LINE_WIDTH /  22 
    '校' :  81900, # LINE_WIDTH /  22 
    '梗' :  81900, # LINE_WIDTH /  22 
    '構' :  81900, # LINE_WIDTH /  22 
    '江' :  81900, # LINE_WIDTH /  22 
    '洪' :  81900, # LINE_WIDTH /  22 
    '浩' :  81900, # LINE_WIDTH /  22 
    '港' :  81900, # LINE_WIDTH /  22 
    '溝' :  81900, # LINE_WIDTH /  22 
    '甲' :  81900, # LINE_WIDTH /  22 
    '皇' :  81900, # LINE_WIDTH /  22 
    '硬' :  81900, # LINE_WIDTH /  22 
    '稿' :  81900, # LINE_WIDTH /  22 
    '糠' :  81900, # LINE_WIDTH /  22 
    '紅' :  81900, # LINE_WIDTH /  22 
    '紘' :  81900, # LINE_WIDTH /  22 
    '絞' :  81900, # LINE_WIDTH /  22 
    '綱' :  81900, # LINE_WIDTH /  22 
    '耕' :  81900, # LINE_WIDTH /  22 
    '考' :  81900, # LINE_WIDTH /  22 
    '肯' :  81900, # LINE_WIDTH /  22 
    '肱' :  81900, # LINE_WIDTH /  22 
    '腔' :  81900, # LINE_WIDTH /  22 
    '膏' :  81900, # LINE_WIDTH /  22 
    '航' :  81900, # LINE_WIDTH /  22 
    '荒' :  81900, # LINE_WIDTH /  22 
    '行' :  81900, # LINE_WIDTH /  22 
    '衡' :  81900, # LINE_WIDTH /  22 
    '講' :  81900, # LINE_WIDTH /  22 
    '貢' :  81900, # LINE_WIDTH /  22 
    '購' :  81900, # LINE_WIDTH /  22 
    '郊' :  81900, # LINE_WIDTH /  22 
    '酵' :  81900, # LINE_WIDTH /  22 
    '鉱' :  81900, # LINE_WIDTH /  22 
    '砿' :  81900, # LINE_WIDTH /  22 
    '鋼' :  81900, # LINE_WIDTH /  22 
    '閤' :  81900, # LINE_WIDTH /  22 
    '降' :  81900, # LINE_WIDTH /  22 
    '項' :  81900, # LINE_WIDTH /  22 
    '香' :  81900, # LINE_WIDTH /  22 
    '高' :  81900, # LINE_WIDTH /  22 
    '鴻' :  81900, # LINE_WIDTH /  22 
    '剛' :  81900, # LINE_WIDTH /  22 
    '劫' :  81900, # LINE_WIDTH /  22 
    '号' :  81900, # LINE_WIDTH /  22 
    '合' :  81900, # LINE_WIDTH /  22 
    '壕' :  81900, # LINE_WIDTH /  22 
    '拷' :  81900, # LINE_WIDTH /  22 
    '濠' :  81900, # LINE_WIDTH /  22 
    '豪' :  81900, # LINE_WIDTH /  22 
    '轟' :  81900, # LINE_WIDTH /  22 
    '麹' :  81900, # LINE_WIDTH /  22 
    '克' :  81900, # LINE_WIDTH /  22 
    '刻' :  81900, # LINE_WIDTH /  22 
    '告' :  81900, # LINE_WIDTH /  22 
    '国' :  81900, # LINE_WIDTH /  22 
    '穀' :  81900, # LINE_WIDTH /  22 
    '酷' :  81900, # LINE_WIDTH /  22 
    '鵠' :  81900, # LINE_WIDTH /  22 
    '黒' :  81900, # LINE_WIDTH /  22 
    '獄' :  81900, # LINE_WIDTH /  22 
    '漉' :  81900, # LINE_WIDTH /  22 
    '腰' :  81900, # LINE_WIDTH /  22 
    '甑' :  81900, # LINE_WIDTH /  22 
    '忽' :  81900, # LINE_WIDTH /  22 
    '惚' :  81900, # LINE_WIDTH /  22 
    '骨' :  81900, # LINE_WIDTH /  22 
    '狛' :  81900, # LINE_WIDTH /  22 
    '込' :  81900, # LINE_WIDTH /  22 
    '此' :  81900, # LINE_WIDTH /  22 
    '頃' :  81900, # LINE_WIDTH /  22 
    '今' :  81900, # LINE_WIDTH /  22 
    '困' :  81900, # LINE_WIDTH /  22 
    '坤' :  81900, # LINE_WIDTH /  22 
    '墾' :  81900, # LINE_WIDTH /  22 
    '婚' :  81900, # LINE_WIDTH /  22 
    '恨' :  81900, # LINE_WIDTH /  22 
    '懇' :  81900, # LINE_WIDTH /  22 
    '昏' :  81900, # LINE_WIDTH /  22 
    '昆' :  81900, # LINE_WIDTH /  22 
    '根' :  81900, # LINE_WIDTH /  22 
    '梱' :  81900, # LINE_WIDTH /  22 
    '混' :  81900, # LINE_WIDTH /  22 
    '痕' :  81900, # LINE_WIDTH /  22 
    '紺' :  81900, # LINE_WIDTH /  22 
    '艮' :  81900, # LINE_WIDTH /  22 
    '魂' :  81900, # LINE_WIDTH /  22 
    '些' :  81900, # LINE_WIDTH /  22 
    '佐' :  81900, # LINE_WIDTH /  22 
    '叉' :  81900, # LINE_WIDTH /  22 
    '唆' :  81900, # LINE_WIDTH /  22 
    '嵯' :  81900, # LINE_WIDTH /  22 
    '左' :  81900, # LINE_WIDTH /  22 
    '差' :  81900, # LINE_WIDTH /  22 
    '査' :  81900, # LINE_WIDTH /  22 
    '沙' :  81900, # LINE_WIDTH /  22 
    '瑳' :  81900, # LINE_WIDTH /  22 
    '砂' :  81900, # LINE_WIDTH /  22 
    '詐' :  81900, # LINE_WIDTH /  22 
    '鎖' :  81900, # LINE_WIDTH /  22 
    '裟' :  81900, # LINE_WIDTH /  22 
    '坐' :  81900, # LINE_WIDTH /  22 
    '座' :  81900, # LINE_WIDTH /  22 
    '挫' :  81900, # LINE_WIDTH /  22 
    '債' :  81900, # LINE_WIDTH /  22 
    '催' :  81900, # LINE_WIDTH /  22 
    '再' :  81900, # LINE_WIDTH /  22 
    '最' :  81900, # LINE_WIDTH /  22 
    '哉' :  81900, # LINE_WIDTH /  22 
    '塞' :  81900, # LINE_WIDTH /  22 
    '妻' :  81900, # LINE_WIDTH /  22 
    '宰' :  81900, # LINE_WIDTH /  22 
    '彩' :  81900, # LINE_WIDTH /  22 
    '才' :  81900, # LINE_WIDTH /  22 
    '採' :  81900, # LINE_WIDTH /  22 
    '栽' :  81900, # LINE_WIDTH /  22 
    '歳' :  81900, # LINE_WIDTH /  22 
    '済' :  81900, # LINE_WIDTH /  22 
    '災' :  81900, # LINE_WIDTH /  22 
    '采' :  81900, # LINE_WIDTH /  22 
    '犀' :  81900, # LINE_WIDTH /  22 
    '砕' :  81900, # LINE_WIDTH /  22 
    '砦' :  81900, # LINE_WIDTH /  22 
    '祭' :  81900, # LINE_WIDTH /  22 
    '斎' :  81900, # LINE_WIDTH /  22 
    '細' :  81900, # LINE_WIDTH /  22 
    '菜' :  81900, # LINE_WIDTH /  22 
    '裁' :  81900, # LINE_WIDTH /  22 
    '載' :  81900, # LINE_WIDTH /  22 
    '際' :  81900, # LINE_WIDTH /  22 
    '剤' :  81900, # LINE_WIDTH /  22 
    '在' :  81900, # LINE_WIDTH /  22 
    '材' :  81900, # LINE_WIDTH /  22 
    '罪' :  81900, # LINE_WIDTH /  22 
    '財' :  81900, # LINE_WIDTH /  22 
    '冴' :  81900, # LINE_WIDTH /  22 
    '坂' :  81900, # LINE_WIDTH /  22 
    '阪' :  81900, # LINE_WIDTH /  22 
    '堺' :  81900, # LINE_WIDTH /  22 
    '榊' :  81900, # LINE_WIDTH /  22 
    '肴' :  81900, # LINE_WIDTH /  22 
    '咲' :  81900, # LINE_WIDTH /  22 
    '崎' :  81900, # LINE_WIDTH /  22 
    '埼' :  81900, # LINE_WIDTH /  22 
    '碕' :  81900, # LINE_WIDTH /  22 
    '鷺' :  81900, # LINE_WIDTH /  22 
    '作' :  81900, # LINE_WIDTH /  22 
    '削' :  81900, # LINE_WIDTH /  22 
    '咋' :  81900, # LINE_WIDTH /  22 
    '搾' :  81900, # LINE_WIDTH /  22 
    '昨' :  81900, # LINE_WIDTH /  22 
    '朔' :  81900, # LINE_WIDTH /  22 
    '柵' :  81900, # LINE_WIDTH /  22 
    '窄' :  81900, # LINE_WIDTH /  22 
    '策' :  81900, # LINE_WIDTH /  22 
    '索' :  81900, # LINE_WIDTH /  22 
    '錯' :  81900, # LINE_WIDTH /  22 
    '桜' :  81900, # LINE_WIDTH /  22 
    '鮭' :  81900, # LINE_WIDTH /  22 
    '笹' :  81900, # LINE_WIDTH /  22 
    '匙' :  81900, # LINE_WIDTH /  22 
    '冊' :  81900, # LINE_WIDTH /  22 
    '刷' :  81900, # LINE_WIDTH /  22 
    '察' :  81900, # LINE_WIDTH /  22 
    '拶' :  81900, # LINE_WIDTH /  22 
    '撮' :  81900, # LINE_WIDTH /  22 
    '擦' :  81900, # LINE_WIDTH /  22 
    '札' :  81900, # LINE_WIDTH /  22 
    '殺' :  81900, # LINE_WIDTH /  22 
    '薩' :  81900, # LINE_WIDTH /  22 
    '雑' :  81900, # LINE_WIDTH /  22 
    '皐' :  81900, # LINE_WIDTH /  22 
    '鯖' :  81900, # LINE_WIDTH /  22 
    '捌' :  81900, # LINE_WIDTH /  22 
    '錆' :  81900, # LINE_WIDTH /  22 
    '鮫' :  81900, # LINE_WIDTH /  22 
    '皿' :  81900, # LINE_WIDTH /  22 
    '晒' :  81900, # LINE_WIDTH /  22 
    '三' :  81900, # LINE_WIDTH /  22 
    '傘' :  81900, # LINE_WIDTH /  22 
    '参' :  81900, # LINE_WIDTH /  22 
    '山' :  81900, # LINE_WIDTH /  22 
    '惨' :  81900, # LINE_WIDTH /  22 
    '撒' :  81900, # LINE_WIDTH /  22 
    '散' :  81900, # LINE_WIDTH /  22 
    '桟' :  81900, # LINE_WIDTH /  22 
    '燦' :  81900, # LINE_WIDTH /  22 
    '珊' :  81900, # LINE_WIDTH /  22 
    '産' :  81900, # LINE_WIDTH /  22 
    '算' :  81900, # LINE_WIDTH /  22 
    '纂' :  81900, # LINE_WIDTH /  22 
    '蚕' :  81900, # LINE_WIDTH /  22 
    '讃' :  81900, # LINE_WIDTH /  22 
    '賛' :  81900, # LINE_WIDTH /  22 
    '酸' :  81900, # LINE_WIDTH /  22 
    '餐' :  81900, # LINE_WIDTH /  22 
    '斬' :  81900, # LINE_WIDTH /  22 
    '暫' :  81900, # LINE_WIDTH /  22 
    '残' :  81900, # LINE_WIDTH /  22 
    '仕' :  81900, # LINE_WIDTH /  22 
    '仔' :  81900, # LINE_WIDTH /  22 
    '伺' :  81900, # LINE_WIDTH /  22 
    '使' :  81900, # LINE_WIDTH /  22 
    '刺' :  81900, # LINE_WIDTH /  22 
    '司' :  81900, # LINE_WIDTH /  22 
    '史' :  81900, # LINE_WIDTH /  22 
    '嗣' :  81900, # LINE_WIDTH /  22 
    '四' :  81900, # LINE_WIDTH /  22 
    '士' :  81900, # LINE_WIDTH /  22 
    '始' :  81900, # LINE_WIDTH /  22 
    '姉' :  81900, # LINE_WIDTH /  22 
    '姿' :  81900, # LINE_WIDTH /  22 
    '子' :  81900, # LINE_WIDTH /  22 
    '屍' :  81900, # LINE_WIDTH /  22 
    '市' :  81900, # LINE_WIDTH /  22 
    '師' :  81900, # LINE_WIDTH /  22 
    '志' :  81900, # LINE_WIDTH /  22 
    '思' :  81900, # LINE_WIDTH /  22 
    '指' :  81900, # LINE_WIDTH /  22 
    '支' :  81900, # LINE_WIDTH /  22 
    '孜' :  81900, # LINE_WIDTH /  22 
    '斯' :  81900, # LINE_WIDTH /  22 
    '施' :  81900, # LINE_WIDTH /  22 
    '旨' :  81900, # LINE_WIDTH /  22 
    '枝' :  81900, # LINE_WIDTH /  22 
    '止' :  81900, # LINE_WIDTH /  22 
    '死' :  81900, # LINE_WIDTH /  22 
    '氏' :  81900, # LINE_WIDTH /  22 
    '獅' :  81900, # LINE_WIDTH /  22 
    '祉' :  81900, # LINE_WIDTH /  22 
    '私' :  81900, # LINE_WIDTH /  22 
    '糸' :  81900, # LINE_WIDTH /  22 
    '紙' :  81900, # LINE_WIDTH /  22 
    '紫' :  81900, # LINE_WIDTH /  22 
    '肢' :  81900, # LINE_WIDTH /  22 
    '脂' :  81900, # LINE_WIDTH /  22 
    '至' :  81900, # LINE_WIDTH /  22 
    '視' :  81900, # LINE_WIDTH /  22 
    '詞' :  81900, # LINE_WIDTH /  22 
    '詩' :  81900, # LINE_WIDTH /  22 
    '試' :  81900, # LINE_WIDTH /  22 
    '誌' :  81900, # LINE_WIDTH /  22 
    '諮' :  81900, # LINE_WIDTH /  22 
    '資' :  81900, # LINE_WIDTH /  22 
    '賜' :  81900, # LINE_WIDTH /  22 
    '雌' :  81900, # LINE_WIDTH /  22 
    '飼' :  81900, # LINE_WIDTH /  22 
    '歯' :  81900, # LINE_WIDTH /  22 
    '事' :  81900, # LINE_WIDTH /  22 
    '似' :  81900, # LINE_WIDTH /  22 
    '侍' :  81900, # LINE_WIDTH /  22 
    '児' :  81900, # LINE_WIDTH /  22 
    '字' :  81900, # LINE_WIDTH /  22 
    '寺' :  81900, # LINE_WIDTH /  22 
    '慈' :  81900, # LINE_WIDTH /  22 
    '持' :  81900, # LINE_WIDTH /  22 
    '時' :  81900, # LINE_WIDTH /  22 
    '次' :  81900, # LINE_WIDTH /  22 
    '滋' :  81900, # LINE_WIDTH /  22 
    '治' :  81900, # LINE_WIDTH /  22 
    '爾' :  81900, # LINE_WIDTH /  22 
    '璽' :  81900, # LINE_WIDTH /  22 
    '痔' :  81900, # LINE_WIDTH /  22 
    '磁' :  81900, # LINE_WIDTH /  22 
    '示' :  81900, # LINE_WIDTH /  22 
    '而' :  81900, # LINE_WIDTH /  22 
    '耳' :  81900, # LINE_WIDTH /  22 
    '自' :  81900, # LINE_WIDTH /  22 
    '蒔' :  81900, # LINE_WIDTH /  22 
    '辞' :  81900, # LINE_WIDTH /  22 
    '汐' :  81900, # LINE_WIDTH /  22 
    '鹿' :  81900, # LINE_WIDTH /  22 
    '式' :  81900, # LINE_WIDTH /  22 
    '識' :  81900, # LINE_WIDTH /  22 
    '鴫' :  81900, # LINE_WIDTH /  22 
    '竺' :  81900, # LINE_WIDTH /  22 
    '軸' :  81900, # LINE_WIDTH /  22 
    '宍' :  81900, # LINE_WIDTH /  22 
    '雫' :  81900, # LINE_WIDTH /  22 
    '七' :  81900, # LINE_WIDTH /  22 
    '叱' :  81900, # LINE_WIDTH /  22 
    '執' :  81900, # LINE_WIDTH /  22 
    '失' :  81900, # LINE_WIDTH /  22 
    '嫉' :  81900, # LINE_WIDTH /  22 
    '室' :  81900, # LINE_WIDTH /  22 
    '悉' :  81900, # LINE_WIDTH /  22 
    '湿' :  81900, # LINE_WIDTH /  22 
    '漆' :  81900, # LINE_WIDTH /  22 
    '疾' :  81900, # LINE_WIDTH /  22 
    '質' :  81900, # LINE_WIDTH /  22 
    '実' :  81900, # LINE_WIDTH /  22 
    '蔀' :  81900, # LINE_WIDTH /  22 
    '篠' :  81900, # LINE_WIDTH /  22 
    '偲' :  81900, # LINE_WIDTH /  22 
    '柴' :  81900, # LINE_WIDTH /  22 
    '芝' :  81900, # LINE_WIDTH /  22 
    '屡' :  81900, # LINE_WIDTH /  22 
    '蕊' :  81900, # LINE_WIDTH /  22 
    '縞' :  81900, # LINE_WIDTH /  22 
    '舎' :  81900, # LINE_WIDTH /  22 
    '写' :  81900, # LINE_WIDTH /  22 
    '射' :  81900, # LINE_WIDTH /  22 
    '捨' :  81900, # LINE_WIDTH /  22 
    '赦' :  81900, # LINE_WIDTH /  22 
    '斜' :  81900, # LINE_WIDTH /  22 
    '煮' :  81900, # LINE_WIDTH /  22 
    '社' :  81900, # LINE_WIDTH /  22 
    '紗' :  81900, # LINE_WIDTH /  22 
    '者' :  81900, # LINE_WIDTH /  22 
    '謝' :  81900, # LINE_WIDTH /  22 
    '車' :  81900, # LINE_WIDTH /  22 
    '遮' :  81900, # LINE_WIDTH /  22 
    '蛇' :  81900, # LINE_WIDTH /  22 
    '邪' :  81900, # LINE_WIDTH /  22 
    '借' :  81900, # LINE_WIDTH /  22 
    '勺' :  81900, # LINE_WIDTH /  22 
    '尺' :  81900, # LINE_WIDTH /  22 
    '杓' :  81900, # LINE_WIDTH /  22 
    '灼' :  81900, # LINE_WIDTH /  22 
    '爵' :  81900, # LINE_WIDTH /  22 
    '酌' :  81900, # LINE_WIDTH /  22 
    '釈' :  81900, # LINE_WIDTH /  22 
    '錫' :  81900, # LINE_WIDTH /  22 
    '若' :  81900, # LINE_WIDTH /  22 
    '寂' :  81900, # LINE_WIDTH /  22 
    '弱' :  81900, # LINE_WIDTH /  22 
    '惹' :  81900, # LINE_WIDTH /  22 
    '主' :  81900, # LINE_WIDTH /  22 
    '取' :  81900, # LINE_WIDTH /  22 
    '守' :  81900, # LINE_WIDTH /  22 
    '手' :  81900, # LINE_WIDTH /  22 
    '朱' :  81900, # LINE_WIDTH /  22 
    '殊' :  81900, # LINE_WIDTH /  22 
    '狩' :  81900, # LINE_WIDTH /  22 
    '珠' :  81900, # LINE_WIDTH /  22 
    '種' :  81900, # LINE_WIDTH /  22 
    '腫' :  81900, # LINE_WIDTH /  22 
    '趣' :  81900, # LINE_WIDTH /  22 
    '酒' :  81900, # LINE_WIDTH /  22 
    '首' :  81900, # LINE_WIDTH /  22 
    '儒' :  81900, # LINE_WIDTH /  22 
    '受' :  81900, # LINE_WIDTH /  22 
    '呪' :  81900, # LINE_WIDTH /  22 
    '寿' :  81900, # LINE_WIDTH /  22 
    '授' :  81900, # LINE_WIDTH /  22 
    '樹' :  81900, # LINE_WIDTH /  22 
    '綬' :  81900, # LINE_WIDTH /  22 
    '需' :  81900, # LINE_WIDTH /  22 
    '囚' :  81900, # LINE_WIDTH /  22 
    '収' :  81900, # LINE_WIDTH /  22 
    '周' :  81900, # LINE_WIDTH /  22 
    '宗' :  81900, # LINE_WIDTH /  22 
    '就' :  81900, # LINE_WIDTH /  22 
    '州' :  81900, # LINE_WIDTH /  22 
    '修' :  81900, # LINE_WIDTH /  22 
    '愁' :  81900, # LINE_WIDTH /  22 
    '拾' :  81900, # LINE_WIDTH /  22 
    '洲' :  81900, # LINE_WIDTH /  22 
    '秀' :  81900, # LINE_WIDTH /  22 
    '秋' :  81900, # LINE_WIDTH /  22 
    '終' :  81900, # LINE_WIDTH /  22 
    '繍' :  81900, # LINE_WIDTH /  22 
    '習' :  81900, # LINE_WIDTH /  22 
    '臭' :  81900, # LINE_WIDTH /  22 
    '舟' :  81900, # LINE_WIDTH /  22 
    '蒐' :  81900, # LINE_WIDTH /  22 
    '衆' :  81900, # LINE_WIDTH /  22 
    '襲' :  81900, # LINE_WIDTH /  22 
    '讐' :  81900, # LINE_WIDTH /  22 
    '蹴' :  81900, # LINE_WIDTH /  22 
    '輯' :  81900, # LINE_WIDTH /  22 
    '週' :  81900, # LINE_WIDTH /  22 
    '酋' :  81900, # LINE_WIDTH /  22 
    '酬' :  81900, # LINE_WIDTH /  22 
    '集' :  81900, # LINE_WIDTH /  22 
    '醜' :  81900, # LINE_WIDTH /  22 
    '什' :  81900, # LINE_WIDTH /  22 
    '住' :  81900, # LINE_WIDTH /  22 
    '充' :  81900, # LINE_WIDTH /  22 
    '十' :  81900, # LINE_WIDTH /  22 
    '従' :  81900, # LINE_WIDTH /  22 
    '戎' :  81900, # LINE_WIDTH /  22 
    '柔' :  81900, # LINE_WIDTH /  22 
    '汁' :  81900, # LINE_WIDTH /  22 
    '渋' :  81900, # LINE_WIDTH /  22 
    '獣' :  81900, # LINE_WIDTH /  22 
    '縦' :  81900, # LINE_WIDTH /  22 
    '重' :  81900, # LINE_WIDTH /  22 
    '銃' :  81900, # LINE_WIDTH /  22 
    '叔' :  81900, # LINE_WIDTH /  22 
    '夙' :  81900, # LINE_WIDTH /  22 
    '宿' :  81900, # LINE_WIDTH /  22 
    '淑' :  81900, # LINE_WIDTH /  22 
    '祝' :  81900, # LINE_WIDTH /  22 
    '縮' :  81900, # LINE_WIDTH /  22 
    '粛' :  81900, # LINE_WIDTH /  22 
    '塾' :  81900, # LINE_WIDTH /  22 
    '熟' :  81900, # LINE_WIDTH /  22 
    '出' :  81900, # LINE_WIDTH /  22 
    '術' :  81900, # LINE_WIDTH /  22 
    '述' :  81900, # LINE_WIDTH /  22 
    '俊' :  81900, # LINE_WIDTH /  22 
    '峻' :  81900, # LINE_WIDTH /  22 
    '春' :  81900, # LINE_WIDTH /  22 
    '瞬' :  81900, # LINE_WIDTH /  22 
    '竣' :  81900, # LINE_WIDTH /  22 
    '舜' :  81900, # LINE_WIDTH /  22 
    '駿' :  81900, # LINE_WIDTH /  22 
    '准' :  81900, # LINE_WIDTH /  22 
    '循' :  81900, # LINE_WIDTH /  22 
    '旬' :  81900, # LINE_WIDTH /  22 
    '楯' :  81900, # LINE_WIDTH /  22 
    '殉' :  81900, # LINE_WIDTH /  22 
    '淳' :  81900, # LINE_WIDTH /  22 
    '準' :  81900, # LINE_WIDTH /  22 
    '潤' :  81900, # LINE_WIDTH /  22 
    '盾' :  81900, # LINE_WIDTH /  22 
    '純' :  81900, # LINE_WIDTH /  22 
    '巡' :  81900, # LINE_WIDTH /  22 
    '遵' :  81900, # LINE_WIDTH /  22 
    '醇' :  81900, # LINE_WIDTH /  22 
    '順' :  81900, # LINE_WIDTH /  22 
    '処' :  81900, # LINE_WIDTH /  22 
    '初' :  81900, # LINE_WIDTH /  22 
    '所' :  81900, # LINE_WIDTH /  22 
    '暑' :  81900, # LINE_WIDTH /  22 
    '曙' :  81900, # LINE_WIDTH /  22 
    '渚' :  81900, # LINE_WIDTH /  22 
    '庶' :  81900, # LINE_WIDTH /  22 
    '緒' :  81900, # LINE_WIDTH /  22 
    '署' :  81900, # LINE_WIDTH /  22 
    '書' :  81900, # LINE_WIDTH /  22 
    '薯' :  81900, # LINE_WIDTH /  22 
    '藷' :  81900, # LINE_WIDTH /  22 
    '諸' :  81900, # LINE_WIDTH /  22 
    '助' :  81900, # LINE_WIDTH /  22 
    '叙' :  81900, # LINE_WIDTH /  22 
    '女' :  81900, # LINE_WIDTH /  22 
    '序' :  81900, # LINE_WIDTH /  22 
    '徐' :  81900, # LINE_WIDTH /  22 
    '恕' :  81900, # LINE_WIDTH /  22 
    '鋤' :  81900, # LINE_WIDTH /  22 
    '除' :  81900, # LINE_WIDTH /  22 
    '傷' :  81900, # LINE_WIDTH /  22 
    '償' :  81900, # LINE_WIDTH /  22 
    '勝' :  81900, # LINE_WIDTH /  22 
    '匠' :  81900, # LINE_WIDTH /  22 
    '升' :  81900, # LINE_WIDTH /  22 
    '召' :  81900, # LINE_WIDTH /  22 
    '哨' :  81900, # LINE_WIDTH /  22 
    '商' :  81900, # LINE_WIDTH /  22 
    '唱' :  81900, # LINE_WIDTH /  22 
    '嘗' :  81900, # LINE_WIDTH /  22 
    '奨' :  81900, # LINE_WIDTH /  22 
    '妾' :  81900, # LINE_WIDTH /  22 
    '娼' :  81900, # LINE_WIDTH /  22 
    '宵' :  81900, # LINE_WIDTH /  22 
    '将' :  81900, # LINE_WIDTH /  22 
    '小' :  81900, # LINE_WIDTH /  22 
    '少' :  81900, # LINE_WIDTH /  22 
    '尚' :  81900, # LINE_WIDTH /  22 
    '庄' :  81900, # LINE_WIDTH /  22 
    '床' :  81900, # LINE_WIDTH /  22 
    '廠' :  81900, # LINE_WIDTH /  22 
    '彰' :  81900, # LINE_WIDTH /  22 
    '承' :  81900, # LINE_WIDTH /  22 
    '抄' :  81900, # LINE_WIDTH /  22 
    '招' :  81900, # LINE_WIDTH /  22 
    '掌' :  81900, # LINE_WIDTH /  22 
    '捷' :  81900, # LINE_WIDTH /  22 
    '昇' :  81900, # LINE_WIDTH /  22 
    '昌' :  81900, # LINE_WIDTH /  22 
    '昭' :  81900, # LINE_WIDTH /  22 
    '晶' :  81900, # LINE_WIDTH /  22 
    '松' :  81900, # LINE_WIDTH /  22 
    '梢' :  81900, # LINE_WIDTH /  22 
    '樟' :  81900, # LINE_WIDTH /  22 
    '樵' :  81900, # LINE_WIDTH /  22 
    '沼' :  81900, # LINE_WIDTH /  22 
    '消' :  81900, # LINE_WIDTH /  22 
    '渉' :  81900, # LINE_WIDTH /  22 
    '湘' :  81900, # LINE_WIDTH /  22 
    '焼' :  81900, # LINE_WIDTH /  22 
    '焦' :  81900, # LINE_WIDTH /  22 
    '照' :  81900, # LINE_WIDTH /  22 
    '症' :  81900, # LINE_WIDTH /  22 
    '省' :  81900, # LINE_WIDTH /  22 
    '硝' :  81900, # LINE_WIDTH /  22 
    '礁' :  81900, # LINE_WIDTH /  22 
    '祥' :  81900, # LINE_WIDTH /  22 
    '称' :  81900, # LINE_WIDTH /  22 
    '章' :  81900, # LINE_WIDTH /  22 
    '笑' :  81900, # LINE_WIDTH /  22 
    '粧' :  81900, # LINE_WIDTH /  22 
    '紹' :  81900, # LINE_WIDTH /  22 
    '肖' :  81900, # LINE_WIDTH /  22 
    '菖' :  81900, # LINE_WIDTH /  22 
    '蒋' :  81900, # LINE_WIDTH /  22 
    '蕉' :  81900, # LINE_WIDTH /  22 
    '衝' :  81900, # LINE_WIDTH /  22 
    '裳' :  81900, # LINE_WIDTH /  22 
    '訟' :  81900, # LINE_WIDTH /  22 
    '証' :  81900, # LINE_WIDTH /  22 
    '詔' :  81900, # LINE_WIDTH /  22 
    '詳' :  81900, # LINE_WIDTH /  22 
    '象' :  81900, # LINE_WIDTH /  22 
    '賞' :  81900, # LINE_WIDTH /  22 
    '醤' :  81900, # LINE_WIDTH /  22 
    '鉦' :  81900, # LINE_WIDTH /  22 
    '鍾' :  81900, # LINE_WIDTH /  22 
    '鐘' :  81900, # LINE_WIDTH /  22 
    '障' :  81900, # LINE_WIDTH /  22 
    '鞘' :  81900, # LINE_WIDTH /  22 
    '上' :  81900, # LINE_WIDTH /  22 
    '丈' :  81900, # LINE_WIDTH /  22 
    '丞' :  81900, # LINE_WIDTH /  22 
    '乗' :  81900, # LINE_WIDTH /  22 
    '冗' :  81900, # LINE_WIDTH /  22 
    '剰' :  81900, # LINE_WIDTH /  22 
    '城' :  81900, # LINE_WIDTH /  22 
    '場' :  81900, # LINE_WIDTH /  22 
    '壌' :  81900, # LINE_WIDTH /  22 
    '嬢' :  81900, # LINE_WIDTH /  22 
    '常' :  81900, # LINE_WIDTH /  22 
    '情' :  81900, # LINE_WIDTH /  22 
    '擾' :  81900, # LINE_WIDTH /  22 
    '条' :  81900, # LINE_WIDTH /  22 
    '杖' :  81900, # LINE_WIDTH /  22 
    '浄' :  81900, # LINE_WIDTH /  22 
    '状' :  81900, # LINE_WIDTH /  22 
    '畳' :  81900, # LINE_WIDTH /  22 
    '穣' :  81900, # LINE_WIDTH /  22 
    '蒸' :  81900, # LINE_WIDTH /  22 
    '譲' :  81900, # LINE_WIDTH /  22 
    '醸' :  81900, # LINE_WIDTH /  22 
    '錠' :  81900, # LINE_WIDTH /  22 
    '嘱' :  81900, # LINE_WIDTH /  22 
    '埴' :  81900, # LINE_WIDTH /  22 
    '飾' :  81900, # LINE_WIDTH /  22 
    '拭' :  81900, # LINE_WIDTH /  22 
    '植' :  81900, # LINE_WIDTH /  22 
    '殖' :  81900, # LINE_WIDTH /  22 
    '燭' :  81900, # LINE_WIDTH /  22 
    '織' :  81900, # LINE_WIDTH /  22 
    '職' :  81900, # LINE_WIDTH /  22 
    '色' :  81900, # LINE_WIDTH /  22 
    '触' :  81900, # LINE_WIDTH /  22 
    '食' :  81900, # LINE_WIDTH /  22 
    '蝕' :  81900, # LINE_WIDTH /  22 
    '辱' :  81900, # LINE_WIDTH /  22 
    '尻' :  81900, # LINE_WIDTH /  22 
    '伸' :  81900, # LINE_WIDTH /  22 
    '信' :  81900, # LINE_WIDTH /  22 
    '侵' :  81900, # LINE_WIDTH /  22 
    '唇' :  81900, # LINE_WIDTH /  22 
    '娠' :  81900, # LINE_WIDTH /  22 
    '寝' :  81900, # LINE_WIDTH /  22 
    '審' :  81900, # LINE_WIDTH /  22 
    '心' :  81900, # LINE_WIDTH /  22 
    '慎' :  81900, # LINE_WIDTH /  22 
    '振' :  81900, # LINE_WIDTH /  22 
    '新' :  81900, # LINE_WIDTH /  22 
    '晋' :  81900, # LINE_WIDTH /  22 
    '森' :  81900, # LINE_WIDTH /  22 
    '榛' :  81900, # LINE_WIDTH /  22 
    '浸' :  81900, # LINE_WIDTH /  22 
    '深' :  81900, # LINE_WIDTH /  22 
    '申' :  81900, # LINE_WIDTH /  22 
    '疹' :  81900, # LINE_WIDTH /  22 
    '真' :  81900, # LINE_WIDTH /  22 
    '神' :  81900, # LINE_WIDTH /  22 
    '秦' :  81900, # LINE_WIDTH /  22 
    '紳' :  81900, # LINE_WIDTH /  22 
    '臣' :  81900, # LINE_WIDTH /  22 
    '芯' :  81900, # LINE_WIDTH /  22 
    '薪' :  81900, # LINE_WIDTH /  22 
    '親' :  81900, # LINE_WIDTH /  22 
    '診' :  81900, # LINE_WIDTH /  22 
    '身' :  81900, # LINE_WIDTH /  22 
    '辛' :  81900, # LINE_WIDTH /  22 
    '進' :  81900, # LINE_WIDTH /  22 
    '針' :  81900, # LINE_WIDTH /  22 
    '震' :  81900, # LINE_WIDTH /  22 
    '人' :  81900, # LINE_WIDTH /  22 
    '仁' :  81900, # LINE_WIDTH /  22 
    '刃' :  81900, # LINE_WIDTH /  22 
    '塵' :  81900, # LINE_WIDTH /  22 
    '壬' :  81900, # LINE_WIDTH /  22 
    '尋' :  81900, # LINE_WIDTH /  22 
    '甚' :  81900, # LINE_WIDTH /  22 
    '尽' :  81900, # LINE_WIDTH /  22 
    '腎' :  81900, # LINE_WIDTH /  22 
    '訊' :  81900, # LINE_WIDTH /  22 
    '迅' :  81900, # LINE_WIDTH /  22 
    '陣' :  81900, # LINE_WIDTH /  22 
    '靭' :  81900, # LINE_WIDTH /  22 
    '笥' :  81900, # LINE_WIDTH /  22 
    '諏' :  81900, # LINE_WIDTH /  22 
    '須' :  81900, # LINE_WIDTH /  22 
    '酢' :  81900, # LINE_WIDTH /  22 
    '図' :  81900, # LINE_WIDTH /  22 
    '厨' :  81900, # LINE_WIDTH /  22 
    '逗' :  81900, # LINE_WIDTH /  22 
    '吹' :  81900, # LINE_WIDTH /  22 
    '垂' :  81900, # LINE_WIDTH /  22 
    '帥' :  81900, # LINE_WIDTH /  22 
    '推' :  81900, # LINE_WIDTH /  22 
    '水' :  81900, # LINE_WIDTH /  22 
    '炊' :  81900, # LINE_WIDTH /  22 
    '睡' :  81900, # LINE_WIDTH /  22 
    '粋' :  81900, # LINE_WIDTH /  22 
    '翠' :  81900, # LINE_WIDTH /  22 
    '衰' :  81900, # LINE_WIDTH /  22 
    '遂' :  81900, # LINE_WIDTH /  22 
    '酔' :  81900, # LINE_WIDTH /  22 
    '錐' :  81900, # LINE_WIDTH /  22 
    '錘' :  81900, # LINE_WIDTH /  22 
    '随' :  81900, # LINE_WIDTH /  22 
    '瑞' :  81900, # LINE_WIDTH /  22 
    '髄' :  81900, # LINE_WIDTH /  22 
    '崇' :  81900, # LINE_WIDTH /  22 
    '嵩' :  81900, # LINE_WIDTH /  22 
    '数' :  81900, # LINE_WIDTH /  22 
    '枢' :  81900, # LINE_WIDTH /  22 
    '趨' :  81900, # LINE_WIDTH /  22 
    '雛' :  81900, # LINE_WIDTH /  22 
    '据' :  81900, # LINE_WIDTH /  22 
    '杉' :  81900, # LINE_WIDTH /  22 
    '椙' :  81900, # LINE_WIDTH /  22 
    '菅' :  81900, # LINE_WIDTH /  22 
    '頗' :  81900, # LINE_WIDTH /  22 
    '雀' :  81900, # LINE_WIDTH /  22 
    '裾' :  81900, # LINE_WIDTH /  22 
    '澄' :  81900, # LINE_WIDTH /  22 
    '摺' :  81900, # LINE_WIDTH /  22 
    '寸' :  81900, # LINE_WIDTH /  22 
    '世' :  81900, # LINE_WIDTH /  22 
    '瀬' :  81900, # LINE_WIDTH /  22 
    '畝' :  81900, # LINE_WIDTH /  22 
    '是' :  81900, # LINE_WIDTH /  22 
    '凄' :  81900, # LINE_WIDTH /  22 
    '制' :  81900, # LINE_WIDTH /  22 
    '勢' :  81900, # LINE_WIDTH /  22 
    '姓' :  81900, # LINE_WIDTH /  22 
    '征' :  81900, # LINE_WIDTH /  22 
    '性' :  81900, # LINE_WIDTH /  22 
    '成' :  81900, # LINE_WIDTH /  22 
    '政' :  81900, # LINE_WIDTH /  22 
    '整' :  81900, # LINE_WIDTH /  22 
    '星' :  81900, # LINE_WIDTH /  22 
    '晴' :  81900, # LINE_WIDTH /  22 
    '棲' :  81900, # LINE_WIDTH /  22 
    '栖' :  81900, # LINE_WIDTH /  22 
    '正' :  81900, # LINE_WIDTH /  22 
    '清' :  81900, # LINE_WIDTH /  22 
    '牲' :  81900, # LINE_WIDTH /  22 
    '生' :  81900, # LINE_WIDTH /  22 
    '盛' :  81900, # LINE_WIDTH /  22 
    '精' :  81900, # LINE_WIDTH /  22 
    '聖' :  81900, # LINE_WIDTH /  22 
    '声' :  81900, # LINE_WIDTH /  22 
    '製' :  81900, # LINE_WIDTH /  22 
    '西' :  81900, # LINE_WIDTH /  22 
    '誠' :  81900, # LINE_WIDTH /  22 
    '誓' :  81900, # LINE_WIDTH /  22 
    '請' :  81900, # LINE_WIDTH /  22 
    '逝' :  81900, # LINE_WIDTH /  22 
    '醒' :  81900, # LINE_WIDTH /  22 
    '青' :  81900, # LINE_WIDTH /  22 
    '静' :  81900, # LINE_WIDTH /  22 
    '斉' :  81900, # LINE_WIDTH /  22 
    '税' :  81900, # LINE_WIDTH /  22 
    '脆' :  81900, # LINE_WIDTH /  22 
    '隻' :  81900, # LINE_WIDTH /  22 
    '席' :  81900, # LINE_WIDTH /  22 
    '惜' :  81900, # LINE_WIDTH /  22 
    '戚' :  81900, # LINE_WIDTH /  22 
    '斥' :  81900, # LINE_WIDTH /  22 
    '昔' :  81900, # LINE_WIDTH /  22 
    '析' :  81900, # LINE_WIDTH /  22 
    '石' :  81900, # LINE_WIDTH /  22 
    '積' :  81900, # LINE_WIDTH /  22 
    '籍' :  81900, # LINE_WIDTH /  22 
    '績' :  81900, # LINE_WIDTH /  22 
    '脊' :  81900, # LINE_WIDTH /  22 
    '責' :  81900, # LINE_WIDTH /  22 
    '赤' :  81900, # LINE_WIDTH /  22 
    '跡' :  81900, # LINE_WIDTH /  22 
    '蹟' :  81900, # LINE_WIDTH /  22 
    '碩' :  81900, # LINE_WIDTH /  22 
    '切' :  81900, # LINE_WIDTH /  22 
    '拙' :  81900, # LINE_WIDTH /  22 
    '接' :  81900, # LINE_WIDTH /  22 
    '摂' :  81900, # LINE_WIDTH /  22 
    '折' :  81900, # LINE_WIDTH /  22 
    '設' :  81900, # LINE_WIDTH /  22 
    '窃' :  81900, # LINE_WIDTH /  22 
    '節' :  81900, # LINE_WIDTH /  22 
    '説' :  81900, # LINE_WIDTH /  22 
    '雪' :  81900, # LINE_WIDTH /  22 
    '絶' :  81900, # LINE_WIDTH /  22 
    '舌' :  81900, # LINE_WIDTH /  22 
    '蝉' :  81900, # LINE_WIDTH /  22 
    '仙' :  81900, # LINE_WIDTH /  22 
    '先' :  81900, # LINE_WIDTH /  22 
    '千' :  81900, # LINE_WIDTH /  22 
    '占' :  81900, # LINE_WIDTH /  22 
    '宣' :  81900, # LINE_WIDTH /  22 
    '専' :  81900, # LINE_WIDTH /  22 
    '尖' :  81900, # LINE_WIDTH /  22 
    '川' :  81900, # LINE_WIDTH /  22 
    '戦' :  81900, # LINE_WIDTH /  22 
    '扇' :  81900, # LINE_WIDTH /  22 
    '撰' :  81900, # LINE_WIDTH /  22 
    '栓' :  81900, # LINE_WIDTH /  22 
    '栴' :  81900, # LINE_WIDTH /  22 
    '泉' :  81900, # LINE_WIDTH /  22 
    '浅' :  81900, # LINE_WIDTH /  22 
    '洗' :  81900, # LINE_WIDTH /  22 
    '染' :  81900, # LINE_WIDTH /  22 
    '潜' :  81900, # LINE_WIDTH /  22 
    '煎' :  81900, # LINE_WIDTH /  22 
    '煽' :  81900, # LINE_WIDTH /  22 
    '旋' :  81900, # LINE_WIDTH /  22 
    '穿' :  81900, # LINE_WIDTH /  22 
    '箭' :  81900, # LINE_WIDTH /  22 
    '線' :  81900, # LINE_WIDTH /  22 
    '繊' :  81900, # LINE_WIDTH /  22 
    '羨' :  81900, # LINE_WIDTH /  22 
    '腺' :  81900, # LINE_WIDTH /  22 
    '舛' :  81900, # LINE_WIDTH /  22 
    '船' :  81900, # LINE_WIDTH /  22 
    '薦' :  81900, # LINE_WIDTH /  22 
    '詮' :  81900, # LINE_WIDTH /  22 
    '賎' :  81900, # LINE_WIDTH /  22 
    '践' :  81900, # LINE_WIDTH /  22 
    '選' :  81900, # LINE_WIDTH /  22 
    '遷' :  81900, # LINE_WIDTH /  22 
    '銭' :  81900, # LINE_WIDTH /  22 
    '銑' :  81900, # LINE_WIDTH /  22 
    '閃' :  81900, # LINE_WIDTH /  22 
    '鮮' :  81900, # LINE_WIDTH /  22 
    '前' :  81900, # LINE_WIDTH /  22 
    '善' :  81900, # LINE_WIDTH /  22 
    '漸' :  81900, # LINE_WIDTH /  22 
    '然' :  81900, # LINE_WIDTH /  22 
    '全' :  81900, # LINE_WIDTH /  22 
    '禅' :  81900, # LINE_WIDTH /  22 
    '繕' :  81900, # LINE_WIDTH /  22 
    '膳' :  81900, # LINE_WIDTH /  22 
    '糎' :  81900, # LINE_WIDTH /  22 
    '噌' :  81900, # LINE_WIDTH /  22 
    '塑' :  81900, # LINE_WIDTH /  22 
    '岨' :  81900, # LINE_WIDTH /  22 
    '措' :  81900, # LINE_WIDTH /  22 
    '曾' :  81900, # LINE_WIDTH /  22 
    '曽' :  81900, # LINE_WIDTH /  22 
    '楚' :  81900, # LINE_WIDTH /  22 
    '狙' :  81900, # LINE_WIDTH /  22 
    '疏' :  81900, # LINE_WIDTH /  22 
    '疎' :  81900, # LINE_WIDTH /  22 
    '礎' :  81900, # LINE_WIDTH /  22 
    '祖' :  81900, # LINE_WIDTH /  22 
    '租' :  81900, # LINE_WIDTH /  22 
    '粗' :  81900, # LINE_WIDTH /  22 
    '素' :  81900, # LINE_WIDTH /  22 
    '組' :  81900, # LINE_WIDTH /  22 
    '蘇' :  81900, # LINE_WIDTH /  22 
    '訴' :  81900, # LINE_WIDTH /  22 
    '阻' :  81900, # LINE_WIDTH /  22 
    '遡' :  81900, # LINE_WIDTH /  22 
    '鼠' :  81900, # LINE_WIDTH /  22 
    '僧' :  81900, # LINE_WIDTH /  22 
    '創' :  81900, # LINE_WIDTH /  22 
    '双' :  81900, # LINE_WIDTH /  22 
    '叢' :  81900, # LINE_WIDTH /  22 
    '倉' :  81900, # LINE_WIDTH /  22 
    '喪' :  81900, # LINE_WIDTH /  22 
    '壮' :  81900, # LINE_WIDTH /  22 
    '奏' :  81900, # LINE_WIDTH /  22 
    '爽' :  81900, # LINE_WIDTH /  22 
    '宋' :  81900, # LINE_WIDTH /  22 
    '層' :  81900, # LINE_WIDTH /  22 
    '匝' :  81900, # LINE_WIDTH /  22 
    '惣' :  81900, # LINE_WIDTH /  22 
    '想' :  81900, # LINE_WIDTH /  22 
    '捜' :  81900, # LINE_WIDTH /  22 
    '掃' :  81900, # LINE_WIDTH /  22 
    '挿' :  81900, # LINE_WIDTH /  22 
    '掻' :  81900, # LINE_WIDTH /  22 
    '操' :  81900, # LINE_WIDTH /  22 
    '早' :  81900, # LINE_WIDTH /  22 
    '曹' :  81900, # LINE_WIDTH /  22 
    '巣' :  81900, # LINE_WIDTH /  22 
    '槍' :  81900, # LINE_WIDTH /  22 
    '槽' :  81900, # LINE_WIDTH /  22 
    '漕' :  81900, # LINE_WIDTH /  22 
    '燥' :  81900, # LINE_WIDTH /  22 
    '争' :  81900, # LINE_WIDTH /  22 
    '痩' :  81900, # LINE_WIDTH /  22 
    '相' :  81900, # LINE_WIDTH /  22 
    '窓' :  81900, # LINE_WIDTH /  22 
    '糟' :  81900, # LINE_WIDTH /  22 
    '総' :  81900, # LINE_WIDTH /  22 
    '綜' :  81900, # LINE_WIDTH /  22 
    '聡' :  81900, # LINE_WIDTH /  22 
    '草' :  81900, # LINE_WIDTH /  22 
    '荘' :  81900, # LINE_WIDTH /  22 
    '葬' :  81900, # LINE_WIDTH /  22 
    '蒼' :  81900, # LINE_WIDTH /  22 
    '藻' :  81900, # LINE_WIDTH /  22 
    '装' :  81900, # LINE_WIDTH /  22 
    '走' :  81900, # LINE_WIDTH /  22 
    '送' :  81900, # LINE_WIDTH /  22 
    '遭' :  81900, # LINE_WIDTH /  22 
    '鎗' :  81900, # LINE_WIDTH /  22 
    '霜' :  81900, # LINE_WIDTH /  22 
    '騒' :  81900, # LINE_WIDTH /  22 
    '像' :  81900, # LINE_WIDTH /  22 
    '増' :  81900, # LINE_WIDTH /  22 
    '憎' :  81900, # LINE_WIDTH /  22 
    '臓' :  81900, # LINE_WIDTH /  22 
    '蔵' :  81900, # LINE_WIDTH /  22 
    '贈' :  81900, # LINE_WIDTH /  22 
    '造' :  81900, # LINE_WIDTH /  22 
    '促' :  81900, # LINE_WIDTH /  22 
    '側' :  81900, # LINE_WIDTH /  22 
    '則' :  81900, # LINE_WIDTH /  22 
    '即' :  81900, # LINE_WIDTH /  22 
    '息' :  81900, # LINE_WIDTH /  22 
    '捉' :  81900, # LINE_WIDTH /  22 
    '束' :  81900, # LINE_WIDTH /  22 
    '測' :  81900, # LINE_WIDTH /  22 
    '足' :  81900, # LINE_WIDTH /  22 
    '速' :  81900, # LINE_WIDTH /  22 
    '俗' :  81900, # LINE_WIDTH /  22 
    '属' :  81900, # LINE_WIDTH /  22 
    '賊' :  81900, # LINE_WIDTH /  22 
    '族' :  81900, # LINE_WIDTH /  22 
    '続' :  81900, # LINE_WIDTH /  22 
    '卒' :  81900, # LINE_WIDTH /  22 
    '袖' :  81900, # LINE_WIDTH /  22 
    '其' :  81900, # LINE_WIDTH /  22 
    '揃' :  81900, # LINE_WIDTH /  22 
    '存' :  81900, # LINE_WIDTH /  22 
    '孫' :  81900, # LINE_WIDTH /  22 
    '尊' :  81900, # LINE_WIDTH /  22 
    '損' :  81900, # LINE_WIDTH /  22 
    '村' :  81900, # LINE_WIDTH /  22 
    '遜' :  81900, # LINE_WIDTH /  22 
    '他' :  81900, # LINE_WIDTH /  22 
    '多' :  81900, # LINE_WIDTH /  22 
    '太' :  81900, # LINE_WIDTH /  22 
    '汰' :  81900, # LINE_WIDTH /  22 
    '詑' :  81900, # LINE_WIDTH /  22 
    '唾' :  81900, # LINE_WIDTH /  22 
    '堕' :  81900, # LINE_WIDTH /  22 
    '妥' :  81900, # LINE_WIDTH /  22 
    '惰' :  81900, # LINE_WIDTH /  22 
    '打' :  81900, # LINE_WIDTH /  22 
    '柁' :  81900, # LINE_WIDTH /  22 
    '舵' :  81900, # LINE_WIDTH /  22 
    '楕' :  81900, # LINE_WIDTH /  22 
    '陀' :  81900, # LINE_WIDTH /  22 
    '駄' :  81900, # LINE_WIDTH /  22 
    '騨' :  81900, # LINE_WIDTH /  22 
    '体' :  81900, # LINE_WIDTH /  22 
    '堆' :  81900, # LINE_WIDTH /  22 
    '対' :  81900, # LINE_WIDTH /  22 
    '耐' :  81900, # LINE_WIDTH /  22 
    '岱' :  81900, # LINE_WIDTH /  22 
    '帯' :  81900, # LINE_WIDTH /  22 
    '待' :  81900, # LINE_WIDTH /  22 
    '怠' :  81900, # LINE_WIDTH /  22 
    '態' :  81900, # LINE_WIDTH /  22 
    '戴' :  81900, # LINE_WIDTH /  22 
    '替' :  81900, # LINE_WIDTH /  22 
    '泰' :  81900, # LINE_WIDTH /  22 
    '滞' :  81900, # LINE_WIDTH /  22 
    '胎' :  81900, # LINE_WIDTH /  22 
    '腿' :  81900, # LINE_WIDTH /  22 
    '苔' :  81900, # LINE_WIDTH /  22 
    '袋' :  81900, # LINE_WIDTH /  22 
    '貸' :  81900, # LINE_WIDTH /  22 
    '退' :  81900, # LINE_WIDTH /  22 
    '逮' :  81900, # LINE_WIDTH /  22 
    '隊' :  81900, # LINE_WIDTH /  22 
    '黛' :  81900, # LINE_WIDTH /  22 
    '鯛' :  81900, # LINE_WIDTH /  22 
    '代' :  81900, # LINE_WIDTH /  22 
    '台' :  81900, # LINE_WIDTH /  22 
    '大' :  81900, # LINE_WIDTH /  22 
    '第' :  81900, # LINE_WIDTH /  22 
    '醍' :  81900, # LINE_WIDTH /  22 
    '題' :  81900, # LINE_WIDTH /  22 
    '鷹' :  81900, # LINE_WIDTH /  22 
    '滝' :  81900, # LINE_WIDTH /  22 
    '瀧' :  81900, # LINE_WIDTH /  22 
    '卓' :  81900, # LINE_WIDTH /  22 
    '啄' :  81900, # LINE_WIDTH /  22 
    '宅' :  81900, # LINE_WIDTH /  22 
    '托' :  81900, # LINE_WIDTH /  22 
    '択' :  81900, # LINE_WIDTH /  22 
    '拓' :  81900, # LINE_WIDTH /  22 
    '沢' :  81900, # LINE_WIDTH /  22 
    '濯' :  81900, # LINE_WIDTH /  22 
    '琢' :  81900, # LINE_WIDTH /  22 
    '託' :  81900, # LINE_WIDTH /  22 
    '鐸' :  81900, # LINE_WIDTH /  22 
    '濁' :  81900, # LINE_WIDTH /  22 
    '諾' :  81900, # LINE_WIDTH /  22 
    '茸' :  81900, # LINE_WIDTH /  22 
    '凧' :  81900, # LINE_WIDTH /  22 
    '蛸' :  81900, # LINE_WIDTH /  22 
    '只' :  81900, # LINE_WIDTH /  22 
    '叩' :  81900, # LINE_WIDTH /  22 
    '但' :  81900, # LINE_WIDTH /  22 
    '達' :  81900, # LINE_WIDTH /  22 
    '辰' :  81900, # LINE_WIDTH /  22 
    '奪' :  81900, # LINE_WIDTH /  22 
    '脱' :  81900, # LINE_WIDTH /  22 
    '巽' :  81900, # LINE_WIDTH /  22 
    '竪' :  81900, # LINE_WIDTH /  22 
    '辿' :  81900, # LINE_WIDTH /  22 
    '棚' :  81900, # LINE_WIDTH /  22 
    '谷' :  81900, # LINE_WIDTH /  22 
    '狸' :  81900, # LINE_WIDTH /  22 
    '鱈' :  81900, # LINE_WIDTH /  22 
    '樽' :  81900, # LINE_WIDTH /  22 
    '誰' :  81900, # LINE_WIDTH /  22 
    '丹' :  81900, # LINE_WIDTH /  22 
    '単' :  81900, # LINE_WIDTH /  22 
    '嘆' :  81900, # LINE_WIDTH /  22 
    '坦' :  81900, # LINE_WIDTH /  22 
    '担' :  81900, # LINE_WIDTH /  22 
    '探' :  81900, # LINE_WIDTH /  22 
    '旦' :  81900, # LINE_WIDTH /  22 
    '歎' :  81900, # LINE_WIDTH /  22 
    '淡' :  81900, # LINE_WIDTH /  22 
    '湛' :  81900, # LINE_WIDTH /  22 
    '炭' :  81900, # LINE_WIDTH /  22 
    '短' :  81900, # LINE_WIDTH /  22 
    '端' :  81900, # LINE_WIDTH /  22 
    '箪' :  81900, # LINE_WIDTH /  22 
    '綻' :  81900, # LINE_WIDTH /  22 
    '耽' :  81900, # LINE_WIDTH /  22 
    '胆' :  81900, # LINE_WIDTH /  22 
    '蛋' :  81900, # LINE_WIDTH /  22 
    '誕' :  81900, # LINE_WIDTH /  22 
    '鍛' :  81900, # LINE_WIDTH /  22 
    '団' :  81900, # LINE_WIDTH /  22 
    '壇' :  81900, # LINE_WIDTH /  22 
    '弾' :  81900, # LINE_WIDTH /  22 
    '断' :  81900, # LINE_WIDTH /  22 
    '暖' :  81900, # LINE_WIDTH /  22 
    '檀' :  81900, # LINE_WIDTH /  22 
    '段' :  81900, # LINE_WIDTH /  22 
    '男' :  81900, # LINE_WIDTH /  22 
    '談' :  81900, # LINE_WIDTH /  22 
    '値' :  81900, # LINE_WIDTH /  22 
    '知' :  81900, # LINE_WIDTH /  22 
    '地' :  81900, # LINE_WIDTH /  22 
    '弛' :  81900, # LINE_WIDTH /  22 
    '恥' :  81900, # LINE_WIDTH /  22 
    '智' :  81900, # LINE_WIDTH /  22 
    '池' :  81900, # LINE_WIDTH /  22 
    '痴' :  81900, # LINE_WIDTH /  22 
    '稚' :  81900, # LINE_WIDTH /  22 
    '置' :  81900, # LINE_WIDTH /  22 
    '致' :  81900, # LINE_WIDTH /  22 
    '蜘' :  81900, # LINE_WIDTH /  22 
    '遅' :  81900, # LINE_WIDTH /  22 
    '馳' :  81900, # LINE_WIDTH /  22 
    '築' :  81900, # LINE_WIDTH /  22 
    '畜' :  81900, # LINE_WIDTH /  22 
    '竹' :  81900, # LINE_WIDTH /  22 
    '筑' :  81900, # LINE_WIDTH /  22 
    '蓄' :  81900, # LINE_WIDTH /  22 
    '逐' :  81900, # LINE_WIDTH /  22 
    '秩' :  81900, # LINE_WIDTH /  22 
    '窒' :  81900, # LINE_WIDTH /  22 
    '茶' :  81900, # LINE_WIDTH /  22 
    '嫡' :  81900, # LINE_WIDTH /  22 
    '着' :  81900, # LINE_WIDTH /  22 
    '中' :  81900, # LINE_WIDTH /  22 
    '仲' :  81900, # LINE_WIDTH /  22 
    '宙' :  81900, # LINE_WIDTH /  22 
    '忠' :  81900, # LINE_WIDTH /  22 
    '抽' :  81900, # LINE_WIDTH /  22 
    '昼' :  81900, # LINE_WIDTH /  22 
    '柱' :  81900, # LINE_WIDTH /  22 
    '注' :  81900, # LINE_WIDTH /  22 
    '虫' :  81900, # LINE_WIDTH /  22 
    '衷' :  81900, # LINE_WIDTH /  22 
    '註' :  81900, # LINE_WIDTH /  22 
    '酎' :  81900, # LINE_WIDTH /  22 
    '鋳' :  81900, # LINE_WIDTH /  22 
    '駐' :  81900, # LINE_WIDTH /  22 
    '樗' :  81900, # LINE_WIDTH /  22 
    '瀦' :  81900, # LINE_WIDTH /  22 
    '猪' :  81900, # LINE_WIDTH /  22 
    '苧' :  81900, # LINE_WIDTH /  22 
    '著' :  81900, # LINE_WIDTH /  22 
    '貯' :  81900, # LINE_WIDTH /  22 
    '丁' :  81900, # LINE_WIDTH /  22 
    '兆' :  81900, # LINE_WIDTH /  22 
    '凋' :  81900, # LINE_WIDTH /  22 
    '喋' :  81900, # LINE_WIDTH /  22 
    '寵' :  81900, # LINE_WIDTH /  22 
    '帖' :  81900, # LINE_WIDTH /  22 
    '帳' :  81900, # LINE_WIDTH /  22 
    '庁' :  81900, # LINE_WIDTH /  22 
    '弔' :  81900, # LINE_WIDTH /  22 
    '張' :  81900, # LINE_WIDTH /  22 
    '彫' :  81900, # LINE_WIDTH /  22 
    '徴' :  81900, # LINE_WIDTH /  22 
    '懲' :  81900, # LINE_WIDTH /  22 
    '挑' :  81900, # LINE_WIDTH /  22 
    '暢' :  81900, # LINE_WIDTH /  22 
    '朝' :  81900, # LINE_WIDTH /  22 
    '潮' :  81900, # LINE_WIDTH /  22 
    '牒' :  81900, # LINE_WIDTH /  22 
    '町' :  81900, # LINE_WIDTH /  22 
    '眺' :  81900, # LINE_WIDTH /  22 
    '聴' :  81900, # LINE_WIDTH /  22 
    '脹' :  81900, # LINE_WIDTH /  22 
    '腸' :  81900, # LINE_WIDTH /  22 
    '蝶' :  81900, # LINE_WIDTH /  22 
    '調' :  81900, # LINE_WIDTH /  22 
    '諜' :  81900, # LINE_WIDTH /  22 
    '超' :  81900, # LINE_WIDTH /  22 
    '跳' :  81900, # LINE_WIDTH /  22 
    '銚' :  81900, # LINE_WIDTH /  22 
    '長' :  81900, # LINE_WIDTH /  22 
    '頂' :  81900, # LINE_WIDTH /  22 
    '鳥' :  81900, # LINE_WIDTH /  22 
    '勅' :  81900, # LINE_WIDTH /  22 
    '捗' :  81900, # LINE_WIDTH /  22 
    '直' :  81900, # LINE_WIDTH /  22 
    '朕' :  81900, # LINE_WIDTH /  22 
    '沈' :  81900, # LINE_WIDTH /  22 
    '珍' :  81900, # LINE_WIDTH /  22 
    '賃' :  81900, # LINE_WIDTH /  22 
    '鎮' :  81900, # LINE_WIDTH /  22 
    '陳' :  81900, # LINE_WIDTH /  22 
    '津' :  81900, # LINE_WIDTH /  22 
    '墜' :  81900, # LINE_WIDTH /  22 
    '椎' :  81900, # LINE_WIDTH /  22 
    '槌' :  81900, # LINE_WIDTH /  22 
    '追' :  81900, # LINE_WIDTH /  22 
    '鎚' :  81900, # LINE_WIDTH /  22 
    '痛' :  81900, # LINE_WIDTH /  22 
    '通' :  81900, # LINE_WIDTH /  22 
    '塚' :  81900, # LINE_WIDTH /  22 
    '栂' :  81900, # LINE_WIDTH /  22 
    '掴' :  81900, # LINE_WIDTH /  22 
    '槻' :  81900, # LINE_WIDTH /  22 
    '佃' :  81900, # LINE_WIDTH /  22 
    '漬' :  81900, # LINE_WIDTH /  22 
    '柘' :  81900, # LINE_WIDTH /  22 
    '辻' :  81900, # LINE_WIDTH /  22 
    '蔦' :  81900, # LINE_WIDTH /  22 
    '綴' :  81900, # LINE_WIDTH /  22 
    '鍔' :  81900, # LINE_WIDTH /  22 
    '椿' :  81900, # LINE_WIDTH /  22 
    '潰' :  81900, # LINE_WIDTH /  22 
    '坪' :  81900, # LINE_WIDTH /  22 
    '壷' :  81900, # LINE_WIDTH /  22 
    '嬬' :  81900, # LINE_WIDTH /  22 
    '紬' :  81900, # LINE_WIDTH /  22 
    '爪' :  81900, # LINE_WIDTH /  22 
    '吊' :  81900, # LINE_WIDTH /  22 
    '釣' :  81900, # LINE_WIDTH /  22 
    '鶴' :  81900, # LINE_WIDTH /  22 
    '亭' :  81900, # LINE_WIDTH /  22 
    '低' :  81900, # LINE_WIDTH /  22 
    '停' :  81900, # LINE_WIDTH /  22 
    '偵' :  81900, # LINE_WIDTH /  22 
    '剃' :  81900, # LINE_WIDTH /  22 
    '貞' :  81900, # LINE_WIDTH /  22 
    '呈' :  81900, # LINE_WIDTH /  22 
    '堤' :  81900, # LINE_WIDTH /  22 
    '定' :  81900, # LINE_WIDTH /  22 
    '帝' :  81900, # LINE_WIDTH /  22 
    '底' :  81900, # LINE_WIDTH /  22 
    '庭' :  81900, # LINE_WIDTH /  22 
    '廷' :  81900, # LINE_WIDTH /  22 
    '弟' :  81900, # LINE_WIDTH /  22 
    '悌' :  81900, # LINE_WIDTH /  22 
    '抵' :  81900, # LINE_WIDTH /  22 
    '挺' :  81900, # LINE_WIDTH /  22 
    '提' :  81900, # LINE_WIDTH /  22 
    '梯' :  81900, # LINE_WIDTH /  22 
    '汀' :  81900, # LINE_WIDTH /  22 
    '碇' :  81900, # LINE_WIDTH /  22 
    '禎' :  81900, # LINE_WIDTH /  22 
    '程' :  81900, # LINE_WIDTH /  22 
    '締' :  81900, # LINE_WIDTH /  22 
    '艇' :  81900, # LINE_WIDTH /  22 
    '訂' :  81900, # LINE_WIDTH /  22 
    '諦' :  81900, # LINE_WIDTH /  22 
    '蹄' :  81900, # LINE_WIDTH /  22 
    '逓' :  81900, # LINE_WIDTH /  22 
    '邸' :  81900, # LINE_WIDTH /  22 
    '鄭' :  81900, # LINE_WIDTH /  22 
    '釘' :  81900, # LINE_WIDTH /  22 
    '鼎' :  81900, # LINE_WIDTH /  22 
    '泥' :  81900, # LINE_WIDTH /  22 
    '摘' :  81900, # LINE_WIDTH /  22 
    '擢' :  81900, # LINE_WIDTH /  22 
    '敵' :  81900, # LINE_WIDTH /  22 
    '滴' :  81900, # LINE_WIDTH /  22 
    '的' :  81900, # LINE_WIDTH /  22 
    '笛' :  81900, # LINE_WIDTH /  22 
    '適' :  81900, # LINE_WIDTH /  22 
    '鏑' :  81900, # LINE_WIDTH /  22 
    '溺' :  81900, # LINE_WIDTH /  22 
    '哲' :  81900, # LINE_WIDTH /  22 
    '徹' :  81900, # LINE_WIDTH /  22 
    '撤' :  81900, # LINE_WIDTH /  22 
    '轍' :  81900, # LINE_WIDTH /  22 
    '迭' :  81900, # LINE_WIDTH /  22 
    '鉄' :  81900, # LINE_WIDTH /  22 
    '典' :  81900, # LINE_WIDTH /  22 
    '填' :  81900, # LINE_WIDTH /  22 
    '天' :  81900, # LINE_WIDTH /  22 
    '展' :  81900, # LINE_WIDTH /  22 
    '店' :  81900, # LINE_WIDTH /  22 
    '添' :  81900, # LINE_WIDTH /  22 
    '纏' :  81900, # LINE_WIDTH /  22 
    '甜' :  81900, # LINE_WIDTH /  22 
    '貼' :  81900, # LINE_WIDTH /  22 
    '転' :  81900, # LINE_WIDTH /  22 
    '顛' :  81900, # LINE_WIDTH /  22 
    '点' :  81900, # LINE_WIDTH /  22 
    '伝' :  81900, # LINE_WIDTH /  22 
    '殿' :  81900, # LINE_WIDTH /  22 
    '澱' :  81900, # LINE_WIDTH /  22 
    '田' :  81900, # LINE_WIDTH /  22 
    '電' :  81900, # LINE_WIDTH /  22 
    '兎' :  81900, # LINE_WIDTH /  22 
    '吐' :  81900, # LINE_WIDTH /  22 
    '堵' :  81900, # LINE_WIDTH /  22 
    '塗' :  81900, # LINE_WIDTH /  22 
    '妬' :  81900, # LINE_WIDTH /  22 
    '屠' :  81900, # LINE_WIDTH /  22 
    '徒' :  81900, # LINE_WIDTH /  22 
    '斗' :  81900, # LINE_WIDTH /  22 
    '杜' :  81900, # LINE_WIDTH /  22 
    '渡' :  81900, # LINE_WIDTH /  22 
    '登' :  81900, # LINE_WIDTH /  22 
    '菟' :  81900, # LINE_WIDTH /  22 
    '賭' :  81900, # LINE_WIDTH /  22 
    '途' :  81900, # LINE_WIDTH /  22 
    '都' :  81900, # LINE_WIDTH /  22 
    '鍍' :  81900, # LINE_WIDTH /  22 
    '砥' :  81900, # LINE_WIDTH /  22 
    '砺' :  81900, # LINE_WIDTH /  22 
    '努' :  81900, # LINE_WIDTH /  22 
    '度' :  81900, # LINE_WIDTH /  22 
    '土' :  81900, # LINE_WIDTH /  22 
    '奴' :  81900, # LINE_WIDTH /  22 
    '怒' :  81900, # LINE_WIDTH /  22 
    '倒' :  81900, # LINE_WIDTH /  22 
    '党' :  81900, # LINE_WIDTH /  22 
    '冬' :  81900, # LINE_WIDTH /  22 
    '凍' :  81900, # LINE_WIDTH /  22 
    '刀' :  81900, # LINE_WIDTH /  22 
    '唐' :  81900, # LINE_WIDTH /  22 
    '塔' :  81900, # LINE_WIDTH /  22 
    '塘' :  81900, # LINE_WIDTH /  22 
    '套' :  81900, # LINE_WIDTH /  22 
    '宕' :  81900, # LINE_WIDTH /  22 
    '島' :  81900, # LINE_WIDTH /  22 
    '嶋' :  81900, # LINE_WIDTH /  22 
    '悼' :  81900, # LINE_WIDTH /  22 
    '投' :  81900, # LINE_WIDTH /  22 
    '搭' :  81900, # LINE_WIDTH /  22 
    '東' :  81900, # LINE_WIDTH /  22 
    '桃' :  81900, # LINE_WIDTH /  22 
    '梼' :  81900, # LINE_WIDTH /  22 
    '棟' :  81900, # LINE_WIDTH /  22 
    '盗' :  81900, # LINE_WIDTH /  22 
    '淘' :  81900, # LINE_WIDTH /  22 
    '湯' :  81900, # LINE_WIDTH /  22 
    '涛' :  81900, # LINE_WIDTH /  22 
    '灯' :  81900, # LINE_WIDTH /  22 
    '燈' :  81900, # LINE_WIDTH /  22 
    '当' :  81900, # LINE_WIDTH /  22 
    '痘' :  81900, # LINE_WIDTH /  22 
    '祷' :  81900, # LINE_WIDTH /  22 
    '等' :  81900, # LINE_WIDTH /  22 
    '答' :  81900, # LINE_WIDTH /  22 
    '筒' :  81900, # LINE_WIDTH /  22 
    '糖' :  81900, # LINE_WIDTH /  22 
    '統' :  81900, # LINE_WIDTH /  22 
    '到' :  81900, # LINE_WIDTH /  22 
    '董' :  81900, # LINE_WIDTH /  22 
    '蕩' :  81900, # LINE_WIDTH /  22 
    '藤' :  81900, # LINE_WIDTH /  22 
    '討' :  81900, # LINE_WIDTH /  22 
    '謄' :  81900, # LINE_WIDTH /  22 
    '豆' :  81900, # LINE_WIDTH /  22 
    '踏' :  81900, # LINE_WIDTH /  22 
    '逃' :  81900, # LINE_WIDTH /  22 
    '透' :  81900, # LINE_WIDTH /  22 
    '鐙' :  81900, # LINE_WIDTH /  22 
    '陶' :  81900, # LINE_WIDTH /  22 
    '頭' :  81900, # LINE_WIDTH /  22 
    '騰' :  81900, # LINE_WIDTH /  22 
    '闘' :  81900, # LINE_WIDTH /  22 
    '働' :  81900, # LINE_WIDTH /  22 
    '動' :  81900, # LINE_WIDTH /  22 
    '同' :  81900, # LINE_WIDTH /  22 
    '堂' :  81900, # LINE_WIDTH /  22 
    '導' :  81900, # LINE_WIDTH /  22 
    '憧' :  81900, # LINE_WIDTH /  22 
    '撞' :  81900, # LINE_WIDTH /  22 
    '洞' :  81900, # LINE_WIDTH /  22 
    '瞳' :  81900, # LINE_WIDTH /  22 
    '童' :  81900, # LINE_WIDTH /  22 
    '胴' :  81900, # LINE_WIDTH /  22 
    '萄' :  81900, # LINE_WIDTH /  22 
    '道' :  81900, # LINE_WIDTH /  22 
    '銅' :  81900, # LINE_WIDTH /  22 
    '峠' :  81900, # LINE_WIDTH /  22 
    '鴇' :  81900, # LINE_WIDTH /  22 
    '匿' :  81900, # LINE_WIDTH /  22 
    '得' :  81900, # LINE_WIDTH /  22 
    '徳' :  81900, # LINE_WIDTH /  22 
    '涜' :  81900, # LINE_WIDTH /  22 
    '特' :  81900, # LINE_WIDTH /  22 
    '督' :  81900, # LINE_WIDTH /  22 
    '禿' :  81900, # LINE_WIDTH /  22 
    '篤' :  81900, # LINE_WIDTH /  22 
    '毒' :  81900, # LINE_WIDTH /  22 
    '独' :  81900, # LINE_WIDTH /  22 
    '読' :  81900, # LINE_WIDTH /  22 
    '栃' :  81900, # LINE_WIDTH /  22 
    '橡' :  81900, # LINE_WIDTH /  22 
    '凸' :  81900, # LINE_WIDTH /  22 
    '突' :  81900, # LINE_WIDTH /  22 
    '椴' :  81900, # LINE_WIDTH /  22 
    '届' :  81900, # LINE_WIDTH /  22 
    '鳶' :  81900, # LINE_WIDTH /  22 
    '苫' :  81900, # LINE_WIDTH /  22 
    '寅' :  81900, # LINE_WIDTH /  22 
    '酉' :  81900, # LINE_WIDTH /  22 
    '瀞' :  81900, # LINE_WIDTH /  22 
    '噸' :  81900, # LINE_WIDTH /  22 
    '屯' :  81900, # LINE_WIDTH /  22 
    '惇' :  81900, # LINE_WIDTH /  22 
    '敦' :  81900, # LINE_WIDTH /  22 
    '沌' :  81900, # LINE_WIDTH /  22 
    '豚' :  81900, # LINE_WIDTH /  22 
    '遁' :  81900, # LINE_WIDTH /  22 
    '頓' :  81900, # LINE_WIDTH /  22 
    '呑' :  81900, # LINE_WIDTH /  22 
    '曇' :  81900, # LINE_WIDTH /  22 
    '鈍' :  81900, # LINE_WIDTH /  22 
    '奈' :  81900, # LINE_WIDTH /  22 
    '那' :  81900, # LINE_WIDTH /  22 
    '内' :  81900, # LINE_WIDTH /  22 
    '乍' :  81900, # LINE_WIDTH /  22 
    '凪' :  81900, # LINE_WIDTH /  22 
    '薙' :  81900, # LINE_WIDTH /  22 
    '謎' :  81900, # LINE_WIDTH /  22 
    '灘' :  81900, # LINE_WIDTH /  22 
    '捺' :  81900, # LINE_WIDTH /  22 
    '鍋' :  81900, # LINE_WIDTH /  22 
    '楢' :  81900, # LINE_WIDTH /  22 
    '馴' :  81900, # LINE_WIDTH /  22 
    '縄' :  81900, # LINE_WIDTH /  22 
    '畷' :  81900, # LINE_WIDTH /  22 
    '南' :  81900, # LINE_WIDTH /  22 
    '楠' :  81900, # LINE_WIDTH /  22 
    '軟' :  81900, # LINE_WIDTH /  22 
    '難' :  81900, # LINE_WIDTH /  22 
    '汝' :  81900, # LINE_WIDTH /  22 
    '二' :  81900, # LINE_WIDTH /  22 
    '尼' :  81900, # LINE_WIDTH /  22 
    '弐' :  81900, # LINE_WIDTH /  22 
    '迩' :  81900, # LINE_WIDTH /  22 
    '匂' :  81900, # LINE_WIDTH /  22 
    '賑' :  81900, # LINE_WIDTH /  22 
    '肉' :  81900, # LINE_WIDTH /  22 
    '虹' :  81900, # LINE_WIDTH /  22 
    '廿' :  81900, # LINE_WIDTH /  22 
    '日' :  81900, # LINE_WIDTH /  22 
    '乳' :  81900, # LINE_WIDTH /  22 
    '入' :  81900, # LINE_WIDTH /  22 
    '如' :  81900, # LINE_WIDTH /  22 
    '尿' :  81900, # LINE_WIDTH /  22 
    '韮' :  81900, # LINE_WIDTH /  22 
    '任' :  81900, # LINE_WIDTH /  22 
    '妊' :  81900, # LINE_WIDTH /  22 
    '忍' :  81900, # LINE_WIDTH /  22 
    '認' :  81900, # LINE_WIDTH /  22 
    '濡' :  81900, # LINE_WIDTH /  22 
    '禰' :  81900, # LINE_WIDTH /  22 
    '祢' :  81900, # LINE_WIDTH /  22 
    '寧' :  81900, # LINE_WIDTH /  22 
    '葱' :  81900, # LINE_WIDTH /  22 
    '猫' :  81900, # LINE_WIDTH /  22 
    '熱' :  81900, # LINE_WIDTH /  22 
    '年' :  81900, # LINE_WIDTH /  22 
    '念' :  81900, # LINE_WIDTH /  22 
    '捻' :  81900, # LINE_WIDTH /  22 
    '撚' :  81900, # LINE_WIDTH /  22 
    '燃' :  81900, # LINE_WIDTH /  22 
    '粘' :  81900, # LINE_WIDTH /  22 
    '乃' :  81900, # LINE_WIDTH /  22 
    '廼' :  81900, # LINE_WIDTH /  22 
    '之' :  81900, # LINE_WIDTH /  22 
    '埜' :  81900, # LINE_WIDTH /  22 
    '嚢' :  81900, # LINE_WIDTH /  22 
    '悩' :  81900, # LINE_WIDTH /  22 
    '濃' :  81900, # LINE_WIDTH /  22 
    '納' :  81900, # LINE_WIDTH /  22 
    '能' :  81900, # LINE_WIDTH /  22 
    '脳' :  81900, # LINE_WIDTH /  22 
    '膿' :  81900, # LINE_WIDTH /  22 
    '農' :  81900, # LINE_WIDTH /  22 
    '覗' :  81900, # LINE_WIDTH /  22 
    '蚤' :  81900, # LINE_WIDTH /  22 
    '巴' :  81900, # LINE_WIDTH /  22 
    '把' :  81900, # LINE_WIDTH /  22 
    '播' :  81900, # LINE_WIDTH /  22 
    '覇' :  81900, # LINE_WIDTH /  22 
    '杷' :  81900, # LINE_WIDTH /  22 
    '波' :  81900, # LINE_WIDTH /  22 
    '派' :  81900, # LINE_WIDTH /  22 
    '琶' :  81900, # LINE_WIDTH /  22 
    '破' :  81900, # LINE_WIDTH /  22 
    '婆' :  81900, # LINE_WIDTH /  22 
    '罵' :  81900, # LINE_WIDTH /  22 
    '芭' :  81900, # LINE_WIDTH /  22 
    '馬' :  81900, # LINE_WIDTH /  22 
    '俳' :  81900, # LINE_WIDTH /  22 
    '廃' :  81900, # LINE_WIDTH /  22 
    '拝' :  81900, # LINE_WIDTH /  22 
    '排' :  81900, # LINE_WIDTH /  22 
    '敗' :  81900, # LINE_WIDTH /  22 
    '杯' :  81900, # LINE_WIDTH /  22 
    '盃' :  81900, # LINE_WIDTH /  22 
    '牌' :  81900, # LINE_WIDTH /  22 
    '背' :  81900, # LINE_WIDTH /  22 
    '肺' :  81900, # LINE_WIDTH /  22 
    '輩' :  81900, # LINE_WIDTH /  22 
    '配' :  81900, # LINE_WIDTH /  22 
    '倍' :  81900, # LINE_WIDTH /  22 
    '培' :  81900, # LINE_WIDTH /  22 
    '媒' :  81900, # LINE_WIDTH /  22 
    '梅' :  81900, # LINE_WIDTH /  22 
    '楳' :  81900, # LINE_WIDTH /  22 
    '煤' :  81900, # LINE_WIDTH /  22 
    '狽' :  81900, # LINE_WIDTH /  22 
    '買' :  81900, # LINE_WIDTH /  22 
    '売' :  81900, # LINE_WIDTH /  22 
    '賠' :  81900, # LINE_WIDTH /  22 
    '陪' :  81900, # LINE_WIDTH /  22 
    '這' :  81900, # LINE_WIDTH /  22 
    '蝿' :  81900, # LINE_WIDTH /  22 
    '秤' :  81900, # LINE_WIDTH /  22 
    '矧' :  81900, # LINE_WIDTH /  22 
    '萩' :  81900, # LINE_WIDTH /  22 
    '伯' :  81900, # LINE_WIDTH /  22 
    '剥' :  81900, # LINE_WIDTH /  22 
    '博' :  81900, # LINE_WIDTH /  22 
    '拍' :  81900, # LINE_WIDTH /  22 
    '柏' :  81900, # LINE_WIDTH /  22 
    '泊' :  81900, # LINE_WIDTH /  22 
    '白' :  81900, # LINE_WIDTH /  22 
    '箔' :  81900, # LINE_WIDTH /  22 
    '粕' :  81900, # LINE_WIDTH /  22 
    '舶' :  81900, # LINE_WIDTH /  22 
    '薄' :  81900, # LINE_WIDTH /  22 
    '迫' :  81900, # LINE_WIDTH /  22 
    '曝' :  81900, # LINE_WIDTH /  22 
    '漠' :  81900, # LINE_WIDTH /  22 
    '爆' :  81900, # LINE_WIDTH /  22 
    '縛' :  81900, # LINE_WIDTH /  22 
    '莫' :  81900, # LINE_WIDTH /  22 
    '駁' :  81900, # LINE_WIDTH /  22 
    '麦' :  81900, # LINE_WIDTH /  22 
    '函' :  81900, # LINE_WIDTH /  22 
    '箱' :  81900, # LINE_WIDTH /  22 
    '硲' :  81900, # LINE_WIDTH /  22 
    '箸' :  81900, # LINE_WIDTH /  22 
    '肇' :  81900, # LINE_WIDTH /  22 
    '筈' :  81900, # LINE_WIDTH /  22 
    '櫨' :  81900, # LINE_WIDTH /  22 
    '幡' :  81900, # LINE_WIDTH /  22 
    '肌' :  81900, # LINE_WIDTH /  22 
    '畑' :  81900, # LINE_WIDTH /  22 
    '畠' :  81900, # LINE_WIDTH /  22 
    '八' :  81900, # LINE_WIDTH /  22 
    '鉢' :  81900, # LINE_WIDTH /  22 
    '溌' :  81900, # LINE_WIDTH /  22 
    '発' :  81900, # LINE_WIDTH /  22 
    '醗' :  81900, # LINE_WIDTH /  22 
    '髪' :  81900, # LINE_WIDTH /  22 
    '伐' :  81900, # LINE_WIDTH /  22 
    '罰' :  81900, # LINE_WIDTH /  22 
    '抜' :  81900, # LINE_WIDTH /  22 
    '筏' :  81900, # LINE_WIDTH /  22 
    '閥' :  81900, # LINE_WIDTH /  22 
    '鳩' :  81900, # LINE_WIDTH /  22 
    '噺' :  81900, # LINE_WIDTH /  22 
    '塙' :  81900, # LINE_WIDTH /  22 
    '蛤' :  81900, # LINE_WIDTH /  22 
    '隼' :  81900, # LINE_WIDTH /  22 
    '伴' :  81900, # LINE_WIDTH /  22 
    '判' :  81900, # LINE_WIDTH /  22 
    '半' :  81900, # LINE_WIDTH /  22 
    '反' :  81900, # LINE_WIDTH /  22 
    '叛' :  81900, # LINE_WIDTH /  22 
    '帆' :  81900, # LINE_WIDTH /  22 
    '搬' :  81900, # LINE_WIDTH /  22 
    '斑' :  81900, # LINE_WIDTH /  22 
    '板' :  81900, # LINE_WIDTH /  22 
    '氾' :  81900, # LINE_WIDTH /  22 
    '汎' :  81900, # LINE_WIDTH /  22 
    '版' :  81900, # LINE_WIDTH /  22 
    '犯' :  81900, # LINE_WIDTH /  22 
    '班' :  81900, # LINE_WIDTH /  22 
    '畔' :  81900, # LINE_WIDTH /  22 
    '繁' :  81900, # LINE_WIDTH /  22 
    '般' :  81900, # LINE_WIDTH /  22 
    '藩' :  81900, # LINE_WIDTH /  22 
    '販' :  81900, # LINE_WIDTH /  22 
    '範' :  81900, # LINE_WIDTH /  22 
    '釆' :  81900, # LINE_WIDTH /  22 
    '煩' :  81900, # LINE_WIDTH /  22 
    '頒' :  81900, # LINE_WIDTH /  22 
    '飯' :  81900, # LINE_WIDTH /  22 
    '挽' :  81900, # LINE_WIDTH /  22 
    '晩' :  81900, # LINE_WIDTH /  22 
    '番' :  81900, # LINE_WIDTH /  22 
    '盤' :  81900, # LINE_WIDTH /  22 
    '磐' :  81900, # LINE_WIDTH /  22 
    '蕃' :  81900, # LINE_WIDTH /  22 
    '蛮' :  81900, # LINE_WIDTH /  22 
    '匪' :  81900, # LINE_WIDTH /  22 
    '卑' :  81900, # LINE_WIDTH /  22 
    '否' :  81900, # LINE_WIDTH /  22 
    '妃' :  81900, # LINE_WIDTH /  22 
    '庇' :  81900, # LINE_WIDTH /  22 
    '彼' :  81900, # LINE_WIDTH /  22 
    '悲' :  81900, # LINE_WIDTH /  22 
    '扉' :  81900, # LINE_WIDTH /  22 
    '批' :  81900, # LINE_WIDTH /  22 
    '披' :  81900, # LINE_WIDTH /  22 
    '斐' :  81900, # LINE_WIDTH /  22 
    '比' :  81900, # LINE_WIDTH /  22 
    '泌' :  81900, # LINE_WIDTH /  22 
    '疲' :  81900, # LINE_WIDTH /  22 
    '皮' :  81900, # LINE_WIDTH /  22 
    '碑' :  81900, # LINE_WIDTH /  22 
    '秘' :  81900, # LINE_WIDTH /  22 
    '緋' :  81900, # LINE_WIDTH /  22 
    '罷' :  81900, # LINE_WIDTH /  22 
    '肥' :  81900, # LINE_WIDTH /  22 
    '被' :  81900, # LINE_WIDTH /  22 
    '誹' :  81900, # LINE_WIDTH /  22 
    '費' :  81900, # LINE_WIDTH /  22 
    '避' :  81900, # LINE_WIDTH /  22 
    '非' :  81900, # LINE_WIDTH /  22 
    '飛' :  81900, # LINE_WIDTH /  22 
    '樋' :  81900, # LINE_WIDTH /  22 
    '簸' :  81900, # LINE_WIDTH /  22 
    '備' :  81900, # LINE_WIDTH /  22 
    '尾' :  81900, # LINE_WIDTH /  22 
    '微' :  81900, # LINE_WIDTH /  22 
    '枇' :  81900, # LINE_WIDTH /  22 
    '毘' :  81900, # LINE_WIDTH /  22 
    '琵' :  81900, # LINE_WIDTH /  22 
    '眉' :  81900, # LINE_WIDTH /  22 
    '美' :  81900, # LINE_WIDTH /  22 
    '鼻' :  81900, # LINE_WIDTH /  22 
    '柊' :  81900, # LINE_WIDTH /  22 
    '稗' :  81900, # LINE_WIDTH /  22 
    '匹' :  81900, # LINE_WIDTH /  22 
    '疋' :  81900, # LINE_WIDTH /  22 
    '髭' :  81900, # LINE_WIDTH /  22 
    '彦' :  81900, # LINE_WIDTH /  22 
    '膝' :  81900, # LINE_WIDTH /  22 
    '菱' :  81900, # LINE_WIDTH /  22 
    '肘' :  81900, # LINE_WIDTH /  22 
    '弼' :  81900, # LINE_WIDTH /  22 
    '必' :  81900, # LINE_WIDTH /  22 
    '畢' :  81900, # LINE_WIDTH /  22 
    '筆' :  81900, # LINE_WIDTH /  22 
    '逼' :  81900, # LINE_WIDTH /  22 
    '桧' :  81900, # LINE_WIDTH /  22 
    '姫' :  81900, # LINE_WIDTH /  22 
    '媛' :  81900, # LINE_WIDTH /  22 
    '紐' :  81900, # LINE_WIDTH /  22 
    '百' :  81900, # LINE_WIDTH /  22 
    '謬' :  81900, # LINE_WIDTH /  22 
    '俵' :  81900, # LINE_WIDTH /  22 
    '彪' :  81900, # LINE_WIDTH /  22 
    '標' :  81900, # LINE_WIDTH /  22 
    '氷' :  81900, # LINE_WIDTH /  22 
    '漂' :  81900, # LINE_WIDTH /  22 
    '瓢' :  81900, # LINE_WIDTH /  22 
    '票' :  81900, # LINE_WIDTH /  22 
    '表' :  81900, # LINE_WIDTH /  22 
    '評' :  81900, # LINE_WIDTH /  22 
    '豹' :  81900, # LINE_WIDTH /  22 
    '廟' :  81900, # LINE_WIDTH /  22 
    '描' :  81900, # LINE_WIDTH /  22 
    '病' :  81900, # LINE_WIDTH /  22 
    '秒' :  81900, # LINE_WIDTH /  22 
    '苗' :  81900, # LINE_WIDTH /  22 
    '錨' :  81900, # LINE_WIDTH /  22 
    '鋲' :  81900, # LINE_WIDTH /  22 
    '蒜' :  81900, # LINE_WIDTH /  22 
    '蛭' :  81900, # LINE_WIDTH /  22 
    '鰭' :  81900, # LINE_WIDTH /  22 
    '品' :  81900, # LINE_WIDTH /  22 
    '彬' :  81900, # LINE_WIDTH /  22 
    '斌' :  81900, # LINE_WIDTH /  22 
    '浜' :  81900, # LINE_WIDTH /  22 
    '瀕' :  81900, # LINE_WIDTH /  22 
    '貧' :  81900, # LINE_WIDTH /  22 
    '賓' :  81900, # LINE_WIDTH /  22 
    '頻' :  81900, # LINE_WIDTH /  22 
    '敏' :  81900, # LINE_WIDTH /  22 
    '瓶' :  81900, # LINE_WIDTH /  22 
    '不' :  81900, # LINE_WIDTH /  22 
    '付' :  81900, # LINE_WIDTH /  22 
    '埠' :  81900, # LINE_WIDTH /  22 
    '夫' :  81900, # LINE_WIDTH /  22 
    '婦' :  81900, # LINE_WIDTH /  22 
    '富' :  81900, # LINE_WIDTH /  22 
    '冨' :  81900, # LINE_WIDTH /  22 
    '布' :  81900, # LINE_WIDTH /  22 
    '府' :  81900, # LINE_WIDTH /  22 
    '怖' :  81900, # LINE_WIDTH /  22 
    '扶' :  81900, # LINE_WIDTH /  22 
    '敷' :  81900, # LINE_WIDTH /  22 
    '斧' :  81900, # LINE_WIDTH /  22 
    '普' :  81900, # LINE_WIDTH /  22 
    '浮' :  81900, # LINE_WIDTH /  22 
    '父' :  81900, # LINE_WIDTH /  22 
    '符' :  81900, # LINE_WIDTH /  22 
    '腐' :  81900, # LINE_WIDTH /  22 
    '膚' :  81900, # LINE_WIDTH /  22 
    '芙' :  81900, # LINE_WIDTH /  22 
    '譜' :  81900, # LINE_WIDTH /  22 
    '負' :  81900, # LINE_WIDTH /  22 
    '賦' :  81900, # LINE_WIDTH /  22 
    '赴' :  81900, # LINE_WIDTH /  22 
    '阜' :  81900, # LINE_WIDTH /  22 
    '附' :  81900, # LINE_WIDTH /  22 
    '侮' :  81900, # LINE_WIDTH /  22 
    '撫' :  81900, # LINE_WIDTH /  22 
    '武' :  81900, # LINE_WIDTH /  22 
    '舞' :  81900, # LINE_WIDTH /  22 
    '葡' :  81900, # LINE_WIDTH /  22 
    '蕪' :  81900, # LINE_WIDTH /  22 
    '部' :  81900, # LINE_WIDTH /  22 
    '封' :  81900, # LINE_WIDTH /  22 
    '楓' :  81900, # LINE_WIDTH /  22 
    '風' :  81900, # LINE_WIDTH /  22 
    '葺' :  81900, # LINE_WIDTH /  22 
    '蕗' :  81900, # LINE_WIDTH /  22 
    '伏' :  81900, # LINE_WIDTH /  22 
    '副' :  81900, # LINE_WIDTH /  22 
    '復' :  81900, # LINE_WIDTH /  22 
    '幅' :  81900, # LINE_WIDTH /  22 
    '服' :  81900, # LINE_WIDTH /  22 
    '福' :  81900, # LINE_WIDTH /  22 
    '腹' :  81900, # LINE_WIDTH /  22 
    '複' :  81900, # LINE_WIDTH /  22 
    '覆' :  81900, # LINE_WIDTH /  22 
    '淵' :  81900, # LINE_WIDTH /  22 
    '弗' :  81900, # LINE_WIDTH /  22 
    '払' :  81900, # LINE_WIDTH /  22 
    '沸' :  81900, # LINE_WIDTH /  22 
    '仏' :  81900, # LINE_WIDTH /  22 
    '物' :  81900, # LINE_WIDTH /  22 
    '鮒' :  81900, # LINE_WIDTH /  22 
    '分' :  81900, # LINE_WIDTH /  22 
    '吻' :  81900, # LINE_WIDTH /  22 
    '噴' :  81900, # LINE_WIDTH /  22 
    '墳' :  81900, # LINE_WIDTH /  22 
    '憤' :  81900, # LINE_WIDTH /  22 
    '扮' :  81900, # LINE_WIDTH /  22 
    '焚' :  81900, # LINE_WIDTH /  22 
    '奮' :  81900, # LINE_WIDTH /  22 
    '粉' :  81900, # LINE_WIDTH /  22 
    '糞' :  81900, # LINE_WIDTH /  22 
    '紛' :  81900, # LINE_WIDTH /  22 
    '雰' :  81900, # LINE_WIDTH /  22 
    '文' :  81900, # LINE_WIDTH /  22 
    '聞' :  81900, # LINE_WIDTH /  22 
    '丙' :  81900, # LINE_WIDTH /  22 
    '併' :  81900, # LINE_WIDTH /  22 
    '兵' :  81900, # LINE_WIDTH /  22 
    '塀' :  81900, # LINE_WIDTH /  22 
    '幣' :  81900, # LINE_WIDTH /  22 
    '平' :  81900, # LINE_WIDTH /  22 
    '弊' :  81900, # LINE_WIDTH /  22 
    '柄' :  81900, # LINE_WIDTH /  22 
    '並' :  81900, # LINE_WIDTH /  22 
    '蔽' :  81900, # LINE_WIDTH /  22 
    '閉' :  81900, # LINE_WIDTH /  22 
    '陛' :  81900, # LINE_WIDTH /  22 
    '米' :  81900, # LINE_WIDTH /  22 
    '頁' :  81900, # LINE_WIDTH /  22 
    '僻' :  81900, # LINE_WIDTH /  22 
    '壁' :  81900, # LINE_WIDTH /  22 
    '癖' :  81900, # LINE_WIDTH /  22 
    '碧' :  81900, # LINE_WIDTH /  22 
    '別' :  81900, # LINE_WIDTH /  22 
    '瞥' :  81900, # LINE_WIDTH /  22 
    '蔑' :  81900, # LINE_WIDTH /  22 
    '箆' :  81900, # LINE_WIDTH /  22 
    '偏' :  81900, # LINE_WIDTH /  22 
    '変' :  81900, # LINE_WIDTH /  22 
    '片' :  81900, # LINE_WIDTH /  22 
    '篇' :  81900, # LINE_WIDTH /  22 
    '編' :  81900, # LINE_WIDTH /  22 
    '辺' :  81900, # LINE_WIDTH /  22 
    '返' :  81900, # LINE_WIDTH /  22 
    '遍' :  81900, # LINE_WIDTH /  22 
    '便' :  81900, # LINE_WIDTH /  22 
    '勉' :  81900, # LINE_WIDTH /  22 
    '娩' :  81900, # LINE_WIDTH /  22 
    '弁' :  81900, # LINE_WIDTH /  22 
    '鞭' :  81900, # LINE_WIDTH /  22 
    '保' :  81900, # LINE_WIDTH /  22 
    '舗' :  81900, # LINE_WIDTH /  22 
    '鋪' :  81900, # LINE_WIDTH /  22 
    '圃' :  81900, # LINE_WIDTH /  22 
    '捕' :  81900, # LINE_WIDTH /  22 
    '歩' :  81900, # LINE_WIDTH /  22 
    '甫' :  81900, # LINE_WIDTH /  22 
    '補' :  81900, # LINE_WIDTH /  22 
    '輔' :  81900, # LINE_WIDTH /  22 
    '穂' :  81900, # LINE_WIDTH /  22 
    '募' :  81900, # LINE_WIDTH /  22 
    '墓' :  81900, # LINE_WIDTH /  22 
    '慕' :  81900, # LINE_WIDTH /  22 
    '戊' :  81900, # LINE_WIDTH /  22 
    '暮' :  81900, # LINE_WIDTH /  22 
    '母' :  81900, # LINE_WIDTH /  22 
    '簿' :  81900, # LINE_WIDTH /  22 
    '菩' :  81900, # LINE_WIDTH /  22 
    '倣' :  81900, # LINE_WIDTH /  22 
    '俸' :  81900, # LINE_WIDTH /  22 
    '包' :  81900, # LINE_WIDTH /  22 
    '呆' :  81900, # LINE_WIDTH /  22 
    '報' :  81900, # LINE_WIDTH /  22 
    '奉' :  81900, # LINE_WIDTH /  22 
    '宝' :  81900, # LINE_WIDTH /  22 
    '峰' :  81900, # LINE_WIDTH /  22 
    '峯' :  81900, # LINE_WIDTH /  22 
    '崩' :  81900, # LINE_WIDTH /  22 
    '庖' :  81900, # LINE_WIDTH /  22 
    '抱' :  81900, # LINE_WIDTH /  22 
    '捧' :  81900, # LINE_WIDTH /  22 
    '放' :  81900, # LINE_WIDTH /  22 
    '方' :  81900, # LINE_WIDTH /  22 
    '朋' :  81900, # LINE_WIDTH /  22 
    '法' :  81900, # LINE_WIDTH /  22 
    '泡' :  81900, # LINE_WIDTH /  22 
    '烹' :  81900, # LINE_WIDTH /  22 
    '砲' :  81900, # LINE_WIDTH /  22 
    '縫' :  81900, # LINE_WIDTH /  22 
    '胞' :  81900, # LINE_WIDTH /  22 
    '芳' :  81900, # LINE_WIDTH /  22 
    '萌' :  81900, # LINE_WIDTH /  22 
    '蓬' :  81900, # LINE_WIDTH /  22 
    '蜂' :  81900, # LINE_WIDTH /  22 
    '褒' :  81900, # LINE_WIDTH /  22 
    '訪' :  81900, # LINE_WIDTH /  22 
    '豊' :  81900, # LINE_WIDTH /  22 
    '邦' :  81900, # LINE_WIDTH /  22 
    '鋒' :  81900, # LINE_WIDTH /  22 
    '飽' :  81900, # LINE_WIDTH /  22 
    '鳳' :  81900, # LINE_WIDTH /  22 
    '鵬' :  81900, # LINE_WIDTH /  22 
    '乏' :  81900, # LINE_WIDTH /  22 
    '亡' :  81900, # LINE_WIDTH /  22 
    '傍' :  81900, # LINE_WIDTH /  22 
    '剖' :  81900, # LINE_WIDTH /  22 
    '坊' :  81900, # LINE_WIDTH /  22 
    '妨' :  81900, # LINE_WIDTH /  22 
    '帽' :  81900, # LINE_WIDTH /  22 
    '忘' :  81900, # LINE_WIDTH /  22 
    '忙' :  81900, # LINE_WIDTH /  22 
    '房' :  81900, # LINE_WIDTH /  22 
    '暴' :  81900, # LINE_WIDTH /  22 
    '望' :  81900, # LINE_WIDTH /  22 
    '某' :  81900, # LINE_WIDTH /  22 
    '棒' :  81900, # LINE_WIDTH /  22 
    '冒' :  81900, # LINE_WIDTH /  22 
    '紡' :  81900, # LINE_WIDTH /  22 
    '肪' :  81900, # LINE_WIDTH /  22 
    '膨' :  81900, # LINE_WIDTH /  22 
    '謀' :  81900, # LINE_WIDTH /  22 
    '貌' :  81900, # LINE_WIDTH /  22 
    '貿' :  81900, # LINE_WIDTH /  22 
    '鉾' :  81900, # LINE_WIDTH /  22 
    '防' :  81900, # LINE_WIDTH /  22 
    '吠' :  81900, # LINE_WIDTH /  22 
    '頬' :  81900, # LINE_WIDTH /  22 
    '北' :  81900, # LINE_WIDTH /  22 
    '僕' :  81900, # LINE_WIDTH /  22 
    '卜' :  81900, # LINE_WIDTH /  22 
    '墨' :  81900, # LINE_WIDTH /  22 
    '撲' :  81900, # LINE_WIDTH /  22 
    '朴' :  81900, # LINE_WIDTH /  22 
    '牧' :  81900, # LINE_WIDTH /  22 
    '睦' :  81900, # LINE_WIDTH /  22 
    '穆' :  81900, # LINE_WIDTH /  22 
    '釦' :  81900, # LINE_WIDTH /  22 
    '勃' :  81900, # LINE_WIDTH /  22 
    '没' :  81900, # LINE_WIDTH /  22 
    '殆' :  81900, # LINE_WIDTH /  22 
    '堀' :  81900, # LINE_WIDTH /  22 
    '幌' :  81900, # LINE_WIDTH /  22 
    '奔' :  81900, # LINE_WIDTH /  22 
    '本' :  81900, # LINE_WIDTH /  22 
    '翻' :  81900, # LINE_WIDTH /  22 
    '凡' :  81900, # LINE_WIDTH /  22 
    '盆' :  81900, # LINE_WIDTH /  22 
    '摩' :  81900, # LINE_WIDTH /  22 
    '磨' :  81900, # LINE_WIDTH /  22 
    '魔' :  81900, # LINE_WIDTH /  22 
    '麻' :  81900, # LINE_WIDTH /  22 
    '埋' :  81900, # LINE_WIDTH /  22 
    '妹' :  81900, # LINE_WIDTH /  22 
    '昧' :  81900, # LINE_WIDTH /  22 
    '枚' :  81900, # LINE_WIDTH /  22 
    '毎' :  81900, # LINE_WIDTH /  22 
    '哩' :  81900, # LINE_WIDTH /  22 
    '槙' :  81900, # LINE_WIDTH /  22 
    '幕' :  81900, # LINE_WIDTH /  22 
    '膜' :  81900, # LINE_WIDTH /  22 
    '枕' :  81900, # LINE_WIDTH /  22 
    '鮪' :  81900, # LINE_WIDTH /  22 
    '柾' :  81900, # LINE_WIDTH /  22 
    '鱒' :  81900, # LINE_WIDTH /  22 
    '桝' :  81900, # LINE_WIDTH /  22 
    '亦' :  81900, # LINE_WIDTH /  22 
    '俣' :  81900, # LINE_WIDTH /  22 
    '又' :  81900, # LINE_WIDTH /  22 
    '抹' :  81900, # LINE_WIDTH /  22 
    '末' :  81900, # LINE_WIDTH /  22 
    '沫' :  81900, # LINE_WIDTH /  22 
    '迄' :  81900, # LINE_WIDTH /  22 
    '侭' :  81900, # LINE_WIDTH /  22 
    '繭' :  81900, # LINE_WIDTH /  22 
    '麿' :  81900, # LINE_WIDTH /  22 
    '万' :  81900, # LINE_WIDTH /  22 
    '慢' :  81900, # LINE_WIDTH /  22 
    '満' :  81900, # LINE_WIDTH /  22 
    '漫' :  81900, # LINE_WIDTH /  22 
    '蔓' :  81900, # LINE_WIDTH /  22 
    '味' :  81900, # LINE_WIDTH /  22 
    '未' :  81900, # LINE_WIDTH /  22 
    '魅' :  81900, # LINE_WIDTH /  22 
    '巳' :  81900, # LINE_WIDTH /  22 
    '箕' :  81900, # LINE_WIDTH /  22 
    '岬' :  81900, # LINE_WIDTH /  22 
    '密' :  81900, # LINE_WIDTH /  22 
    '蜜' :  81900, # LINE_WIDTH /  22 
    '湊' :  81900, # LINE_WIDTH /  22 
    '蓑' :  81900, # LINE_WIDTH /  22 
    '稔' :  81900, # LINE_WIDTH /  22 
    '脈' :  81900, # LINE_WIDTH /  22 
    '妙' :  81900, # LINE_WIDTH /  22 
    '粍' :  81900, # LINE_WIDTH /  22 
    '民' :  81900, # LINE_WIDTH /  22 
    '眠' :  81900, # LINE_WIDTH /  22 
    '務' :  81900, # LINE_WIDTH /  22 
    '夢' :  81900, # LINE_WIDTH /  22 
    '無' :  81900, # LINE_WIDTH /  22 
    '牟' :  81900, # LINE_WIDTH /  22 
    '矛' :  81900, # LINE_WIDTH /  22 
    '霧' :  81900, # LINE_WIDTH /  22 
    '鵡' :  81900, # LINE_WIDTH /  22 
    '椋' :  81900, # LINE_WIDTH /  22 
    '婿' :  81900, # LINE_WIDTH /  22 
    '娘' :  81900, # LINE_WIDTH /  22 
    '冥' :  81900, # LINE_WIDTH /  22 
    '名' :  81900, # LINE_WIDTH /  22 
    '命' :  81900, # LINE_WIDTH /  22 
    '明' :  81900, # LINE_WIDTH /  22 
    '盟' :  81900, # LINE_WIDTH /  22 
    '迷' :  81900, # LINE_WIDTH /  22 
    '銘' :  81900, # LINE_WIDTH /  22 
    '鳴' :  81900, # LINE_WIDTH /  22 
    '姪' :  81900, # LINE_WIDTH /  22 
    '牝' :  81900, # LINE_WIDTH /  22 
    '滅' :  81900, # LINE_WIDTH /  22 
    '免' :  81900, # LINE_WIDTH /  22 
    '棉' :  81900, # LINE_WIDTH /  22 
    '綿' :  81900, # LINE_WIDTH /  22 
    '緬' :  81900, # LINE_WIDTH /  22 
    '面' :  81900, # LINE_WIDTH /  22 
    '麺' :  81900, # LINE_WIDTH /  22 
    '摸' :  81900, # LINE_WIDTH /  22 
    '模' :  81900, # LINE_WIDTH /  22 
    '茂' :  81900, # LINE_WIDTH /  22 
    '妄' :  81900, # LINE_WIDTH /  22 
    '孟' :  81900, # LINE_WIDTH /  22 
    '毛' :  81900, # LINE_WIDTH /  22 
    '猛' :  81900, # LINE_WIDTH /  22 
    '盲' :  81900, # LINE_WIDTH /  22 
    '網' :  81900, # LINE_WIDTH /  22 
    '耗' :  81900, # LINE_WIDTH /  22 
    '蒙' :  81900, # LINE_WIDTH /  22 
    '儲' :  81900, # LINE_WIDTH /  22 
    '木' :  81900, # LINE_WIDTH /  22 
    '黙' :  81900, # LINE_WIDTH /  22 
    '目' :  81900, # LINE_WIDTH /  22 
    '杢' :  81900, # LINE_WIDTH /  22 
    '勿' :  81900, # LINE_WIDTH /  22 
    '餅' :  81900, # LINE_WIDTH /  22 
    '尤' :  81900, # LINE_WIDTH /  22 
    '戻' :  81900, # LINE_WIDTH /  22 
    '籾' :  81900, # LINE_WIDTH /  22 
    '貰' :  81900, # LINE_WIDTH /  22 
    '問' :  81900, # LINE_WIDTH /  22 
    '悶' :  81900, # LINE_WIDTH /  22 
    '紋' :  81900, # LINE_WIDTH /  22 
    '門' :  81900, # LINE_WIDTH /  22 
    '匁' :  81900, # LINE_WIDTH /  22 
    '也' :  81900, # LINE_WIDTH /  22 
    '冶' :  81900, # LINE_WIDTH /  22 
    '夜' :  81900, # LINE_WIDTH /  22 
    '爺' :  81900, # LINE_WIDTH /  22 
    '耶' :  81900, # LINE_WIDTH /  22 
    '野' :  81900, # LINE_WIDTH /  22 
    '弥' :  81900, # LINE_WIDTH /  22 
    '矢' :  81900, # LINE_WIDTH /  22 
    '厄' :  81900, # LINE_WIDTH /  22 
    '役' :  81900, # LINE_WIDTH /  22 
    '約' :  81900, # LINE_WIDTH /  22 
    '薬' :  81900, # LINE_WIDTH /  22 
    '訳' :  81900, # LINE_WIDTH /  22 
    '躍' :  81900, # LINE_WIDTH /  22 
    '靖' :  81900, # LINE_WIDTH /  22 
    '柳' :  81900, # LINE_WIDTH /  22 
    '薮' :  81900, # LINE_WIDTH /  22 
    '鑓' :  81900, # LINE_WIDTH /  22 
    '愉' :  81900, # LINE_WIDTH /  22 
    '愈' :  81900, # LINE_WIDTH /  22 
    '油' :  81900, # LINE_WIDTH /  22 
    '癒' :  81900, # LINE_WIDTH /  22 
    '諭' :  81900, # LINE_WIDTH /  22 
    '輸' :  81900, # LINE_WIDTH /  22 
    '唯' :  81900, # LINE_WIDTH /  22 
    '佑' :  81900, # LINE_WIDTH /  22 
    '優' :  81900, # LINE_WIDTH /  22 
    '勇' :  81900, # LINE_WIDTH /  22 
    '友' :  81900, # LINE_WIDTH /  22 
    '宥' :  81900, # LINE_WIDTH /  22 
    '幽' :  81900, # LINE_WIDTH /  22 
    '悠' :  81900, # LINE_WIDTH /  22 
    '憂' :  81900, # LINE_WIDTH /  22 
    '揖' :  81900, # LINE_WIDTH /  22 
    '有' :  81900, # LINE_WIDTH /  22 
    '柚' :  81900, # LINE_WIDTH /  22 
    '湧' :  81900, # LINE_WIDTH /  22 
    '涌' :  81900, # LINE_WIDTH /  22 
    '猶' :  81900, # LINE_WIDTH /  22 
    '猷' :  81900, # LINE_WIDTH /  22 
    '由' :  81900, # LINE_WIDTH /  22 
    '祐' :  81900, # LINE_WIDTH /  22 
    '裕' :  81900, # LINE_WIDTH /  22 
    '誘' :  81900, # LINE_WIDTH /  22 
    '遊' :  81900, # LINE_WIDTH /  22 
    '邑' :  81900, # LINE_WIDTH /  22 
    '郵' :  81900, # LINE_WIDTH /  22 
    '雄' :  81900, # LINE_WIDTH /  22 
    '融' :  81900, # LINE_WIDTH /  22 
    '夕' :  81900, # LINE_WIDTH /  22 
    '予' :  81900, # LINE_WIDTH /  22 
    '余' :  81900, # LINE_WIDTH /  22 
    '与' :  81900, # LINE_WIDTH /  22 
    '誉' :  81900, # LINE_WIDTH /  22 
    '輿' :  81900, # LINE_WIDTH /  22 
    '預' :  81900, # LINE_WIDTH /  22 
    '傭' :  81900, # LINE_WIDTH /  22 
    '幼' :  81900, # LINE_WIDTH /  22 
    '妖' :  81900, # LINE_WIDTH /  22 
    '容' :  81900, # LINE_WIDTH /  22 
    '庸' :  81900, # LINE_WIDTH /  22 
    '揚' :  81900, # LINE_WIDTH /  22 
    '揺' :  81900, # LINE_WIDTH /  22 
    '擁' :  81900, # LINE_WIDTH /  22 
    '曜' :  81900, # LINE_WIDTH /  22 
    '楊' :  81900, # LINE_WIDTH /  22 
    '様' :  81900, # LINE_WIDTH /  22 
    '洋' :  81900, # LINE_WIDTH /  22 
    '溶' :  81900, # LINE_WIDTH /  22 
    '熔' :  81900, # LINE_WIDTH /  22 
    '用' :  81900, # LINE_WIDTH /  22 
    '窯' :  81900, # LINE_WIDTH /  22 
    '羊' :  81900, # LINE_WIDTH /  22 
    '耀' :  81900, # LINE_WIDTH /  22 
    '葉' :  81900, # LINE_WIDTH /  22 
    '蓉' :  81900, # LINE_WIDTH /  22 
    '要' :  81900, # LINE_WIDTH /  22 
    '謡' :  81900, # LINE_WIDTH /  22 
    '踊' :  81900, # LINE_WIDTH /  22 
    '遥' :  81900, # LINE_WIDTH /  22 
    '陽' :  81900, # LINE_WIDTH /  22 
    '養' :  81900, # LINE_WIDTH /  22 
    '慾' :  81900, # LINE_WIDTH /  22 
    '抑' :  81900, # LINE_WIDTH /  22 
    '欲' :  81900, # LINE_WIDTH /  22 
    '沃' :  81900, # LINE_WIDTH /  22 
    '浴' :  81900, # LINE_WIDTH /  22 
    '翌' :  81900, # LINE_WIDTH /  22 
    '翼' :  81900, # LINE_WIDTH /  22 
    '淀' :  81900, # LINE_WIDTH /  22 
    '羅' :  81900, # LINE_WIDTH /  22 
    '螺' :  81900, # LINE_WIDTH /  22 
    '裸' :  81900, # LINE_WIDTH /  22 
    '来' :  81900, # LINE_WIDTH /  22 
    '莱' :  81900, # LINE_WIDTH /  22 
    '頼' :  81900, # LINE_WIDTH /  22 
    '雷' :  81900, # LINE_WIDTH /  22 
    '洛' :  81900, # LINE_WIDTH /  22 
    '絡' :  81900, # LINE_WIDTH /  22 
    '落' :  81900, # LINE_WIDTH /  22 
    '酪' :  81900, # LINE_WIDTH /  22 
    '乱' :  81900, # LINE_WIDTH /  22 
    '卵' :  81900, # LINE_WIDTH /  22 
    '嵐' :  81900, # LINE_WIDTH /  22 
    '欄' :  81900, # LINE_WIDTH /  22 
    '濫' :  81900, # LINE_WIDTH /  22 
    '藍' :  81900, # LINE_WIDTH /  22 
    '蘭' :  81900, # LINE_WIDTH /  22 
    '覧' :  81900, # LINE_WIDTH /  22 
    '利' :  81900, # LINE_WIDTH /  22 
    '吏' :  81900, # LINE_WIDTH /  22 
    '履' :  81900, # LINE_WIDTH /  22 
    '李' :  81900, # LINE_WIDTH /  22 
    '梨' :  81900, # LINE_WIDTH /  22 
    '理' :  81900, # LINE_WIDTH /  22 
    '璃' :  81900, # LINE_WIDTH /  22 
    '痢' :  81900, # LINE_WIDTH /  22 
    '裏' :  81900, # LINE_WIDTH /  22 
    '裡' :  81900, # LINE_WIDTH /  22 
    '里' :  81900, # LINE_WIDTH /  22 
    '離' :  81900, # LINE_WIDTH /  22 
    '陸' :  81900, # LINE_WIDTH /  22 
    '律' :  81900, # LINE_WIDTH /  22 
    '率' :  81900, # LINE_WIDTH /  22 
    '立' :  81900, # LINE_WIDTH /  22 
    '葎' :  81900, # LINE_WIDTH /  22 
    '掠' :  81900, # LINE_WIDTH /  22 
    '略' :  81900, # LINE_WIDTH /  22 
    '劉' :  81900, # LINE_WIDTH /  22 
    '流' :  81900, # LINE_WIDTH /  22 
    '溜' :  81900, # LINE_WIDTH /  22 
    '琉' :  81900, # LINE_WIDTH /  22 
    '留' :  81900, # LINE_WIDTH /  22 
    '硫' :  81900, # LINE_WIDTH /  22 
    '粒' :  81900, # LINE_WIDTH /  22 
    '隆' :  81900, # LINE_WIDTH /  22 
    '竜' :  81900, # LINE_WIDTH /  22 
    '龍' :  81900, # LINE_WIDTH /  22 
    '侶' :  81900, # LINE_WIDTH /  22 
    '慮' :  81900, # LINE_WIDTH /  22 
    '旅' :  81900, # LINE_WIDTH /  22 
    '虜' :  81900, # LINE_WIDTH /  22 
    '了' :  81900, # LINE_WIDTH /  22 
    '亮' :  81900, # LINE_WIDTH /  22 
    '僚' :  81900, # LINE_WIDTH /  22 
    '両' :  81900, # LINE_WIDTH /  22 
    '凌' :  81900, # LINE_WIDTH /  22 
    '寮' :  81900, # LINE_WIDTH /  22 
    '料' :  81900, # LINE_WIDTH /  22 
    '梁' :  81900, # LINE_WIDTH /  22 
    '涼' :  81900, # LINE_WIDTH /  22 
    '猟' :  81900, # LINE_WIDTH /  22 
    '療' :  81900, # LINE_WIDTH /  22 
    '瞭' :  81900, # LINE_WIDTH /  22 
    '稜' :  81900, # LINE_WIDTH /  22 
    '糧' :  81900, # LINE_WIDTH /  22 
    '良' :  81900, # LINE_WIDTH /  22 
    '諒' :  81900, # LINE_WIDTH /  22 
    '遼' :  81900, # LINE_WIDTH /  22 
    '量' :  81900, # LINE_WIDTH /  22 
    '陵' :  81900, # LINE_WIDTH /  22 
    '領' :  81900, # LINE_WIDTH /  22 
    '力' :  81900, # LINE_WIDTH /  22 
    '緑' :  81900, # LINE_WIDTH /  22 
    '倫' :  81900, # LINE_WIDTH /  22 
    '厘' :  81900, # LINE_WIDTH /  22 
    '林' :  81900, # LINE_WIDTH /  22 
    '淋' :  81900, # LINE_WIDTH /  22 
    '燐' :  81900, # LINE_WIDTH /  22 
    '琳' :  81900, # LINE_WIDTH /  22 
    '臨' :  81900, # LINE_WIDTH /  22 
    '輪' :  81900, # LINE_WIDTH /  22 
    '隣' :  81900, # LINE_WIDTH /  22 
    '鱗' :  81900, # LINE_WIDTH /  22 
    '麟' :  81900, # LINE_WIDTH /  22 
    '瑠' :  81900, # LINE_WIDTH /  22 
    '塁' :  81900, # LINE_WIDTH /  22 
    '涙' :  81900, # LINE_WIDTH /  22 
    '累' :  81900, # LINE_WIDTH /  22 
    '類' :  81900, # LINE_WIDTH /  22 
    '令' :  81900, # LINE_WIDTH /  22 
    '伶' :  81900, # LINE_WIDTH /  22 
    '例' :  81900, # LINE_WIDTH /  22 
    '冷' :  81900, # LINE_WIDTH /  22 
    '励' :  81900, # LINE_WIDTH /  22 
    '嶺' :  81900, # LINE_WIDTH /  22 
    '怜' :  81900, # LINE_WIDTH /  22 
    '玲' :  81900, # LINE_WIDTH /  22 
    '礼' :  81900, # LINE_WIDTH /  22 
    '苓' :  81900, # LINE_WIDTH /  22 
    '鈴' :  81900, # LINE_WIDTH /  22 
    '隷' :  81900, # LINE_WIDTH /  22 
    '零' :  81900, # LINE_WIDTH /  22 
    '霊' :  81900, # LINE_WIDTH /  22 
    '麗' :  81900, # LINE_WIDTH /  22 
    '齢' :  81900, # LINE_WIDTH /  22 
    '暦' :  81900, # LINE_WIDTH /  22 
    '歴' :  81900, # LINE_WIDTH /  22 
    '列' :  81900, # LINE_WIDTH /  22 
    '劣' :  81900, # LINE_WIDTH /  22 
    '烈' :  81900, # LINE_WIDTH /  22 
    '裂' :  81900, # LINE_WIDTH /  22 
    '廉' :  81900, # LINE_WIDTH /  22 
    '恋' :  81900, # LINE_WIDTH /  22 
    '憐' :  81900, # LINE_WIDTH /  22 
    '漣' :  81900, # LINE_WIDTH /  22 
    '煉' :  81900, # LINE_WIDTH /  22 
    '簾' :  81900, # LINE_WIDTH /  22 
    '練' :  81900, # LINE_WIDTH /  22 
    '聯' :  81900, # LINE_WIDTH /  22 
    '蓮' :  81900, # LINE_WIDTH /  22 
    '連' :  81900, # LINE_WIDTH /  22 
    '錬' :  81900, # LINE_WIDTH /  22 
    '呂' :  81900, # LINE_WIDTH /  22 
    '魯' :  81900, # LINE_WIDTH /  22 
    '櫓' :  81900, # LINE_WIDTH /  22 
    '炉' :  81900, # LINE_WIDTH /  22 
    '賂' :  81900, # LINE_WIDTH /  22 
    '路' :  81900, # LINE_WIDTH /  22 
    '露' :  81900, # LINE_WIDTH /  22 
    '労' :  81900, # LINE_WIDTH /  22 
    '婁' :  81900, # LINE_WIDTH /  22 
    '廊' :  81900, # LINE_WIDTH /  22 
    '弄' :  81900, # LINE_WIDTH /  22 
    '朗' :  81900, # LINE_WIDTH /  22 
    '楼' :  81900, # LINE_WIDTH /  22 
    '榔' :  81900, # LINE_WIDTH /  22 
    '浪' :  81900, # LINE_WIDTH /  22 
    '漏' :  81900, # LINE_WIDTH /  22 
    '牢' :  81900, # LINE_WIDTH /  22 
    '狼' :  81900, # LINE_WIDTH /  22 
    '篭' :  81900, # LINE_WIDTH /  22 
    '老' :  81900, # LINE_WIDTH /  22 
    '聾' :  81900, # LINE_WIDTH /  22 
    '蝋' :  81900, # LINE_WIDTH /  22 
    '郎' :  81900, # LINE_WIDTH /  22 
    '六' :  81900, # LINE_WIDTH /  22 
    '麓' :  81900, # LINE_WIDTH /  22 
    '禄' :  81900, # LINE_WIDTH /  22 
    '肋' :  81900, # LINE_WIDTH /  22 
    '録' :  81900, # LINE_WIDTH /  22 
    '論' :  81900, # LINE_WIDTH /  22 
    '倭' :  81900, # LINE_WIDTH /  22 
    '和' :  81900, # LINE_WIDTH /  22 
    '話' :  81900, # LINE_WIDTH /  22 
    '歪' :  81900, # LINE_WIDTH /  22 
    '賄' :  81900, # LINE_WIDTH /  22 
    '脇' :  81900, # LINE_WIDTH /  22 
    '惑' :  81900, # LINE_WIDTH /  22 
    '枠' :  81900, # LINE_WIDTH /  22 
    '鷲' :  81900, # LINE_WIDTH /  22 
    '亙' :  81900, # LINE_WIDTH /  22 
    '亘' :  81900, # LINE_WIDTH /  22 
    '鰐' :  81900, # LINE_WIDTH /  22 
    '詫' :  81900, # LINE_WIDTH /  22 
    '藁' :  81900, # LINE_WIDTH /  22 
    '蕨' :  81900, # LINE_WIDTH /  22 
    '椀' :  81900, # LINE_WIDTH /  22 
    '湾' :  81900, # LINE_WIDTH /  22 
    '碗' :  81900, # LINE_WIDTH /  22 
    '腕' :  81900 # LINE_WIDTH /  22
}

# To run tests, enter the following into a python3 REPL:
# >>> import Messages
# >>> from TextBox import line_wrap_tests
# >>> line_wrap_tests()
def line_wrap_tests():
    test_wrap_simple_line()
    test_honor_forced_line_wraps()
    test_honor_box_breaks()
    test_honor_control_characters()
    test_honor_player_name()
    test_maintain_multiple_forced_breaks()
    test_trim_whitespace()
    test_support_long_words()


def test_wrap_simple_line():
    if settings.default_language == 'english':
        words = 'Hello World! Hello World! Hello World!'
        expected = 'Hello World! Hello World! Hello\x01World!'
        result = line_wrap(words)

        if result != expected:
            print('"Wrap Simple Line" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Wrap Simple Line" test passed!')
    else:
        words = 'てすとテスト?テストテスト!てすとテスト'
        expected = 'てすとテスト?テストテスト!てすと\x000Aテスト '
        result = line_wrap(words)

        if result != expected:
            print('改行 テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('改行 テスト成功!')


def test_honor_forced_line_wraps():
    if settings.default_language == 'english':
        words = 'Hello World! Hello World!&Hello World! Hello World! Hello World!'
        expected = 'Hello World! Hello World!\x01Hello World! Hello World! Hello\x01World!'
        result = line_wrap(words)

        if result != expected:
            print('"Honor Forced Line Wraps" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Honor Forced Line Wraps" test passed!')
    else:
        words = 'てすとテスト?テストテスト!&てすとテスト テストテスト~てすとテスト-'
        expected = 'てすとテスト?テストテスト!\x000Aてすとテスト テストテスト~てすと\x000Aテスト-'
        result = line_wrap(words)

        if result != expected:
            print('強制改行 テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('強制改行 テスト成功!')


def test_honor_box_breaks():
    if settings.default_language == 'english':
        words = 'Hello World! Hello World!^Hello World! Hello World! Hello World!'
        expected = 'Hello World! Hello World!\x04Hello World! Hello World! Hello\x01World!'
        result = line_wrap(words)

        if result != expected:
            print('"Honor Box Breaks" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Honor Box Breaks" test passed!')
    else:
        words = 'てすとテスト?テストテスト!^てすとテスト テストテスト~てすとテスト-'
        expected = 'てすとテスト?テストテスト!\x81A5てすとテスト テストテスト~てすと\x000Aテスト-'
        result = line_wrap(words)

        if result != expected:
            print('ボックステキスト テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('ボックステキスト テスト成功!')


def test_honor_control_characters():
    if settings.default_language == 'english':
        words = 'Hello World! #Hello# World! Hello World!'
        expected = 'Hello World! \x05\x00Hello\x05\x00 World! Hello\x01World!'
        result = line_wrap(words)

        if result != expected:
            print('"Honor Control Characters" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Honor Control Characters" test passed!')
    else:
        words = 'てすとテスト?#テスト#テスト!てすとテスト '
        expected = 'てすとテスト?\x000B\x0000テスト\x000B\x0000テスト! てすと\x000Aテスト '
        result = line_wrap(words)

        if result != expected:
            print('操作キャラ テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('操作キャラ テスト成功!')


def test_honor_player_name():
    if settings.default_language == 'english':
        words = 'Hello @! Hello World! Hello World!'
        expected = 'Hello \x0F! Hello World!\x01Hello World!'
        result = line_wrap(words)

        if result != expected:
            print('"Honor Player Name" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Honor Player Name" test passed!')
    else:
        words = 'てすと@?テストテスト!てすとテスト '
        expected = 'てすと\x874F?テストテスト!\x000Aてすとテスト '
        result = line_wrap(words)

        if result != expected:
            print('プレイヤー名 テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('プレイヤー名 テスト成功!')


def test_maintain_multiple_forced_breaks():
    if settings.default_language == 'english':
        words = 'Hello World!&&&Hello World!'
        expected = 'Hello World!\x01\x01\x01Hello World!'
        result = line_wrap(words)

        if result != expected:
            print('"Maintain Multiple Forced Breaks" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Maintain Multiple Forced Breaks" test passed!')
    else:
        words = 'てすとテスト?&&テストテスト!'
        expected = 'てすとテスト?\x000A\x000Aテストテスト!'
        result = line_wrap(words)

        if result != expected:
            print('複改行 テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('複改行 テスト成功!')


def test_trim_whitespace():
    if settings.default_language == 'english':
        words = 'Hello World! & Hello World!'
        expected = 'Hello World!\x01Hello World!'
        result = line_wrap(words)

        if result != expected:
            print('"Trim Whitespace" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Trim Whitespace" test passed!')
    else:
        words = 'てすとテスト? & テストテスト!'
        expected = 'てすとテスト?\x000Aテストテスト!'
        result = line_wrap(words)

        if result != expected:
            print('空白無視 テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('空白無視 テスト成功!')


def test_support_long_words():
    if settings.default_language == 'english':
        words = 'Hello World! WWWWWWWWWWWWWWWWWWWW Hello World!'
        expected = 'Hello World!\x01WWWWWWWWWWWWWWWWWWWW\x01Hello World!'
        result = line_wrap(words)

        if result != expected:
            print('"Support Long Words" test failed: Got ' + result + ', wanted ' + expected)
        else:
            print('"Support Long Words" test passed!')
    else:
        words = 'てすとテスト?ウリイイイイイイイイイイイイイイイイイイイ!!テストテスト!'
        expected = 'てすとテスト?\x000Aウリイイイイイイイイイイイイイイイイイイイ!!\x000Aテストテスト!'
        result = line_wrap(words)

        if result != expected:
            print('長文 テスト失敗: 結果 ' + result + '、 予定 ' + expected)
        else:
            print('長文 テスト成功!')
