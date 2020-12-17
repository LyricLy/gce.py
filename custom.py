import asyncio
import io
import time


languages = {
    "brainfuck": "tritium -b -z .code",
    "letra": "python ../letra.py .code",
}

async def execute(lang, code, input_):
    if isinstance(code, str):
        code = code.encode()
    with open(".code", "wb") as f:
        f.write(code)
    start = time.perf_counter()
    sh = await asyncio.create_subprocess_shell(languages[lang], stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(sh.communicate(input_.encode()), timeout=15)
        return stdout, stderr + f"\nReal time: {time.perf_counter()-start:.3f} s\na\na\na\n{sh.returncode}".encode(), b""
    except asyncio.TimeoutError:
        # if we try to read the data, we're likely just to deadlock
        return b"", b"", b"Execution timed out after 15s."
