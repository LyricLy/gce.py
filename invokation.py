import asyncio
import datetime
import discord
import shlex
import io

import sources


SUCCESS = "<a:success:1063592453434773635>"
FAILED = "<a:failed:1063589487420117052>"
TIMED_OUT = "<a:timed_out:1063619304945360907>"
OOM = "<a:oom:1101042334818385960>"
STDOUT = "<a:stdout:1063612629765079171>"
STDERR = "<a:stderr:1063598758153158756>"
RUNNING = "<a:running:1063577055796658277>"


def render(b, name, *, file=False, codeblock=False):
    try:
        out = b.decode()
    except UnicodeDecodeError:
        out = None
    if file or out is None or sum(1 + len(x) // 90 for x in out.splitlines()) > 11:
        return discord.File(io.BytesIO(b), f"{name}.txt")
    if codeblock:
        out = out.replace('```', '`\u200b``')
        out = f"```\n\u200b{out}```"
    return name, out

def attr(e):
    return "send_stdout" if e == STDOUT or e[1:] == STDOUT[2:] else "send_stderr" if e == STDERR or e[1:] == STDERR[2:] else None


class Invokation:
    def __init__(self, session, message, lang, code, *, outputter, stdin="", options=(), args=()):
        self.session = session
        self.lang = lang
        self.message = message
        self.outputter = outputter
        self.code = code
        self.stdin = stdin
        self.options = options
        self.args = args
        self.stdout = b""
        self.stderr = b""
        self.success = sources.FAILED

    async def send_public_message(self, content="", embed=None, files=None):
        if not (content.strip() or embed or files):
            await self.outputter.delete()
            return

        if self.outputter.can_edit():
            return await self.outputter.edit(content=content, embed=embed, attachments=files)

        await self.outputter.send(content, embed=embed, files=files, reference=self.message if self.message.channel.last_message_id != self.message.id else None, mention_author=False)

    async def send_output(self):
        texts = []
        files = []

        if self.send_stdout:
            s = render(self.stdout, "stdout")
            if isinstance(s, discord.File):
                files.append(s)
            else:
                texts.append(s)

        if self.send_stderr:
            s = render(self.stderr, "stderr", file=files, codeblock=True)
            if isinstance(s, discord.File):
                files.append(s)
            else:
                texts.append(s)

        if len(texts) == 2 or self.stdin or self.options or self.args:
            text = ""
            embed = discord.Embed()
            if self.options:
                embed.add_field(name="Options", value=shlex.join(self.options), inline=False)
            if self.stdin:
                embed.add_field(name="Input", value=self.stdin, inline=False)
            if self.args:
                embed.add_field(name="Arguments", value=shlex.join(self.args), inline=False)
            for name, value in texts:
                embed.add_field(name=name, value=value, inline=False)
        elif texts:
            text = texts[0][1]
            embed = None
        else:
            text = ""
            embed = None

        await self.send_public_message(text, embed=embed, files=files)

    async def _execute(self):
        loop = asyncio.get_event_loop()
        me = self.message.guild.me
        can_react = hasattr(self.outputter, "add_reaction")

        async def running():
            # wait a bit for quick programs to finish right away without wasting time reacting
            await asyncio.sleep(2)

            await self.outputter.clear_reactions()
            await self.outputter.add_reaction(RUNNING)

            if self.outputter.can_edit():
                await self.outputter.edit(content="Message edited. Recalculating...", embed=None, attachments=[])

        send_running = loop.create_task(running() if can_react else asyncio.sleep(0))
        await self.lang.execute(self)
        send_running.cancel()

        is_stdout = bool(self.stdout)
        is_stderr = bool(self.stderr)

        if can_react:
            self.send_stdout = self.success == sources.SUCCESS and is_stdout
            self.send_stderr = False

            async def send_reactions():
                await self.outputter.clear_reactions()

                if self.success == sources.SUCCESS:
                    await self.outputter.add_reaction(SUCCESS)
                elif self.success == sources.TIMEOUT:
                    await self.outputter.add_reaction(TIMED_OUT)
                elif self.success == sources.OOM:
                    await self.outputter.add_reaction(OOM)
                else:
                    await self.outputter.add_reaction(FAILED)

                if self.success != sources.SUCCESS and is_stdout:
                    await self.outputter.add_reaction(STDOUT)
                if is_stderr:
                    await self.outputter.add_reaction(STDERR)

            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_reactions())
                tg.create_task(self.send_output())
        else:
            self.send_stdout = is_stdout
            self.send_stderr = is_stderr
            await self.send_output()

    async def execute(self):
        self.task = task = asyncio.get_event_loop().create_task(self._execute())
        await task
