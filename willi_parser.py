import os
from typing import Final
import dsbapi

TABLE_KEYS: Final = ('lesson', 'replacing_teacher', 'teacher', 'subject', 'room', 'info_text')


def parse_willi_infos(events: list[dict[str, str]]):
    cases: dict[str, list[str]] = {
        'Vorverlegt': ['vorverlegt', 'vorziehung', 'vorgezogen'],
        'Raumänderung': ['raumänderung', 'raumvertretung'],
        'Vertretung': ['vertretung'],
        'Entfall': ['entfällt', 'fällt aus'],
        'Aufgaben': ['aa in', 'aa von']
    }

    for event in events:
        if event.get('info_text') is None:
            continue

        info_text = event['info_text']
        lower_info: str = event['info_text'].casefold()
        for case, values in cases.items():
            for value in values:
                if lower_info == value:
                    event.pop('info_text')
                elif lower_info.startswith(value):
                    if info_text[len(value)] == ',':
                        event['info_text'] = info_text[len(value):].strip(' ,')
                    elif len(lower_info) - len(value) == 1 and not lower_info[-1].isalnum():
                        event.pop('info_text')
                else:
                    continue

                event['type'] = case
                break
            else:
                continue
            break

    return events


def load_credentials(path: str):
    uname = os.environ.get('willi_uname')
    if uname is not None:
        return uname, os.environ.get('willi_pw')

    with open(path, encoding='utf-8', mode='r') as file:
        uname, password = file.readlines()[:2]

    return uname.strip(), password.strip()


dsbclient = dsbapi.DSBApi(*load_credentials('willi_secret'), tablemapper=TABLE_KEYS,
                          inline_header=True)
entries: list[dict[str, str]] = dsbclient.fetch_entries() # Rückgabe einer JSON Liste an Arrays
print(entries)
for day in entries:
    for event in parse_willi_infos(day):
        print(event)
