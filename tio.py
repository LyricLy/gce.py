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


async def request(session, lang, code, input_=None, options=(), args=()):
    if isinstance(lang, str):
        lang = lang.encode()
    if isinstance(code, str):
        code = code.encode()
    if isinstance(input_, str):
        input_ = input_.encode()

    r = Request()
    r.add_variable(b"lang", lang)
    r.add_variable(b"TIO_OPTIONS", *map(str.encode, options))
    r.add_variable(b"args", *map(str.encode, args))
    r.add_file(b".code.tio", code)
    if input_:
        r.add_file(b".input.tio", input_)
    d = r.render_bytes()
    async with session.post("https://tio.run/cgi-bin/run/api/", data=d) as resp:
        t = await resp.read()
        d = list(filter(bool, t.split(t[:16])))
        if len(d) == 1:
            return b"", *d, b""
        elif len(d) == 2:
            if b"Real time" not in d[0]:
                return *d, b""
            else:
                return b"", *d
        else:
            return tuple(d)

async def get_languages(session):
    async with session.get("https://tio.run/languages.json") as resp:
        return dict(sorted((await resp.json()).items()))
