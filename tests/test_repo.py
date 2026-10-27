import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Machine- and person-specific values must never ship with the skill.
FORBIDDEN = [r"00008\d{3}-[0-9A-F]{16}", r"/Users/[a-z0-9._-]+/", r"phone\.[a-z0-9]{10}\."]


class RepoTest(unittest.TestCase):
    def files(self):
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for n in names:
                if n.endswith((".png", ".pyc")) or n == ".DS_Store":
                    continue
                yield os.path.join(base, n)

    def test_no_machine_specific_values(self):
        for path in self.files():
            if os.path.basename(path) == "test_repo.py":
                continue
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
            for pat in FORBIDDEN:
                self.assertIsNone(re.search(pat, text), "%s matches %s" % (path, pat))

    def test_skill_frontmatter(self):
        with open(os.path.join(ROOT, "skills", "proto-to-phone", "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\nname: proto-to-phone\ndescription: "))
        self.assertLess(len(text.splitlines()), 450)

    def test_template_placeholders_are_all_known(self):
        known = {"__TEAM_ID__", "__BUNDLE_ID__", "__BUNDLE_PREFIX__", "__PRODUCT_NAME__", "__DISPLAY_NAME__",
                 "__ANDROID_ID__", "__ANDROID_LABEL__"}
        for tpl in (os.path.join(ROOT, "skills", "proto-to-phone", "template"),
                    os.path.join(ROOT, "skills", "proto-to-phone", "template-android")):
          for base, _, names in os.walk(tpl):
            for n in names:
                if n.endswith(".png"):
                    continue
                with open(os.path.join(base, n), encoding="utf-8", errors="ignore") as f:
                    found = set(re.findall(r"__[A-Z_]+__", f.read()))
                self.assertLessEqual(found, known, n)


if __name__ == "__main__":
    unittest.main()
