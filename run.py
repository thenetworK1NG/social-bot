import random
import time
import sys
from datetime import datetime

from config import BOTS
from engine.scheduler import SmartScheduler
from engine.poster import create_post
from engine.engager import engage_with_feed
from social import feed
from social import dynamics
from git_push import autopush


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cycle(cycle_num):
    scheduler = SmartScheduler()

    # Engagements happen frequently (every few minutes)
    log("-- engagement cycle --")
    count = engage_with_feed()
    if count:
        log(f"  {count} engagement(s) recorded")
    autopush()

    # Posting happens less frequently, with natural gaps
    delay = scheduler.next_post_delay()
    log(f"  waiting {delay//60} min before next post...")
    time.sleep(min(delay, 600))
    post = create_post()
    log(f"  posted by {post.author}: {post.content[:80]}")
    # Do a quick engagement pass right after posting so new posts get early reactions
    engage_with_feed()
    autopush()


def main():
    feed.ensure_files()
    log("Social bot network starting up with big-pickle...")
    log(f"Active bots: {', '.join(b.name for b in BOTS)}")

    cycle_num = 0
    try:
        while True:
            cycle_num += 1
            log(f"--- cycle {cycle_num} ---")
            run_cycle(cycle_num)
    except KeyboardInterrupt:
        log("Shutting down, saving state...")
        feed.ensure_files()
        autopush()
        log("State saved and pushed. Goodbye.")
        sys.exit(0)
    except Exception as e:
        log(f"Error in cycle: {e}")
        raise


if __name__ == "__main__":
    main()
