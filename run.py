import random
import time
import sys
import os
import subprocess
from datetime import datetime, timedelta

from config import BOTS
from engine.scheduler import SmartScheduler
from engine.poster import create_post
from engine.engager import engage_with_feed
from social import feed
from social import dynamics

CREATE_NO_WINDOW = 0x08000000


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def kill_existing_instances():
    """Kill any other running `run.py` so a fresh launch never clashes with an
    already-running bot (two writers to the DB would race).

    `python run.py` can spawn a paired wrapper process (self + one parent), so
    both this process and its direct parent are excluded to avoid self-kill."""
    me = os.getpid()
    my_parent = os.getppid()
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run\\.py' } "
             "| ForEach-Object { \"$($_.ProcessId):$($_.ParentProcessId)\" }"],
            capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, timeout=15,
        ).stdout
    except Exception:
        out = ""
    for line in out.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        pid = int(parts[0])
        if pid in (me, my_parent):
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=10,
            )
            log(f"killed existing bot instance (PID {pid})")
        except Exception:
            pass


class ActivityLoop:
    """
    The bot never truly idles. While it waits for the next big post it keeps
    generating background activity: likes, comments, reply threads, and casual
    mini-posts, all saved straight to Firebase on every write.
    """

    def __init__(self):
        self.scheduler = SmartScheduler()
        self.next_post_delay = self._next_post_delay()
        self.next_post_at = datetime.now() + timedelta(seconds=self.next_post_delay)
        self.next_engage_delay = self._engagement_delay()
        self.next_engage_at = datetime.now() + timedelta(seconds=self.next_engage_delay)
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

    def _should_engage(self):
        return datetime.now() >= self.next_engage_at

    def _engage(self):
        """One background engagement pass. Returns how many interactions happened."""
        count = engage_with_feed()
        self.total_engagements += count
        self.next_engage_delay = self._engagement_delay()
        self.next_engage_at = datetime.now() + timedelta(seconds=self.next_engage_delay)
        return count

    def _mini_post(self):
        """Occasionally post a casual mini update during long waits."""
        if random.random() < 0.35:
            post = create_post()
            self.posts_since_push += 1
            return post
        return None

    def _status(self):
        """One-line status for the next scheduled events."""
        nxt = self.next_post_at - datetime.now()
        nxt_s = max(0, int(nxt.total_seconds()))
        nxt_m = nxt_s // 60
        nxt_sec = nxt_s % 60
        return f"next post: {nxt_m}m{0 if nxt_sec<10 else ''}{nxt_sec}s | posts: {self.posts_since_push} | engagements: {self.total_engagements}"

    def run_step(self):
        now = datetime.now()

        # If it's time for the main scheduled post, do it.
        if self._should_post():
            self._main_post()
            self.next_post_delay = self._next_post_delay()
            self.next_post_at = datetime.now() + timedelta(seconds=self.next_post_delay)
            self.last_engage = now
            self.next_engage_delay = self._engagement_delay()
            self.next_engage_at = now + timedelta(seconds=self.next_engage_delay)
            return

        # Otherwise keep the network alive with background activity while waiting.
        if self._should_engage():
            self.last_engage = now
            count = self._engage()
            if count:
                log(f"  engagement pass: {count} new like(s)/comment(s)")
            else:
                log("  engagement pass: nothing new")
            mini = self._mini_post()
            if mini:
                log(f"  mini post by {mini.author}: {mini.content[:70]}")
            log(f"  {self._status()}")

    def _main_post(self):
        post = create_post()
        self.posts_since_push += 1
        log(f"-- new main post by {post.author} [{post.post_type}] --")
        log(f"  content: {post.content[:90]}")
        count = engage_with_feed()
        self.total_engagements += count
        if count:
            log(f"  early reactions: {count}")
        log(f"  {self._status()}")


def main():
    feed.ensure_files()
    kill_existing_instances()
    log("Social bot network starting up with big-pickle...")
    log(f"Active bots: {', '.join(b.name for b in BOTS)}")

    loop = ActivityLoop()
    log(f"Schedule: next post in ~{loop.next_post_delay//60}m{loop.next_post_delay%60:02d}s | "
        f"engagement every ~{loop.next_engage_delay//60}m{loop.next_engage_delay%60:02d}s")
    try:
        while True:
            loop.run_step()
            time.sleep(5)
    except KeyboardInterrupt:
        log("Shutting down, saving state...")
        feed.ensure_files()
        log(f"Goodbye. ({loop.total_engagements} total engagements this run)")
        sys.exit(0)
    except Exception as e:
        log(f"Error: {e}")
        feed.ensure_files()
        raise


if __name__ == "__main__":
    main()
