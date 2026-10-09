import unittest

from textkit.cli import main


class CliTest(unittest.TestCase):
    def test_max_length_flag(self):
        self.assertEqual(main(["--max-length", "3", "abcdef"]), 0)
