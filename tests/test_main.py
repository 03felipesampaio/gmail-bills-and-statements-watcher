import pytest
from src import main

class TestBuildGmailServiceFromUserTokens:
    def test_build_gmail_service_from_user_tokens(self, monkeypatch):
        class DummyCreds:
            valid = True
        class DummyGmail:
            pass
        def dummy_build_credentials_from_token(auth_tokens, scopes):
            return DummyCreds()
        def dummy_build_user_gmail_service(creds):
            return object()
        monkeypatch.setattr(main.oauth_utils, "build_credentials_from_token", dummy_build_credentials_from_token)
        monkeypatch.setattr(main.gmail_service, "build_user_gmail_service", dummy_build_user_gmail_service)
        monkeypatch.setattr(main.gmail_service, "GmailService", lambda s, u: "gmail_service_instance")
        result = main.build_gmail_service_from_user_tokens("user@example.com", {"token": "abc"})
        assert result == "gmail_service_instance"

class TestOauthCallbackFunction:
    def test_oauth_callback_function_returns_400(self, monkeypatch):
        class DummyRequest:
            args = {}
        response, status = main.oauth_callback_function(DummyRequest())
        assert status == 400
        assert "Authorization code not found" in response

class TestWatcher:
    def test_refresh_watch_handles_no_tokens(self, monkeypatch):
        class DummyUserRef:
            id = "user@example.com"
        class DummyDB:
            def get_all_users_iterator(self):
                return [DummyUserRef()]
            def get_user_data(self, user_id):
                return {"authTokens": None}
        monkeypatch.setattr(main, "db", DummyDB())
        response, status = main.refresh_watch(None)
        assert status == 200
        assert response["usersRefreshed"] == 0

class TestHandler:
    def test_download_statements_and_bills_from_message_on_topic_handles_no_user(self, monkeypatch):
        class DummyCloudEvent:
            data = {"message": {"data": ""}}
        monkeypatch.setattr(main, "db", type("DB", (), {"get_user_data": lambda self, email: None})())
        result = main.download_statements_and_bills_from_message_on_topic(DummyCloudEvent())
        assert result[1] == 404
        assert "There is no record of user" in result[0]
