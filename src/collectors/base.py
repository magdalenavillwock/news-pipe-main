# src/collectors/base.py
from abc import ABC, abstractmethod

import httpx

from src.models import Article


class BaseCollector(ABC):
    def __init__(self, source_config: dict, settings: dict):
        self.config = source_config
        self.settings = settings

    @property
    def name(self) -> str:
        return self.config["name"]

    @property
    def category(self) -> str:
        return self.config["category"]

    @property
    def priority(self) -> str:
        return self.config.get("priority", "medium")

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        ...
