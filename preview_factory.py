import json
from typing import Final, List
from discord import Embed, Color
from replacement_types import ReplacementType
from attachment_database import ImageDatabase


# Read the Timetable Data - unused
with open('pages.json', 'r', encoding='utf-8') as page_json:
    PAGES: Final[dict] = json.loads(page_json.read())['keys']


REPLACED: Final = ('vertretung', 'betreuung')
OMITTED: Final = ('entfall', 'eva', 'aufgaben')
ROOM_REPLACEMENT: Final = ('raumvertretung', 'raumänderung', 'raum-vtr.')
EARLIER: Final = ('vorverlegt')

event_types = ((REPLACED, Color.blue()), (OMITTED, Color.red()),
               (ROOM_REPLACEMENT, Color.orange()), (EARLIER, Color.green()))

DEFAULT_FOOTER = {'text': 'Alle Angaben ohne Gewähr! Aber mit Gewehr. '}

UNKNOWNS_FILE = open('unknowns.txt', 'r+')


def __del__():
  print('i have to go')

def write_unknown(event_type: str):
    with open('unknowns.txt', 'a') as f:
        f.write(event_type + '\n')


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

    return Embed(title=repl_type, description=desc, color=get_color(repl_type))


def create_vplan_message(replacements: List[ReplacementType],
                         class_: str,
                         database: ImageDatabase,
                         date: str = None,
                         subtitle: bool = True) -> List[dict]:
    message: dict = {
        'content': f"**Vertretungsplan für die {class_}**",
        'embeds': [],
        'files': []
    }

    if subtitle:
        message[
            'content'] += f"\nHier siehst du deine Vertretungen für den {date.split(' ')[0] if date is not None else 'heutigen Tag'}:"

    if replacements is None or len(replacements) == 0:
        message[
            'content'] += '\n\nOooaah, es sieht so aus als hättest du heute keine Vertretung! :('

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
            messages.append({'embeds': [embed], 'files': []})
            embed_count = 1

        lesson: str = replacement['lesson']
        if not lesson in lessons:
            thumb = database.get_icon(lesson)
        else:
            thumb = lessons[lesson]

        if isinstance(thumb, str):
            messages[-1]['embeds'][-1].set_thumbnail(url=thumb)
        else:
            messages[-1]['embeds'][-1].set_thumbnail(
                url=f'attachment://{thumb.filename}')
            if not thumb in messages[-1]['files']:
                messages[-1]['files'].append(thumb)

    messages[-1]['embeds'][-1].set_footer(
        **DEFAULT_FOOTER)  # adds the no responsibility statement

    return messages


def prepare_replacements(
        replacements: List[ReplacementType]) -> List[List[ReplacementType]]:
    '''Applies the Embed limits of discord
    Splits and sorts the Replacements'''
    return chunks(sort_items(replacements), 10)
