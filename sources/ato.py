import asyncio
import aiohttp
import msgpack
import logging

from .common import *


async def execute(inv):
    async with inv.session.ws_connect("https://ato.pxeger.com/api/v1/ws/execute", receive_timeout=65) as ws:
        msg = {
            "language": inv.lang.id,
            "code": inv.code,
            "input": inv.stdin.encode(),
            "options": [x.encode() for x in inv.options],
            "arguments": [x.encode() for x in inv.args],
            "timeout": 60,
        }
        logging.info(f"sending: {msg}")
        await ws.send_bytes(msgpack.packb(msg))

        async for resp in ws:
            data = msgpack.unpackb(resp.data)
            logging.info(f"received: {data}")
            if "Stdout" in data:
                inv.stdout += data["Stdout"]
            if "Stderr" in data:
                inv.stderr += data["Stderr"]
            if "Done" in data:
                d = data["Done"]
                if d["timed_out"]:
                    inv.success = TIMEOUT
                elif d["status_type"] == "exited" and d["status_value"] == 137:
                    inv.success = OOM
                elif d["status_type"] == "exited" and d["status_value"] == 0:
                    inv.success = SUCCESS
                else:
                    inv.success = FAILED
                return

        inv.stdout = ""
        inv.stderr = ""
        inv.success = FAILED


RENAMES = {
    "python": "python3",
    "cplusplus_gcc": "cpp-gcc",
    "objective_cplusplus_gcc": "objective-c-gcc",
    "clang": "c-clang",
    "dyalog_apl": "apl-dyalog",
    "node": "javascript-node",
}

async def populate_languages(session, languages):
    async with session.get("https://ato.pxeger.com/languages.json") as resp:
        data = await resp.json()
        for key, value in data.items():
            # prefer names and conventions from TIO
            better = RENAMES.get(key, key).replace("_", "-").lower()
            name = languages[better].name if better in languages else value["name"]

            languages[better] = Language(key, name, execute, "with ATO")
