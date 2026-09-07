import random
from datetime import datetime

from config import BOTS
from engine.llm import generate_text
from social import feed
from social import dynamics
from social.models import Comment
from engine.scheduler import is_bot_active


def _like_rate_drift(bs):
    """Bots that like a lot keep liking; generous likers exist."""
    return bs.total_likes_given * 0.001 if bs.total_likes_given else 0.0


def decide_engagement(post, bot_list):
    """Return list of (bot, action) where action in {like, comment, both, none}."""
    actions = []
    author = post.author
    now = datetime.now()

    for bp in bot_list:
        if bp.name == author:
            continue
        bs = feed.get_bot_state(bp.name)
        # personality-based base rates plus relationship influence
        rel = dynamics.relationship_score(bp.name, author)
        base_like = bp.like_rate + max(0, rel) * 0.2 + _like_rate_drift(bs)
        base_comment = bp.comment_rate + max(0, rel) * 0.15

        like_roll = random.random() < min(0.95, base_like)
        comment_roll = random.random() < min(0.85, base_comment)

        # active bots engage more; sleeping bots rarely engage
        if not is_bot_active(bp, now) and random.random() > 0.25:
            comment_roll = False
            like_roll = like_roll and random.random() < 0.3

        if like_roll and comment_roll:
            actions.append((bp, "both"))
        elif like_roll:
            actions.append((bp, "like"))
        elif comment_roll:
            actions.append((bp, "comment"))

    # Limit how many engage per cycle to look realistic
    max_engagers = 4
    return actions[:max_engagers]


def build_comment_prompt(bot, post, surrounding_comments):
    ctx = ""
    if surrounding_comments:
        others = "; ".join(f"{c.author}: {c.content}" for c in surrounding_comments)
        ctx = f"Existing comments on this post: {others}\n"
    return (
        f"You are {bot.name}, a user on a social media platform. "
        f"Bio: {bot.bio}. Personality: {bot.personality_prompt}. "
        f"{bot.name} posted previously: \"{post.author}\" wrote: \"{post.content}\".\n"
        f"{ctx}"
        f"Write a short natural comment replying to {post.author}'s post. 1-2 sentences. "
        f"Be casual, react to what they actually said, stay in character. "
        f"{'You love using emojis.' if bot.uses_emojis else 'Do not use emojis.'} "
        f"Do NOT use hashtags. Output ONLY the raw comment text with zero preamble, no quotes, no labels, no explanation."
    )


def engage_with_feed():
    """Process engagement on recent posts."""
    now = datetime.now()
    posts = feed.get_recent_posts(6)
    if not posts:
        return 0

    engagement_count = 0
    for post in posts:
        if random.random() > 0.7:
            continue
        actions = decide_engagement(post, BOTS)
        if not actions:
            continue

        change = False
        existing_commenters = [c.author for c in post.comments]
        for bp, action in actions:
            should_like = "like" in action and bp.name not in post.likes
            should_comment = "comment" in action and bp.name not in existing_commenters

            bs = feed.get_bot_state(bp.name)

            if should_like:
                post.likes.append(bp.name)
                bs.total_likes_given += 1
                dynamics.bump_relationship(bp.name, post.author, 0.02)
                change = True

            if should_comment:
                surrounding = [c for c in post.comments[:3]]
                prompt = build_comment_prompt(bp, post, surrounding)
                content = generate_text(prompt)
                if not content:
                    content = _fallback_comment(bp, post)
                comment = Comment(
                    author=bp.name,
                    content=content,
                    timestamp=now.isoformat(),
                )
                post.comments.append(comment)
                dynamics.bump_relationship(bp.name, post.author, 0.05)
                bs.total_comments += 1
                engagement_count += 1
                change = True

            feed.update_bot_state(bs)

        if change:
            feed.update_post(post)

    # Occasionally add reply threads to the most recent comment
    if posts and random.random() < 0.4:
        _maybe_extend_thread(posts[0])

    return engagement_count


def _maybe_extend_thread(post):
    """Add a 1-2 level reply chain to a comment."""
    if not post.comments:
        return
    comment = random.choice(post.comments)
    thread = dynamics.get_thread(post.id)
    chain = thread.get("chain", [comment.author])
    last_author = chain[-1] if chain else comment.author

    # pick a replier (not the original author, not same as last)
    candidates = [b for b in BOTS if b.name != last_author and b.name != comment.author]
    if not candidates:
        return
    replier = random.choice(candidates)
    prompt = (
        f"You are {replier.name}, a user on a social media platform. "
        f"Personality: {replier.personality_prompt}. "
        f"{comment.author} commented \"{comment.content}\" on a post by {post.author}. "
        f"Write a short natural reply to {comment.author}'s comment. 1 sentence. "
        f"Stay in character. {'' if replier.uses_emojis else 'Do not use emojis.'} "
        f"Output ONLY the raw reply text with zero preamble, no quotes, no labels, no explanation."
    )
    reply_content = generate_text(prompt)
    if not reply_content:
        return
    comment.replies.append({
        "author": replier.name,
        "content": reply_content,
        "timestamp": datetime.now().isoformat(),
    })
    chain = chain + [replier.name]
    dynamics.mark_recent_thread(post.id, chain)
    dynamics.bump_relationship(replier.name, comment.author, 0.05)
    feed.update_post(post)


def _fallback_comment(bot, post):
    templates = [
        f"ok i felt that one {post.author}",
        "this is so real actually",
        "lmaooo",
        f"wait this is a great point about {random.choice(bot.interests)}",
        "no because why is this so accurate",
        "big if true",
    ]
    return random.choice(templates)
