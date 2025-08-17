from enum import Enum, auto

class CrawlerStatus(Enum):
    CONN_FAIL = auto()
    INTERNAL_ERROR = auto()
    NO_INTRO = auto()
    NO_TOC = auto()
    RESULT_EMPTY = auto()
    SUCCESS = auto()