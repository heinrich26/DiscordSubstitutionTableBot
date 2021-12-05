import os
import sqlite3
import io
from typing import Union
import discord
from PIL import Image, ImageDraw, ImageFont


IMG_RES = 320


class ImageDatabase:
    '''A Database, that stores Image Attachment Links'''

    def __init__(self, name: str = 'attachments.db'):
        create_tables = not os.path.exists(name)
        self.database = sqlite3.connect(name)
        self.cursor = self.database.cursor()

        if create_tables:
            self.cursor.execute('CREATE TABLE icons (key text, link text)')
            self.cursor.execute(
                'CREATE TABLE plans (key text, link text, date text)')

    def get_icon(self, key: str) -> Union[str, discord.File]:
        '''Request an Icon from the database'''
        key = key.replace(' - ', '-')

        self.cursor.execute(
            'SELECT link FROM icons WHERE key = ?', [f"{key}_icon"])
        link = self.cursor.fetchone()
        self.cursor = self.database.cursor()

        # create the Image
        if link is None:
            img = Image.new("RGBA", (IMG_RES, IMG_RES), (0, 0, 0, 0))
            font = ImageFont.truetype(
                "fonts/arialrounded.ttf", min(int(105 * (4.5 / (len(key) - key.count('.')))), 210))

            draw = ImageDraw.Draw(img)
            draw.text((IMG_RES / 2, IMG_RES / 2), key,
                      anchor='mm', font=font, fill=(142, 146, 151))

            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            file = discord.File(buf, filename=f"{key.replace(' ', '_')}_icon.png")

            return file
        return link[0]

    def get_plan(self, key: str, date: str) -> str:
        '''Request the URL for a plan from the Database'''
        key = [f'{key}_plan']
        self.cursor.execute('SELECT * FROM plans WHERE key = ?', key)
        result = self.cursor.fetchone()
        self.cursor = self.database.cursor()

        if result is None:
            return None

        if date == result[2]:
            return result[1]

        self.cursor.execute('DELETE FROM plans WHERE key = ?', key)
        self.database.commit()

        return None

    def set_attachment(self, key: str, link: str, date: str = None):
        '''Sets the Attachment Link for the given key'''
        self.cursor.execute(*('INSERT INTO icons VALUES (?, ?)',
                            (f'{key}_icon', link)) if date is None else
                            ('INSERT INTO plans VALUES (?, ?, ?)',
                            (f'{key}_plan', link, date)))
        self.database.commit()

    def __del__(self):
        self.database.commit()
        self.database.close()
