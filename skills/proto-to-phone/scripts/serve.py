#!/usr/bin/env python3
"""Web mode: open the adapted prototype in the phone's browser over the local network.

Usage: serve.py --project DIR --confirm-network [--minutes 60] [--port 0] [--open-sim]

Works on macOS, Windows and Linux, with any phone on the same Wi-Fi, no app
install. Less native than the app (the browser decides the keyboard and the
bars), but it is the only way for an iPhone without a Mac.

Safety: serves three files only (the page, its manifest and the icon), from
memory, under a random unguessable path, on the local network, for a limited
time (default 60 minutes). Anyone on the same network who has the exact link
can open it while it runs, so the person must agree first (--confirm-network)
and should not use it on public Wi-Fi.
"""
import argparse
import http.server
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_lib as pl  # noqa: E402


def lan_ip():
    """The address other devices on the network reach this computer at (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = None
    finally:
        s.close()
    if not ip or ip.startswith("127."):
        raise pl.PhoneError("No local network found. Connect this computer to the same Wi-Fi as the phone.")
    return ip


def manifest(name, color="#FFFFFF"):
    return json.dumps({
        "name": name, "short_name": name[:12], "start_url": "./", "scope": "./", "display": "standalone",
        "orientation": "portrait", "background_color": color, "theme_color": color,
        "icons": [{"src": "icon.png", "sizes": "1024x1024", "type": "image/png", "purpose": "any"}],
    }, indent=2).encode("utf-8")


def make_handler(token, files, log):
    prefix = "/%s/" % token

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "proto-to-phone"
        sys_version = ""

        def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", head_only=False, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

        def _route(self, head_only):
            path = self.path.split("?", 1)[0].split("#", 1)[0]
            if path == prefix[:-1]:
                return self._send(301, head_only=head_only, extra={"Location": prefix})
            if not path.startswith(prefix):
                return self._send(404, b"Not found", head_only=head_only)
            name = path[len(prefix):] or "index.html"
            if name not in files:
                return self._send(404, b"Not found", head_only=head_only)
            body, ctype = files[name]
            return self._send(200, body, ctype, head_only=head_only)

        def do_GET(self):
            self._route(False)

        def do_HEAD(self):
            self._route(True)

        def _refuse(self):
            self._send(405, b"Method not allowed", extra={"Allow": "GET, HEAD"})

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse

        def log_message(self, fmt, *args):
            # never print the secret path
            log("%s %s" % (self.client_address[0], (fmt % args).replace(token, "<link>")))

    return Handler


def start_server(m, minutes, port=0, log=print):
    """Adapt for the web, then serve it on the local network. Returns (server, url);
    the caller runs server.serve_forever(). It shuts itself down after `minutes`."""
    page = pl.prepare(m, "web")
    icon = os.path.join(m["dir"], "icon.png")
    files = {
        "index.html": (open(page, "rb").read(), "text/html; charset=utf-8"),
        "manifest.webmanifest": (manifest(m["name"]), "application/manifest+json"),
    }
    if os.path.isfile(icon):
        files["icon.png"] = (open(icon, "rb").read(), "image/png")
    ip = lan_ip()
    token = secrets.token_urlsafe(12)
    server = http.server.ThreadingHTTPServer((ip, port), make_handler(token, files, log))
    url = "http://%s:%d/%s/" % (ip, server.server_address[1], token)
    timer = threading.Timer(minutes * 60, server.shutdown)
    timer.daemon = True
    timer.start()
    return server, url


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--confirm-network", action="store_true",
                    help="the person agreed to share the prototype on their local network")
    ap.add_argument("--minutes", type=int, default=60, help="stop after this many minutes (1-480)")
    ap.add_argument("--port", type=int, default=0, help="0 = any free port")
    ap.add_argument("--open-sim", action="store_true", help="macOS: also open it in the booted iOS simulator")
    args = ap.parse_args()
    try:
        m = pl.load_project(args.project)
        if not args.confirm_network:
            raise pl.PhoneError(
                "Web mode shares the prototype on the local network while it runs (%d minutes): anyone on the "
                "same Wi-Fi with the exact link can open it. Ask the person; if they agree, run again with "
                "--confirm-network. Do not use it on public Wi-Fi." % args.minutes)
        if not 1 <= args.minutes <= 480:
            raise pl.PhoneError("--minutes must be between 1 and 480.")
        server, url = start_server(m, args.minutes, args.port, print)
        print("serve: open this on the phone (same Wi-Fi):\n\n    %s\n" % url)
        if shutil.which("qrencode"):
            subprocess.run(["qrencode", "-t", "ANSIUTF8", url])
        print("serve: add it to the home screen to hide the browser bars:")
        print("       iPhone: Share > Add to Home Screen.   Android: menu > Add to home screen.")
        print("serve: stops in %d minutes or with Ctrl+C. The link changes every run." % args.minutes)
        if args.open_sim and sys.platform == "darwin":
            subprocess.run(["xcrun", "simctl", "openurl", "booted", url], check=False)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            print("serve: stopped.")
    except pl.PhoneError as e:
        sys.exit("serve: %s" % e)


if __name__ == "__main__":
    main()
