import aiohttp
import time
import re
import shlex
from typing import Optional

import discord
from discord.ext import commands

import sources
from invokation import Invokation


intents = discord.Intents(
    guilds=True,
    messages=True,
    message_content=True,
)

bot = commands.Bot(
    command_prefix="gce!",
    help_command=None,
    intents=discord.Intents(
        guilds=True,
        messages=True,
        message_content=True,
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
        await Invokation(session, *m, message=message).execute()

@bot.event
async def on_message_edit(before, after):
    if after.author.bot or not after.guild:
        return
    if before.content != after.content and (m := parse_text(after.content)):
        await Invokation(session, *m, message=after).execute()

@bot.event
async def on_message_delete(message):
    await Invokation.delete(message)


async def parse_invokation(interaction, lang, code, stdin, options, args):
    lang = sources.languages.get(lang)
    if not lang:
        return await interaction.response.send_message("Unknown language.", ephemeral=True)
    if not isinstance(code, bytes):
        code = code.encode()
    try:
        options = shlex.split(options)
    except ValueError as e:
        return await interaction.response.send_message("Invalid options: {e}", ephemeral=True)
    try:
        args = shlex.split(args)
    except ValueError as e:
        return await interaction.response.send_message("Invalid arguments: {e}", ephemeral=True)

    await Invokation(session, lang, code, stdin, options, args, interaction=interaction).execute()

class Run(discord.ui.Modal, title="Run code"):
    code = discord.ui.TextInput(label="Code", style=discord.TextStyle.paragraph, required=False)
    options = discord.ui.TextInput(label="Options", required=False, placeholder="Options to the interpreter or compiler.")
    stdin = discord.ui.TextInput(label="Input", required=False)
    args = discord.ui.TextInput(label="Arguments", required=False, placeholder="Arguments to the program.")
    lang = discord.ui.TextInput(label="Language", max_length=32)

    def __init__(self, lang, code, stdin, options, args):
        super().__init__()
        self.lang.default = lang
        self.lang.placeholder = lang
        self.options.default = options
        try:
            c = code.decode()
        except UnicodeDecodeError:
            c = None
        if c is None or len(c) > 4000:
            self.code_value = code
            self.remove_item(self.code)
        else:
            self.code.default = c
        self.stdin.default = stdin
        self.args.default = args

    async def on_submit(self, interaction):
        await parse_invokation(interaction, self.lang.value, self.code.value if self.code.value is not None else self.code_value, self.stdin.value, self.options.value, self.args.value)

@bot.tree.command()
async def run(
    interaction, lang: str,
    code: Optional[str], attachment: Optional[discord.Attachment],
    input: Optional[str] = "", options: Optional[str] = "", arguments: Optional[str] = "",
):
    if lang not in sources.languages:
        return await interaction.response.send_message("Unknown language.", ephemeral=True)
    await interaction.response.send_modal(Run(lang, await attachment.read() if attachment else code.encode() if code else b"", input, options, arguments))

@bot.tree.command()
async def eval(
    interaction, lang: str, code: str,
    input: Optional[str] = "", options: Optional[str] = "", arguments: Optional[str] = "",
):
    await parse_invokation(interaction, lang, code, input, options, arguments)

@bot.tree.context_menu()
async def invoke(interaction, message: discord.Message):
    if inv := Invokation.results.get(message):
        r = Run(inv.lang.id, inv.code, inv.stdin, inv.options, inv.args)
    elif m := parse_text(message):
        r = Run(*m, "", "", "")
    await interaction.response.send_modal(r)

@bot.tree.context_menu()
async def debug(interaction, message: discord.Message):
    await Invokation.debug(interaction, message)

@run.autocomplete("lang")
@eval.autocomplete("lang")
async def lang_autocomplete(interaction, current):
    if not current:
        return []
    l = [discord.app_commands.Choice(name=lang.name, value=lang.id) for lang in sources.languages.values() if lang.name.lower().startswith(current.lower()) or lang.id.lower().startswith(current.lower())]
    l.sort(key=lambda c: c.value)
    return l[:25]


async def setup():
    global session
    session = aiohttp.ClientSession()
    await sources.populate_languages(session)
    await bot.load_extension("jishaku")
    
bot.setup_hook = setup

with open("token.txt") as f:
    bot.run(f.read().strip())
