import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "04_Application"))

import gmail_client


class TestGmailOAuthRecovery(unittest.TestCase):

    def test_gmail_scope_is_readonly(self):
        self.assertEqual(
            gmail_client.SCOPES,
            ["https://www.googleapis.com/auth/gmail.readonly"],
        )

    @patch("gmail_client.TOKEN_FILE")
    @patch("gmail_client.Credentials")
    def test_valid_cached_credentials(self, mock_credentials_cls, mock_token_file):
        mock_token_file.exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.valid = True
        mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

        result = gmail_client.get_credentials()

        self.assertEqual(result, mock_creds)
        mock_creds.refresh.assert_not_called()

    @patch("gmail_client.TOKEN_FILE")
    @patch("gmail_client.Credentials")
    def test_successful_token_refresh(self, mock_credentials_cls, mock_token_file):
        mock_token_file.exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "valid_refresh_token"
        mock_creds.valid = True
        mock_creds.to_json.return_value = '{"token": "refreshed"}'
        mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

        result = gmail_client.get_credentials()

        mock_creds.refresh.assert_called_once()
        mock_token_file.write_text.assert_called_once_with(
            '{"token": "refreshed"}', encoding="utf-8"
        )
        self.assertEqual(result, mock_creds)

    @patch("gmail_client.InstalledAppFlow")
    @patch("gmail_client.TOKEN_FILE")
    @patch("gmail_client.Credentials")
    def test_refresh_error_triggers_reauthorization(
        self, mock_credentials_cls, mock_token_file, mock_flow_cls
    ):
        mock_token_file.exists.return_value = True
        mock_old_creds = MagicMock()
        mock_old_creds.expired = True
        mock_old_creds.refresh_token = "revoked_token"
        mock_old_creds.refresh.side_effect = RefreshError(
            "invalid_grant: Token has been expired or revoked."
        )
        mock_credentials_cls.from_authorized_user_file.return_value = mock_old_creds

        mock_flow = MagicMock()
        mock_new_creds = MagicMock()
        mock_new_creds.valid = True
        mock_new_creds.to_json.return_value = '{"token": "fresh"}'
        mock_flow.run_local_server.return_value = mock_new_creds
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow

        result = gmail_client.get_credentials()

        mock_flow_cls.from_client_secrets_file.assert_called_once_with(
            gmail_client.CREDENTIALS_FILE,
            gmail_client.SCOPES,
        )
        mock_flow.run_local_server.assert_called_once_with(
            port=0,
            open_browser=True,
            authorization_prompt_message=unittest.mock.ANY,
        )
        mock_token_file.write_text.assert_called_once_with(
            '{"token": "fresh"}', encoding="utf-8"
        )
        self.assertEqual(result, mock_new_creds)

    @patch("gmail_client.InstalledAppFlow")
    @patch("gmail_client.TOKEN_FILE")
    def test_missing_token_triggers_interactive_auth(
        self, mock_token_file, mock_flow_cls
    ):
        mock_token_file.exists.return_value = False

        mock_flow = MagicMock()
        mock_new_creds = MagicMock()
        mock_new_creds.valid = True
        mock_new_creds.to_json.return_value = '{"token": "fresh"}'
        mock_flow.run_local_server.return_value = mock_new_creds
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow

        result = gmail_client.get_credentials()

        mock_flow_cls.from_client_secrets_file.assert_called_once_with(
            gmail_client.CREDENTIALS_FILE,
            gmail_client.SCOPES,
        )
        mock_flow.run_local_server.assert_called_once_with(
            port=0,
            open_browser=True,
            authorization_prompt_message=unittest.mock.ANY,
        )
        mock_token_file.write_text.assert_called_once_with(
            '{"token": "fresh"}', encoding="utf-8"
        )
        self.assertEqual(result, mock_new_creds)


if __name__ == "__main__":
    unittest.main()
