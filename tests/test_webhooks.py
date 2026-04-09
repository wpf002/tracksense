"""
tests/test_webhooks.py

Tests for webhook delivery retry logic (ITEM 1).
Outbound HTTP (_attempt_delivery) and DB writes (_write_delivery_log)
are mocked. Only the retry coordination logic is tested here.
"""

from unittest.mock import patch, MagicMock, call

import pytest


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _sub(id=1, name="Test Hook", url="http://example.com/hook", secret="secret"):
    m = MagicMock()
    m.id = id
    m.name = name
    m.url = url
    m.secret = secret
    return m


def _patch_attempt(return_values):
    """Patch _attempt_delivery to return successive tuples."""
    it = iter(return_values)
    return patch("app.webhooks._attempt_delivery", side_effect=lambda *_: next(it))


def _patch_log():
    """Patch _write_delivery_log to no-op, return the mock."""
    return patch("app.webhooks._write_delivery_log")


# ------------------------------------------------------------------ #
# deliver_webhook — single attempt wrapper
# ------------------------------------------------------------------ #

class TestDeliverWebhook:

    def test_returns_true_on_success(self):
        from app.webhooks import deliver_webhook
        sub = _sub()
        with _patch_attempt([(True, 200, None)]):
            with _patch_log():
                assert deliver_webhook(sub, {}) is True

    def test_returns_false_on_http_error(self):
        from app.webhooks import deliver_webhook
        sub = _sub()
        with _patch_attempt([(False, 500, None)]):
            with _patch_log():
                assert deliver_webhook(sub, {}) is False

    def test_returns_false_on_network_error(self):
        from app.webhooks import deliver_webhook
        sub = _sub()
        with _patch_attempt([(False, None, "timeout")]):
            with _patch_log():
                assert deliver_webhook(sub, {}) is False

    def test_writes_delivery_log_with_correct_args(self):
        from app.webhooks import deliver_webhook
        sub = _sub()
        with _patch_attempt([(True, 200, None)]):
            with _patch_log() as mock_log:
                deliver_webhook(sub, {}, attempt_number=2)
        mock_log.assert_called_once()
        kwargs = mock_log.call_args
        assert kwargs[1]["attempt_number"] == 2 or kwargs[0][1] == 2
        # Check attempt_number in either positional or keyword args
        args, kw = mock_log.call_args
        assert (len(args) > 1 and args[1] == 2) or kw.get("attempt_number") == 2


# ------------------------------------------------------------------ #
# deliver_webhook_with_retry — exponential backoff
# ------------------------------------------------------------------ #

class TestDeliverWebhookWithRetry:

    def test_success_on_first_attempt_no_retry(self):
        """1 attempt, no sleep."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(True, 200, None)]):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep") as mock_sleep:
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 1
        assert mock_log.call_args_list[0][0][1] == 1  # attempt_number=1
        mock_sleep.assert_not_called()

    def test_failure_then_success_on_second_attempt(self):
        """Fail attempt 1, succeed attempt 2. 2 log rows, 1 sleep."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(False, 500, None), (True, 200, None)]):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep") as mock_sleep:
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 2
        assert mock_log.call_args_list[0][0][1] == 1   # attempt 1
        assert mock_log.call_args_list[1][0][1] == 2   # attempt 2
        # Success column: _write_delivery_log(sub_id, attempt, success, ...)
        assert mock_log.call_args_list[0][0][2] is False  # attempt 1 failed
        assert mock_log.call_args_list[1][0][2] is True   # attempt 2 succeeded
        mock_sleep.assert_called_once_with(5)

    def test_all_attempts_fail_three_rows(self):
        """All 3 attempts fail → 3 log rows, 2 sleeps."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(False, 500, None)] * 3):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep") as mock_sleep:
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 3
        for i, c in enumerate(mock_log.call_args_list, 1):
            assert c[0][1] == i    # attempt_number
            assert c[0][2] is False  # success=False

    def test_http_400_no_retry(self):
        """HTTP 4xx → 1 attempt only, no sleep."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(False, 400, None)]):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep") as mock_sleep:
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 1
        mock_sleep.assert_not_called()

    def test_retry_delays_are_5s_then_30s(self):
        """Delays between attempts: 5s after 1st, 30s after 2nd."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        sleep_calls = []

        with _patch_attempt([(False, 500, None)] * 3):
            with _patch_log():
                with patch("app.webhooks.time.sleep", side_effect=sleep_calls.append):
                    deliver_webhook_with_retry(sub, {})

        assert sleep_calls == [5, 30]

    def test_network_error_retries_all_three_times(self):
        """Network errors (no response_code) trigger full retry sequence."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(False, None, "conn refused")] * 3):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep"):
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 3

    def test_http_404_no_retry(self):
        """Any 4xx code stops retrying immediately."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(False, 404, None)]):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep") as mock_sleep:
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 1
        mock_sleep.assert_not_called()

    def test_success_on_third_attempt(self):
        """Fail twice, succeed on third → 3 rows, 2 sleeps."""
        from app.webhooks import deliver_webhook_with_retry
        sub = _sub()

        with _patch_attempt([(False, 500, None), (False, 500, None), (True, 200, None)]):
            with _patch_log() as mock_log:
                with patch("app.webhooks.time.sleep") as mock_sleep:
                    deliver_webhook_with_retry(sub, {})

        assert mock_log.call_count == 3
        assert mock_log.call_args_list[2][0][2] is True   # 3rd attempt succeeded
        assert mock_sleep.call_count == 2
