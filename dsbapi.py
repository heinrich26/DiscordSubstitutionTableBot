from typing import Final, Iterable, List
import json
import requests
import datetime
import base64
import uuid
import gzip
import bs4


NONE_CASES: Final = ('\xa0', '+', '---')

DEFAULT_MAPPER: Final[List[str]] = ['type', 'class', 'lesson','subject', 'room',
                                    'new_subject', 'new_teacher', 'teacher']


class DSBApi:
    def __init__(self, username: str, password: str,
                 tablemapper: Iterable[str] = DEFAULT_MAPPER,
                 inline_header: bool = False):
        """
        Class constructor for class DSBApi
        @param username: string, the username of the DSBMobile account
        @param password: string, the password of the DSBMobile account
        @param tablemapper: list, the field mapping of the DSBMobile tables (default: ['type','class','lesson','subject','room','new_subject','new_teacher','teacher'])
        @return: class
        @raise TypeError: If the attribute tablemapper is not of type list
        """
        self.DATA_URL: str = "https://app.dsbcontrol.de/JsonHandler.ashx/GetData"
        self.username: str = username
        self.password: str = password

        if not isinstance(tablemapper, Iterable):
            raise TypeError('Attribute tablemapper is not of type Iterable!')

        self.tablemapper: Iterable[str] = tablemapper
        self.inline_header: bool = inline_header


    def fetch_entries(self):
        """
        Fetch all the DSBMobile entries
        @return: list, containing lists of DSBMobile entries from the tables or only the entries if just one table was received (default: empty list)
        @raise Exception: If the request to DSBMonile failed
        """

        # Iso format is for example 2019-10-29T19:20:31.875466
        current_time: str = datetime.datetime.now().isoformat()

        # Cut off last 3 digits and add 'Z' to get correct format
        current_time = current_time[:-3] + "Z"

        # Parameters required for the server to accept our data request
        params: dict[str, str] = {
            "UserId": self.username,
            "UserPw": self.password,
            "AppVersion": "2.5.9",
            "Language": "de",
            "OsVersion": "28 8.0",
            "AppId": str(uuid.uuid4()),
            "Device": "SM-G930F",
            "BundleId": "de.heinekingmedia.dsbmobile",
            "Date": current_time,
            "LastUpdate": current_time
        }

        # Convert params into the right format
        params_bytestring: bytes = json.dumps(
            params, separators=(',', ':')).encode("UTF-8")
        params_compressed: str = base64.b64encode(
            gzip.compress(params_bytestring)).decode("UTF-8")

        # Send the request
        json_data: dict[str, dict] = {
            "req": {"Data": params_compressed, "DataType": 1}}
        timetable_data = requests.post(self.DATA_URL, json=json_data)

        # Decompress response
        data_compressed = json.loads(timetable_data.content)["d"]
        data = json.loads(gzip.decompress(base64.b64decode(data_compressed)))

        # validate response before proceed
        if data['Resultcode'] != 0:
            raise Exception(data['ResultStatusInfo'])

        # Find the timetable page, and extract the timetable URL from it
        final = []
        for page in data["ResultMenuItems"][0]["Childs"]:
            for child in page["Root"]["Childs"]:
                if isinstance(child["Childs"], list):
                    for sub_child in child["Childs"]:
                        final.append(sub_child["Detail"])
                else:
                    final.append(child["Childs"]["Detail"])

        if not final:
            raise Exception("Timetable data could not be found")

        output = []
        for entry in final:
            if entry.endswith(".htm") and not entry.endswith(".html") and not entry.endswith("news.htm"):
                output.append(self.fetch_timetable(entry))
            # elif entry.endswith(".jpg"):
            #     output.append(self.fetch_img(entry))

        if len(output) == 1:
            return output[0]
        else:
            return output

    def fetch_img(self, imgurl):
        """
        Extract data from the image
        @param imgurl: string, the URL to the image
        @return: list, list of dicts
        @todo: Future use - implement OCR
        @raise Exception: If the function will be crawled, because the funbtion is not implemented yet
        """
        raise Exception(
            'Extraction of data from images is not implemented yet!')

    def fetch_timetable(self, timetableurl) -> list:
        """
        parse the timetableurl HTML page and return the parsed entries
        @param timetableurl: string, the URL to the timetable in HTML format
        @return: list, list of dicts
        """
        results = []
        sauce = requests.get(timetableurl).text
        soupi = bs4.BeautifulSoup(sauce, "html.parser")
        ind = -1
        for soup in soupi.find_all('table', {'class': 'mon_list'}):
            ind += 1
            updates = [o.p.findAll('span')[-1].next_sibling.split("Stand: ")[1]
                       for o in soupi.findAll('table', {'class': 'mon_head'})][ind]
            titles = [o.text for o in soupi.findAll(
                'div', {'class': 'mon_title'})][ind]
            date = titles.split(" ")[0]
            day = titles.split(" ")[1].split(", ")[0].replace(",", "")
            entries = soup.find_all("tr")
            entries.pop(0)

            current_class: str = None

            for entry in entries:
                infos = entry.find_all("td")

                if len(infos) < 2:
                    current_class = infos[0].text
                    continue

                for class_ in infos[1].text.split(", "):
                    new_entry = {'date': date, 'day': day, 'updated': updates}

                    if self.inline_header:
                        new_entry['class'] = current_class

                    i = 0
                    while i < len(infos):
                        if i < len(self.tablemapper):
                            attribute = self.tablemapper[i]
                        else:
                            attribute = 'col' + str(i)

                        if attribute == 'class':
                            new_entry[attribute] = current_class if self.inline_header else class_ if not infos[i].text in NONE_CASES else None
                        elif not infos[i].text in NONE_CASES:
                            new_entry[attribute] = infos[i].text
                        i += 1

                    results.append(new_entry)

        return results