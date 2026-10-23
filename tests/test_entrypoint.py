import subprocess
import sys
import unittest


class EntrypointTests(unittest.TestCase):
    def test_help_does_not_start_an_interactive_session(self):
        result = subprocess.run(
            [sys.executable, "-m", "personal_assistant", "--help"],
            input="", capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--data-file", result.stdout)


if __name__ == "__main__":
    unittest.main()
