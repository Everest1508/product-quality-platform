import tempfile
from pathlib import Path

from django.test import TestCase, override_settings


class UiAssetsTest(TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "app.js").write_text("console.log(1)")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "x.js").write_text("secret")
        self.override = override_settings(FRONTEND_DIST=self.dir)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_serves_a_built_file_without_caching(self):
        response = self.client.get("/ui/app.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"console.log(1)")
        self.assertEqual(response["Cache-Control"], "no-cache")

    def test_unknown_file_is_404(self):
        self.assertEqual(self.client.get("/ui/nope.js").status_code, 404)

    def test_nothing_outside_the_dist_root_is_served(self):
        self.assertEqual(self.client.get("/ui/sub").status_code, 404)
        self.assertEqual(self.client.get("/ui/..%2Fsettings.py").status_code, 404)
        self.assertEqual(self.client.get("/ui/sub/x.js").status_code, 404)
