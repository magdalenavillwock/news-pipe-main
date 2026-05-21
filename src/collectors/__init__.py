from src.collectors.base import BaseCollector
from src.collectors.rss import RSSCollector
from src.collectors.github import GitHubCollector
from src.collectors.arxiv import ArxivCollector

COLLECTOR_MAP: dict[str, type[BaseCollector]] = {
    "rss": RSSCollector,
    "github_releases": GitHubCollector,
    "github_trending": GitHubCollector,
    "arxiv": ArxivCollector,
}


def build_collectors(sources: dict, settings: dict) -> list[BaseCollector]:
    """Build collectors from a subscription's sources dict and global settings."""
    collectors = []
    for category, source_list in sources.items():
        for source in source_list:
            source_with_category = {**source, "category": category}
            cls = COLLECTOR_MAP[source["type"]]
            collectors.append(cls(source_with_category, settings))
    return collectors
