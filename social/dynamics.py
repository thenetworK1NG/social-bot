import json
import os
import random
from typing import List, Dict

from social.feed import load_state, save_state


def get_state_meta() -> dict:
    state = load_state()
    return state


def update_meta(key, value):
    state = load_state()
    state[key] = value
    save_state(state)


def get_running_jokes() -> List[str]:
    state = load_state()
    return state.get("running_jokes", [])


def add_running_joke(joke: str):
    state = load_state()
    jokes = state.get("running_jokes", [])
    if joke and joke not in jokes:
        jokes.append(joke)
        # keep max 10 running jokes
        state["running_jokes"] = jokes[-10:]
        save_state(state)


def bump_relationship(author_a, author_b, delta=0.1):
    """Increase/decrease relationship score between two bots."""
    if author_a == author_b:
        return
    state = load_state()
    bots = state.get("bots", {})
    for name in [author_a, author_b]:
        bs = bots.get(name, {})
        rels = bs.get("relationships", {})
        other = author_b if name == author_a else author_a
        current = rels.get(other, 0.0)
        rels[other] = max(-1.0, min(1.0, current + delta))
        bs["relationships"] = rels
        bots[name] = bs
    state["bots"] = bots
    save_state(state)


def relationship_score(author_a, author_b) -> float:
    state = load_state()
    bots = state.get("bots", {})
    bs = bots.get(author_a, {})
    return bs.get("relationships", {}).get(author_b, 0.0)


def mark_recent_thread(post_id: str, chain: List[str]):
    """Track an active conversation thread on a post so it can be compounded."""
    state = load_state()
    threads = state.get("threads", {})
    timestamp = __import__("datetime").datetime.now().isoformat()
    threads[post_id] = {"chain": chain, "updated": timestamp}
    state["threads"] = threads
    save_state(state)


def get_thread(post_id) -> Dict:
    state = load_state()
    return state.get("threads", {}).get(post_id, {})
