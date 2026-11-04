"""Serve the web page locally: python3 serve.py, then open http://127.0.0.1:8765

The page itself is static (web/: index.html + data/charts-cn.json) and works the same on GitHub Pages: scores are
imported in the browser with the player's own token and kept in the browser. Run locally, this server adds:

  GET  /api/profile  the newest import saved by scores.py (data/player/<source>.json), used when the browser has none
  GET  /api/manual   data/player/manual.json resolved to chart ids, merged into whatever profile the page uses
  GET  /api/plan     data/player/plan.json
  PUT  /api/plan     save it, so the plan stays readable outside the browser

Listens on 127.0.0.1 only. Writes accept JSON bodies from this host only, so other sites open in the browser
cannot change the plan.
"""
import argparse
import json
import math
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import rating
import scores

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
PLAN = scores.PLAYER_DIR / "plan.json"


def newest_profile():
    profiles = []
    for source in scores.SOURCES:
        path = scores.PLAYER_DIR / f"{source}.json"
        if path.exists():
            profiles.append(json.loads(path.read_text(encoding="utf-8")))
    if not profiles:
        return None
    p = max(profiles, key=lambda p: (p["complete"], p["fetched_at"]))
    return {
        "source": p["source"], "fetchedAt": p["fetched_at"], "player": p["player"],
        "scores": [{k: s.get(k) for k in ("music_id", "type", "difficulty", "achievement", "combo")} for s in p["scores"]],
    }


def manual_scores():
    if not scores.MANUAL.exists():
        return []
    by_title = {(c["title"], c["type"], c["difficulty"]): c["music_id"] for c in rating.load_charts("cn")}
    out = []
    for m in json.loads(scores.MANUAL.read_text(encoding="utf-8")):
        mid = m.get("music_id", by_title.get((m.get("title"), m["type"], m["difficulty"])))
        if mid is not None:
            out.append({"music_id": mid, "type": m["type"], "difficulty": m["difficulty"],
                        "achievement": m["achievement"], "combo": m.get("combo")})
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _local_host(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def _static(self, path):
        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/json":
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_GET(self):
        if not self._local_host():
            return self._send(403, {"error": "forbidden"})
        path = self.path.split("?", 1)[0]
        if path == "/api/profile":
            p = newest_profile()
            return self._send(200, p) if p else self._send(404, {"error": "no saved import"})
        if path == "/api/manual":
            return self._send(200, manual_scores())
        if path == "/api/plan":
            return self._send(200, json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {})
        self._static(path)

    def do_PUT(self):
        if self.path != "/api/plan":
            return self._send(404, {"error": "not found"})
        if not self._local_host() or not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._send(403, {"error": "forbidden"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "body is not JSON"})
        target, items = body.get("target"), body.get("items")
        if not isinstance(items, dict) or not isinstance(target, (int, float)) or not all(
                isinstance(v, (int, float)) and math.isfinite(v) and 0 < v <= 101 for v in items.values()):
            return self._send(400, {"error": "expected {target: number, items: {chart id: achievement}}"})
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps({"target": target, "items": items}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        self._send(200, {"ok": True})

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/plan"):  # saves are frequent; keep the console readable
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"舞萌 B50 规划：http://127.0.0.1:{args.port}  （Ctrl+C 退出）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
