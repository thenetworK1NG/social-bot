import json
import os
from typing import List

from social.models import Post, BotState

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FEED_PATH = os.path.join(DATA_DIR, "feed.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")


def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(FEED_PATH):
        _write_json(FEED_PATH, [])
    if not os.path.exists(STATE_PATH):
        _write_json(STATE_PATH, {})


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_feed() -> List[Post]:
    try:
        with open(FEED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Post.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return []


def save_feed(posts: List[Post]):
    _write_json(FEED_PATH, [p.to_dict() for p in posts])


def load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_state(state: dict):
    _write_json(STATE_PATH, state)


def add_post(post: Post):
    posts = load_feed()
    posts.insert(0, post)
    save_feed(posts)


def get_recent_posts(n=5) -> List[Post]:
    posts = load_feed()
    return posts[:n]


def get_post(post_id) -> Post:
    for p in load_feed():
        if p.id == post_id:
            return p
    return None


def update_post(post: Post):
    posts = load_feed()
    for i, p in enumerate(posts):
        if p.id == post.id:
            posts[i] = post
            break
    save_feed(posts)


def get_bot_state(name) -> BotState:
    state = load_state()
    bots = state.get("bots", {})
    bs = bots.get(name, {})
    return BotState.from_dict(bs) if bs else BotState(name=name)


def update_bot_state(bs: BotState):
    state = load_state()
    bots = state.get("bots", {})
    bots[bs.name] = bs.to_dict()
    state["bots"] = bots
    save_state(state)
