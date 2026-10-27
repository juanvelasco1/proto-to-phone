"""The iPhone gates in sync.py: nothing is built or installed on a device
without the person's confirmation and without a simulator check of this exact
version. A fake device stands in for the phone; any real command fails the test."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "proto-to-phone", "scripts"))
import phone_lib as pl  # noqa: E402
import sync  # noqa: E402

DEVICE = {"id": "X", "udid": "FAKE-UDID", "name": "Test iPhone", "reachable": True}


class CommandRan(Exception):
    pass


def no_commands(*a, **k):
    raise CommandRan(a[0] if a else k)


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        os.makedirs(os.path.join(d, "Web"))
        self.html = os.path.join(d, "Web", "index.html")
        with open(self.html, "w") as f:
            f.write("<html>adapted</html>")
        self.meta = {"name": "T", "slug": "t", "product": "T", "bundle_id": "phone.abc.t", "team": "ABCDEFGHIJ",
                     "source": os.path.join(d, "p.html"), "device_confirmed": False, "verified": None}

    def tearDown(self):
        self.tmp.cleanup()

    def write_meta(self, **kw):
        m = dict(self.meta, **kw)
        with open(os.path.join(self.tmp.name, pl.META), "w") as f:
            json.dump(m, f)

    def run_sync(self, *extra, expect=SystemExit):
        argv = ["sync.py", "--project", self.tmp.name, "--target", "device"] + list(extra)
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sync, "pick_device", return_value=DEVICE), \
                mock.patch.object(pl, "prepare", return_value=None), \
                mock.patch.object(pl, "run", side_effect=no_commands), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(expect) as cm:
                sync.main()
        e = cm.exception
        return str(e.code if isinstance(e, SystemExit) else e)

    def test_first_install_needs_confirmation(self):
        self.write_meta()
        msg = self.run_sync()
        self.assertIn("First install on an iPhone", msg)
        self.assertIn("--confirm-device", msg)

    def test_unchecked_version_is_refused(self):
        self.write_meta()
        self.assertIn("has not been checked in the simulator", self.run_sync("--confirm-device"))

    def test_changed_version_is_refused(self):
        self.write_meta(device_confirmed=True, verified={"sha256": "0" * 64})
        self.assertIn("has not been checked in the simulator", self.run_sync())

    def test_checked_and_confirmed_reaches_the_build(self):
        self.write_meta(device_confirmed=True, verified={"sha256": pl.sha256_file(self.html)})
        cmd = self.run_sync(expect=CommandRan)  # the first real command is the build
        self.assertIn("xcodebuild", cmd)
        self.assertIn("id=FAKE-UDID", cmd)

    def test_no_team_cannot_go_to_device(self):
        self.write_meta(team=None)
        self.assertIn("no signing team", self.run_sync("--confirm-device"))


class ValidationTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(pl.check_name("  Mi App "), "Mi App")
        for bad in ("", " ", "x" * 31, "a\nb"):
            with self.assertRaises(pl.PhoneError):
                pl.check_name(bad)

    def test_ids(self):
        self.assertTrue(pl.TEAM_RE.match("ABCDE12345"))
        self.assertFalse(pl.TEAM_RE.match("abc"))
        self.assertTrue(pl.BUNDLE_RE.match("com.example.my-app"))
        for bad in ("noDots", "com..x", "com.ex ample", "com.example.app;rm"):
            self.assertFalse(pl.BUNDLE_RE.match(bad), bad)

    def test_logo_checks(self):
        with tempfile.TemporaryDirectory() as d:
            exe = os.path.join(d, "logo.exe")
            open(exe, "w").close()
            with mock.patch.object(pl, "have", return_value=True), mock.patch.object(pl, "run", side_effect=no_commands):
                with self.assertRaises(pl.PhoneError):
                    pl.make_icon(os.path.join(d, "o.png"), "A", logo=exe)
                with self.assertRaises(pl.PhoneError):
                    pl.make_icon(os.path.join(d, "o.png"), "A", logo=os.path.join(d, "missing.png"))
                with self.assertRaises(pl.PhoneError):
                    pl.make_icon(os.path.join(d, "o.png"), "A", background="red")


if __name__ == "__main__":
    unittest.main()
