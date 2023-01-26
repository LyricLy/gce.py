import aiohttp
import base64

from .common import *


versions = {}

async def execute(inv):
    try:
        c = inv.code.decode()
    except UnicodeDecodeError:
        file = {"content": base64.b64encode(inv.code), "encoding": "base64"}
    else:
        file = {"content": c}
    async with inv.session.post("http://localhost:2000/api/v2/execute", json={
        "language": inv.lang.id,
        "version": versions[inv.lang.id],
        "files": [file],
        "stdin": inv.stdin,
        "args": inv.args,
        "run_timeout": 29_900,  # 30s
        "run_memory_limit": 500_000_000,  # 500MB
    }) as resp:
        d = await resp.json()
        try:
            stderr = d["compile"]["output"] + "\n\n"
        except KeyError:
            stderr = ""
        stderr += d["run"]["stderr"]
        inv.stdout = d["run"]["stdout"]
        inv.stderr = stderr
        inv.success = d["run"]["code"] == 0 if d["run"]["signal"] != "SIGKILL" else None

async def populate_languages(session, languages):
    async with session.get("http://localhost:2000/api/v2/runtimes") as resp:
        for lang in await resp.json():
            name = lang["language"]
            languages[name] = Language(name, name, execute)
