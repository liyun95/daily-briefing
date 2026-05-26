import io
import importlib
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

offwork_reminder = None


def setUpModule():
    global offwork_reminder

    os.environ["DRY_RUN"] = "1"
    os.environ.pop("FORCE_SEND", None)
    sys.modules.setdefault("requests", types.SimpleNamespace())
    offwork_reminder = importlib.import_module("offwork_reminder")


SHANGHAI = timezone(timedelta(hours=8))


class OffworkSendGateTest(unittest.TestCase):
    def test_scheduled_weekday_run_sends_even_when_github_starts_late(self):
        dt = datetime(2026, 5, 26, 20, 36, tzinfo=SHANGHAI)

        self.assertTrue(offwork_reminder.should_send(dt, event_name="schedule"))

    def test_manual_weekday_run_outside_window_still_skips(self):
        dt = datetime(2026, 5, 26, 20, 36, tzinfo=SHANGHAI)

        self.assertFalse(offwork_reminder.should_send(dt, event_name="workflow_dispatch"))

    def test_weekday_run_inside_window_sends(self):
        dt = datetime(2026, 5, 26, 18, 0, tzinfo=SHANGHAI)

        self.assertTrue(offwork_reminder.should_send(dt, event_name="workflow_dispatch"))

    def test_scheduled_weekend_run_skips(self):
        dt = datetime(2026, 5, 30, 20, 36, tzinfo=SHANGHAI)

        self.assertFalse(offwork_reminder.should_send(dt, event_name="schedule"))

    def test_force_send_overrides_weekend_and_window(self):
        dt = datetime(2026, 5, 30, 20, 36, tzinfo=SHANGHAI)

        self.assertTrue(
            offwork_reminder.should_send(
                dt,
                event_name="workflow_dispatch",
                force_send=True,
            )
        )

    def test_main_allows_late_scheduled_action_run(self):
        dt = datetime(2026, 5, 26, 20, 36, tzinfo=SHANGHAI)

        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"}):
            with mock.patch.object(offwork_reminder, "shanghai_now", return_value=dt):
                with mock.patch.object(offwork_reminder, "generate_ai_offwork", return_value=None):
                    with mock.patch("sys.stdout", new=io.StringIO()) as stdout:
                        offwork_reminder.main()

        output = stdout.getvalue()
        self.assertIn("Scheduled run started late", output)
        self.assertIn("下班提醒", output)


if __name__ == "__main__":
    unittest.main()
