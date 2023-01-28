import aiohttp
import time
import re
import shlex
from typing import Optional

import discord
from discord.ext import commands
from thefuzz import process

import sources
from invokation import Invokation, STDOUT, STDERR


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
)


@bot.event
async def on_ready():
    print(f"Ready on {bot.user}")


CODEBLOCK = re.compile(rf"```([a-zA-Z_\-+.0-9]+)\n(.*?)```", re.DOTALL)

ALIASES = {
    "bf": "brainfuck",
    "rb": "ruby",
    "rs": "rust",
    "py": "python3",
    "python": "python3",
    "java": "java-jdk",
    "c": "c-gcc",
    "cpp": "cpp-gcc",
    "c++": "cpp-gcc",
    "js": "javascript-node",
    "javascript": "javascript-node",
    "hs": "haskell",
    "pl": "perl5",
    "perl": "perl5",
    "vb": "vb-core",
    "x86asm": "assembly-fasm",
    "k": "k-ngn",
    "cr": "crystal",
}


def parse_text(text):
    if m := CODEBLOCK.search(text):
        lang = m.group(1)
        lang = ALIASES.get(lang, lang)
        code = m.group(2)
        if l := sources.languages.get(lang):
            return l, code.encode()
    return None

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author.bot or not message.guild:
        return
    if m := parse_text(message.content):
        await Invokation(session, message, *m).execute()

@bot.event
async def on_message_edit(before, after):
    if after.author.bot or not after.guild:
        return
    if (m := parse_text(after.content)) and (not (inv := Invokation.results.get(after.id)) or m != (inv.lang, inv.code)):
        await Invokation(session, after, *m).execute()

@bot.event
async def on_message_delete(message):
    await Invokation.delete(message)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    if str(payload.emoji) == STDOUT:
        await Invokation.jostle_stdout(payload.message_id, True)
    elif str(payload.emoji) == STDERR:
        await Invokation.jostle_stderr(payload.message_id, True)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return

    if str(payload.emoji)[1:] == STDOUT[2:]:
        await Invokation.jostle_stdout(payload.message_id, False)
    elif str(payload.emoji)[1:] == STDERR[2:]:
        await Invokation.jostle_stderr(payload.message_id, False)


class Options(discord.ui.Modal, title="Edit options"):
    options = discord.ui.TextInput(label="Options", required=False, placeholder="Options to the interpreter or compiler.")
    stdin = discord.ui.TextInput(label="Input", required=False, placeholder="Standard input.")
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

        inv = Invokation(session, self.inv.message, self.inv.lang, self.inv.code)
        inv.stdin = self.stdin.value
        inv.options = options
        inv.args = args
        await inv.execute()

@bot.tree.context_menu(name="Edit options")
async def edit_options(interaction, message: discord.Message):
    if inv := Invokation.results.get(message.id):
        await interaction.response.send_modal(Options(inv))
    else:
        await interaction.response.send_message("There's no code in this message.", ephemeral=True)

@bot.tree.context_menu()
async def info(interaction, message: discord.Message):
    if inv := Invokation.results.get(message.id):
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
        return e

    async def on_timeout(self):
        await self.message.delete()

def match_lang(term, score, limit):
    return [x[0] for x in process.extractBests(term, [l.id for l in sources.languages.values()], processor=lambda s: s.rsplit("-", 1)[0], score_cutoff=score, limit=limit)]

@bot.command()
async def langs(ctx, *, search=None):
    """Find usable languages."""
    if search:
        langs = match_lang(search, 88, 20)
    else:
        langs = [l.id for l in sources.languages.values()]

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
    bot.run(f.read().strip())
