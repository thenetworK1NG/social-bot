#!/usr/bin/env python3
"""Reset the socials — wipe all bot data locally and on GitHub.

Usage:
    python reset.py          # prompts for confirmation
    python reset.py --yes    # skips confirmation (for automation)
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
FEED_PATH = os.path.join(DATA_DIR, "feed.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=ROOT,
    )


def reset_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        json.dump([], f)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f)
    print(f"[{datetime.now():%H:%M:%S}] Data cleared  (feed.json=[], state.json={{}})")


def rebuild_site():
    sys.path.insert(0, ROOT)
    import build_site
    build_site.generate()
    print(f"[{datetime.now():%H:%M:%S}] Site rebuilt from empty state")


def commit_and_push():
    # Stage both data and docs — this is a one-time full wipe, not the
    # normal bot flow where only data/ is staged and Actions rebuilds docs.
    git("add", "--", "data", "docs")
    r = git("commit", "-m", "reset: cleared all bot data")
    if r.returncode != 0:
        print(f"[{datetime.now():%H:%M:%S}] Nothing to commit")
        return False

    # Push with rebase retry (handles concurrent Actions rebuild commits)
    for attempt in range(4):
        r = git("push")
        if r.returncode == 0:
            print(f"[{datetime.now():%H:%M:%S}] Pushed reset to GitHub")
            return True
        git("pull", "--rebase", "--autostash")
    r = git("push")
    if r.returncode == 0:
        print(f"[{datetime.now():%H:%M:%S}] Pushed reset to GitHub (after rebase)")
        return True
    print(f"[{datetime.now():%H:%M:%S}] WARNING: push failed — run 'git status' to check")
    return False


def verify_live():
    import urllib.request
    try:
        html = urllib.request.urlopen(
            "https://thenetwork1ng.github.io/social-bot/", timeout=25
        ).read().decode("utf-8")
        if "No posts yet" in html:
            print(f"[{datetime.now():%H:%M:%S}] Live site verified: empty ✓")
        elif "the socials" in html:
            print(f"[{datetime.now():%H:%M:%S}] Live site updated (may still be deploying new content...)")
        else:
            print(f"[{datetime.now():%H:%M:%S}] Live site returned unexpected content")
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Live site check skipped ({e})")


def main():
    yes = "--yes" in sys.argv
    print("=" * 48)
    print("  THE SOCIALS — FULL RESET")
    print("=" * 48)
    print()
    print("This will erase:")
    print("  - all posts and comments")
    print("  - all bot stats and relationships")
    print("  - all running joke history")
    print("  - all conversation threads")
    print()
    print("The live site will show 'No posts yet' until new posts appear.")
    print()

    if not yes:
        ans = input("Proceed with full reset? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return

    print()
    reset_data()
    rebuild_site()
    pushed = commit_and_push()

    if pushed:
        print()
        print("Waiting 15s for GitHub Actions to rebuild the live site...")
        time.sleep(15)
        verify_live()

    print()
    print("=" * 48)
    print("  RESET COMPLETE")
    print("=" * 48)
    print()
    print("Start fresh with:  python run.py")
    print("The first bot run will seed new posts into the empty feed.")
    print()


if __name__ == "__main__":
    main()
