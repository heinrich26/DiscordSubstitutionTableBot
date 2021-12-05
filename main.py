import os
from discord import Embed, Message, Intents
from discord.ext import commands
from typing import Tuple, List, Dict
from discord_slash import SlashCommand

from attachment_database import ImageDatabase
from timetable_parser import DEFAULT_URL, Page
from replacement_types import ReplacementType, PlanPreview
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


def build_plan(
        key: str, replacements: ReplacementType,
        preview: PlanPreview) -> Tuple[str, list, Embed, Tuple[bool, bool]]:
    '''Returns everything needed to send a Substitutiontable as Message for the given Data'''
    # embed = class_vplan(key, replacements)
    embed = Embed(title=f'**Vertretungsplan der {key}**',
                  description='Hier siehst du deine heutigen Vertretungen:')
    embed.set_footer(**DEFAULT_FOOTER)

    files: list = []
    thumbnail = img_db.get_icon(key)

    known_icon = isinstance(thumbnail, str)
    if known_icon:
        embed.set_thumbnail(url=thumbnail)
    else:
        embed.set_thumbnail(url=f'attachment://{thumbnail.filename}')
        files.append(thumbnail)

    generated_plan = isinstance(preview, str)

    if preview is not None:
        if generated_plan:
            embed.set_image(url=preview)
        else:
            embed.set_image(url=f'attachment://{preview.filename}')
            files.append(preview)

    return key, files, embed, (known_icon, generated_plan)


def update_database_from_msg(key: str, message: Message,
                             bools: Tuple[bool, bool]) -> None:
    '''Adds the Attachment Links from the given Message to the Database'''
    if not bools[0]:
        img_db.set_attachment(key, message.embeds[0].thumbnail.url)

    if not bools[1]:
        link = message.embeds[-1].image.url
        img_db.set_attachment(key, link, liliplan.times[key])
        liliplan.previews[key] = link


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

    files = ('main.py', 'preview_factory.py', 'timetable_parser.py',
             'attachment_database.py')
    db_last_mod = os.path.getmtime(database)
    for file in files:
        if db_last_mod < os.path.getmtime(file):
            os.remove(database)
            break


if __name__ == "__main__":
    # remove the database, if it's older than the Source Code
    check_last_modified()

    img_db = ImageDatabase()
    liliplan = Page(DEFAULT_URL, database=img_db)

    bot = commands.Bot(intents=Intents.all(), command_prefix='/')
    slash = SlashCommand(bot, sync_commands=True)

    @bot.event
    async def on_ready():
        """Called when the Bot is ready"""
        print(f"We've logged in as {bot.user}")

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
        await context.defer()
        data = liliplan.get_plan_for_class(klasse)

        if data is None or data[1] is {}:
            # Send
            await context.send(embed=NO_REPLACEMENTS_EMBED)
        else:
            klasse: str = data[0]
            date: str = liliplan.times.get(klasse)
            for msg in create_vplan_message(data[1], klasse, img_db, date):
                await context.send(**msg)

    @slash.subcommand(
        base='vplan',
        name='klassen',
        description='Schickt alle Klassen, die heute Vertretung haben!')
    async def send_classes_w_replacements(context):
        await context.defer()
        info_embed = Embed(
            title='**Klassen die heute Vertretung haben**:',
            description=
            f"`{'`, `'.join(liliplan.get_classes())}`\n\n Verwende `/vplan get <Klasse>` um einen bestimmten Plan zu sehen!"
        )
        info_embed.set_footer(**DEFAULT_FOOTER)
        await context.send(embed=info_embed)

    @slash.subcommand(
        base='vplan',
        name='all',
        description=
        'Schickt ALLE Vertretungen — Nervig & sollte vermieden werden!!!')
    async def send_plan_for_all(context):
        """Sends all replacements, quite annoying!"""
        await context.defer()
        replacements: Dict[
            str, List[ReplacementType]] = liliplan.get_plan_for_all()

        if replacements is None or replacements == {}:
            # No replacements
            await context.send(embed=NO_REPLACEMENTS_EMBED)
        else:
            first: bool = True
            for klasse, events in replacements.items():
                date: str = liliplan.times.get(klasse)
                for msg in create_vplan_message(events, klasse, img_db, date,
                                                False):
                    if first:
                        msg['content'] = f"**Vertretungsplan der ganzen Schule für den {'heutigen Tag' if date is None else date.split(' ')[0]}:**\n\n" + msg[
                            'content']
                        await context.send(**msg)
                        first = False
                    else:
                        await context.send(**msg)

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
