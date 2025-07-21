import pytest
from handler_service.conditions import MessageConditions
from datetime import datetime

def make_message(subject="Test subject", from_name="Sender Name", from_email="sender@example.com"):
    return {
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": f"{from_name} <{from_email}>"},
            ]
        },
        "internalDate": str(int(datetime.now().timestamp() * 1000)),
        "sizeEstimate": 1000,
        "labelIds": ["INBOX"],
    }

class TestMessageConditions:
    @pytest.mark.parametrize("cond,msg,expected", [
        ( {"subject": {"equal": "Test subject"}}, make_message(subject="Test subject"), True ),
        ( {"subject": {"equal": "Other"}}, make_message(subject="Test subject"), False ),
        ( {"subject": {"contains": "Test"}}, make_message(subject="Test subject"), True ),
        ( {"subject": {"contains": "Nope"}}, make_message(subject="Test subject"), False ),
    ])
    def test_subject(self, cond, msg, expected):
        assert MessageConditions(cond).check_message(msg) == expected

    @pytest.mark.parametrize("cond,msg,expected", [
        ( {"from_": {"equal": "sender@example.com"}}, make_message(from_email="sender@example.com"), True ),
        ( {"from_": {"equal": "other@example.com"}}, make_message(from_email="sender@example.com"), False ),
        ( {"from_": {"equal": "Sender Name"}}, make_message(from_name="Sender Name"), True ),
        ( {"from_": {"equal": "Other Name"}}, make_message(from_name="Sender Name"), False ),
        ( {"from_": {"contains": "sender@"}}, make_message(from_email="sender@example.com"), True ),
        ( {"from_": {"contains": "Name"}}, make_message(from_name="Sender Name"), True ),
        ( {"from_": {"contains": "nope"}}, make_message(from_name="Sender Name"), False ),
    ])
    def test_from_(self, cond, msg, expected):
        assert MessageConditions(cond).check_message(msg) == expected

    @pytest.mark.parametrize("cond,msg,expected", [
        (
            {"subject": {"equal": "Test subject"}, "from_": {"equal": "sender@example.com"}},
            make_message(subject="Test subject", from_email="sender@example.com"),
            True
        ),
        (
            {"subject": {"equal": "Test subject"}, "from_": {"equal": "other@example.com"}},
            make_message(subject="Test subject", from_email="sender@example.com"),
            False
        ),
        (
            {"subject": {"equal": "Other"}, "from_": {"equal": "sender@example.com"}},
            make_message(subject="Test subject", from_email="sender@example.com"),
            False
        ),
        (
            {"subject": {"contains": "Test"}, "from_": {"contains": "sender@"}},
            make_message(subject="Test subject", from_email="sender@example.com"),
            True
        ),
        (
            {"subject": {"contains": "Nope"}, "from_": {"contains": "sender@"}},
            make_message(subject="Test subject", from_email="sender@example.com"),
            False
        ),
    ])
    def test_subject_and_from_(self, cond, msg, expected):
        assert MessageConditions(cond).check_message(msg) == expected
