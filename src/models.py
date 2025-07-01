from typing import TypedDict, NotRequired, Literal


class User(TypedDict):
    email: str
    authTokens: NotRequired[dict]
    currentWatch: NotRequired[dict]
    lastHistoryId: NotRequired[int | str]
    watchConfig: NotRequired[dict | None]


class ConditionRule(TypedDict, total=False):
    """
    Defines a matching rule for a single field, using comparison operators.
    """

    equal: str
    in_: list[str]
    startswith: str
    endswith: str
    contains: str


# Defines the possible literal values for the 'has' operator
HasLiteral = Literal[
    "attachment", "youtube", "drive", "document", "spreadsheet", "presentation"
]

# Defines the possible literal values for the 'category' operator
CategoryLiteral = Literal[
    "primary", "social", "promotions", "updates", "forums", "reservations", "purchases"
]


class Conditions(TypedDict, total=False):
    """
    Defines a group of conditions for a message, implicitly combined with 'AND'.
    This is the 'leaf node' in the filter logic tree.
    """

    subject: ConditionRule
    from_: ConditionRule
    to: ConditionRule
    cc: ConditionRule
    bcc: ConditionRule

    has: list[HasLiteral]

    # Category condition is always a list
    category: list[CategoryLiteral]

    # Filename condition uses ConditionRule
    filename: ConditionRule

    # Date and duration conditions
    after: str
    before: str
    older: str
    newer: str

    label_ids: str | list[str]

    min_size_bytes: int
    max_size_bytes: int


class LogicalConditionGroup(TypedDict):
    """
    Represents a group of conditions combined by a logical operator (AND, OR, NOT).
    This is the 'branch' in the logic tree, allowing for nesting.
    """

    operator: Literal["AND", "OR", "NOT"]
    conditions: list["Conditions | LogicalConditionGroup"]


# The main type for a complete filter
FilterCondition = Conditions | LogicalConditionGroup


class MessageAction(TypedDict):
    """MessageActions have each their own parameters. This is only a placeholder"""

    className: str
    args: NotRequired[dict]


class MessageHandler(TypedDict):
    """Handlers for messages"""

    name: str
    filterCondition: FilterCondition
    actions: list[MessageAction]
