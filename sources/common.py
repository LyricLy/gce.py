from collections import namedtuple


Language = namedtuple("Language", "id name execute runner")
SUCCESS = 0
FAILED = 1
TIMEOUT = 2
OOM = 3
