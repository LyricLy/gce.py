import asyncio
import json
import re
import traceback
from subprocess import PIPE

import aiohttp
import discord
from discord.ext import commands
from fuzzywuzzy import process

import tio


bot = commands.Bot(command_prefix="tiop!", help_command=commands.DefaultHelpCommand(width=100))
bot.load_extension("jishaku")


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
    sys.exit(0)


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
    return map(lambda x: x[0], process.extractBests(term, bot.langs, processor=lambda s: s.split("-", 1)[0], score_cutoff=score, limit=limit))

@bot.command()
async def langs(ctx, *, search=None):
    langs = bot.langs
    if search:
        langs = match_lang(search, 88, 20)

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


CODEBLOCK_REGEX = re.compile(r"```(\w+)\n(.*?)```", re.DOTALL)

aliases = {
    "bf": "brainfuck",
    "rb": "ruby",
    "rs": "rust",
    "py": "python3",
    "python": "python3",
    "java": "java-jdk",
    "c": "c-gcc",
    "cpp": "cpp-gcc",
    "js": "javascript-node",
    "javascript": "javascript-node",
    "hs": "haskell",
    "perl": "perl5",
    "vb": "vb-core",
    "x86asm": "assembly",
    "k": "k-kona"
}

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot:
        return

    explicit = bot.user in message.mentions
    if explicit or get_options(message.author, "implicit"):
        match = re.search(CODEBLOCK_REGEX, message.content)
        if not match:
            if explicit:
                # TODO: attachments
                await message.channel.send("I didn't find a code block in your message.")
            return
        else:
            lang, code = match.group(1), match.group(2)

        lang = aliases.get(lang, lang)
        if lang not in bot.langs and explicit:
            o = f"`{lang}` is not a supported language."
            matches = list(match_lang(lang, 88, 8))
            if matches:
                o += f" Did you mean one of: {', '.join(matches)}"
            return await message.channel.send(o)

        input_ = ""
        if explicit:
            msg = await message.channel.send("Enter some input for the program to take, or click the X to run with no input.")
            await msg.add_reaction("❌")
            done, pending = await asyncio.wait([
                bot.wait_for("message", check=lambda m: m.author == message.author),
                bot.wait_for("reaction_add", check=lambda r, u: u == message.author and str(r.emoji) == "❌")
            ], return_when=asyncio.FIRST_COMPLETED); [*map(asyncio.Future.cancel, pending)]
            obj = done.pop().result()
            if isinstance(obj, discord.Message):
                input_ = obj.content

        output, debug = await tio.request(bot.session, lang, code, input_)

        if len(output) < 2000:
            if output:
                await message.channel.send(output)
        elif explicit:
            # TODO: send as attachment
            await message.channel.send("Output is too large.")

        if debug[-1] != "0" and explicit:
            await message.channel.send(embed=discord.Embed(title="Debug", description="".join(debug.splitlines(True)[:-4])[:2000]))


async def setup():
    bot.session = aiohttp.ClientSession()
    bot.langs = await tio.get_languages(bot.session)

bot.loop.run_until_complete(setup())

with open("token.txt") as f:
    bot.run(f.read().strip())
