import asyncio
import datetime
import discord
import textwrap
import io

import sources


def render(b, name, *, codeblock=False, extension=None):
    try:
        out = b.decode()
    except UnicodeDecodeError:
        out = None
    if out is None or textwrap.fill(out, 80, tabsize=4, replace_whitespace=False).count("\n") > 10:
        return discord.File(io.BytesIO(b), f"{name}.{extension or 'txt'}")
    if codeblock:
        out = out.replace('```', '`\u200b``')
        return f"```{extension or ''}\n\u200b{out}```"
    return out


class ControlPanel(discord.ui.View):
    def __init__(self, inv):
        self.inv = inv
        super().__init__()

    async def used(self, interaction, button):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Show stdout", style=discord.ButtonStyle.primary)
    async def show_stdout(self, interaction, button):
        r = render(self.inv.stdout, "output")
        if not r:
            r = "(no output)"
        await self.inv.send_public(r)
        await self.used(interaction, button)

    @discord.ui.button(label="Show stderr", style=discord.ButtonStyle.primary)
    async def show_stderr(self, interaction, button):
        r = render(self.inv.stderr, "error", codeblock=True)
        await self.inv.send_public(r)
        await self.used(interaction, button)

    @discord.ui.button(label="Show all")
    async def show_all(self, interaction, button):
        await self.inv.send_full(public=True)
        await self.used(interaction, button)


class Invokation:
    results = {}

    def __init__(self, session, lang, code, stdin="", options=(), args=(), *, interaction=None, message=None):
        self.session = session
        self.lang = lang
        self.interaction = interaction
        self.message = message
        self.output_message = None
        self.code = code
        self.stdin = stdin
        self.options = options
        self.args = args
        self.stdout = b""
        self.stderr = b""
        self.info = ""
        self.success = False
        self.start = message.channel.last_message_id if message else None
        self.end = self.start
        self.last_bot_message = None

        if old := Invokation.results.get(message):
            # re-use some things
            self.output_message = old.output_message
            self.interaction = old.interaction
            self.stdin = old.stdin
            self.options = old.options
            self.args = old.args
            self.start = old.start
            self.end = old.end
            self.last_bot_message = old.last_bot_message

    def get_reply(self):
        return self.message if self.message and self.now() != self.start else None

    def now(self):
        last = self.message.channel.last_message_id
        return last if last != self.last_bot_message else self.end

    async def send_public_message(self, content=None, embed=None, files=None):
        if self.output_message:
            return await self.output_message.edit(content=content, embed=embed, attachments=files)

        if self.message:
            self.end = self.now()
            msg = await self.message.channel.send(content, embed=embed, files=files, reference=self.message if self.now() != self.start else None, mention_author=False)
        else:
            msg = await self.interaction.channel.send(content, embed=embed, files=files)

        self.last_bot_message = msg.id
        Invokation.results[msg] = self
        self.output_message = msg

    async def send_full(self, *, public=False):
        embed = discord.Embed()
        files = []

        content = ""
        if not self.message:
            r = render(self.code, "code", codeblock=True, extension=self.lang.extension)
            if isinstance(r, discord.File):
                files.append(r)
            else:
                content = r

        for b, name in [(self.stdout, "stdout"), (self.stderr, "stderr")]:
            if not b.strip():
                continue
            r = render(b, name, codeblock=name == "stderr")
            if isinstance(r, discord.File):
                files.append(r)
            else:
                embed.add_field(name=name, value=r, inline=False)

        embed.set_footer(text=self.info)

        if not len(embed):
            embed = None
        if not embed and not files:
            embed = discord.Embed().set_footer(text="No output")

        if public:
            await self.send_public_message(content, embed=embed, files=files)
        elif self.interaction.response.is_done():
            await self.interaction.edit_original_message(content=content, embed=embed, attachments=files, view=ControlPanel(self))
        else:
            await self.interaction.response.send_message(content, embed=embed, files=files, view=ControlPanel(self), ephemeral=True)

    async def send_public(self, s):
        if isinstance(s, discord.File):
            content = ""
            files = [s]
        else:
            content = s
            files = []
        if not self.message:
            # add context
            r = render(self.code, "code", codeblock=True, extension=self.lang.extension)
            if isinstance(r, discord.File):
                files.insert(0, r)
            else:
                content = r + content
        await self.send_public_message(content, files=files)

    async def execute(self):
        if self.message:
            async def typer():
                # don't type for 2 seconds
                # 2 seconds is enough for programs that don't compile or that error quickly to finish
                # we don't want to generate a typing indicator for programs that fail immediately, because the indicator will last for 5 seconds
                await asyncio.sleep(2)
                async with self.message.channel.typing():
                    await asyncio.sleep(120)
            t = asyncio.get_event_loop().create_task(typer())
            await self.lang.execute(self)
            t.cancel()

            Invokation.results[self.message] = self
            output = render(self.stdout, "output")
            if not isinstance(output, str) or not output.strip() or not self.success:
                return

            await self.send_public(output)
        elif self.interaction:
            await self.interaction.response.defer(ephemeral=True, thinking=True)
            await self.lang.execute(self)
            await self.send_full()

    @staticmethod
    async def debug(interaction, message):
        inv = Invokation.results.get(message)
        if not inv:
            return await interaction.response.send_message("That message isn't associated with a completed evaluation.", ephemeral=True)
        if inv.message.author != interaction.user:
            return await interaction.response.send_message("You didn't invoke that evaluation.", ephemeral=True)

        inv.interaction = interaction
        await inv.send_full()

    @staticmethod
    async def delete(message):
        if (inv := Invokation.results.get(message)) and inv.output_message:
            await inv.output_message.delete()
            inv.output_message = None
