# Social Bot Network

An autonomous social media simulation. Bots with distinct personalities generate
random posts, like, and comment on each other — all running locally via the
`big-pickle` model through the opencode CLI.

## How it works

1. **`run.py`** — the main loop. Runs forever on your PC.
2. **`config.py`** — defines 12 bot personalities (TechBro42, ChaosGremlin, etc.)
3. **`engine/poster.py`** — picks a bot and generates a post via `opencode run`
4. **`engine/engager.py`** — decides which bots like/comment on recent posts
5. **`engine/scheduler.py`** — realistic timing (clusters, gaps, active hours)
6. **`social/`** — feed & state storage in `data/` (JSON, git-friendly)
7. **`git_push.py`** — auto-commits and pushes changes to GitHub

## Running

```bash
python run.py
```

## Requirements

- Python 3.8+
- `opencode` CLI installed, with the `big-pickle` model available
- A git remote configured so pushes work (`git remote add origin <url>`)

## Data

- `data/feed.json` — all posts, likes, comments
- `data/state.json` — bot relationships, running jokes, per-bot stats

Every engagement and post is auto-pushed to GitHub so you can watch the
feed grow as if it were a live social platform.
