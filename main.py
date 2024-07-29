import aiohttp
import time
import re
import shlex
from typing import Optional

import discord
from discord.ext import commands
from parse_discord import parse, Codeblock

import sources
from outputter import StandardOutputter, InteractionOutputter
from invokation import Invokation, attr
from langdata import ALIASES


bot = commands.Bot(
    command_prefix="gce!",
    help_command=None,
    intents=discord.Intents(
        guilds=True,
        messages=True,
        message_content=True,
        reactions=True,
    ),
    allowed_mentions=discord.AllowedMentions.none(),
    max_messages=None,
)
results = {}


@bot.event
async def on_ready():
    print(f"Ready on {bot.user}")

def parse_text(msg):
    text = msg.content
    if msg.author.id in (261243340752814085, 179957318941671424) and "gce" not in text.lower():
        return None
    for m in parse(text).walk():
        if not isinstance(m, Codeblock):
            continue
        if not m.language:
            continue
        lang = ALIASES.get(m.language, m.language)
        code = m.content.encode() + b"\n"
        if l := sources.languages.get(lang):
            return l, code
    return None

async def execute(inv):
    results[inv.message.id] = inv
    await inv.execute()

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author.bot or not message.guild:
        return
    if m := parse_text(message):
        await execute(Invokation(session, message, *m, outputter=StandardOutputter(message)))

async def delete(message):
    if inv := results.get(message.id):
        del results[message.id]
        await inv.outputter.delete()

@bot.event
async def on_message_edit(before, after):
    if after.author.bot or not after.guild:
        return
    inv = results.get(after.id)
    if m := parse_text(after):
        if not inv or m != (inv.lang, inv.code):
            if inv:
                inv.task.cancel()
                inv = Invokation(session, after, *m, stdin=inv.stdin, args=inv.args, options=inv.options, outputter=inv.outputter)
            else:
                inv = Invokation(session, after, *m, outputter=StandardOutputter(after))
            await execute(inv)
    elif inv:
        await after.clear_reactions()
        await delete(after)

@bot.event
async def on_message_delete(message):
    await delete(message)

async def jostle(emoji, message_id, user_id, value):
    if (inv := results.get(message_id)) and user_id == inv.message.author.id and (a := attr(emoji)):
        setattr(inv, a, value)
        await inv.send_output()

@bot.event
async def on_raw_reaction_add(payload):
    await jostle(str(payload.emoji), payload.message_id, payload.user_id, True)

@bot.event
async def on_raw_reaction_remove(payload):
    await jostle(str(payload.emoji), payload.message_id, payload.user_id, False)


class Options(discord.ui.Modal, title="Edit options"):
    options = discord.ui.TextInput(label="Options", required=False, placeholder="Options to the interpreter or compiler.")
    stdin = discord.ui.TextInput(label="Input", style=discord.TextStyle.paragraph, required=False, placeholder="Standard input.")
    args = discord.ui.TextInput(label="Arguments", required=False, placeholder="Arguments to the program.")

    def __init__(self, inv):
        super().__init__()
        self.inv = inv
        self.options.default = shlex.join(inv.options)
        self.args.default = shlex.join(inv.args)

    async def on_submit(self, interaction):
        try:
            options = shlex.split(self.options.value)
        except ValueError as e:
            return await interaction.response.send_message("Invalid options: {e}", ephemeral=True)
        try:
            args = shlex.split(self.args.value)
        except ValueError as e:
            return await interaction.response.send_message("Invalid arguments: {e}", ephemeral=True)
        await interaction.response.defer()

        if not (self.stdin.value != self.inv.stdin or options != self.inv.options or args != self.inv.args):
            return

        await execute(Invokation(
            session,
            self.inv.message,
            self.inv.lang,
            self.inv.code,
            stdin=self.stdin.value,
            options=options,
            args=args,
            outputter=self.inv.outputter,
        ))

@discord.app_commands.user_install()
@bot.tree.context_menu()
async def invoke(interaction, message: discord.Message):
    ephemeral = message.author.id != interaction.user.id
    if m := parse_text(message):
        await interaction.response.defer(ephemeral=ephemeral)
        await Invokation(session, message, *m, outputter=InteractionOutputter(interaction)).execute()
    else:
        await interaction.response.send_message("There's no code in this message.", ephemeral=True)

@bot.tree.context_menu(name="Edit options")
async def edit_options(interaction, message: discord.Message):
    if message.author.id != interaction.user.id:
        await interaction.response.send_message("This isn't your message.", ephemeral=True)
    elif inv := results.get(message.id):
        await interaction.response.send_modal(Options(inv))
    else:
        await interaction.response.send_message("There's no code in this message.", ephemeral=True)

@bot.tree.context_menu()
async def info(interaction, message: discord.Message):
    if inv := results.get(message.id):
        await interaction.response.send_message(f"Executed {inv.lang.runner} as {inv.lang.name}.", ephemeral=True)
    else:
        await interaction.response.send_message("There's no code in this message.", ephemeral=True)


class LeftButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Back")

    async def callback(self, interaction):
        self.view.page -= 1
        await interaction.response.edit_message(embed=self.view.embed(), view=self.view)

class RightButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Next")

    async def callback(self, interaction):
        self.view.page += 1
        await interaction.response.edit_message(embed=self.view.embed(), view=self.view)

class ListView(discord.ui.View):
    def __init__(self, langs):
        super().__init__(timeout=60)
        self.langs = langs
        self.per_page = 60
        self.page = 1
        self.left = LeftButton()
        self.right = RightButton()
        if len(langs) > self.per_page:
            self.add_item(self.left)
            self.add_item(self.right)

    def embed(self):
        start = (self.page-1)*self.per_page
        end = self.page*self.per_page
        self.left.disabled = self.page == 1
        self.right.disabled = end >= len(self.langs)
        page = self.langs[start:end]
        e = discord.Embed()
        for field in [page[i:i+10] for i in range(0, len(page), 10)]:
            if not field:
                continue
            e.add_field(name="\u200b", value="\n".join(field), inline=True)
        if len(e.fields) == 1:
            e.description = e.fields[0].value
            e.clear_fields()
        return e

    async def on_timeout(self):
        await self.message.delete()

@bot.command()
async def langs(ctx, *, search=None):
    """Find usable languages."""
    langs = [l.id for l in sources.languages.values()]
    if search:
        langs = [x for x in langs if search in x]

    if langs:
        view = ListView(langs)
        view.message = await ctx.send(embed=view.embed(), view=view)
    else:
        await ctx.send("No matches found.")


async def setup():
    global session
    session = aiohttp.ClientSession()
    await sources.populate_languages(session)
    await bot.load_extension("jishaku")
    
bot.setup_hook = setup

with open("token.txt") as f:
    bot.run(f.read().strip(), root_logger=True)
