"""
models/image_metadata.py — Canonical data model for an image record.

Keeping the model separate from persistence lets us swap storage backends
without touching handler logic.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class ImageMetadata:
    user_id: str
    filename: str
    content_type: str
    s3_key: str
    size_bytes: int
    tag: str = ""
    description: str = ""
    image_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    uploaded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Denormalized list stored as a JSON string in DynamoDB (simple approach)
    tags: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    #  Serialization helpers
    # ------------------------------------------------------------------ #

    def to_item(self) -> dict:
        """Convert to a DynamoDB-ready dict."""
        d = asdict(self)
        # DynamoDB GSI key — store first tag for the tag-GSI
        d["tag"] = self.tags[0] if self.tags else "__none__"
        return d

    @classmethod
    def from_item(cls, item: dict) -> "ImageMetadata":
        """Hydrate from a DynamoDB item dict."""
        return cls(
            image_id=item["image_id"],
            user_id=item["user_id"],
            filename=item["filename"],
            content_type=item["content_type"],
            s3_key=item["s3_key"],
            size_bytes=int(item.get("size_bytes", 0)),
            tag=item.get("tag", "__none__"),
            description=item.get("description", ""),
            uploaded_at=item.get("uploaded_at", ""),
            tags=item.get("tags", []),
        )

    def to_response_dict(self) -> dict:
        """Safe dict for API responses (no internal fields)."""
        return {
            "image_id":    self.image_id,
            "user_id":     self.user_id,
            "filename":    self.filename,
            "content_type": self.content_type,
            "size_bytes":  self.size_bytes,
            "description": self.description,
            "tags":        self.tags,
            "uploaded_at": self.uploaded_at,
        }
