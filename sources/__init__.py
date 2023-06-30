import traceback

from . import tio, custom, ato
from .common import SUCCESS, FAILED, TIMEOUT, OOM


SOURCES = (tio, custom)

languages = {}

async def populate_languages(session):
    for source in SOURCES:
        try:
            await source.populate_languages(session, languages)
        except Exception:
            traceback.print_exc()
