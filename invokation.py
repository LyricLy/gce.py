import asyncio
import datetime
import discord
import textwrap
import shlex
import io

import sources


SUCCESS = "<a:success:1063592453434773635>"
FAILED = "<a:failed:1063589487420117052>"
TIMED_OUT = "<a:timed_out:1063619304945360907>"
STDOUT = "<a:stdout:1063612629765079171>"
STDERR = "<a:stderr:1063598758153158756>"
RUNNING = "<a:running:1063577055796658277>"


def render(b, name, *, file=False, codeblock=False):
    try:
        out = b.decode()
    except UnicodeDecodeError:
        out = None
    if file or out is None or textwrap.fill(out, 80, tabsize=4, replace_whitespace=False).count("\n") > 10:
        return discord.File(io.BytesIO(b), f"{name}.txt")
    if codeblock:
        out = out.replace('```', '`\u200b``')
        out = f"```\n\u200b{out}```"
    return name, out


class Invokation:
    results = {}

    def __init__(self, session, message, lang, code, stdin="", options=[], args=[]):
        self.session = session
        self.lang = lang
        self.message = message
        self.output_message = None
        self.code = code
        self.stdin = stdin
        self.options = options
        self.args = args
        self.stdout = b""
        self.stderr = b""
        self.is_reboot = False
        self.success = False

        if old := Invokation.results.get(message.id):
            old.task.cancel()
            # re-use some things
            self.output_message = old.output_message
            self.stdin = old.stdin
            self.options = old.options
            self.args = old.args
            self.is_reboot = True

    async def send_public_message(self, content=None, embed=None, files=None):
        if not (content or embed or files):
            if self.output_message:
                await self.output_message.delete()
                self.output_message = None
            return

        if self.output_message:
            return await self.output_message.edit(content=content, embed=embed, attachments=files)

        self.output_message = await self.message.channel.send(content, embed=embed, files=files, reference=self.message if self.message.channel.last_message_id != self.message.id else None, mention_author=False)

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

        async def running():
            nonlocal sent_running
            # wait a bit for quick programs to finish right away without wasting time reacting
            await asyncio.sleep(2)

            if self.is_reboot:
                await self.message.clear_reactions()
            await self.message.add_reaction(RUNNING)
            sent_running = True

            if self.output_message:
                await self.output_message.edit(content="Message edited. Recalculating...", embed=None, attachments=[])

        sent_running = False
        send_running = loop.create_task(running())
        await self.lang.execute(self)
        send_running.cancel()

        is_stdout = bool(self.stdout)
        is_stderr = bool(self.stderr)
        self.send_stdout = bool(self.success) and is_stdout
        self.send_stderr = False

        async def send_reactions():
            if sent_running or self.is_reboot:
                await self.message.clear_reactions()

            if self.success:
                await self.message.add_reaction(SUCCESS)
            elif self.success is None:
                await self.message.add_reaction(TIMED_OUT)
            else:
                await self.message.add_reaction(FAILED)

            if not self.success and is_stdout:
                await self.message.add_reaction(STDOUT)
            if is_stderr:
                await self.message.add_reaction(STDERR)

        loop.create_task(send_reactions())

        await self.send_output()

    async def execute(self):
        Invokation.results[self.message.id] = self
        self.task = task = asyncio.get_event_loop().create_task(self._execute())
        await task

    @staticmethod
    async def delete(message):
        if (inv := Invokation.results.get(message.id)) and inv.output_message:
            del Invokation.results[message.id]
            await inv.output_message.delete()

    @staticmethod
    async def jostle_stdout(message_id, value):
        if inv := Invokation.results.get(message_id):
            if not value:
                inv.send_stdout -= 1
                if not inv.send_stdout:
                    await inv.send_output()
            else:
                send = not inv.send_stdout
                inv.send_stdout += 1
                if send:
                    await inv.send_output()

    @staticmethod
    async def jostle_stderr(message_id, value):
        if inv := Invokation.results.get(message_id):
            if not value:
                inv.send_stderr -= 1
                if not inv.send_stderr:
                    await inv.send_output()
            else:
                send = not inv.send_stderr
                inv.send_stderr += 1
                if send:
                    await inv.send_output()
