import typing
import unittest
import urllib.parse

from quark.subproject import Subproject


class TestSubproject(unittest.TestCase):
    def test_parse_fragment(self):
        self.assertEqual({}, self._parse_fragment("http://foo"))
        self.assertEqual({}, self._parse_fragment("http://foo#"))

        self.assertEqual({"bar": "baz"}, self._parse_fragment("http://foo#bar=baz"))
        self.assertEqual({"bar": ""}, self._parse_fragment("http://foo#bar"))

        self.assertEqual(
            {
                "bar": "",
                "baz": "",
                "qux": "",
                "quux": "barbaz",
                "foobar": "barbaz",
                "": "barqux",
            },
            self._parse_fragment(
                "http://foo#bar&baz&qux=&quux=foobar&quux=barbaz&&&foobar=barbaz&=barqux&"
            ),
        )

    @staticmethod
    def _parse_fragment(url: str) -> typing.Dict[str, str]:
        return Subproject._parse_fragment(urllib.parse.urlparse(url))
