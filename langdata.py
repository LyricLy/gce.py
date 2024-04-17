ALIASES = {
    "bf": "brainfuck",
    "rb": "ruby",
    "rs": "rust",
    "py": "python3",
    "python": "python3",
    "java": "java-jdk",
    "c": "c-gcc",
    "cpp": "cpp-gcc",
    "c++": "cpp-gcc",
    "cs": "cs-core",
    "csharp": "cs-core",
    "js": "javascript-node",
    "javascript": "javascript-node",
    "hs": "haskell",
    "pl": "perl5",
    "perl": "perl5",
    "vb": "vb-core",
    "x86asm": "assembly-fasm",
    "k": "k-ngn",
    "apl": "apl-dyalog",
    "cr": "crystal",
    "clj": "clojure",
}

def is_snippet(lang, code):
    return (lang.split("-")[0] in ("rust", "c", "cpp", "haskell", "java") and b"main" not in code
         or lang.startswith("cs-") and b"Main" not in code
         or lang == "brainfuck" and b"." not in code
         or lang.startswith("python") and all([not line or line.startswith((b"def ", b"async def ", b"#", b'"', b"'", b" ", b"\t")) for line in code.splitlines()]))
