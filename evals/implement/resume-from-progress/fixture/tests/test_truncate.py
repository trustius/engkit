import unittest

from textkit.truncate import truncate


class TruncateTest(unittest.TestCase):
    def test_cut(self):
        self.assertEqual(truncate("abcdef", 3), "abc")
