"""
Topic and tag management.

Stores topics with auto-generated search tags.
Supports add, remove, list, and tag editing.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Topic:
    name: str
    description: str
    tags: list[str] = field(default_factory=list)


def _get_topics_path(data_dir: Path) -> Path:
    return data_dir / "topics.json"


def _load_topics(data_dir: Path) -> list[Topic]:
    path = _get_topics_path(data_dir)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Topic(**t) for t in raw]


def _save_topics(data_dir: Path, topics: list[Topic]):
    path = _get_topics_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(t) for t in topics], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class TopicManager:
    """CRUD operations for topics and their search tags."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.topics = _load_topics(data_dir)

    def add_topic(self, name: str, description: str, tags: list[str]) -> Topic:
        """Add a new topic with tags."""
        # Check duplicate
        for t in self.topics:
            if t.name.lower() == name.lower():
                raise ValueError(f"Topic '{name}' already exists.")

        topic = Topic(name=name, description=description, tags=tags)
        self.topics.append(topic)
        _save_topics(self.data_dir, self.topics)
        return topic

    def remove_topic(self, name: str) -> bool:
        """Remove a topic by name. Returns True if found and removed."""
        before = len(self.topics)
        self.topics = [t for t in self.topics if t.name.lower() != name.lower()]
        if len(self.topics) < before:
            _save_topics(self.data_dir, self.topics)
            return True
        return False

    def list_topics(self) -> list[Topic]:
        """List all topics."""
        return self.topics

    def add_tags(self, topic_name: str, tags: list[str]) -> Topic:
        """Add tags to an existing topic."""
        topic = self._find_topic(topic_name)
        for tag in tags:
            if tag not in topic.tags:
                topic.tags.append(tag)
        _save_topics(self.data_dir, self.topics)
        return topic

    def remove_tags(self, topic_name: str, tags: list[str]) -> Topic:
        """Remove tags from an existing topic."""
        topic = self._find_topic(topic_name)
        topic.tags = [t for t in topic.tags if t not in tags]
        _save_topics(self.data_dir, self.topics)
        return topic

    def get_all_tags(self) -> list[str]:
        """Get all unique tags across all topics."""
        seen = set()
        result = []
        for topic in self.topics:
            for tag in topic.tags:
                if tag not in seen:
                    seen.add(tag)
                    result.append(tag)
        return result

    def _find_topic(self, name: str) -> Topic:
        for t in self.topics:
            if t.name.lower() == name.lower():
                return t
        raise ValueError(f"Topic '{name}' not found.")
