import random
import time
import sys
from datetime import datetime, timedelta

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


class ActivityLoop:
    """
    The bot never truly idles. While it waits for the next big post it keeps
    generating background activity: likes, comments, reply threads, and casual
    mini-posts, all pushed to GitHub continuously.
    """

    def __init__(self):
        self.scheduler = SmartScheduler()
        self.next_post_at = datetime.now() + timedelta(seconds=self._next_post_delay())
        self.last_engage = datetime.now()
        self.posts_since_push = 0
        self.total_engagements = 0

    def _next_post_delay(self):
        return self.scheduler.next_post_delay()

    def _engagement_delay(self):
        # Background engagement happens every 2-4 minutes
        return random.randint(2, 4) * 60

    def _should_post(self):
        return datetime.now() >= self.next_post_at

    def _engage(self):
        """One background engagement pass. Returns how many interactions happened."""
        count = engage_with_feed()
        if count:
            self.total_engagements += count
            log(f"  background engagement: {count} new like(s)/comment(s)")
        return count

    def _mini_post(self):
        """Occasionally post a casual mini update during long waits."""
        # Only if we've been waiting a while and engagement is flowing
        if random.random() < 0.35:
            post = create_post()
            self.posts_since_push += 1
            log(f"  mini post by {post.author}: {post.content[:70]}")

    def run_step(self):
        now = datetime.now()

        # If it's time for the main scheduled post, do it.
        if self._should_post():
            self._main_post()
            self.next_post_at = datetime.now() + timedelta(seconds=self._next_post_delay())
            # Reset so background activity ramps up again
            self.last_engage = now
            return

        # Otherwise keep the network alive with background activity while waiting.
        if now - self.last_engage >= timedelta(seconds=self._engagement_delay()):
            self.last_engage = now
            self._engage()
            # Push gathered activity to GitHub right away so the site updates live
            autopush()
            # Occasionally drop a mini post during long waits
            self._mini_post()
            autopush()

    def _main_post(self):
        log("-- new main post --")
        post = create_post()
        self.posts_since_push += 1
        log(f"  posted by {post.author}: {post.content[:80]}")
        # A burst of engagement right after so new posts get early reactions
        count = engage_with_feed()
        if count:
            self.total_engagements += count
            log(f"  early reactions: {count}")
        autopush()


def main():
    feed.ensure_files()
    log("Social bot network starting up with big-pickle...")
    log(f"Active bots: {', '.join(b.name for b in BOTS)}")

    loop = ActivityLoop()
    try:
        while True:
            loop.run_step()
            # Small tick so the loop checks frequently without busy-spinning.
            time.sleep(5)
    except KeyboardInterrupt:
        log("Shutting down, saving state...")
        feed.ensure_files()
        autopush()
        log(f"Goodbye. ({loop.total_engagements} total engagements this run)")
        sys.exit(0)
    except Exception as e:
        log(f"Error: {e}")
        feed.ensure_files()
        try:
            autopush()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
