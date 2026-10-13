"""I confini tra i livelli di DuckNet, controllati leggendo gli import."""
import ast
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def imports(folder):
    """Ritorna {file: set di moduli importati} per ogni .py sotto `folder`."""
    found = {}
    for base, _, files in os.walk(os.path.join(ROOT, folder)):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    # i relativi li risolviamo come "<livello>:<modulo>" per distinguere ..ui da .ui
                    mods.add("%s%s" % ("." * node.level, node.module or ""))
                    mods |= {"%s%s.%s" % ("." * node.level, node.module or "", a.name) for a in node.names}
            found[os.path.relpath(path, ROOT)] = mods
    return found


class ArchitectureTest(unittest.TestCase):
    def test_ducknet_is_standalone_stdlib(self):
        for path, mods in imports("ducknet").items():
            for m in mods:
                self.assertFalse(m.split(".")[0] in ("stagno", "PySide6"), "%s importa %s" % (path, m))

    def test_stagno_core_has_no_qt_and_no_ui(self):
        for path, mods in imports("stagno/core").items():
            for m in mods:
                self.assertFalse(m.startswith("PySide6"), "%s importa %s" % (path, m))
                self.assertNotIn("ui", m.lstrip(".").split("."), "%s importa %s" % (path, m))

    def test_ui_does_not_touch_the_protocol_directly(self):
        # la UI parla col mondo solo tramite stagno.core (fetcher/address/pages), mai con socket o DNS
        for path, mods in imports("stagno/ui").items():
            for m in mods:
                self.assertNotIn(m.lstrip(".").split(".")[0], ("socket", "asyncio", "ducknet"), "%s importa %s" % (path, m))


if __name__ == "__main__":
    unittest.main()
