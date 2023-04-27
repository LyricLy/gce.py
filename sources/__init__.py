from . import tio, custom, ato
from .common import SUCCESS, FAILED, TIMEOUT, OOM

SOURCES = (tio, ato, custom)

languages = {}

async def populate_languages(session):
    for source in SOURCES:
        await source.populate_languages(session, languages)
