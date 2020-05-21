"""
A library to access the private API of tio.run.
Requests are encoded in a simple format and DEFLATE-compressed before sending.
"""

import zlib

import aiohttp


class Request:
    def __init__(self):
        self.files = []
        self.variables = []

    def add_file(self, name, content):
        self.files.append((name, content))

    def add_variable(self, name, value):
        self.variables.append((name, value))

    def render_bytes(self):
        output = b""
        for name, value in self.variables:
            output += f"V{name}\x00{len(value.split(' '))}\x00{value}\x00".encode()
        for name, content in self.files:
            output += f"F{name}\x00{len(content)}\x00{content}\x00".encode()
        output += b"R"
        return zlib.compress(output, 9)[2:-4]


async def request(session, lang, code, input_=None):
    r = Request()
    r.add_variable("lang", lang)
    r.add_file(".code.tio", code)
    if input_:
        r.add_file(".input.tio", input_)
    d = r.render_bytes()
    async with session.post("https://tio.run/cgi-bin/run/api/", data=d) as resp:
        t = await resp.text()
        d = list(filter(bool, t.split(t[:16])))
        if len(d) == 1:
            return "", d[0]
        elif len(d) == 2:
            return d[0], d[1]
        else:
            print(f"abnormal data: {d}")
            return "", ""

async def get_languages(session):
    async with session.get("https://tio.run/languages.json") as resp:
        return sorted((await resp.json()).keys())
