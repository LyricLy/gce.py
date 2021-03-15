import asyncio
import io
import time


with open("languages") as f:
    languages = {(x := l.split(":"))[0].strip(): x[1].strip() for l in f.read().splitlines()}

async def execute(lang, code, input_):
    if isinstance(code, str):
        code = code.encode()
    filename = f".code_{hash(code)}"
    with open(filename, "wb") as f:
        f.write(code)
    start = time.perf_counter()
    sh = await asyncio.create_subprocess_shell(languages[lang].format(code=filename), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(sh.communicate(input_.encode()), timeout=15)
        return stdout, stderr + f"\nReal time: {time.perf_counter()-start:.3f} s\na\na\na\n{sh.returncode}".encode(), b""
    except asyncio.TimeoutError:
        # if we try to read the data, we're likely just to deadlock
        return b"", b"", b"Execution timed out after 15s."
