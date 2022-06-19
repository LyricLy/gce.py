from . import tio, custom, ato

SOURCES = (tio, ato, custom)

languages = {}

async def populate_languages(session):
    for source in SOURCES:
        await source.populate_languages(session, languages)
