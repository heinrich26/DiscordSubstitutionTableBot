'''Parser for various Timetables'''

import urllib.request
import os
# import platform
# import io
import json
from itertools import zip_longest
from typing import Union, Final, Tuple, List, Dict
from datetime import datetime
# from discord import File
from lxml import html, etree
# from preview_factory import create_html_preview
from replacement_types import ReplacementType, PlanPreview
from attachment_database import ImageDatabase
from dsbapi import DSBApi


# Read the Timetable Data
with open('pages.json', 'r', encoding='utf-8') as page_json:
    PAGES: Final[dict] = json.loads(page_json.read())['keys']

# Keys for the Timetable Types
UNTIS_HTML: Final = 0
DSB_MOBILE: Final = 1

DEFAULT_URL: Final = tuple(PAGES.keys())[0]
WILLI_URL: Final[str] = tuple(PAGES.keys())[1]

DEFAULT_MAPPER: Final = ('type', 'class', 'lesson','subject', 'room',
                         'new_subject', 'new_teacher', 'teacher')



def load_credentials(id: str):
    uname = os.environ.get(f'{id}_uname')
    if uname is not None:
        return uname, os.environ.get(f'{id}_pw')

    with open(f'secret_{id}', encoding='utf-8', mode='r') as file:
        uname, password = file.readlines()[:2]

    return uname.strip(), password.strip()


# Klasse für die Webseitenobjekte
class Page:
    '''Klasse für Vertetungsplan Webseiten
    Extrahiert Vertretungen & produziert Previews'''

    def __init__(self, url: str = DEFAULT_URL, database: ImageDatabase = None):
        self.url: Final = url

        self.replacements: dict = {}
        self.times: dict = {}
        # self.previews: dict = {}

        self.database = database

        self.page_struct: dict = PAGES.get(url)
        if self.page_struct is None:
            raise KeyError(url)

        self.mapper: tuple = self.page_struct.get('mapper', DEFAULT_MAPPER)


        # den Websitetypen bestimmen
        self.page_type: int = self.page_struct['id']

        if self.page_type is not None:
            self.extract_data()


    def extract_data(self, key: str = None, keys_only: bool = False) -> Union[Tuple[str, List[ReplacementType]], Dict[str, List[ReplacementType]], None]:
        '''Führt die Funktionen für den jeweiligen Websitetypen aus'''
        self.refresh_page()
        if self.page_type is None:
            return None
        elif self.page_type == UNTIS_HTML:
            return self.parse_untis_html(key, keys_only)
        elif self.page_type == DSB_MOBILE:
            return self.parse_dsb_entries(key, keys_only)


    def parse_untis_html(self, key: str = None, keys_only: bool = False) -> Union[Tuple[str, List[ReplacementType]], Dict[str, List[ReplacementType]], None]:
        '''Extrahiert die Klassen & Links aus der Webseite'''
        # 2. Tabelle auswählen
        tables = self.page.findall('//center//table')
        if len(tables) <= 1:
            return None

        # Daten aus den Zellen extrahieren
        data_cells = {cell.text_content(): cell.get('href')
                      for cell in tables[1].iterfind('.//td/a')}

        # nur die Klassen mit Vertretungen zurückgeben!
        if keys_only:
            return data_cells.keys()

        key_dict = {item.lower(): item for item in data_cells} if key else None
        # Vplan für einzelne Klasse konstruieren
        if key is not None:
            if key_dict is None: return None

            key: str = key_dict.get(key.lower())

            if key is None: return None

            return key, self.parse_untis_html_table(key, data_cells[key])

        del key_dict, key
        # die Vertretungen für die alle Klassen ermitteln
        for kv in data_cells.items():
            self.parse_untis_html_table(*kv, False)


        # nicht mehr vorkommene Elemente löschen
        if len(data_cells) != len(self.replacements):
            for class_repl in self.replacements:
                if not class_repl in data_cells:
                    self.replacements.pop(class_repl)
                    # self.previews.pop(class_repl)
                else:
                    continue


    def parse_untis_html_table(self, key, link, single: bool = True) -> List[ReplacementType]:
        '''Extrahiert den Untis Vertretungsplan für die jeweilige Klasse'''
        # den Link zum Plan konstruieren
        if link.count('/') == 0:  # deal with relative Links
            link = self.url.rsplit('/', 1)[0] + '/' + link
        with urllib.request.urlopen(link) as web_page:
            page = html.parse(web_page)


        # Abfragen, ob der Plan neuer ist als der in unserer Datenbank
        time_data = page.xpath(
            '(((.//center//table)[1])/tr[2])/td[last()]')[0].text_content()
        if self.times.get(key) == time_data and key in self.replacements:
            # überspringen, vorherigen Wert zurückgeben
            # return self.replacements[key], self.previews.get(key, self.get_plan_preview(key, time_data))
            return self.replacements[key]

        self.times[key] = time_data  # Datum eintragen
        events = page.xpath('(.//center//table)[2]/tr[position()>1]')

        self.replacements[key] = []

        none_cases = ('\xa0', '+', '---')

        # Alle Vertretungen aus der Tabelle extrahieren
        for event in events:
            cells: list = [item.text_content().strip('\n ').replace('\xa0', ' ')
                           if not item.text_content().strip('\n ') in none_cases else None
                           for item in event.xpath('(.//td)[position()>1]')]
            replacement: ReplacementType = {k:v for k, v in
                dict(zip_longest(self.mapper, cells)).items() if v is not None}




            self.replacements[key].append(replacement)

        if single:
            # return self.replacements[key], self.get_plan_preview(key)
            return self.replacements[key]

        # self.previews[key] = self.get_plan_preview(key)
        return None


    def parse_dsb_entries(self, key: str, keys_only: bool):
        '''Extrahiert den DSBMobile Vertretungsplan für ganze Schule'''
        FORMAT: str = '%d.%m.%Y'
        plan_dates: list = [datetime.strptime(day[0]['date'], FORMAT) for day in self.dsbentries]

        plan = self.dsbentries[plan_dates.index(max(plan_dates))]
        plan_updated = plan[0]['updated']

        if self.times.get('all') != plan_updated:
            if not 'type_of_replacement' in self.mapper:
                plan = self.parse_type_from_dsb_info(plan)


            self.replacements.clear()

            for event in plan:
                class_ = event.pop('class')
                if not class_ in self.replacements:
                    self.replacements[class_] = [event]
                else:
                    self.replacements[class_].append(event)

            self.times['all'] = plan_updated



        if keys_only:
            return self.replacements.keys()


        # Vplan für einzelne Klasse zurückgeben
        if key is not None:
            key_dict = {item.lower(): item for item in self.replacements.keys()}

            if key_dict is None: return None

            key: str = key_dict.get(key.lower())

            if key is None: return None


            # return key, self.replacements.get(key), self.get_plan_preview(key, 'all')
            return key, self.replacements.get(key)

        # for key in self.replacements:
        #     self.previews[key] = self.get_plan_preview(key, 'all')


    def get_plan_preview(self, key: str, time_key: str = None) -> PlanPreview:
        '''Produziert die Preview für den Vertretungsplan'''
        return ''
        # plan_img_url: str = self.database.get_plan(key, self.times[key] if time_key is None else time_key)
        # if plan_img_url is not None:
        #     self.previews[key] = plan_img_url  # put the value to the dict
        #     return plan_img_url

        # # Nach HTML konvertieren & newlines entfernen, die extra Spaces erzeugen
        # html_code: str = create_html_preview(self.replacements[key])

        # filename = f'{key}_plan.png'
        # options: Final = {'quiet': None, 'width': 500, 'transparent': None,
        #                   'enable-local-file-access': None, 'format': 'png',
        #                   'encoding': "UTF-8"}

        # try:
        #     conf = imgkit.config()
        #     if platform.system() == 'Linux':
        #         try:
        #             conf.get_wkhtmltoimage()
        #         except:
        #             conf.wkhtmltoimage = "./.apt/usr/local/bin/wkhtmltoimage"
        #     else:
        #         conf.wkhtmltoimage = "C:/Program Files/wkhtmltopdf/bin/wkhtmltoimage.exe"
        #     config: Final = {
        #         'options': options,
        #         'config': conf
        #     }

        #     buf = io.BytesIO(imgkit.from_string(html_code, False, **config))
        #     buf.seek(0)
        # except:
        #     buf = io.BytesIO()

        # return File(buf, filename=filename)


    def get_plan_for_class(self, key: str) -> Tuple[str, List[ReplacementType]]:
        '''Gibt den Vertretungsplan der gegebenen Klasse zurück'''
        return self.extract_data(key)


    def get_plan_for_all(self) -> Dict[str, List[ReplacementType]]:
        '''Gibt den Vertretungsplan für alle Klassen der Seite zurück!'''
        self.extract_data()
        return self.replacements


    def refresh_page(self):
        '''Url abfragen, Code laden!'''
        if self.page_type == UNTIS_HTML:
            try:
                with urllib.request.urlopen(self.url) as web_page:
                    self.page: etree.ElementTree = html.parse(web_page)
            except urllib.error.HTTPError:
                self.page: etree.ElementTree = etree.ElementTree(html.fromstring('<html><body><center></body></html>'))
        elif self.page_type == DSB_MOBILE:
            if not hasattr(self, 'dsbclient'):
                self.dsbclient = DSBApi(*load_credentials(self.page_struct['id']),
                                   tablemapper=self.mapper,
                                   inline_header=self.page_struct.get('inline_header', False))

            # refresh Entries
            self.dsbentries = self.dsbclient.fetch_entries()




    def get_classes(self) -> list:
        '''Gibt alle Klassen mit Vertretungen zurück'''
        return self.extract_data(keys_only=True)

    def parse_type_from_dsb_info(self, events: List[dict]):
        for event in events:
            if event.get('info_text') is None:
                continue

            info_text = event['info_text']
            lower_info: str = event['info_text'].casefold()
            for case, values in self.page_struct['event_cases'].items():
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

                    event['type_of_replacement'] = case
                    break
                else:
                    continue
                break

        return events



if __name__ == '__main__':
    example_page = Page(DEFAULT_URL, database=ImageDatabase())

    print(example_page.replacements)
