# src/models.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, date


@dataclass
class Article:
    title: str
    url: str
    source: str
    category: str
    published: datetime
    summary: str | None
    content: str | None
    priority: str = "medium"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Article:
        return cls(
            title=d["title"],
            url=d["url"],
            source=d["source"],
            category=d["category"],
            published=datetime.fromisoformat(d["published"]),
            summary=d.get("summary"),
            content=d.get("content"),
            priority=d.get("priority", "medium"),
        )


@dataclass
class DigestResult:
    date: date
    subscription_id: str
    subscription_name: str
    articles: list[Article]
    digest_markdown: str
    top3_summary: str
    notification_summary: str = ""
    digest_type: str = "daily"
