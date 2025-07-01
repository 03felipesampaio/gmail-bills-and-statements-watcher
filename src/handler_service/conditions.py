import models
import gmail_service.models as gmail_models
from email.utils import parseaddr
from datetime import datetime, timedelta
import re


class MessageConditions:
    """
    A wrapper class that encapsulates the filter logic.
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
        return ""

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
        if isinstance(field_value, list):
            # Join list of strings for substring checks
            field_value = " ".join(field_value)

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

    def _check_conditions(
        self, conditions_dict: models.Conditions, message: gmail_models.MessageFull
    ) -> bool:
        """
        Checks if a message matches all conditions in a Conditions dictionary (implicit AND).
        """
        payload_headers = message["payload"]["headers"]

        for key, rule_value in conditions_dict.items():
            # Check fields that use ConditionRule (now extracted from headers)
            if key == "subject":
                subject_value = self._get_header_value(payload_headers, "Subject")
                if not self._check_condition_rule(subject_value, rule_value):  # type: ignore
                    return False
            elif key == "from_":
                from_value = parseaddr(self._get_header_value(payload_headers, "From"))[
                    1
                ]  # Extract email address
                if not self._check_condition_rule(from_value, rule_value):  # type: ignore
                    return False
            elif key in ["to", "cc", "bcc"]:
                # Extract email addresses from headers and check
                header_value = self._get_header_value(payload_headers, key)
                recipients = [parseaddr(addr)[1] for addr in header_value.split(",")]
                if not self._check_condition_rule(recipients, rule_value):  # type: ignore
                    return False
            elif key == "filename":
                # Check all filenames in the payload recursively
                all_filenames = self._extract_all_filenames(message["payload"])
                # This check should pass if ANY filename matches the rule
                if not any(
                    self._check_condition_rule(f, rule_value) for f in all_filenames  # type: ignore
                ):
                    return False

            # Check 'has' condition
            elif key == "has":
                # Check for attachments in the payload
                has_attachment = any(
                    part.get("body", {}).get("attachmentId")
                    for part in message["payload"].get("parts", [])
                )
                # Note: 'youtube', 'drive', etc. would require checking the snippet or body content.
                # For this implementation, we'll only check for attachment existence based on the payload structure.
                if "attachment" in rule_value and not has_attachment:  # type: ignore
                    return False

            # Check 'category' condition - This data is not in MessageFull, requires an external check
            # We will assume a 'category' key is available at the top level for demonstration
            elif key == "category":
                # This field would need to be added to MessageFull or derived from labels.
                # For now, let's assume it's directly available.
                # if message.get('category') not in rule_value:  # type: ignore
                #     return False
                pass  # Skipping this check as the field is not in the provided MessageFull

            # Check date/duration conditions using internalDate
            elif key in ["after", "before", "older", "newer"]:
                internal_date_ms = int(message["internalDate"])
                message_date = datetime.fromtimestamp(
                    internal_date_ms / 1000
                )  # Convert ms to datetime

                if key == "after":
                    after_date = datetime.strptime(rule_value, "%Y/%m/%d")  # type: ignore
                    if message_date <= after_date:
                        return False
                elif key == "before":
                    before_date = datetime.strptime(rule_value, "%Y/%m/%d")  # type: ignore
                    if message_date >= before_date:
                        return False
                elif key == "older":
                    duration = self._parse_duration(rule_value)  # type: ignore
                    if message_date >= datetime.now() - duration:
                        return False
                elif key == "newer":
                    duration = self._parse_duration(rule_value)  # type: ignore
                    if message_date <= datetime.now() - duration:
                        return False

            # Check size conditions
            elif key == "min_size_bytes":
                if message["sizeEstimate"] < rule_value:  # type: ignore
                    return False
            elif key == "max_size_bytes":
                if message["sizeEstimate"] > rule_value:  # type: ignore
                    return False

            # Check label_ids
            elif key == "label_ids":
                if isinstance(rule_value, str):
                    rule_value = [rule_value]  # type: ignore
                if not any(label in message["labelIds"] for label in rule_value):  # type: ignore
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
