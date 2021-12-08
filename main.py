import os
import json
from typing import List, Dict
from datetime import date, datetime
from pytz import timezone
from discord import Embed, Intents
from discord.abc import Messageable
from discord.ext import commands, tasks
from discord_slash import SlashCommand

from attachment_database import ImageDatabase
from server_database import PageDatabase
from timetable_parser import Page
from replacement_types import ReplacementType
from preview_factory import create_vplan_message
from keep_alive import keep_alive

EMPTY_FIELD = {'name': '\u200b', 'value': '\u200b', 'inline': False}

DEFAULT_FOOTER = {'text': 'Alle Angaben ohne Gewähr! Aber mit Gewehr. '}

INVITE_LINK = 'https://discord.com/api/oauth2/authorize?client_id=489087343589064704&permissions=268594240&scope=bot'

NO_REPLACEMENTS_EMBED: Embed = Embed(
    title='Vertretungsplan',
    description='Hier siehst du deine heutigen Vertretungen:')

NO_REPLACEMENTS_EMBED.add_field(name='**Keine Vertretungen heute...**',
                                value='\u200b',
                                inline=False)
NO_REPLACEMENTS_EMBED.set_footer(**DEFAULT_FOOTER)

TIMEZONE = timezone('Europe/Berlin')

# Read the Timetable Data - unused
with open('pages.json', 'r', encoding='utf-8') as page_json:
    PAGES: dict = json.loads(page_json.read())


def sort_classes(classes: List[str]) -> List[str]:
    '''Sorts Classes by their Identifiers/Names'''
    def comp(key: str):
        i = 0
        while key[:i + 1].isnumeric():
            i += 1
        return key[:i], key[i:]

    return sorted(classes, key=comp)


def check_last_modified() -> None:
    '''Deletes the Database when the Code has changed'''
    database = './attachments.db'
    if not os.path.exists(database):
        return

    files = (  #'main.py', 'preview_factory.py', 'timetable_parser.py',
        'attachment_database.py', )
    db_last_mod = os.path.getmtime(database)
    for file in files:
        if db_last_mod < os.path.getmtime(file):
            os.remove(database)
            break


if __name__ == "__main__":
    # remove the database, if it's older than the Source Code
    check_last_modified()

    img_db: ImageDatabase = ImageDatabase()
    page_db: PageDatabase = PageDatabase()
    plans = {
        page['id']: Page(url, img_db)
        for url, page in PAGES['keys'].items()
    }

    bot = commands.Bot(intents=Intents.all(), command_prefix='/')
    slash = SlashCommand(bot, sync_commands=True)

    @bot.event
    async def on_ready():
        """Called when the Bot is ready"""
        print(f"We've logged in as {bot.user}")

        exec_events.start()
        exec_events.change_interval(minutes=15.0)

    @slash.subcommand(
        base='vplan',
        name='set_default',
        description=
        'Setze den Plan der auf diesem Server standardmäßig angezeigt werden soll',
        subcommand_group='config',
        options=[{
            'name':
            'plan_id',
            'type':
            4,
            'description':
            'Name der Schule',
            'required':
            True,
            'choices': [{
                'name': page['name'],
                'value': page['id']
            } for page in PAGES['keys'].values()]
        }],
        subcommand_group_description='Verwalte die Pläne für diesen Server')
    async def set_server_default(context, plan_id: int):
        page_db.config_server(context.guild, plan_id)
        for page in PAGES['keys'].values():
            if page['id'] == plan_id:
                await context.send(
                    f"Erfolgreich den Standard-Vertretungsplan des Servers auf **{page['name']}** festgelegt!"
                )
                break

    # @slash.subcommand(
    #     base='vplan',
    #     name='add',
    #     subcommand_group='config',
    #     description='Fügt einen neuen Plan zum Server hinzu',
    #     subcommand_group_description='Verwalte die Pläne für diesen Server',
    #     options=[{
    #         'name': 'plan_name',
    #         'description': 'Name des neuen Plans',
    #         'type': 3,
    #         'required': True,
    #     }, {
    #         'name': 'seitentyp',
    #         'description': 'Typ der Website',
    #         'type': 4,
    #         'required': True,
    #         'choices': [{
    #             'name': name,
    #             'value': int(id)
    #         } for id, name in PAGES['types'].items()]
    #     }, {
    #         'name': 'seitenlink',
    #         'description': 'Link zum Plan',
    #         'type': 3,
    #         'required': False,
    #     }, {
    #         'name': 'username',
    #         'description': 'Anmeldename für die Seite',
    #         'type': 3,
    #         'required': False,
    #     }, {
    #         'name': 'password',
    #         'description': 'Anmeldename für die Seite',
    #         'type': 3,
    #         'required': False,
    #     }, {
    #         'name': 'default',
    #         'description': 'Den Plan als Standard setzen',
    #         'type': 5,
    #         'required': False
    #     }],
    #     connector={
    #         'seitentyp': 'page_type',
    #         'seitenlink': 'link'
    #     })
    # async def add_plan(context,
    #                    plan_name: str,
    #                    page_type: int,
    #                    link: str,
    #                    username: str,
    #                    password: str,
    #                    default: bool = False):
    #     ...
    #     await context.send('Not yet implemented!')

    @slash.subcommand(
        base='vplan',
        name='add-event',
        subcommand_group='config',
        description='Plant ein neues Event auf diesem Server',
        subcommand_group_description='Verwalte die Pläne für diesen Server',
        options=[{
            'name': 'time',
            'description':
            'Uhreit, zu welcher gesendet wird (gerundet auf 1/4h, Format: hh:mm)',
            'type': 3,
            'required': True,
        }, {
            'name': 'klasse',
            'description': 'Optional: Nur für eine bestimmte Klasse senden',
            'type': 3,
            'required': False,
        }, {
            'name': 'channel',
            'description':
            'Der Channel, in dem gesendet wird (fällt auf den aktuellen zurück)',
            'type': 7,
            'required': False
        }])
    async def add_event(context,
                        time: str,
                        klasse: str = None,
                        channel: Messageable = None):
        await context.defer()
        if len(time) > 5 or not time.count(':') or not time.split(
                ':')[0].isnumeric() or not time.split(':')[1].isnumeric():
            await context.send(
                'Wrong Time Format, please stick to `hh:mm`, example: `17:45`!'
            )
        else:
            hours, mins = time.split(':')
            t_stamp: int = round(int(hours) * 4 + int(mins) / 15)

            if channel is None:
                channel = context.channel

            page_db.add_event(channel, t_stamp, klasse)

            await context.send(
                f'Neues Event um {time} Uhr für Klasse: {klasse} im Channel **#-{channel.name}** ({channel.id}) hinzugefüt!'
            )

    async def _send_plan(context, klasse, silent: bool = False):
        plan_id: int = page_db.get_server_default(context.guild)
        plan: Page = plans[plan_id]
        data = plan.get_plan_for_class(klasse)

        if data is None or data[1] is {}:
            # Send, if we dont ignore empty Tables
            if not silent:
                await context.send(embed=NO_REPLACEMENTS_EMBED)
        else:
            klasse: str = data[0]
            date_str: str = plan.times.get(klasse)
            for msg in create_vplan_message(data[1], klasse, img_db, date_str):
                await context.send(**msg)

    @slash.subcommand(
        base='vplan',
        name='get',
        description='Lass dir den Plan für eine Klasse schicken!',
        options=[{
            'name': 'klasse',
            'description': 'Kürzel deiner Klasse',
            'type': 3,
            'required': True
        }])
    async def send_plan(context, klasse):
        """Sends the Substitution-Table for the given Class"""
        await context.defer()
        await _send_plan(context, klasse)

    @slash.subcommand(
        base='vplan',
        name='klassen',
        description='Schickt alle Klassen, die heute Vertretung haben!')
    async def send_classes_w_replacements(context):
        await context.defer()

        plan_id: int = page_db.get_server_default(context.guild)
        plan: Page = plans[plan_id]

        info_embed = Embed(
            title='**Klassen die heute Vertretung haben**:',
            description=
            f"`{'`, `'.join(plan.get_classes())}`\n\n Verwende `/vplan get <Klasse>` um einen bestimmten Plan zu sehen!"
        )
        info_embed.set_footer(**DEFAULT_FOOTER)
        await context.send(embed=info_embed)

    async def _send_plan_for_all(context):
        plan_id: int = page_db.get_server_default(context.guild)
        plan: Page = plans[plan_id]

        replacements: Dict[str,
                           List[ReplacementType]] = plan.get_plan_for_all()

        if replacements is None or replacements == {}:
            # No replacements
            await context.send(embed=NO_REPLACEMENTS_EMBED)
        else:
            first: bool = True
            for klasse, events in replacements.items():
                date_str: str = plan.times.get(klasse)
                for msg in create_vplan_message(events, klasse, img_db, date_str,
                                                False):
                    if first:
                        msg['content'] = f"**Vertretungsplan der ganzen Schule für den {'heutigen Tag' if date_str is None else date_str.split(' ')[0]}:**\n\n" + msg[
                            'content']
                        await context.send(**msg)
                        first = False
                    else:
                        await context.send(**msg)

    @slash.subcommand(
        base='vplan',
        name='all',
        description=
        'Schickt ALLE Vertretungen — Nervig & sollte vermieden werden!!!')
    async def send_plan_for_all(context):
        """Sends all replacements, quite annoying!"""
        await context.defer()
        await _send_plan_for_all(context)



    ctime = datetime.now(TIMEZONE)

    @tasks.loop(minutes=15 - ctime.minute % 15, seconds=60 - ctime.second)
    # @tasks.loop(minutes=0, seconds=5.0)
    async def exec_events():

        ctime = datetime.now(TIMEZONE)

        if ctime.date().weekday() == 5: return  # samstag ist freitag
        
    
        cur_min: int = round(ctime.hour * 4 + ctime.minute / 15)

        events = page_db.events.get(cur_min)
        if events is None: return

        for event in events:
            if isinstance(event[0], int):  # deal with channel and guild id
                try:
                    channel: Messageable = bot.get_channel(event[1])
                except AttributeError as error:
                    print(error)
                    print('nix gefunden warum bin ich dumm?', event)
                    page_db.delete_event(event[0], event[1], cur_min, event[2])
                    continue
            else:
                channel = event[0]
            _class: str = event[2]
            try:    
                context = await bot.get_context(await channel.fetch_message(channel.last_message_id))
            except:
                continue
            if not context.valid: continue

            if _class is None:
                await _send_plan_for_all(context)
            else:
                await _send_plan(context, _class, silent=True)




    # @slash.subcommand()

    #         elif args[1] in ('help', 'h'):  # send an info message to the channel
    #             async with msg.channel.typing():
    #                 help_embed = Embed(title='**__Vertretungsplan Hilfe__**',
    #                                    description='Hier findest du alle wichtigen Commands für den Vertretungsplan!')
    #                 help_embed.add_field(name='**Verwendung:** `!vplan [Optionen]`',
    #                                      value=('`ohne Args` Zeigt den kompletten Plan\n'
    #                                             '`... help` Zeigt diese Info\n'
    #                                             '`... <Klasse>` Zeigt den Plan für eine Klasse\n'
    #                                             '`... klassen` Zeigt alle Klassen die heute Vertretung haben'))
    #                 await msg.channel.send(embed=help_embed)
    #         # send all classes that have replacements at this day!
    #         elif args[1] in ('klassen', 'classes', 'list', 'liste'):
    #             await msg.channel.trigger_typing()
    #             info_embed = Embed(title='**Klassen die heute Vertretung haben**:',
    #                                description=f"`{'`, `'.join(liliplan.get_classes())}`\n\n Verwende `!vplan <Klasse>` um einen bestimmten Plan zu sehen!")
    #             info_embed.set_footer(**DEFAULT_FOOTER)
    #             await msg.channel.send(embed=info_embed)
    #         elif args[1] == 'invite':  # send an invitation Link
    #             await msg.channel.send(f"Du willst den Bot auch auf deinem Server haben?\n\nLad ihn hiermit ein: {INVITE_LINK}")

    keep_alive()
    bot.run(os.environ['BOT_TOKEN'] if 'BOT_TOKEN' in os.environ else open(
        'token_secret', 'r', encoding='utf-8').readlines()[0])
