"""File storage: local disk for development, Supabase Storage in production."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.config import Settings, get_settings


class Storage(Protocol):
    def save(self, path: str, data: bytes, content_type: str) -> str: ...
    def load(self, path: str) -> bytes: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        full = (self.root / path).resolve()
        if self.root not in full.parents:
            raise ValueError("invalid storage path")
        return full

    def save(self, path: str, data: bytes, content_type: str) -> str:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp = full.with_suffix(full.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, full)
        return path

    def load(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()


class SupabaseStorage:
    def __init__(self, settings: Settings) -> None:
        if not (settings.supabase_url and settings.supabase_service_key):
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for Supabase storage")
        self.base = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}"
        self.headers = {"Authorization": f"Bearer {settings.supabase_service_key}", "apikey": settings.supabase_service_key}

    def save(self, path: str, data: bytes, content_type: str) -> str:
        import httpx

        r = httpx.post(f"{self.base}/{path}", content=data, headers={**self.headers, "Content-Type": content_type,
                                                                       "x-upsert": "true"}, timeout=30)
        r.raise_for_status()
        return path

    def load(self, path: str) -> bytes:
        import httpx

        r = httpx.get(f"{self.base}/{path}", headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.content


def get_storage(settings: Settings | None = None) -> Storage:
    s = settings or get_settings()
    if s.storage_backend == "supabase":
        return SupabaseStorage(s)
    return LocalStorage(s.local_storage_dir)
