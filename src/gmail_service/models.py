from typing import TypedDict, NotRequired


class MessagePartBody(TypedDict, total=False):
    """Represents the body content of a message part."""

    attachmentId: str
    size: int
    data: str  # Base64 string for direct data


class MessagePartHeader(TypedDict):
    """Represents a header (name-value pair) in a message part."""

    name: str
    value: str


class MessagePayload(TypedDict):
    body: MessagePartBody
    filename: NotRequired[str]
    headers: list[MessagePartHeader]
    mimeType: str
    partId: str
    parts: NotRequired[list["MessagePayload"]]


class MessageMinimal(TypedDict):
    id: str
    threadId: str


class MessageFull(TypedDict):
    id: str
    threadId: str
    labelIds: list[str]
    snippet: str
    historyId: str
    internalDate: str
    payload: MessagePayload
    sizeEstimate: int
    raw: str


class HistoryRecordMessageList(TypedDict):
    message: MessageMinimal


class HistoryRecord(TypedDict):
    id: str
    messages: list[HistoryRecordMessageList]
    messagesAdded: list[HistoryRecordMessageList]
    messagesDeleted: list[HistoryRecordMessageList]
    labelsAdded: list[HistoryRecordMessageList]
    labelsRemoved: list[HistoryRecordMessageList]


class HistoryList(TypedDict):
    history: list[HistoryRecord]
    nextPageToken: str
    resultSizeEstimate: NotRequired[int]


class WatchResponse(TypedDict):
    historyId: str
    expiration: str
