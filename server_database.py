import os
import sqlite3
from sqlite3 import Cursor
from typing import Optional, Union, Dict, Tuple, List
from discord import Guild
from discord.abc import Messageable


class PageDatabase:
    '''A Database, that stores Guild Data and Subsitution Table credentials'''

    server_mapper: Dict[int, int]
    events: Dict[int, List[Union[Tuple[Messageable, str], Tuple[int, int,
                                                                str]]]]
    cursor: Cursor

    def __init__(self, name: str = 'webpages.db'):
        create_tables = not os.path.exists(name)
        self.database = sqlite3.connect(name)
        self.cursor = self.database.cursor()

        if create_tables:
            self.cursor.execute(
                'CREATE TABLE untis_page (name TEXT NOT NULL PRIMARY KEY, link TEXT NOT NULL UNIQUE)'
            )
            self.cursor.execute(
                'CREATE TABLE dsb_page (name TEXT NOT NULL PRIMARY KEY, username TEXT NOT NULL, password TEXT NOT NULL)'
            )
            self.cursor.execute(
                'CREATE TABLE servers (guild_id INT NOT NULL PRIMARY KEY, page_id INT NOT NULL)'
            )
            self.cursor.execute(
                'CREATE TABLE events (guild_id INT NOT NULL, channel_id INT NOT NULL, time INT NOT NULL, class_id INT, PRIMARY KEY (guild_id, channel_id, time, class_id))'
            )

        self.server_mapper = {
            name: id
            for name, id in self.cursor.execute(
                'SELECT * from servers').fetchall()
        } if not create_tables else {}

        self.events = {}
        for guild_id, channel_id, time, class_id in self.cursor.execute(
        'SELECT * FROM events').fetchall():
            if time in self.events:
                self.events[time].append((guild_id, channel_id, class_id))
            else:
                self.events[time] = [(guild_id, channel_id, class_id)]

    def get_page(self, plan_name: str, plan_type: int) -> str:
        '''Request the URL for a plan from the Database'''

        self.cursor.execute('SELECT name FROM plans WHERE key = ?', plan_name)
        result = self.cursor.fetchone()
        self.cursor = self.database.cursor()

        if result is None:
            return None

        return None

    def add_page(self,
                 plan_name: str,
                 plan_type: int,
                 link: Optional[str] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None):
        '''Adds a page to the database'''

        if plan_type == 0:
            exists = len(
                self.cursor.execute(
                    'SELECT untis_page.name FROM untis_page WHERE untis_page.link = ?',
                    link)) != 0
            if not exists:
                self.cursor.execute('INSERT INTO untis_page VALUES (?, ?)',
                                    (plan_name, link))
        elif plan_type == 1:
            exists = len(
                self.cursor.execute(
                    'SELECT dsb_page.name FROM dsb_page WHERE dsb_page.username = ?',
                    username)) != 0
            if not exists:
                self.cursor.execute('INSERT INTO dsb_page VALUES (?, ?, ?)',
                                    (plan_name, username, password))

        self.database.commit()

    def config_server(self, guild: Guild, default_plan: int):
        self.database.execute(
            'REPLACE INTO servers (guild_id, page_id) VALUES (?, ?)',
            (guild.id, default_plan))

        self.server_mapper[guild.id] = default_plan

        self.database.commit()

    def add_event(self, channel: Messageable, time: int,
                  class_id: Optional[str]):
        self.cursor.execute(
            'REPLACE INTO events (guild_id, channel_id, time, class_id) VALUES (?, ?, ?, ?)',
            (channel.guild.id, channel.id, time, class_id))
        if time in self.events:
            self.events[time].append((channel, class_id))
        else:
            self.events[time] = [channel, class_id]

        self.database.commit()

    def delete_event(self, guild_id: int, channel_id: int, time: int,
                     class_id: int):
        self.cursor.execute(
            'DELETE FROM events WHERE events.guild_id = ? and events.channel_id = ? and events.time = ? and events.class_id = ?',
            (guild_id, channel_id, time, class_id))

        self.database.commit()

    def get_server_default(self, guild: Guild) -> int:
        return self.server_mapper.get(guild.id, 0)

    def __del__(self):
        self.database.commit()
        self.database.close()
