import unittest

from textkit.slugify import slugify


class SlugifyTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")
