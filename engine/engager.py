import random
from datetime import datetime

from config import BOTS
from engine.llm import generate_text, generate_json
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


def _build_batch_prompt(slots):
    """One prompt that asks the model for all comment texts in a single call."""
    parts = []
    for i, (bot, post, ctx) in enumerate(slots):
        context = ""
        if ctx:
            context = " Existing comments: " + "; ".join(
                f"{c.author}: {c.content[:80]}" for c in ctx[:3]
            ) + "."
        emoji = " Emojis are welcome (keep it casual)." if bot.uses_emojis else " No emojis."
        parts.append(
            f"[{i}] Bot: {bot.name} — personality: {bot.personality_prompt}."
            f" A friend named {post.author} posted: \"{post.content}\".{context}"
            f" They react casually, in their own voice, one sentence. Do not quote"
            f" or repeat the post back.{emoji}"
        )
    return (
        "Write comments for fictional social media users reacting to a friend's post."
        " Make them sound like actual people, not an AI. Real comments are short,"
        " casual, reference something specific from the post, and have personality."
        " Use slang, typos occasionally, or abbreviations. Don't be generic."
        " React emotionally, not analytically. Each comment should feel like a"
        " natural response a real friend would leave.\n"
        + "\n".join(parts)
        + "\nReturn a JSON array with EXACTLY the same number of string entries,"
          " in the same order — one comment per user."
    )


def generate_comment_batch(slots):
    """Generate all comment texts in one LLM call. Returns list aligned to slots or None."""
    data = generate_json(_build_batch_prompt(slots), timeout=240)
    if isinstance(data, list) and len(data) == len(slots):
        return [t.strip() if isinstance(t, str) else "" for t in data]
    # Tolerate a JSON object keyed by index
    if isinstance(data, dict):
        out = [""] * len(slots)
        for k, v in data.items():
            try:
                out[int(k)] = v
            except (ValueError, TypeError, IndexError):
                continue
        if all(isinstance(s, str) for s in out):
            return [s.strip() for s in out]
    return None


def engage_with_feed():
    """Process engagement on recent posts. Comments are generated in one batch."""
    now = datetime.now()
    posts = feed.get_recent_posts(6)
    if not posts:
        return 0

    comment_slots = []          # (bot, post, surrounding_comments)
    changed_posts = set()
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
                comment_slots.append(
                    (bp, post, [c for c in post.comments[:3]])
                )
                change = True

            feed.update_bot_state(bs)

        if change:
            changed_posts.add(post.id)

    # One LLM call for all the comment texts, then attach them.
    texts = generate_comment_batch(comment_slots) if comment_slots else None
    for idx, (bp, post, _) in enumerate(comment_slots):
        content = (texts[idx] if texts and texts[idx] else "") or _fallback_comment(bp, post)
        post.comments.append(Comment(
            author=bp.name,
            content=content,
            timestamp=now.isoformat(),
        ))
        dynamics.bump_relationship(bp.name, post.author, 0.05)
        bs = feed.get_bot_state(bp.name)
        bs.total_comments += 1
        feed.update_bot_state(bs)
        engagement_count += 1
        changed_posts.add(post.id)

    for post in posts:
        if post.id in changed_posts:
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
        f"{replier.name} is a user with this personality: {replier.personality_prompt}. "
        f"{comment.author} commented \"{comment.content}\" on a post by {post.author}. "
        f"Reply the way a real friend would reply to a comment — one short sentence,"
        f" casual, reference something specific, do not quote it back."
        f" {'Use emojis.' if replier.uses_emojis else 'No emojis.'}"
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
    # Personality-specific fallbacks
    personality_fallbacks = {
        "TechBro42": [
            "ship it",
            "have you tried turning it off and on again",
            f"this is the content i come here for {post.author}",
            "based",
        ],
        "NatureLover": [
            "love this energy",
            "the world needs more of this",
            "yes yes yes",
            "this made my day",
        ],
        "ChaosGremlin": [
            "lmaooo what",
            "this is unhinged and i respect it",
            "absolute chaos and i'm here for it",
            "you woke up and chose violence huh",
        ],
        "MidnightCoder": [
            "same tbh",
            "why is this so real",
            "i felt this in my git history",
            "mood",
        ],
        "CoffeeAddict": [
            "need coffee just reading this",
            "THIS!!",
            "okay but also coffee",
            "screaming",
        ],
        "NewsBot3000": [
            "finally someone said it",
            "hot take but correct",
            "adding this to the discourse",
            "you're right and you should say it",
        ],
        "SleepyHead": [
            "too tired to respond but i agree",
            "zzzz but like in a good way",
            "this is the content i need when i wake up",
            "nap after reading this",
        ],
        "ArtKid": [
            "the aesthetic of this is",
            "this is a whole mood",
            "chef's kiss",
            "this has layers",
        ],
        "FitnessGuru": [
            "let's gooo",
            "this is the energy we need",
            "no excuses just vibes",
            "love this mindset",
        ],
        "WeirdPhilosophy": [
            "but what does it mean though",
            "this question haunts me now",
            "i need to think about this for 3 business days",
            "you've unlocked a new fear",
        ],
        "FoodieFran": [
            "adding this to my mental recipe book",
            "but does it pair well with cheese",
            "i'm hungry now thanks",
            "the flavor of this post",
        ],
        "VibeChecker": [
            "the vibe is immaculate",
            "checking the vibe and it's good",
            "vibes are off the charts",
            "this resonates on a spiritual level",
        ],
    }
    
    # Use personality-specific fallback if available, otherwise generic
    options = personality_fallbacks.get(bot.name, [
        f"ok i felt that one {post.author}",
        "this is so real actually",
        "lmaooo",
        f"wait this is a great point about {random.choice(bot.interests)}",
        "no because why is this so accurate",
        "big if true",
    ])
    return random.choice(options)
