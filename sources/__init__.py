from . import tio, custom

# TODO add ATO, consider piston runner
SOURCES = (tio, custom)

languages = {}

async def populate_languages():
    for source in SOURCES:
        await source.populate_languages(languages)
