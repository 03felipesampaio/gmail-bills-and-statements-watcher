import models
import gmail_service.models as gmail_models
from email.utils import parseaddr
from datetime import timedelta
import re


class MessageConditions:
    """MessageConditions encapsulates the logic for filtering Gmail messages based on a flexible set of conditions.

    This class supports both simple field-based conditions (such as subject, sender, recipients, attachment presence, etc.)
    and complex logical groupings (AND, OR, NOT) of such conditions. It is designed to work with Gmail API message objects
    and custom filter condition models.

    Main Features:
    --------------
    - Parse and evaluate filter conditions on Gmail messages, including:
        * Header fields (subject, from, to, cc, bcc)
        * Attachment filenames
        * Presence of attachments
        * Message size
        * Date-based conditions (after, before, older, newer)
        * Label IDs
    - Support for logical grouping of conditions using AND, OR, and NOT operators.
    - Recursive evaluation of nested logical groups.
    - Utility methods for extracting header values, filenames, and parsing durations.

    Args:
        condition (models.FilterCondition): The filter condition or logical group to evaluate.

    Methods:
        check_message(message: gmail_models.MessageFull) -> bool:
            Evaluates whether the given Gmail message matches the filter conditions encapsulated by this instance.

    Internal Methods:
        _parse_duration(duration_str: str) -> timedelta:

        _get_header_value(headers: list[gmail_models.MessagePartHeader], name: str) -> str:
            Retrieves the value of a specific header from the message.

        _extract_all_filenames(payload: gmail_models.MessagePayload) -> list[str]:
            Recursively extracts all filenames from the message payload.

        _check_condition_rule(field_value: str | list[str], rule: models.ConditionRule) -> bool:
            Checks if a field value matches a given rule (equality, substring, etc.).

        _check_conditions(conditions_dict: models.Conditions, message: gmail_models.MessageFull) -> bool:
            Evaluates all simple conditions (implicit AND) against the message.

        _check_logical_group(group_dict: models.LogicalConditionGroup, message: gmail_models.MessageFull) -> bool:
            Recursively evaluates logical groups (AND, OR, NOT) of conditions.

    Usage Example:
    --------------
        filter_condition = {...}  # models.FilterCondition instance or dict
        message = {...}           # gmail_models.MessageFull instance or dict

        matcher = MessageConditions(filter_condition)
        if matcher.check_message(message):
            # Message matches the filter
            ...
    --------------
    """

    def __init__(self, condition: models.FilterCondition):
        self.condition = condition

    def _parse_duration(self, duration_str: str) -> timedelta:
        """
        Parses a duration string (e.g., '2d', '1w', '3m', '1y') into a timedelta object.
        """
        if not duration_str:
            return timedelta(0)

        match = re.match(r"(\d+)([dwmy])", duration_str)
        if not match:
            raise ValueError(
                f"Invalid duration format: {duration_str}. Expected format is e.g., '2d', '1w', '3m', '1y'."
            )

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "d":
            return timedelta(days=value)
        elif unit == "w":
            return timedelta(weeks=value)
        elif unit == "m":
            # Approximate a month as 30 days
            return timedelta(days=value * 30)
        elif unit == "y":
            # Approximate a year as 365 days
            return timedelta(days=value * 365)

        return timedelta(0)

    def _get_header_value(
        self, headers: list[gmail_models.MessagePartHeader], name: str
    ) -> str:
        """
        Extracts the value of a specific header by name.
        """
        for header in headers:
            if header["name"].lower() == name.lower():
                return header["value"]
        raise ValueError(f"Header '{name}' not found in message headers.")

    def _extract_all_filenames(self, payload: gmail_models.MessagePayload) -> list[str]:
        """
        Recursively extracts all filenames from a message payload.
        """
        filenames = []
        if "filename" in payload and payload["filename"]:
            filenames.append(payload["filename"])
        if "parts" in payload:
            for part in payload["parts"]:
                filenames.extend(self._extract_all_filenames(part))
        return filenames

    def _check_condition_rule(
        self, field_value: str | list[str], rule: models.ConditionRule
    ) -> bool:
        """
        Checks if a message field's value matches a ConditionRule.
        """
        # if isinstance(field_value, list):
        #     # Join list of strings for substring checks
        #     field_value = " ".join(field_value)

        if "equal" in rule:
            return field_value == rule["equal"]

        if "in_" in rule:
            return field_value in rule["in_"]

        if "startswith" in rule:
            return field_value.startswith(rule["startswith"])

        if "endswith" in rule:
            return field_value.endswith(rule["endswith"])

        if "contains" in rule:
            return rule["contains"] in field_value

        return True  # No rule specified, so it matches

    def _check_subject(self, conditions_dict: models.Conditions, message: gmail_models.MessageFull) -> bool:
        """
        Checks if the message subject matches the condition rule.

        Args:
            message (gmail_models.MessageFull): The Gmail message to check.

        Returns:
            bool: True if the sender matches the condition rule, False otherwise.
        """
        msg_subject = self._get_header_value(message["payload"]["headers"], "Subject")

        return self._check_condition_rule(
            msg_subject, conditions_dict["subject"]
        )

    def _check_from(
        self, conditions_dict: models.Conditions, message: gmail_models.MessageFull
    ) -> bool:
        """
        Checks if the message sender matches the condition rule.
        This checks both the name and email address of the sender.

        Args:
            message (gmail_models.MessageFull): The Gmail message to check.

        Returns:
            bool: True if the sender matches the condition rule, False otherwise.
        """
        name, email = parseaddr(
            self._get_header_value(message["payload"]["headers"], "From")
        )

        from_condition = conditions_dict["from_"]

        return any(
            [
                self._check_condition_rule(name, from_condition),
                self._check_condition_rule(email, from_condition),
            ]
        )
        
    def _check_filename(
        self, conditions_dict: models.Conditions, message: gmail_models.MessageFull
    ) -> bool:
        """
        Checks if any filename in the message payload matches the condition rule.

        Args:
            message (gmail_models.MessageFull): The Gmail message to check.

        Returns:
            bool: True if any filename matches the condition rule, False otherwise.
        """
        all_filenames = self._extract_all_filenames(message["payload"])
        
        return any(
            self._check_condition_rule(filename, conditions_dict["filename"])
            for filename in all_filenames
        )

    def _check_conditions(
        self, conditions_dict: models.Conditions, message: gmail_models.MessageFull
    ) -> bool:
        """
        Checks if a message matches all conditions in a Conditions dictionary (implicit AND).
        """
        conditions_handlers = {
            "subject": self._check_subject,
            "from_": self._check_from,
            "filename": self._check_filename,
            # "to": lambda m: [parseaddr(addr)[1] for addr in self._get_header_value(payload_headers, "To").split(",")],
            # "cc": lambda m: [parseaddr(addr)[1] for addr in self._get_header_value(payload_headers, "Cc").split(",")],
            # "bcc": lambda m: [parseaddr(addr)[1] for addr in self._get_header_value(payload_headers, "Bcc").split(",")],
        }

        for key in conditions_dict:
            handler = conditions_handlers.get(key)
            if not handler:
                raise NotImplementedError(f"Unknown condition key: {key}")

            handler_value = handler(conditions_dict, message)
            
            if not handler_value:
                return False

        return True  # All conditions matched

    def _check_logical_group(
        self,
        group_dict: models.LogicalConditionGroup,
        message: gmail_models.MessageFull,
    ) -> bool:
        """
        Recursively checks if a message matches a logical condition group.
        """
        operator = group_dict["operator"]
        conditions = group_dict["conditions"]

        if operator == "AND":
            for condition in conditions:
                if not MessageConditions(condition).check_message(message):
                    return False
            return True

        elif operator == "OR":
            for condition in conditions:
                if MessageConditions(condition).check_message(message):
                    return True
            return False

        elif operator == "NOT":
            if not conditions:
                return True
            return not MessageConditions(conditions[0]).check_message(message)

        return False

    def check_message(self, message: gmail_models.MessageFull) -> bool:
        """
        Checks if the given message matches the filter conditions of this instance.
        """
        if "operator" in self.condition and "conditions" in self.condition:
            # It's a logical group (branch node)
            return self._check_logical_group(self.condition, message)  # type: ignore
        else:
            # It's a simple conditions dictionary (leaf node)
            return self._check_conditions(self.condition, message)

    def _build_query(self, cond: dict) -> list[str]:
        query_parts = []
        # Subject
        if "subject" in cond:
            rule = cond["subject"]
            if "equal" in rule or "contains" in rule:
                value = rule.get("equal") or rule.get("contains")
                query_parts.append(f'subject:"{value}"')
            if "startswith" in rule:
                query_parts.append(f'subject:"{rule["startswith"]}"')
            if "endswith" in rule:
                query_parts.append(f'subject:"{rule["endswith"]}"')
        # From
        if "from_" in cond:
            rule = cond["from_"]
            if "equal" in rule or "contains" in rule:
                value = rule.get("equal") or rule.get("contains")
                query_parts.append(f'from:"{value}"')
        # Filename (Gmail supports filename: query)
        if "filename" in cond:
            rule = cond["filename"]
            if "equal" in rule or "contains" in rule:
                value = rule.get("equal") or rule.get("contains")
                query_parts.append(f'filename:"{value}"')
            if "startswith" in rule:
                query_parts.append(f'filename:"{rule["startswith"]}"')
            if "endswith" in rule:
                query_parts.append(f'filename:"{rule["endswith"]}"')
        return query_parts

    def _logical_group_to_query(self, group: dict) -> str:
        operator = group["operator"]
        conditions = group["conditions"]
        queries = [
            f'({" ".join(self._build_query(c))})' if isinstance(c, dict) and "operator" not in c else f'({self._logical_group_to_query(c)})'
            for c in conditions
        ]
        if operator == "AND":
            return " ".join(queries)
        elif operator == "OR":
            return " OR ".join(queries)
        elif operator == "NOT":
            # Gmail does not support NOT directly, so use '-' before each query
            return " ".join([f'-{q}' for q in queries])
        return ""

    def to_gmail_query(self) -> str:
        """
        Converts the filter condition to a Gmail API query string (supports logical operators AND, OR, NOT for subject and from_).
        Returns:
            str: Gmail-compatible query string.
        """
        cond = self.condition
        if isinstance(cond, dict) and "operator" in cond and "conditions" in cond:
            return self._logical_group_to_query(cond)
        else:
            return " ".join(self._build_query(cond))
