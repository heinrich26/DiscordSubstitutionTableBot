import os
import sqlite3
import io
from typing import Union
import discord



class PageDatabase:
    '''A Database, that stores Image Attachment Links'''

    def __init__(self, name: str = 'webpages.db'):
        create_tables = not os.path.exists(name)
        self.database = sqlite3.connect(name)
        self.cursor = self.database.cursor()

        if create_tables:
            self.cursor.execute('CREATE TABLE untis_page (name TEXT NOT NULL PRIMARY KEY, link TEXT NOT NULL)')
            self.cursor.execute(
                'CREATE TABLE dsb_page (name TEXT NOT NULL PRIMARY KEY, username TEXT NOT NULL, password TEXT NOT NULL)')

    

    def get_page(self, plan_name: str, plan_type: int) -> str:
        '''Request the URL for a plan from the Database'''
        
        self.cursor.execute('SELECT name FROM plans WHERE key = ?', key)
        result = self.cursor.fetchone()
        self.cursor = self.database.cursor()

        if result is None:
            return None

        if date == result[2]:
            return result[1]

        self.cursor.execute('DELETE FROM plans WHERE key = ?', key)
        self.database.commit()

        return None

    def add_page(self, key: str, link: str, date: str = None):
        '''Sets the Attachment Link for the given key'''
        self.cursor.execute(*('INSERT INTO icons VALUES (?, ?)',
                            (f'{key}_icon', link)) if date is None else
                            ('INSERT INTO plans VALUES (?, ?, ?)',
                            (f'{key}_plan', link, date)))
        self.database.commit()

    def __del__(self):
        self.database.commit()
        self.database.close()
