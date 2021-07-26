import asyncio
import json
import re
import traceback
import sys
import socket
import shlex
import os
import time
import io
from subprocess import PIPE

import aiohttp
import discord
from discord.ext import commands
from fuzzywuzzy import process

import tio
import custom


bot = commands.Bot(
    command_prefix="tio!",
    help_command=commands.DefaultHelpCommand(width=100),
    description="A bot that runs code. Use tio!truehelp for more info on actually using me.",
)
bot.load_extension("jishaku")

TRUE_HELP = """
The simplest way to run code is just to use a code block with a language associated, like so:
\`\`\`python
print("Hello, World!")
\`\`\`

You can see a list of the language names you can use by running the `tio!langs` command, or you can search with e.g. `tio!langs pyth`. For most common languages, \
there are also aliases for the names Discord's syntax highlighting will accept, like `py` for `python`, which will work with the bot.

If a program produces too much output, or it exits with a non-zero exit code (signifying a failure), the bot will not produce any output. To see the stderr output \
of a program after TIO.py has executed it, use the `tio!debug` command. By default, it will output from the last time you invoked the bot, but you can specify \
a different invokation by replying to the message or providing a message ID (hold shift while copying it if the message is from a different channel) or a message link.

To provide input and see debug output by default, you can use the bot in "explicit mode" by pinging it in the message with the code block. You can disable "implicit" \
invokation using `tio!opt implicit false`.

You can provide an attachment using explicit mode by specifying a language name after the ping, e.g. `@TIO.py python`. Then simply attach a file.

You can provide options to the compiler or interpreter, or command line arguments, by writing them around the ping. Options go before, and arguments go after. \
If you are passing an attachment, the language name goes before the arguments. For example, one might write `-O3 @TIO.py c arg1 arg2`.

If you reply to a message containing a suitable code block and ping the bot, it will invoke that code for you in explicit mode. There is also a `tio!repeat` command \
which you can use to repeat your last invokation in explicit mode and allows you to provide different input.
"""

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
bot.results_by_msg = {}

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
    try:
        stderr, extra = debug.rsplit("\n\n", 1)
        stderr = stderr.replace('```', '`\u200b``')
        output = f"```{stderr}```\n{extra}"
    except ValueError:
        output = debug
    if len(output) < 4096:
        e = discord.Embed(title="Debug", description=output)
        if info:
            e.add_field(name="Info", value=info)
        return {"embed": e}
    else:
        v = {"file": discord.File(io.StringIO(debug), filename="debug.txt")}
        if info:
            v["embed"] = discord.Embed(title="Info", description=info).set_footer(text="Debug information is in the below file.")
        return v

class Invokation:
    def __init__(self, run_at, message, lang, code, options, args, debug, info):
        self.lang = lang
        self.run_at = run_at
        self.message = message
        self.code = code
        self.options = options
        self.args = args
        self.debug = debug
        self.info = info

async def get_last_invoke(ctx):
    if ctx.author not in bot.results or time.time() - bot.results[ctx.author].run_at > 60:
        await ctx.send("You haven't used TIO.py recently.")
        return None
    return bot.results[ctx.author]

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

    invokation = Invokation(time.time(), message, lang, code, options, args, debug, info)
    bot.results[message.author] = invokation
    bot.results_by_msg[message] = invokation

    if explicit and (info or not debug.endswith(b" 0")):
        embed = format_debug(debug.decode(), info.decode())
    else:
        embed = {}

    if len(output) < 2000:
        if output.strip():
            await message.channel.send(output.decode(), **embed)
        elif explicit:
            await message.channel.send("(no output)", **embed)
    elif explicit:
        await message.channel.send(file=discord.File(fp=io.BytesIO(output), filename="output.txt"))

@bot.command(aliases=["replicate", "redo", "again"])
async def repeat(ctx):
    """Repeat the last TIO invokation you performed in explicit mode."""
    r = await get_last_invoke(ctx)
    if not r:
        return
    await execute_code(ctx.message, r.lang, r.code, True, r.options, r.args)

@bot.command(aliases=["error", "err"])
async def debug(ctx, message: discord.Message = None):
    """Post the debug embed of the last TIO invokation you performed, or the invokation corresponding to a given message."""
    message = message or ctx.message.reference and ctx.message.reference.resolved
    if message:
        if message not in bot.results_by_msg:
            return await ctx.send("The message provided doesn't correspond to an invokation I know of. You can invoke it by replying to it and pinging me in the reply.")
        r = bot.results_by_msg[message]
    else:
        r = await get_last_invoke(ctx)
        if not r:
            return
    content = f"Debug from invokation by {r.message.author.display_name} at <t:{r.run_at:.0f}:T> in {bot.langs[r.lang]['name']}."
    d = format_debug(r.debug.decode(), r.info.decode())
    if r.message.channel == ctx.channel:
        try:
            return await r.message.reply(content, **d, mention_author=False)
        except discord.HTTPException:
            # message gone
            await ctx.send(content, **d)
    else:
        d["embed"].url = r.message.jump_url
        await ctx.send(content, **d)


class CodeParseError(Exception):
    pass

class NoCodeblockError(CodeParseError):
    pass

class NoAttachmentLanguage(CodeParseError):
    pass

async def get_code(message, explicit):
    options = ""
    args = ""
    match = re.search(CODEBLOCK, message.content)
    if not match:
        if explicit:
            if message.attachments:
                code = await message.attachments[0].read()
                lang_match = re.search(rf"^(.*?)<@!?{bot.user.id}>\s*{LANG}(.*?)$", message.content, re.MULTILINE)
                if lang_match:
                    lang = lang_match.group(2)
                    options = lang_match.group(1)
                    args = lang_match.group(3)
                else:
                    raise NoAttachmentLanguage
            else:
                raise NoCodeblockError
        else:
            raise NoCodeblockError
    else:
        lang, code = match.group(1), match.group(2)
        if explicit:
            arg_match = re.search(f"^(?:.*```)?(.*?)<@!?{bot.user.id}>(.*?)$", message.content, re.MULTILINE)
            if arg_match:
                options = arg_match.group(1)
                args = arg_match.group(2)
    return lang, code, options, args
    

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author.bot:
        return

    # only check for explicit mentions
    explicit = bot.user in message.mentions and (f"<@{bot.user.id}>" in message.content or f"<@!{bot.user.id}>" in message.content)

    if explicit or get_options(message.author, "implicit"):
        try:
            lang, code, options, args = await get_code(message, explicit)
        except NoCodeblockError:
            if not explicit:
                return
            success = False
            if message.reference and message.reference.resolved:
                # try to process the replied-to message instead
                try:
                    lang, code, options, args = await get_code(message.reference.resolved, True)
                except CodeParseError:
                    pass
                else:
                    success = True
            if not success:
                return await message.channel.send("Your message doesn't have a code block (remember to specify the language after the ```) or an attachment.")
        except NoAttachmentLanguage:
            return await message.channel.send("Please send a language name after the mention if you want me to run an attachment.")

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
    """Show the 'Hello, World!' program for a TIO language of your choice."""
    try:
        data = bot.langs[aliases.get(lang.lower(), lang.lower())]
    except KeyError:
        return await ctx.send("I couldn't find that language on TIO.")
    name = data["name"]
    code = data["tests"]["helloWorld"]["request"][0]["payload"][".code.tio"].replace("```", "`\u200b``")
    await ctx.send(f'"Hello, World!" in {data["name"]}:\n```{lang}\n{code}```')

@bot.command()
async def truehelp(ctx):
    await ctx.send(TRUE_HELP)


async def setup():
    bot.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(family=socket.AF_INET))
    bot.langs = await tio.get_languages(bot.session)

bot.loop.run_until_complete(setup())

with open("token.txt") as f:
    bot.run(f.read().strip())
