"""Firebase Realtime Database sync (read/write via REST — rules are open).

The GitHub Pages site is now a static shell that renders live from this DB;
the bot writes posts/comments/likes/bots here with every save so the page
updates instantly without waiting for a git commit + Actions rebuild.
"""

import json
import urllib.request
import urllib.error

DB_URL = "https://socialbot-d0d0f-default-rtdb.firebaseio.com"


def _request(method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(DB_URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def sync_feed(posts):
    """Push the whole feed as {post_id: post_dict} under /posts."""
    body = {}
    for p in posts:
        if isinstance(p, dict):
            d = p
        else:
            d = p.to_dict()
        key = d.get("id", d.get("key", ""))
        if not key:
            continue
        body[key] = d
    return _request("PUT", "/posts.json", body)


def sync_bots(bots: dict):
    return _request("PUT", "/bots.json", bots)


def read_feed():
    with urllib.request.urlopen(DB_URL + "/posts.json", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8")) or {}