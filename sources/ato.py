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
                match resp.data:
                    case aiohttp.WSCloseCode.MESSAGE_TOO_BIG:
                        inv.info = "Request exceeded the maximum size, which is 65536 bytes."
                    case aiohttp.WSCloseCode.INTERNAL_ERROR:
                        inv.info = "Something went wrong inside ATO."
                    case _:
                        inv.info = "An unknown error occurred during execution."
                return
            data = msgpack.unpackb(resp.data)
            if "Stdout" in data:
                inv.stdout = data["Stdout"]
            if "Stderr" in data:
                inv.stderr = data["Stderr"]
            if "Done" in data:
                d = data["Done"]
                if d["timed_out"]:
                    inv.info = "Process timed out after 60s."
                inv.success = d["status_type"] == "exited" and d["status_value"] == 0
                break


RENAMES = {
    "python": "python3",
    "cplusplus_gcc": "cpp-gcc",
    "objective_cplusplus_gcc": "objective-c-gcc",
    "clang": "c-clang",
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

            languages[better] = Language(better, name, value.get("se_class") or guess_extension(better) or "txt", execute)
