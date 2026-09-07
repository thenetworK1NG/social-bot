import random
import re
from datetime import datetime, timedelta

from config import BOTS, TOPICS, drama_topics
from engine.llm import generate_text
from social import feed
from social import dynamics
from social.models import Post
from engine.scheduler import is_bot_active

_STOP = frozenset(
    "i me my you he she it we they am is are was were be been being have has had "
    "do does did will shall may can could would should might must need a an the "
    "and or but if then so for of to in on at by with from up about into over after "
    "that this these those what which who whom when where how why all any both each "
    "few more most other some such no nor not only own same than just don now ok like "
    "tbh honestly basically actually also really very much today way kind something "
    "thing things dont wanna gonna imo idk smh ngl lol lmao bruh bro nah yeah yall lol"
    .split()
)


def _keywords(text):
    return [w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in _STOP]


def _too_similar(content, recent_posts):
    new_kw = set(_keywords(content))
    if not new_kw:
        return False
    for p in recent_posts[:5]:
        old_kw = set(_keywords(p.content if hasattr(p, "content") else ""))
        if old_kw and len(new_kw & old_kw) >= 0.4 * len(new_kw):
            return True
    return False


def _recent_topic_hint(recent_posts):
    """Summarise recent topics so the prompt can explicitly avoid them."""
    if not recent_posts:
        return ""
    snippets = [(p.content if hasattr(p, "content") else "")[:70] for p in recent_posts[:4]]
    return "\nRecent posts already covered: " + " | ".join(f"\"{s}\"" for s in snippets if s) + "."


def pick_bot_to_post():
    """Pick a bot weighted by their posting frequency and activity."""
    now = datetime.now()
    candidates = [b for b in BOTS if is_bot_active(b, now)]
    if not candidates:
        candidates = BOTS
    weights = [b.posting_frequency for b in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def decide_post_type(bot, recent_posts, state):
    """Decide what kind of post this is."""
    has_running_jokes = bool(dynamics.get_running_jokes())
    options = ["normal", "normal", "question", "normal", "normal"]
    # Occasionally reply to another bot's post
    if recent_posts and random.random() < 0.25 and bot.reply_to_others:
        return "reply"
    # Occasionally follow up own past post if it blew up
    own = [p for p in recent_posts if p.author == bot.name]
    if own and len(own[0].likes) >= 3:
        options.append("followup")
    # Occasionally reference a running joke
    if has_running_jokes and random.random() < 0.15:
        options.append("joke_reference")
    return random.choice(options)


def build_post_prompt(bot, post_type, recent_posts, now_str):
    if post_type == "reply":
        target = random.choice([p for p in recent_posts if p.author != bot.name])
        return (
            f"{bot.name} is a user whose bio is: {bot.bio}. Personality: {bot.personality_prompt}. "
            f"Current time: {now_str}. "
            f"A friend named {target.author} posted: \"{target.content}\". "
            f"Make a casual short reply to what they said, in your own voice (1 sentence). "
            f"Do not quote or repeat their post. Say something that continues the conversation."
            f"{' Emojis welcome.' if bot.uses_emojis else ' No emojis.'}"
        )
    if post_type == "question":
        return (
            f"{bot.name} is a user whose bio is: {bot.bio}. Personality: {bot.personality_prompt}. "
            f"Current time: {now_str}. "
            f"Ask your followers a genuine casual question ({random.choice(drama_topics)} related or daily life). "
            f"Pick a fresh angle — do not repeat recent themes. One sentence, sounds like a real person reaching out."
            + _recent_topic_hint(recent_posts)
            + f"{' Emojis welcome.' if bot.uses_emojis else ' No emojis.'}"
        )
    if post_type == "followup":
        own = [p for p in recent_posts if p.author == bot.name][0]
        return (
            f"{bot.name} has personality: {bot.personality_prompt}. Current time: {now_str}. "
            f"Your earlier post \"{own.content}\" got a lot of engagement. "
            f"Make a short follow-up comment about the response, casually, in your own voice (1 sentence)."
            f"{' Emojis welcome.' if bot.uses_emojis else ' No emojis.'}"
        )
    if post_type == "joke_reference":
        joke = random.choice(dynamics.get_running_jokes())
        return (
            f"{bot.name} has personality: {bot.personality_prompt}. Current time: {now_str}. "
            f"There's an inside joke on this platform: {joke}. "
            f"Make a short casual post referencing it (1 sentence)."
            f"{' Emojis welcome.' if bot.uses_emojis else ' No emojis.'}"
        )
    topic = random.choice(bot.interests + TOPICS)
    return (
        f"{bot.name} is a user whose bio is: {bot.bio}. Personality: {bot.personality_prompt}. "
        f"Current time: {now_str}. "
        f"Write a single natural social media post about {topic} (1-2 sentences). "
        f"Casual, authentic, sometimes imperfect — like a real person typing. No hashtags."
        + _recent_topic_hint(recent_posts)
        + f"{' Emojis welcome.' if bot.uses_emojis else ' No emojis.'}"
    )


def create_post():
    now = datetime.now()
    now_str = now.strftime("%A %I:%M %p")
    bot = pick_bot_to_post()
    recent_posts = feed.get_recent_posts(5)
    post_type = decide_post_type(bot, recent_posts, feed.load_state())
    prompt = build_post_prompt(bot, post_type, recent_posts, now_str)

    content = None
    for attempt in range(3):
        extra = ""
        if attempt > 0:
            extra = (
                _recent_topic_hint(recent_posts)
                + " That topic was already used — write about something completely different."
            )
        candidate = generate_text(prompt + extra)
        if candidate and not _too_similar(candidate, recent_posts):
            content = candidate
            break
    if not content:
        content = _fallback_post(bot)

    post = Post(
        author=bot.name,
        content=content,
        timestamp=now.isoformat(),
        post_type=post_type,
    )
    feed.add_post(post)
    bs = feed.get_bot_state(bot.name)
    bs.total_posts += 1
    bs.last_posted = now.isoformat()
    feed.update_bot_state(bs)
    return post


def _fallback_post(bot):
    """If LLM fails, use templated filler so the loop keeps running."""
    templates = [
        f"honestly the way {random.choice(bot.interests)} has me feeling some kind of way today",
        f"no thoughts just {random.choice(TOPICS)}",
        "ok so that just happened",
        f"shower thought about {random.choice(bot.interests)}: wild",
        "not today brain. not today.",
    ]
    return random.choice(templates)
