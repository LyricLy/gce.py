import asyncio
import json
import re
import traceback
import sys
import socket
import shlex
import os
import io
from subprocess import PIPE

import aiohttp
import discord
from discord.ext import commands
from fuzzywuzzy import process

import tio
import custom


bot = commands.Bot(command_prefix="tio!", help_command=commands.DefaultHelpCommand(width=100))
bot.load_extension("jishaku")


@bot.event
async def on_ready():
    print(f"Ready on {bot.user}")
    if os.path.exists("close_channel"):
        with open("close_channel") as f:
            close_channel = int(f.read())
        os.remove("close_channel")
        await bot.get_channel(close_channel).send("ただいま！")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument: {error}")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("That command doesn't exist.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You're not permitted to use that command.")
    else:
        await ctx.send("An uncaught exception occurred. It's been logged somewhere, but if this is unexpected, please get LyricLy to take a look at it.")
        traceback.print_exception(type(error), error, error.__traceback__)

@bot.command()
@commands.is_owner()
async def update(ctx):
    embed = discord.Embed(title="Running `git pull`", colour=0x7289DA)
    msg = await ctx.send(embed=embed)
    p = await asyncio.create_subprocess_exec("git", "pull", stdout=PIPE)
    code = await p.wait()
    embed.colour = 0xFF0000 if code else 0x00FF00
    stdout, stderr = await p.communicate()
    if stdout:
        embed.description = f"```\n{stdout.decode('utf-8')}\n```"
    if stderr:
        embed.add_field(name="Error output", value=f"```\n{stderr.decode('utf-8')}\n```", inline=False)
    embed.title = "`git pull` completed" + " with errors" * bool(code)
    await msg.edit(embed=embed)
    await ctx.send("Shutting down...")
    with open("close_channel", "w") as f:
        f.write(str(ctx.channel.id))
    await bot.session.close()
    await bot.close()


def save_json():
    with open("options.json", "w") as f:
        json.dump(bot.options, f)

def get_options(member, key=None):
    try:
        data = bot.options[str(member.id)]
    except KeyError:
        data = {}
        for opt in valid_opts:
            data[opt] = valid_opts[opt][1]
        bot.options[str(member.id)] = data
        save_json()

    return data if not key else data[key]

try:
    with open("options.json") as f:
        bot.options = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    bot.options = {}
    save_json()

valid_opts = {
    "implicit": (bool, True, "Whether you can trigger the bot implicitly, without a mention."),
}

@bot.group(invoke_without_command=True)
async def opt(ctx):
    """Set and get options."""
    await ctx.send("\n".join(f"{key}: {value}" for key, value in get_options(ctx.author).items()))

# LMAO
for key, (converter, default, desc) in valid_opts.items():
    async def _get_setter(ctx, arg: converter = None):
        if arg is None:
            await ctx.send(get_options(ctx.author, ctx.command.name))
        else:
            get_options(ctx.author)[ctx.command.name] = arg
            save_json()
            await ctx.send(f"Set {ctx.command.name} to: {arg}")
    _get_setter.__doc__ = desc
    opt.command(name=key)(_get_setter)



def match_lang(term, score, limit):
    return map(lambda x: x[0], process.extractBests(term, list(bot.langs.keys()) + list(custom.languages.keys()), processor=lambda s: s.split("-", 1)[0], score_cutoff=score, limit=limit))

@bot.command()
async def langs(ctx, *, search=None):
    """Find usable languages."""
    if search:
        langs = match_lang(search, 88, 20)
    else:
        langs = list(set(bot.langs) | set(custom.languages))

    output = []
    length = -1
    for lang in langs:
        length += len(lang) + 1
        if length < 2000:
            output.append(lang)
        else:
            length = 0
            await ctx.send(" ".join(output))
            output = []

    if output:
        await ctx.send(" ".join(output))
    else:
        await ctx.send("No matches found.")


LANG = r"([a-zA-Z_\-+.0-9]+)"
CODEBLOCK = re.compile(rf"```{LANG}\n(.*?)```", re.DOTALL)

bot.results = {}

aliases = {
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
    "perl": "perl5",
    "vb": "vb-core",
    "x86asm": "assembly",
    "k": "k-kona"
}

def format_debug(debug, info):
    output = discord.utils.escape_markdown(debug)
    if len(output) < 2000:
        e = discord.Embed(title="Debug", description=output)
        if info:
            e.add_field(name="Info", value=info)
        return {"embed": e}
    else:
        v = {"file": discord.File(io.StringIO(debug), filename="debug.txt")}
        if info:
            v["embed"] = discord.Embed(title="Info", description=info).set_footer(text="Debug information is in the below file.")
        return v

async def execute_code(message, lang, code, explicit, options, args):
    input_ = ""
    if explicit:
        msg = await message.channel.send("Enter some input for the program to take, or click the X to run with no input.")
        await msg.add_reaction("❌")
        done, pending = await asyncio.wait([
            asyncio.create_task(bot.wait_for("message", check=lambda m: m.author == message.author)),
            asyncio.create_task(bot.wait_for("reaction_add", check=lambda r, u: u == message.author and r.message.id == msg.id and str(r.emoji) == "❌")),
        ], return_when=asyncio.FIRST_COMPLETED)
        obj = done.pop().result()
        if isinstance(obj, discord.Message):
            if obj.attachments:
                input_ = await obj.attachments[0].read()
            else:
                input_ = obj.content
        await msg.delete()

    if lang in custom.languages:
        output, debug, info = await custom.execute(lang, code, input_, options, args)
    else:
        output, debug, info = await tio.request(bot.session, lang, code, input_, options, args)
    bot.results[message.author] = (lang, code, options, args, debug, info)

    if explicit and (info or not debug.endswith(b"0")):
        embed = format_debug(debug.decode(), info.decode())
    else:
        embed = {}

    if len(output) < 2000:
        if output.strip():
            await message.channel.send(output.decode(), **embed)
        elif explicit:
            await message.channel.send("(no output)", **embed)
    elif explicit:
        msg = await message.channel.send(f"Output is too large. Would you like it as a link?")
        await msg.add_reaction("📎")
        await msg.add_reaction("❌")
        reaction, _ = await bot.wait_for("reaction_add", check=lambda r, u: u == message.author and r.message.id == msg.id and str(r.emoji) in ["📎", "❌"])
        if reaction.emoji == "📎":
            async with bot.session.post("https://mystb.in/documents", data=output) as resp:
                key = (await resp.json())["key"]
            await message.channel.send(f"<https://mystb.in/{key}.txt>", **embed)
        await msg.delete()

@bot.command(aliases=["replicate", "redo", "again"])
async def repeat(ctx):
    """Repeat the last TIO invokation you performed in explicit mode, allowing you to give new input."""
    if ctx.author not in bot.results:
        return await ctx.send("You haven't used TIO.py recently.")
    lang, code, options, args, *_ = bot.results[ctx.author]
    await execute_code(ctx.message, lang, code, True, args)

@bot.command(aliases=["error", "err"])
async def debug(ctx):
    """Post the debug embed of the last TIO invokation you performed."""
    if ctx.author not in bot.results:
        return await ctx.send("You haven't used TIO.py recently.")
    _, _, _, _, debug, info = bot.results[ctx.author]
    await ctx.send(**format_debug(debug.decode(), info.decode()))

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot:
        return

    explicit = bot.user in message.mentions
    options = ""
    args = ""
    if explicit or get_options(message.author, "implicit"):
        match = re.search(CODEBLOCK, message.content)
        if not match:
            if explicit:
                if message.attachments:
                    code = await message.attachments[0].read()
                    lang_match = re.search(rf"^(.*?)<@!?{bot.user.id}>\s*{LANG}(.*?)\n", message.content)
                    if lang_match:
                        lang = lang_match.group(2)
                        options = lang_match.group(1)
                        args = lang_match.group(3)
                    else:
                        return await message.channel.send("Please send a language in your message to use an attachment.")
                else:
                    return await message.channel.send("I didn't find a code block or attachment in or on your message.")
            else:
                return
        else:
            lang, code = match.group(1), match.group(2)
            if explicit:
                arg_match = re.search(f"^(.*?)<@!?{bot.user.id}>(.*?)\n", message.content)
                if arg_match:
                    options = arg_match.group(1)
                    args = arg_match.group(2)

        lang = aliases.get(lang.lower(), lang.lower())

        if lang in custom.languages or lang in bot.langs:
            await execute_code(message, lang, code, explicit, shlex.split(options), shlex.split(args))
        elif explicit:
            o = f"`{lang}` is not a supported language."
            matches = list(match_lang(lang, 88, 8))
            if matches:
                o += f" Did you mean one of: {', '.join(matches)}"
            return await message.channel.send(o)


@bot.command(aliases=["example"])
async def helloworld(ctx, lang):
    try:
        data = bot.langs[aliases.get(lang.lower(), lang.lower())]
    except KeyError:
        return await ctx.send("I couldn't find that language on TIO.")
    name = data["name"]
    code = data["tests"]["helloWorld"]["request"][0]["payload"][".code.tio"].replace("```", "`\u200b``")
    await ctx.send(f'"Hello, World!" in {data["name"]}:\n```{lang}\n{code}```')


async def setup():
    bot.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(family=socket.AF_INET))
    bot.langs = await tio.get_languages(bot.session)

bot.loop.run_until_complete(setup())

with open("token.txt") as f:
    bot.run(f.read().strip())
