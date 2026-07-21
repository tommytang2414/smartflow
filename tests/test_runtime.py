import time
import unittest

from smartflow.runtime import ProcessTimeoutError, RemoteProcessError, run_in_process


class ProcessRunnerTests(unittest.TestCase):
    def test_returns_child_result(self):
        result = run_in_process(
            "tests.process_targets:return_value",
            args=(42,),
            timeout_seconds=5,
        )

        self.assertEqual(result, 42)

    def test_propagates_remote_failure(self):
        with self.assertRaisesRegex(RemoteProcessError, "ValueError: expected failure"):
            run_in_process(
                "tests.process_targets:fail",
                args=("expected failure",),
                timeout_seconds=5,
            )

    def test_terminates_child_at_wall_clock_timeout(self):
        started_at = time.monotonic()
        with self.assertRaises(ProcessTimeoutError):
            run_in_process(
                "tests.process_targets:sleep_for",
                args=(10,),
                timeout_seconds=0.2,
            )

        self.assertLess(time.monotonic() - started_at, 3)


if __name__ == "__main__":
    unittest.main()
