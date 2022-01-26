import asyncio
import io
import os
import time
import shlex
import random
import re


TIMEOUT = 30

with open("languages") as f:
    languages = {}
    for line in f:
        m = re.match("^(.*?)\((.*?)\):(.*?)$", line)
        name = m.group(1).strip()
        display = m.group(2).strip()
        cmd = m.group(3).strip()
        languages[name] = (display, cmd)

async def execute(lang, code, input_, options, args):
    if isinstance(code, str):
        code = code.encode()
    filename = f".code_{random.randint(1, 368307)}.{lang.lower()[:4]}"
    with open(filename, "wb") as f:
        f.write(code)
    start = time.perf_counter()
    s = languages[lang][1].format(code=filename, options=" ".join(map(shlex.quote, options)), args=" ".join(map(shlex.quote, args)), input=shlex.quote(input_))
    sh = await asyncio.create_subprocess_shell(s, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(sh.communicate(input_.encode()), timeout=TIMEOUT)
        return stdout, stderr + f"\nReal time: {time.perf_counter()-start:.3f} s\nExit code: {sh.returncode}".encode(), b""
    except asyncio.TimeoutError:
        # if we try to read the data, we're likely just to deadlock
        return b"", b"", b"Execution timed out after " + str(TIMEOUT).encode() + b"s."
    finally:
        os.remove(filename)
