import unittest
from raspberry_pi.command_handler import Command
from raspberry_pi.ui_state import UIState


class Clock:
    def __init__(self):
        self.now = 1000.0
    def __call__(self):
        return self.now


class StateTests(unittest.TestCase):
    def test_navigation_wraps_and_resets_entered(self):
        state = UIState()
        self.assertEqual(state.apply(Command.CCW).page, "status")
        self.assertEqual(state.apply(Command.CW).page, "home")
        state.apply(Command.TAP)
        self.assertTrue(state.snapshot().entered)
        self.assertEqual(state.apply(Command.CW).page, "focus")
        self.assertFalse(state.snapshot().entered)

    def test_back_returns_before_selecting_previous(self):
        state = UIState()
        state.apply(Command.CW)
        state.apply(Command.TAP)
        self.assertEqual(state.apply(Command.CCW).page, "focus")
        self.assertFalse(state.snapshot().entered)
        self.assertEqual(state.apply(Command.CCW).page, "home")

    def test_focus_confirmation_is_a_real_toggle(self):
        state = UIState()
        state.apply(Command.CW)
        state.apply(Command.TAP)
        self.assertFalse(state.snapshot().focus_active)
        self.assertTrue(state.apply(Command.TAP).focus_active)
        self.assertFalse(state.apply(Command.TAP).focus_active)
        self.assertEqual(state.snapshot().confirmations, 2)

    def timer(self):
        clock = Clock()
        state = UIState(timer_minutes=2, clock=clock)
        state.apply(Command.CW)
        state.apply(Command.CW)
        state.apply(Command.TAP)
        return state, clock

    def test_timer_start_pause_resume_uses_monotonic_deadline(self):
        state, clock = self.timer()
        self.assertEqual(state.snapshot().timer_state, "ready")
        self.assertEqual(state.apply(Command.TAP).timer_state, "running")
        clock.now += 30
        self.assertEqual(state.apply(Command.TAP).timer_state, "paused")
        clock.now += 300
        self.assertEqual(state.snapshot().timer_minutes_left, 2)
        state.apply(Command.TAP)
        clock.now += 31
        self.assertEqual(state.tick().timer_minutes_left, 1)

    def test_timer_finishes_and_can_restart(self):
        state, clock = self.timer()
        state.apply(Command.TAP)
        clock.now += 120
        self.assertEqual(state.tick().timer_state, "done")
        self.assertEqual(state.snapshot().timer_minutes_left, 0)
        self.assertEqual(state.apply(Command.TAP).timer_state, "running")
        self.assertEqual(state.snapshot().timer_minutes_left, 2)

    def test_timer_does_not_request_second_by_second_refresh(self):
        state, clock = self.timer()
        state.apply(Command.TAP)
        clock.now += 1
        self.assertIsNone(state.tick())
        clock.now += 59
        self.assertEqual(state.tick().timer_minutes_left, 1)

    def test_snapshot_is_immutable_and_counters_are_real(self):
        state = UIState()
        before = state.snapshot()
        after = state.apply(Command.CW)
        self.assertEqual(before.received_count, 0)
        self.assertEqual(after.received_count, 1)
        self.assertEqual(after.last_command, "CW")
        self.assertEqual(after.revision, 1)
        with self.assertRaises(AttributeError):
            after.index = 2

    def test_custom_pages_are_supported(self):
        state = UIState(("home", "reading"))
        self.assertEqual(state.apply(Command.CW).page, "reading")
        self.assertEqual(state.apply(Command.CW).page, "home")


if __name__ == "__main__":
    unittest.main()
