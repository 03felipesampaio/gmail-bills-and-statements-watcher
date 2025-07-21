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

    @pytest.mark.parametrize("cond,expected", [
        ( {"subject": {"equal": "Invoice"}}, 'subject:"Invoice"' ),
        ( {"from_": {"equal": "sender@example.com"}}, 'from:"sender@example.com"' ),
        ( {"subject": {"contains": "Report"}, "from_": {"contains": "noreply@"}}, 'subject:"Report" from:"noreply@"' ),
        ( {"subject": {"startswith": "Hello"}}, 'subject:"Hello"' ),
        ( {"subject": {"endswith": "World"}}, 'subject:"World"' ),
        ( {"operator": "AND", "conditions": [
            {"subject": {"equal": "Invoice"}},
            {"from_": {"equal": "sender@example.com"}}
        ]}, '(subject:"Invoice") (from:"sender@example.com")' ),
        ( {"operator": "OR", "conditions": [
            {"subject": {"equal": "Invoice"}},
            {"from_": {"equal": "sender@example.com"}}
        ]}, '(subject:"Invoice") OR (from:"sender@example.com")' ),
        ( {"operator": "NOT", "conditions": [
            {"subject": {"equal": "Invoice"}},
            {"from_": {"equal": "sender@example.com"}}
        ]}, '-(subject:"Invoice") -(from:"sender@example.com")' ),
    ])
    def test_to_gmail_query(self, cond, expected):
        assert MessageConditions(cond).to_gmail_query() == expected

    @pytest.mark.parametrize("cond,msg,expected", [
        ( {"filename": {"equal": "statement.pdf"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, True ),
        ( {"filename": {"equal": "other.pdf"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, False ),
        ( {"filename": {"contains": "state"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, True ),
        ( {"filename": {"contains": "nope"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, False ),
        ( {"filename": {"startswith": "state"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, True ),
        ( {"filename": {"endswith": "pdf"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, True ),
        ( {"filename": {"endswith": "doc"}},
          {"payload": {"headers": [], "filename": "statement.pdf"}}, False ),
        # Multiple filenames in parts
        ( {"filename": {"equal": "foo.txt"}},
          {"payload": {"headers": [], "parts": [ {"filename": "foo.txt"}, {"filename": "bar.txt"} ]}}, True ),
        ( {"filename": {"equal": "baz.txt"}},
          {"payload": {"headers": [], "parts": [ {"filename": "foo.txt"}, {"filename": "bar.txt"} ]}}, False ),
    ])
    def test_filename(self, cond, msg, expected):
        # Add required fields for MessageFull
        msg.setdefault("internalDate", str(int(datetime.now().timestamp() * 1000)))
        msg.setdefault("sizeEstimate", 1000)
        msg.setdefault("labelIds", ["INBOX"])
        assert MessageConditions(cond).check_message(msg) == expected

    @pytest.mark.parametrize("cond,expected", [
        ( {"filename": {"equal": "statement.pdf"}}, 'filename:"statement.pdf"' ),
        ( {"filename": {"contains": "state"}}, 'filename:"state"' ),
        ( {"filename": {"startswith": "state"}}, 'filename:"state"' ),
        ( {"filename": {"endswith": "pdf"}}, 'filename:"pdf"' ),
        ( {"filename": {"equal": "foo.txt", "endswith": "txt"}}, 'filename:"foo.txt" filename:"txt"' ),
        ( {"subject": {"equal": "Invoice"}, "filename": {"equal": "statement.pdf"}}, 'subject:"Invoice" filename:"statement.pdf"' ),
        ( {"operator": "AND", "conditions": [
            {"filename": {"equal": "statement.pdf"}},
            {"subject": {"equal": "Invoice"}}
        ]}, '(filename:"statement.pdf") (subject:"Invoice")' ),
        ( {"operator": "OR", "conditions": [
            {"filename": {"equal": "statement.pdf"}},
            {"subject": {"equal": "Invoice"}}
        ]}, '(filename:"statement.pdf") OR (subject:"Invoice")' ),
        ( {"operator": "NOT", "conditions": [
            {"filename": {"equal": "statement.pdf"}},
            {"subject": {"equal": "Invoice"}}
        ]}, '-(filename:"statement.pdf") -(subject:"Invoice")' ),
    ])
    def test_filename_to_gmail_query(self, cond, expected):
        assert MessageConditions(cond).to_gmail_query() == expected
