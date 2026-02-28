"""HTTP client for the BBDSL Platform Registry API.

This module provides a thin synchronous wrapper around the bbdsl-platform
REST API, used by the ``bbdsl registry`` CLI commands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# Default platform URL (can be overridden via --api-url or BBDSL_API_URL)
DEFAULT_API_URL = "http://localhost:8000/api/v1"

# Token config file path
_TOKEN_FILE = Path.home() / ".bbdsl" / "token"


def _load_token() -> str | None:
    """Read a saved API token from ~/.bbdsl/token."""
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text(encoding="utf-8").strip() or None
    return None


def _save_token(token: str) -> None:
    """Persist an API token to ~/.bbdsl/token."""
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token + "\n", encoding="utf-8")


@dataclass
class RegistryClient:
    """Synchronous REST client for the BBDSL Platform Registry."""

    api_url: str = DEFAULT_API_URL
    token: str | None = field(default=None)

    def __post_init__(self) -> None:
        if self.token is None:
            self.token = _load_token()

    # ── helpers ──────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.api_url.rstrip('/')}{path}"

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        """Raise a descriptive error on non-2xx responses."""
        if resp.is_success:
            return
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        if isinstance(detail, dict):
            detail = json.dumps(detail, ensure_ascii=False, indent=2)
        raise RegistryError(
            f"HTTP {resp.status_code}: {detail}"
        )

    # ── publish (POST /conventions) ─────────────────────────

    def publish(
        self,
        *,
        name: str,
        namespace: str,
        version: str,
        yaml_content: str,
        description: str | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """Upload a convention to the registry.

        The server automatically validates the YAML content; if
        validation fails the upload is rejected.
        """
        body = {
            "name": name,
            "namespace": namespace,
            "version": version,
            "yaml_content": yaml_content,
        }
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags

        resp = httpx.post(
            self._url("/conventions"),
            headers=self._headers(),
            json=body,
            timeout=30.0,
        )
        self._raise_for_status(resp)
        return resp.json()

    # ── search (GET /conventions) ───────────────────────────

    def search(
        self,
        *,
        query: str | None = None,
        tag: str | None = None,
        namespace: str | None = None,
        author: str | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Search the convention registry."""
        params: dict[str, str | int] = {
            "sort": sort,
            "page": page,
            "page_size": page_size,
        }
        if query:
            params["q"] = query
        if tag:
            params["tag"] = tag
        if namespace:
            params["namespace"] = namespace
        if author:
            params["author"] = author

        resp = httpx.get(
            self._url("/conventions"),
            headers=self._headers(),
            params=params,
            timeout=15.0,
        )
        self._raise_for_status(resp)
        return resp.json()

    # ── install (GET /conventions/ns/{ns}/{ver} + download) ─

    def install(
        self,
        namespace: str,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Download a convention by namespace (+ optional version).

        If *version* is ``None``, fetches the latest version.
        Also increments the download counter on the server.
        """
        if version:
            path = f"/conventions/ns/{namespace}/{version}"
        else:
            # Latest: search by namespace, take first result
            search_result = self.search(
                namespace=namespace, sort="newest", page_size=1
            )
            items = search_result.get("items", [])
            if not items:
                raise RegistryError(
                    f"No convention found for namespace '{namespace}'"
                )
            conv_id = items[0]["id"]
            # Record download
            resp = httpx.post(
                self._url(f"/conventions/{conv_id}/download"),
                headers=self._headers(),
                timeout=15.0,
            )
            self._raise_for_status(resp)
            return resp.json()

        resp = httpx.get(
            self._url(path),
            headers=self._headers(),
            timeout=15.0,
        )
        self._raise_for_status(resp)
        data = resp.json()
        # Also record download
        conv_id = data.get("id")
        if conv_id:
            try:
                httpx.post(
                    self._url(f"/conventions/{conv_id}/download"),
                    headers=self._headers(),
                    timeout=10.0,
                )
            except Exception:
                pass  # download counter is best-effort
        return data


class RegistryError(Exception):
    """Raised when a registry API call fails."""
