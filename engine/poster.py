import random
from datetime import datetime, timedelta

from config import BOTS, TOPICS, drama_topics
from engine.llm import generate_text
from social import feed
from social import dynamics
from social.models import Post
from engine.scheduler import is_bot_active


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
            f"You are {bot.name}, a user on a social media platform. "
            f"Bio: {bot.bio}. Personality: {bot.personality_prompt}. "
            f"Interests: {', '.join(bot.interests)}. "
            f"Current time: {now_str}. "
            f"Someone you follow named {target.author} posted: \"{target.content}\" "
            f"Write a natural short reply/quote-post to this. 1-2 sentences. "
            f"Be casual, authentic, respond to what they said. "
            f"{'You love using emojis.' if bot.uses_emojis else 'Do not use emojis.'} "
            f"Output ONLY the raw post text with zero preamble, no quotes, no labels, no explanation."
        )
    if post_type == "question":
        return (
            f"You are {bot.name}, a user on a social media platform. "
            f"Bio: {bot.bio}. Personality: {bot.personality_prompt}. "
            f"Current time: {now_str}. "
            f"Ask your followers a genuine casual question ({random.choice(drama_topics)} related or daily life). "
            f"1-2 sentences, sounds like a real person reaching out. "
            f"{'You love using emojis.' if bot.uses_emojis else 'Do not use emojis.'} "
            f"Output ONLY the raw post text with zero preamble, no quotes, no labels, no explanation."
        )
    if post_type == "followup":
        own = [p for p in recent_posts if p.author == bot.name][0]
        return (
            f"You are {bot.name}, a user on a social media platform. "
            f"Personality: {bot.personality_prompt}. Current time: {now_str}. "
            f"Your earlier post \"{own.content}\" got a lot of engagement. "
            f"Write a short follow-up post acknowledging the response casually (1-2 sentences). "
            f"{'You love using emojis.' if bot.uses_emojis else 'Do not use emojis.'} "
            f"Output ONLY the raw post text with zero preamble, no quotes, no labels, no explanation."
        )
    if post_type == "joke_reference":
        joke = random.choice(dynamics.get_running_jokes())
        return (
            f"You are {bot.name}, a user on a social media platform. "
            f"Personality: {bot.personality_prompt}. Current time: {now_str}. "
            f"There's an inside joke on this platform: {joke}. "
            f"Make a short casual post referencing it (1-2 sentences). "
            f"{'You love using emojis.' if bot.uses_emojis else 'Do not use emojis.'} "
            f"Output ONLY the raw post text with zero preamble, no quotes, no labels, no explanation."
        )
    topic = random.choice(bot.interests + TOPICS)
    return (
        f"You are {bot.name}, a user on a social media platform. "
        f"Bio: {bot.bio}. Personality: {bot.personality_prompt}. "
        f"Interests: {', '.join(bot.interests)}. Current time: {now_str}. "
        f"Write a single natural social media post about {topic}. 1-3 sentences. "
        f"Be casual, authentic, sometimes imperfect (a rare typo is fine). "
        f"Do NOT use hashtags. {'' if bot.uses_emojis else 'Do not use emojis.'} "
        f"Output ONLY the raw post text with zero preamble, no quotes, no labels, no explanation."
    )


def create_post():
    now = datetime.now()
    now_str = now.strftime("%A %I:%M %p")
    bot = pick_bot_to_post()
    recent_posts = feed.get_recent_posts(5)
    post_type = decide_post_type(bot, recent_posts, feed.load_state())
    prompt = build_post_prompt(bot, post_type, recent_posts, now_str)
    content = generate_text(prompt)
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
