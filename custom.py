import asyncio
import io
import os
import time
import shlex


with open("languages") as f:
    languages = {(x := l.split(":"))[0].strip(): x[1].strip() for l in f.read().splitlines()}

async def execute(lang, code, input_, options, args):
    if isinstance(code, str):
        code = code.encode()
    filename = f".code_{hash(code)}"
    with open(filename, "wb") as f:
        f.write(code)
    start = time.perf_counter()
    s = languages[lang].format(code=filename, options=" ".join(map(shlex.quote, options)), args=" ".join(map(shlex.quote, args)))
    sh = await asyncio.create_subprocess_shell(s, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(sh.communicate(input_.encode()), timeout=15)
        return stdout, stderr + f"\nReal time: {time.perf_counter()-start:.3f} s\nExit code: {sh.returncode}".encode(), b""
    except asyncio.TimeoutError:
        # if we try to read the data, we're likely just to deadlock
        return b"", b"", b"Execution timed out after 15s."
    finally:
        os.remove(filename)
