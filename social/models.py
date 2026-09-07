from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Comment:
    author: str
    content: str
    timestamp: str
    replies: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": str(uuid.uuid4())[:8],
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp,
            "replies": self.replies,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            author=d.get("author", ""),
            content=d.get("content", ""),
            timestamp=d.get("timestamp", ""),
            replies=d.get("replies", []),
        )


@dataclass
class Post:
    author: str
    content: str
    timestamp: str
    post_type: str = "normal"
    likes: List[str] = field(default_factory=list)
    comments: List[Any] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def to_dict(self):
        return {
            "id": self.id,
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp,
            "post_type": self.post_type,
            "likes": self.likes,
            "comments": [c.to_dict() for c in self.comments],
        }

    @classmethod
    def from_dict(cls, d):
        p = cls(
            id=d.get("id", str(uuid.uuid4())[:12]),
            author=d["author"],
            content=d["content"],
            timestamp=d.get("timestamp", ""),
            post_type=d.get("post_type", "normal"),
            likes=d.get("likes", []),
            comments=[Comment.from_dict(c) for c in d.get("comments", [])],
        )
        return p


@dataclass
class BotState:
    name: str
    last_posted: Optional[str] = None
    total_posts: int = 0
    total_likes_given: int = 0
    total_comments: int = 0
    relationships: Dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        return {
            "name": self.name,
            "last_posted": self.last_posted,
            "total_posts": self.total_posts,
            "total_likes_given": self.total_likes_given,
            "total_comments": self.total_comments,
            "relationships": self.relationships,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d.get("name", ""),
            last_posted=d.get("last_posted"),
            total_posts=d.get("total_posts", 0),
            total_likes_given=d.get("total_likes_given", 0),
            total_comments=d.get("total_comments", 0),
            relationships=d.get("relationships", {}),
        )
