from __future__ import annotations

import gzip
import importlib.util
import io
import sys
import unittest
import zlib
from email.message import Message
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("readlater_cli_main", Path(__file__).with_name("main.py"))
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Response(io.BytesIO):
    status = 200

    def __init__(self, body: bytes, content_type: str = "text/html", encoding: str | None = None):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if encoding:
            self.headers["Content-Encoding"] = encoding
        self.bytes_read = 0

    def read(self, size=-1):
        result = super().read(size)
        self.bytes_read += len(result)
        return result

    def geturl(self):
        return "https://example.invalid/page"


class ReadLaterTests(unittest.TestCase):
    def fetch(self, response):
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            return MODULE.fetch_generic_url("https://example.invalid/page", 10, 280)

    def test_non_html_only_reads_headers(self):
        response = Response(b"x" * 100_000, "application/pdf")
        item = self.fetch(response)
        self.assertEqual(response.bytes_read, 0)
        self.assertEqual(item.summary, "非 HTML 内容: application/pdf")
        self.assertTrue(response.closed)

    def test_download_limit_bounds_reads_even_without_content_length(self):
        response = Response(b"x" * 5000)
        with patch.object(MODULE, "MAX_DOWNLOAD_BYTES", 1000), self.assertRaisesRegex(MODULE.CliError, "下载超过"):
            self.fetch(response)
        self.assertEqual(response.bytes_read, 1001)
        self.assertTrue(response.closed)

    def test_compression_limits_and_formats(self):
        text = b"hello " * 1000
        raw_deflate = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        formats = [
            ("gzip", gzip.compress(text)),
            ("deflate", zlib.compress(text)),
            ("deflate", raw_deflate.compress(text) + raw_deflate.flush()),
            ("gzip", gzip.compress(text[:3000]) + gzip.compress(text[3000:]) + b"\x00\x00"),
        ]
        for encoding, body in formats:
            with self.subTest(encoding=encoding, length=len(body)):
                self.assertEqual(MODULE.decode_response_body(body, {"Content-Encoding": encoding}, max_bytes=len(text)), text)
                with self.assertRaisesRegex(MODULE.CliError, "解压后的正文超过"):
                    MODULE.decode_response_body(body, {"Content-Encoding": encoding}, max_bytes=1000)

    def test_raw_deflate_can_coincidentally_start_with_a_zlib_header(self):
        raw = b"\x78\x9c\x00\x63\xff" + b"\x9c\x00" + b"A" * 154 + b"\x01\x00\x00\xff\xff"
        expected = b"\x9c\x00" + b"A" * 154
        self.assertEqual(MODULE.decode_response_body(raw, {"Content-Encoding": "deflate"}), expected)

    def test_body_part_limit_includes_block_separators(self):
        parser = MODULE.MetadataHTMLParser(max_text_parts=20)
        parser.feed("<body>" + "<p>text</p>" * 10_000 + "</body>")
        self.assertLessEqual(len(parser.body_parts), 20)
        self.assertIn("text", parser.body_text)

    def test_single_body_part_has_character_limit(self):
        parser = MODULE.MetadataHTMLParser()
        parser.feed("<body>" + "x" * (MODULE.MAX_BODY_TEXT_CHARS + 100) + "</body>")
        self.assertEqual(len(parser.body_text), MODULE.MAX_BODY_TEXT_CHARS)

    def test_late_higher_priority_description_is_not_lost(self):
        body = ('<html><head><title>fallback</title><meta name="description" content="fallback summary"></head>'
                '<body>' + '<p>body text</p>' * 1000 +
                '<meta property="og:title" content="preferred">'
                '<meta property="og:description" content="A preferred summary"></body></html>')
        item = self.fetch(Response(body.encode()))
        self.assertEqual(item.title, "preferred")
        self.assertEqual(item.summary, "A preferred summary")

    def test_continuous_text_across_previous_chunk_boundary_is_unchanged(self):
        for text in ("abcdef", "甲乙丙丁戊己"):
            with self.subTest(text=text):
                prefix = "<html><head><title>Title</title>"
                opener = "</head><body>"
                body = prefix + " " * (8192 - len(prefix) - len(opener) - 3) + opener + text + "</body></html>"
                self.assertEqual(body.index(text) + 3, 8192)
                item = self.fetch(Response(body.encode()))
                self.assertEqual(item.summary, text)

    def test_complete_metadata_can_skip_later_body_parsing(self):
        body = ('<html><head><meta property="og:title" content="preferred">'
                '<meta property="og:description" content="summary">'
                '<meta property="og:url" content="/canonical">'
                '<meta property="og:site_name" content="Example">' + ' ' * 8192 +
                '</head><body>' + '<p>unneeded</p>' * 1000 + '</body></html>')
        parser = MODULE.MetadataHTMLParser(stop_when_complete=True)
        with patch.object(MODULE, "MetadataHTMLParser", return_value=parser):
            item = self.fetch(Response(body.encode()))
        self.assertEqual(parser.body_parts, [])
        self.assertEqual(item.canonical_url, "https://example.invalid/canonical")
        self.assertEqual(item.site_name, "Example")


if __name__ == "__main__":
    unittest.main()
