import zlib

import aiohttp

from .common import *


class Request:
    def __init__(self):
        self.files = []
        self.variables = []

    def add_file(self, name, content):
        self.files.append((name, content))

    def add_variable(self, name, *values):
        self.variables.append((name, values))

    def render_bytes(self):
        output = b""
        for name, values in self.variables:
            output += b"V" + name + b"\x00" + f"{len(values)}".encode() + b"\x00" + b"".join(value + b"\x00" for value in values)
        for name, content in self.files:
            output += b"F" + name + b"\x00" + f"{len(content)}".encode() + b"\x00" + content + b"\x00"
        output += b"R"
        return zlib.compress(output, 9)[2:-4]


async def execute(inv):
    r = Request()
    r.add_variable(b"lang", inv.lang.id.encode())
    r.add_variable([b"TIO_OPTIONS", b"TIO_CFLAGS"][language_info[inv.lang.id]], *map(str.encode, inv.options))
    r.add_variable(b"args", *map(str.encode, inv.args))
    r.add_file(b".code.tio", inv.code)
    r.add_file(b".input.tio", inv.stdin.encode())
    d = r.render_bytes()

    async with inv.session.post("https://tio.run/cgi-bin/run/api/", data=d) as resp:
        t = await resp.read()
        d = list(filter(bool, t.split(t[:16])))
        if len(d) == 1:
            d = b"", *d, b""
        elif len(d) == 2:
            if b"Real time" not in d[0]:
                d = *d, b""
            else:
                d = b"", *d

    output, debug, info = d
    inv.stdout = output
    *_, debug, spare = [b""] + debug.rsplit(b"\n\n", 1)
    if spare.endswith(b" 0"):
        inv.success = True
    inv.stderr = debug
    inv.info = info.decode()


language_info = {}

async def populate_languages(session, languages):
    async with session.get("https://tio.run/languages.json") as resp:
        for key, value in (await resp.json()).items():
            languages[key] = Language(key, value["name"], guess_extension(key) or value.get("prettify") or key, execute)
            language_info[key] = "cflags" in value.get("unmask", [])
