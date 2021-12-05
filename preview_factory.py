import codecs
import os
import json
from typing import Final, List
from discord import Embed, Color
from replacement_types import ReplacementType
from attachment_database import ImageDatabase
from replit import db


# Read the Timetable Data
with open('pages.json', 'r', encoding='utf-8') as page_json:
    PAGES: Final[dict] = json.loads(page_json.read())['keys']

# Keys for the Timetable Types
UNTIS_HTML: Final = 0
DSB_MOBILE: Final = 1

REPLACED: Final = ('vertretung', 'betreuung')
OMITTED: Final = ('entfall', 'eva', 'aufgaben')
ROOM_REPLACEMENT: Final = ('raumvertretung', 'raumänderung', 'raum-vtr.')
EARLIER: Final = ('vorverlegt')

event_types = (
    (REPLACED, Color.blue()),
    (OMITTED, Color.red()),
    (ROOM_REPLACEMENT, Color.orange()),
    (EARLIER, Color.green())
)

DEFAULT_FOOTER = {'text': 'Alle Angaben ohne Gewähr! Aber mit Gewehr. '}

FONT_A: Final = os.path.join(os.getcwd(), 'fonts/arialrounded.ttf').replace('\\', '/')
FONT_B: Final = os.path.join(os.getcwd(), 'fonts/Arial_Rounded_MT_ExtraBold.ttf').replace('\\', '/')

STYLESHEET = ('''<style>
@font-face {
    font-family: "ArialRounded";'''
f"  src: url('{FONT_A}');"
'''}

@font-face {
    font-family: "ArialRoundedBold";'''
f"    src: url('{FONT_B}');"
'''}

body {
    margin: 0px;
    width: 500px;
    height: fit-content;
}

table {
    margin-top: -5px;
    width: 490px;
    margin-right: 10px;
    border-spacing: 0px 10px;
    height: fit-content;
    font-family: ArialRounded;
    font-size: 200%;
}

td > div {
  font-family: ArialRoundedBold;
}

tr td:first-child {
  font-family: ArialRoundedBold;
  text-align: center;
  font-size: 32pt;
  width: 30%;
  padding: 6px 6px 0px 6px;
  box-sizing: border-box;
  border-color: rgba(0,0,0,.1);
  border-style: solid;
  border-width: 2px 0px 2px 2px;
  -webkit-border-top-left-radius: 7px;
  -webkit-border-bottom-left-radius: 7px;
}

tr td:last-child {
  width: 70%;
  padding: 6px 6px 6px 0px;
  box-sizing: border-box;
  border-color: rgba(0,0,0,.1);
  border-style: solid;
  border-width: 2px 2px 2px 0px;
  -webkit-border-top-right-radius: 7px;
  -webkit-border-bottom-right-radius: 7px;
}

tr.REPLACED {
  background: -webkit-gradient(linear, left top, right top, color-stop(2%, #202225), color-stop(2%, #3D5AFE));
  background-attachment: fixed;
}

tr.canceled {
  background: -webkit-gradient(linear, left top, right top, color-stop(2%, #202225), color-stop(2%, #F44336));
  background-attachment: fixed;
}
</style>''')


def write_unknown(event_type: str):
    with open('unknowns.txt', 'r+') as f:
        if event_type in f.readlines():
            f += str


def get_color(event_type: str) -> Color:
    '''Determines the color from the given Event Type'''
    _event_type = event_type.lower()
    print(event_type)
    for event in event_types:
        if _event_type in event[0]:
            return event[1]
        continue

    write_unknown(event_type)
    return Color.dark_red()


# splits a List into Sublists with len() <= n
def chunks(items: list, n: int):
    '''Yield successive n-sized chunks from the given list.'''
    for i in range(0, len(items), n):
        yield items[i:i + n]

def sort_items(replacements: List[ReplacementType]) -> List[ReplacementType]:
    '''Sorts the Replacements by Lesson'''
    return sorted(replacements, key=lambda key: key.get('lesson'))


def create_embed(replacement: ReplacementType) -> Embed:
    '''Creates an Embed Tile for a Replacement'''
    subject: str = replacement.get('subject')
    replacer: str = replacement.get('replacing_teacher')
    teacher: str = replacement.get('teacher')
    info: str = replacement.get('info')
    room: str = replacement.get('room')
    repl_type: str = replacement.get('type_of_replacement', 'Info')

    desc: str = (subject + ' ') if subject is not None else ''
    desc += f"({'' if replacer is None else ('**' + replacer + ('** ' if teacher is not None and teacher != replacer else '**'))}"
    if teacher != replacer:
        desc += f"~~{teacher}~~)"
    else:
        desc += ')'

    if room is not None:
        desc += ' in `' + room + '`'
        
    if info is not None:
        desc += '\n' + info

    return Embed(title=repl_type,
                 description=desc,
                 color=get_color(repl_type))

def create_vplan_message(replacements: List[ReplacementType], class_: str,
                         database: ImageDatabase, date: str = None, subtitle: bool = True) -> List[dict]:
    message: dict = {
        'content': f"**Vertretungsplan für die {class_}**",
        'embeds': [],
        'files': []
    }

    if subtitle:
        message['content'] += f"\nHier siehst du deine Vertretungen für den {date.split(' ')[0] if date is not None else 'heutigen Tag'}:"

    if replacements is None or len(replacements) == 0:
        message['content'] += '\n\nOooaah, es sieht so aus als hättest du heute keine Vertretung! :('

    messages: List[dict] = [message]

    embed_count: int = 0
    lessons: dict = {}
    for replacement in replacements:
        embed = create_embed(replacement)


        if embed_count != 10:
            messages[-1]['embeds'].append(embed)
            embed_count += 1
        else:
            messages[-1]['embeds'][-1].set_footer(**DEFAULT_FOOTER)
            messages.append({'embeds': [embed], 'files':[]})
            embed_count = 1


        lesson: str = replacement['lesson']
        if not lesson in lessons:
            thumb = database.get_icon(lesson)
        else:
            thumb = lessons[lesson]

        if isinstance(thumb, str):
            messages[-1]['embeds'][-1].set_thumbnail(url=thumb)
        else:
            messages[-1]['embeds'][-1].set_thumbnail(url=f'attachment://{thumb.filename}')
            if not thumb in messages[-1]['files']:
                messages[-1]['files'].append(thumb)

    messages[-1]['embeds'][-1].set_footer(**DEFAULT_FOOTER)

    return messages

# Splits the Replacements and sorts them
def prepare_replacements(replacements: List[ReplacementType]) -> List[List[ReplacementType]]:
    '''Applies the Embed limits of discord'''
    return chunks(sort_items(replacements), 10)


def wrap_tag(code: str, tag: str = 'div', sclass=None, **kwargs) -> str:
    '''Surrounds the given String with the given Tag'''
    if sclass is not None:
        kwargs['class'] = sclass

    attrs = ' ' + \
            ' '.join([f"{kv[0]}='{str(kv[1])}'" for kv in kwargs.items()]) \
            if kwargs else ''

    return f"<{tag + attrs}>{str(code)}</{tag}>"



def create_replacement_tile(replacement: ReplacementType) -> str:
    '''Creates a HTML Row for a replacement'''
    teacher: str = replacement.get('teacher')
    replacer: str = replacement.get('replacing_teacher')
    info: str = replacement.get('info_text')
    room: str = replacement.get('room')
    repl_type: str = replacement.get('type_of_replacement', 'Info')
    desc: str = replacement.get('subject', '') + \
                 f" ({'' if replacer is None else (replacer + ' ' if teacher is not None else replacer)}{wrap_tag(teacher, 's') if teacher != replacer and teacher is not None else ''})" + \
                 f"{' in ' + room if room is not None else ''}" + \
                 ('<br>' + info if info is not None else '')

    contents = wrap_tag(replacement['lesson'], 'td') + wrap_tag(wrap_tag(repl_type, 'div') + desc, 'td')
    return wrap_tag(contents, 'tr', sclass='REPLACED' if repl_type.lower() in REPLACED else 'canceled')


def convert_unicode_chars(inp: str) -> str:
    '''Removes all Html-unsupported chars from the String'''
    if inp.isalnum():
        return inp

    out = ''
    for char in inp:
        if char in '''  \nabcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890<>/!\\´`'"§$%&()[]{}?=+~*'#-_.:,;|@^°''':
            out += char
        else:
            out += '&#' + str(ord(char)) + ';'
    return inp



def create_html_preview(replacements: List[ReplacementType]) -> str:
    '''Writes the HTML for the given replacements'''
    html = STYLESHEET + '<table>'

    for replacement in sort_items(replacements):
        html += create_replacement_tile(replacement)

    html += '</table>'

    html = '<head><meta http-equiv="content-type" content="text/html; charset=utf-8"></head>\n' + \
        wrap_tag(html, 'body')  # convert_unicode_chars(wrap_tag(html, 'body'))

    return wrap_tag(html, 'html')




if __name__ == '__main__':
    example_replacements = [{
        'lesson': '1', 'teacher': 'Ks', 'subject': 'GEO',
        'replacing_teacher': 'Gw', 'room': 'B108', 'info_text': None,
        'type_of_replacement': 'Vertretung'
    }, {
        'lesson': '1-2', 'teacher': 'Mv', 'subject': 'SP', 'info_text': None,
        'replacing_teacher': 'V\u00F6', 'room': 'G\u00D6E',
        'type_of_replacement': 'Vertretung'
    }, {
        'lesson': '3-4', 'teacher': 'So', 'subject': 'BIO', 'replacing_teacher': None,
        'room': 'A106', 'info_text': None, 'type_of_replacement': 'Entfall'
    }, {
        'lesson': '7', 'teacher': 'Tm', 'subject': 'DE', 'replacing_teacher': None,
        'room': 'OBR', 'info_text': 'OPfer kinder tralllalalalallalala',
        'type_of_replacement': 'EVA'
    }]

    with codecs.open('tiles.html', 'w', 'utf-8') as f:
        f.write(create_html_preview(example_replacements, 'Q1'))
