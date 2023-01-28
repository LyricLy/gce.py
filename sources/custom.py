import asyncio
import io
import os
import time
import shlex
import random
import re

from .common import *


TIMEOUT = 30

with open("languages") as f:
    languages = {}
    for line in f:
        m = re.match(r"^(.*?)\((.*?)\):(.*?)$", line)
        name = m.group(1).strip()
        display = m.group(2).strip()
        cmd = m.group(3).strip()
        languages[name] = display, cmd

async def execute(inv):
    filename = f".code_{random.randint(1, 368307)}.{inv.lang.id}"
    with open(filename, "wb") as f:
        f.write(inv.code)
    s = languages[inv.lang.id][1].format(code=filename, options=shlex.join(inv.options), args=shlex.join(inv.args), input=shlex.quote(inv.stdin))
    sh = await asyncio.create_subprocess_shell(s, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(sh.communicate(inv.stdin.encode()), timeout=TIMEOUT)
        inv.stdout = stdout
        inv.stderr = stderr
        inv.success = sh.returncode == 0
    except asyncio.TimeoutError:
        # if we try to read the data, we're likely just to deadlock
        inv.success = None
    finally:
        os.remove(filename)

async def populate_languages(_, langs):
    for name, (display, _) in languages.items():
        langs[name] = Language(name, display, execute, "locally")
