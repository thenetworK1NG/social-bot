#!/usr/bin/env python3
"""Build the static GitHub Pages site from data/feed.json into docs/."""

import json
import os
import shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
FEED_PATH = os.path.join(DATA_DIR, "feed.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
DOCS_DIR = os.path.join(ROOT, "docs")


def load_feed():
    if not os.path.exists(FEED_PATH):
        return []
    try:
        with open(FEED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def time_ago(ts):
    try:
        dt = datetime.fromisoformat(ts)
        diff = datetime.now() - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            m = secs // 60
            return f"{m}m ago"
        if secs < 86400:
            h = secs // 3600
            return f"{h}h ago"
        d = secs // 86400
        return f"{d}d ago"
    except Exception:
        return "recently"


def avatar_color(name):
    import hashlib
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    palette = [
        "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b",
    ]
    return palette[h % len(palette)]


def initials(name):
    parts = [p for p in re_split(name)]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def re_split(name):
    s = ""
    for ch in name:
        if ch.isalnum():
            s += ch
        else:
            s += " "
    return s.split()


def bot_stats(bots):
    rows = []
    for name, info in bots.items():
        cols = (
            f'<div class="bot-row" style="--c:{avatar_color(name)}">'
            f'<div class="avatar">{initials(name)}</div>'
            f'<div class="bot-meta">'
            f'<div class="bot-name">{_esc(name)}</div>'
            f'<div class="bot-stats">{info.get("total_posts", 0)} posts · '
            f'{info.get("total_likes_given", 0)} likes · '
            f'{info.get("total_comments", 0)} comments</div>'
            f'</div></div>'
        )
        rows.append(cols)
    return "\n".join(rows)


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_post(post):
    author = post.get("author", "unknown")
    content = _esc(post.get("content", ""))
    ts = post.get("timestamp", "")
    likes = post.get("likes", [])
    comments = post.get("comments", [])
    post_type = post.get("post_type", "normal")

    badge = ""
    if post_type == "reply":
        badge = '<span class="badge reply-badge">↩ reply</span>'
    elif post_type == "question":
        badge = '<span class="badge question-badge">❓ question</span>'
    elif post_type == "followup":
        badge = '<span class="badge followup-badge">↻ follow-up</span>'
    elif post_type == "joke_reference":
        badge = '<span class="badge joke-badge">💬 inside joke</span>'

    like_row = ""
    if likes:
        names = ", ".join(_esc(x) for x in likes[:4])
        extra = f" +{len(likes)-4} more" if len(likes) > 4 else ""
        like_row = (
            f'<div class="like-row">'
            f'<span class="heart">♥</span>'
            f'<span class="like-text">{names}{extra}</span>'
            f'</div>'
        )

    comment_html = ""
    n_reacts = len(likes) + len(comments)
    react_count = f"{n_reacts} reactions" if n_reacts else ""
    for c in comments:
        c_author = c.get("author", "?")
        c_content = _esc(c.get("content", ""))
        c_ts = c.get("timestamp", "")
        reply_html = ""
        for r in c.get("replies", []):
            r_author = r.get("author", "?")
            r_content = _esc(r.get("content", ""))
            r_ts = r.get("timestamp", "")
            reply_html += (
                f'<div class="reply">'
                f'<div class="avatar sm" style="--c:{avatar_color(r_author)}">{initials(r_author)}</div>'
                f'<div class="reply-body">'
                f'<span class="c-author">{_esc(r_author)}</span> '
                f'<span class="c-text">{r_content}</span>'
                f'<div class="c-time">{time_ago(r_ts)}</div>'
                f'</div></div>'
            )
        comment_html += (
            f'<div class="comment">'
            f'<div class="avatar sm" style="--c:{avatar_color(c_author)}">{initials(c_author)}</div>'
            f'<div class="comment-body">'
            f'<span class="c-author">{_esc(c_author)}</span> '
            f'<span class="c-text">{c_content}</span>'
            f'<div class="c-time">{time_ago(c_ts)}</div>'
            f'{reply_html}'
            f'</div></div>'
        )

    comments_block = ""
    if comments:
        comments_block = f'<div class="comments">{comment_html}</div>'

    return f"""
    <article class="post">
      <div class="post-head">
        <div class="avatar" style="--c:{avatar_color(author)}">{initials(author)}</div>
        <div class="post-meta">
          <span class="p-author">{_esc(author)}</span> {badge}
          <span class="p-time">{time_ago(ts)}</span>
        </div>
      </div>
      <div class="post-content">{content}</div>
      <div class="post-actions">
        <span class="react badge">{react_count or "no reactions"}</span>
      </div>
      {like_row}
      {comments_block}
    </article>
    """


def generate():
    feed = load_feed()
    state = load_state()

    posts_html = "\n".join(render_post(p) for p in feed) if feed else \
        '<div class="empty">No posts yet. The bots are warming up...</div>'

    bots_html = bot_stats(state.get("bots", {}))

    n_posts = len(feed)
    total_likes = sum(len(p.get("likes", [])) for p in feed)
    total_comments = sum(len(p.get("comments", [])) for p in feed)
    updated = datetime.now().strftime("%B %d, %Y · %I:%M %p")

    total_reactions = total_likes + total_comments

    html = HTML_TEMPLATE
    html = html.replace("__POSTS__", posts_html)
    html = html.replace("__BOTS__", bots_html)
    html = html.replace("__NPOSTS__", str(n_posts))
    html = html.replace("__REACTIONS__", str(total_reactions))
    html = html.replace("__UPDATED__", updated)

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # Also publish the raw feed so the data is browsable
    shutil.copy(FEED_PATH, os.path.join(DOCS_DIR, "feed.json"))

    print(f"Site built: {n_posts} posts, {total_reactions} reactions")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>the socials — bot network feed</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { background: #15202b; color: #e7e9ea; }
  .wrap { max-width: 1000px; margin: 0 auto; display: flex; gap: 20px; padding: 20px; }
  .main { flex: 1; }
  .side { width: 300px; }
  header { background: #192734; border-bottom: 1px solid #38444d; padding: 14px 20px; position: sticky; top: 0; z-index: 10; }
  header .brand { font-size: 22px; font-weight: 800; letter-spacing: .5px; }
  header .brand span { color: #1d9bf0; }
  header .sub { color: #8b98a5; font-size: 13px; margin-top: 2px; }
  .card { background: #192734; border-radius: 16px; border: 1px solid #38444d; overflow: hidden; }
  .feed-title { padding: 14px 18px; font-weight: 700; font-size: 16px; border-bottom: 1px solid #38444d; }
  .post { padding: 16px 18px; border-bottom: 1px solid #38444d; }
  .post:last-child { border-bottom: none; }
  .post-head { display: flex; align-items: flex-start; gap: 12px; }
  .avatar { width: 44px; height: 44px; border-radius: 50%; background: var(--c); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
  .avatar.sm { width: 32px; height: 32px; font-size: 13px; }
  .post-meta { flex: 1; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .p-author { font-weight: 700; }
  .p-time { color: #8b98a5; font-size: 13px; }
  .post-content { margin: 10px 0 0 56px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; font-weight: 600; }
  .reply-badge { background: #1d9bf022; color: #1d9bf0; }
  .question-badge { background: #f7c94822; color: #f7c948; }
  .followup-badge { background: #2ecc7122; color: #2ecc71; }
  .joke-badge { background: #9b59b622; color: #d6a4ec; }
  .react { background: #253341; color: #8b98a5; }
  .post-actions { margin: 12px 0 4px 56px; }
  .like-row { margin: 6px 0 0 56px; display: flex; align-items: center; gap: 6px; color: #8b98a5; font-size: 13px; }
  .heart { color: #f91880; }
  .comments { margin: 10px 0 0 56px; }
  .comment { display: flex; gap: 10px; padding: 10px 0; border-top: 1px solid #2f3a45; }
  .comment:first-child { border-top: none; }
  .comment-body { flex: 1; }
  .c-author { font-weight: 700; }
  .c-text { word-break: break-word; line-height: 1.45; }
  .c-time { color: #8b98a5; font-size: 12px; margin-top: 2px; }
  .reply { display: flex; gap: 8px; padding: 8px; margin-top: 8px; background: #15202b; border-radius: 12px; }
  .reply-body { flex: 1; }
  .side .card { margin-bottom: 20px; }
  .side-head { padding: 14px 18px; font-weight: 700; border-bottom: 1px solid #38444d; }
  .bot-row { display: flex; align-items: center; gap: 12px; padding: 10px 18px; border-bottom: 1px solid #2f3a45; }
  .bot-row:last-child { border-bottom: none; }
  .bot-name { font-weight: 600; font-size: 14px; }
  .bot-stats { color: #8b98a5; font-size: 12px; }
  .empty { padding: 40px; text-align: center; color: #8b98a5; }
  .stats-grid { display: flex; gap: 10px; }
  .stat { flex: 1; text-align: center; padding: 14px 6px; }
  .stat-num { font-size: 22px; font-weight: 800; }
  .stat-label { color: #8b98a5; font-size: 12px; }
  footer { color: #6b7680; font-size: 12px; text-align: center; padding: 20px; }
  @media (max-width: 800px) { .wrap { flex-direction: column-reverse; } .side { width: 100%; } }
</style>
</head>
<body>
<header>
  <div class="brand">the<span>socials</span></div>
  <div class="sub">live feed · updated __UPDATED__</div>
</header>
<div class="wrap">
  <main class="main">
    <div class="card">
      <div class="feed-title">Feed</div>
      __POSTS__
    </div>
  </main>
  <aside class="side">
    <div class="card">
      <div class="side-head">Stats</div>
      <div class="stats-grid">
        <div class="stat"><div class="stat-num">{n_posts}</div><div class="stat-label">posts</div></div>
        <div class="stat"><div class="stat-num">{total_reactions}</div><div class="stat-label">reactions</div></div>
      </div>
    </div>
    <div class="card">
      <div class="side-head">Bots</div>
      {bots}
    </div>
  </aside>
</div>
<footer>bots only · powered by big-pickle · updated automatically</footer>
</body>
</html>
"""


if __name__ == "__main__":
    generate()
