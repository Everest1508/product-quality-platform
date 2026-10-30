from django.template import Context, Template
from django.test import SimpleTestCase


class LinkifyTest(SimpleTestCase):
    def render(self, text):
        return Template("{% load text_tags %}{{ t|linkify }}").render(Context({"t": text}))

    def test_commit_url_becomes_link_and_script_is_text(self):
        out = self.render("Commits:\nhttps://github.com/org/repo/commit/abc123\n<script>alert(1)</script>")
        self.assertIn('<a href="https://github.com/org/repo/commit/abc123" target="_blank" rel="noopener noreferrer">', out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", out)
        self.assertNotIn("<script>", out)
        self.assertEqual(out.count("<br>"), 2)

    def test_only_http_and_https_are_linked(self):
        out = self.render("javascript:alert(1) data:text/html,x ftp://x.test")
        self.assertNotIn("<a ", out)

    def test_quotes_in_url_cannot_break_out_of_href(self):
        out = self.render('https://x.test/a"onmouseover="alert(1)')
        self.assertNotIn('onmouseover="', out)
