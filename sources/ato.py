import aiohttp
import msgpack

from .common import *


async def execute(inv):
    async with inv.session.ws_connect("https://ato.pxeger.com/api/v1/ws/execute") as ws:
        await ws.send_bytes(msgpack.packb({
            "language": actual_names[inv.lang.id],
            "code": inv.code,
            "input": inv.stdin.encode(),
            "options": [x.encode() for x in inv.options],
            "arguments": [x.encode() for x in inv.args],
            "timeout": 60,
        }))
        while True:
            resp = await ws.receive(timeout=65)
            if resp.type == aiohttp.WSMsgType.CLOSE:
                inv.stdout = ""
                inv.stderr = ""
                inv.success = False
                return
            data = msgpack.unpackb(resp.data)
            if "Stdout" in data:
                inv.stdout += data["Stdout"]
            if "Stderr" in data:
                inv.stderr += data["Stderr"]
            if "Done" in data:
                d = data["Done"]
                inv.success = d["status_type"] == "exited" and d["status_value"] == 0 if not d["timed_out"] else None
                break


RENAMES = {
    "python": "python3",
    "cplusplus_gcc": "cpp-gcc",
    "objective_cplusplus_gcc": "objective-c-gcc",
    "clang": "c-clang",
    "dyalog_apl": "apl-dyalog",
    "node": "javascript-node",
}

actual_names = {}

async def populate_languages(session, languages):
    async with session.get("https://ato.pxeger.com/languages.json") as resp:
        data = await resp.json()
        for key, value in data.items():
            # prefer names and conventions from TIO
            better = RENAMES.get(key, key).replace("_", "-").lower()
            actual_names[better] = key
            name = languages[better].name if better in languages else value["name"]

            languages[better] = Language(better, name, execute, "with ATO")
