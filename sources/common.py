import re
from collections import namedtuple


Language = namedtuple("Language", "id name extension execute")

REGII = {
    "brain(?!-flak)|(?<!s)bf": "brainfuck",
    "^python": "py",
    "^javascript": "js",
    "^typescript$": "ts",
    "^c-": "c",
    "^cpp": "cpp",
    "^rust$": "rs",
    "^ruby$": "rb",
    "^crystal$": "cr",
    "^java-": "java",
    "^haskell": "hs",
    "^perl": "pl",
    "^(visual-basic|vb-)": "vb",
    "^assembly-": "x86asm",
    "^k-": "k",
}

def guess_extension(name, prettify=None):
    for pat, ext in REGII.items():
        if re.search(pat, name):
            return ext
    # shrug
    return None
