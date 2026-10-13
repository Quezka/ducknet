"""La release è coerente: versione, CHANGELOG, metainfo, file .desktop, installer e CI."""
import os
import re
import unittest
import xml.etree.ElementTree as ET

import ducknet
import stagno

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(*path):
    with open(os.path.join(ROOT, *path), encoding="utf-8") as f:
        return f.read()


class ReleaseTest(unittest.TestCase):
    def test_versions_are_shared(self):
        self.assertEqual(stagno.__version__, ducknet.__version__)
        self.assertRegex(ducknet.__version__, r"^\d+\.\d+\.\d+$")

    def test_changelog_has_current_version(self):
        self.assertIn("## [%s]" % ducknet.__version__, read("CHANGELOG.md"))

    def test_metainfo_lists_every_changelog_version(self):
        root = ET.fromstring(read("packaging", "%s.metainfo.xml" % stagno.APP_ID))
        self.assertEqual(root.findtext("id"), stagno.APP_ID)
        released = [r.get("version") for r in root.iter("release")]
        in_changelog = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", read("CHANGELOG.md"), re.M)
        self.assertEqual(released, in_changelog)
        self.assertEqual(released[0], ducknet.__version__)

    def test_desktop_file(self):
        text = read("packaging", "%s.desktop" % stagno.APP_ID)
        self.assertIn("Icon=%s" % stagno.APP_ID, text)
        self.assertIn("MimeType=x-scheme-handler/duck;", text)
        self.assertRegex(text, r"(?m)^Exec=stagno %u$")      # %u: il link duck:// arriva come argomento

    def test_icon_files_exist(self):
        for name in ("stagno.svg", "close-light.svg", "close-dark.svg"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "stagno", "assets", name)), name)

    def test_installer_is_per_user_with_stable_id_and_duck_links(self):
        iss = read("packaging", "stagno.iss")
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("{{B7D4E2A1-5C93-4E68-A0F7-2D1B9C8E6A43}", iss)       # mai cambiarlo: serve agli aggiornamenti
        self.assertIn('Software\\Classes\\duck', iss)
        self.assertIn("URL Protocol", iss)
        for lang in ("English", "Italian", "Russian"):
            self.assertIn("Languages\\%s.isl" % lang if lang != "English" else "Default.isl", iss)

    def test_build_scripts_keep_webengine(self):
        build = read("scripts", "build.py")
        self.assertNotIn("QtWebEngineCore", build)        # il browser ne ha bisogno
        self.assertIn("stagno/assets", build)

    def test_ci_checks_tag_against_version(self):
        ci = read(".github", "workflows", "build.yml")
        self.assertIn("ducknet/__init__.py", ci)
        self.assertIn("--installer", ci)
        self.assertIn("--deb", ci)

    def test_release_notes_script_finds_sections(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rn", os.path.join(ROOT, "scripts", "release_notes.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(mod.notes_for(ducknet.__version__))


if __name__ == "__main__":
    unittest.main()
