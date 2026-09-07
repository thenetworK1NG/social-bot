from social import feed
posts = feed.load_feed()
before = len(posts)
posts = [p for p in posts if "The notes skill" not in p.content and "I'll just output the post" not in p.content]
feed.save_feed(posts)
print("removed", before - len(posts), "polluted post(s); remaining", len(posts))
