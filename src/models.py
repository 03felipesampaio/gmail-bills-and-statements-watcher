from typing import TypedDict, NotRequired

class User (TypedDict):
    email: str
    authTokens: NotRequired[dict]
    currentWatch: NotRequired[dict]
    lastHistoryId: NotRequired[int|str]
    watchConfig: NotRequired[dict|None]
    