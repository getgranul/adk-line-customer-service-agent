"""Signature checks using LINE's published, known-answer example.

Source: https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/
The body, signature, and secret below are public documentation fixtures.
"""

import json
import unittest

from line_customer_service.integrations.line.signature import is_valid_line_signature

EXAMPLE_BODY = (
    b'{"destination":"U8e742f61d673b39c7fff3cecb7536ef0","events":[]}'
)
EXAMPLE_SECRET = "8c570fa6dd201bb328f1c1eac23a96d8"
EXAMPLE_SIGNATURE = "GhRKmvmHys4Pi8DxkF4+EayaH0OqtJtaZxgTD9fMDLs="


class LineSignatureTests(unittest.TestCase):
    def test_accepts_official_known_answer(self) -> None:
        self.assertTrue(
            is_valid_line_signature(
                body=EXAMPLE_BODY,
                signature=EXAMPLE_SIGNATURE,
                channel_secret=EXAMPLE_SECRET,
            )
        )

    def test_rejects_body_changed_by_one_space(self) -> None:
        self.assertFalse(
            is_valid_line_signature(
                body=EXAMPLE_BODY + b" ",
                signature=EXAMPLE_SIGNATURE,
                channel_secret=EXAMPLE_SECRET,
            )
        )

    def test_rejects_wrong_secret(self) -> None:
        self.assertFalse(
            is_valid_line_signature(
                body=EXAMPLE_BODY,
                signature=EXAMPLE_SIGNATURE,
                channel_secret="different-test-secret",
            )
        )

    def test_rejects_missing_or_malformed_signature(self) -> None:
        for signature in (None, "", "not-a-signature", "非 ASCII 簽章"):
            with self.subTest(signature=signature):
                self.assertFalse(
                    is_valid_line_signature(
                        body=EXAMPLE_BODY,
                        signature=signature,
                        channel_secret=EXAMPLE_SECRET,
                    )
                )

    def test_rejects_parsed_and_reserialized_json(self) -> None:
        rebuilt_body = json.dumps(json.loads(EXAMPLE_BODY)).encode("utf-8")
        self.assertNotEqual(rebuilt_body, EXAMPLE_BODY)
        self.assertFalse(
            is_valid_line_signature(
                body=rebuilt_body,
                signature=EXAMPLE_SIGNATURE,
                channel_secret=EXAMPLE_SECRET,
            )
        )

    def test_empty_secret_is_a_configuration_error(self) -> None:
        with self.assertRaises(ValueError):
            is_valid_line_signature(
                body=EXAMPLE_BODY,
                signature=EXAMPLE_SIGNATURE,
                channel_secret="",
            )
