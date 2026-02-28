"""Tests for ``bbdsl registry publish/search/install`` CLI commands.

All HTTP interactions are mocked so these tests don't require a running
platform server.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bbdsl.cli.main import cli
from bbdsl.cli.registry_client import RegistryClient, RegistryError


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def sample_yaml(tmp_path: Path) -> Path:
    content = (
        "bbdsl_version: '0.3'\n"
        "system:\n"
        "  name: Test\n"
        "  authors:\n"
        "    - name: Tester\n"
        "openings: []\n"
    )
    p = tmp_path / "test.bbdsl.yaml"
    p.write_text(content, encoding="utf-8")
    return p


MOCK_PUBLISH_RESPONSE = {
    "id": 42,
    "name": "Test Convention",
    "namespace": "test/conv",
    "version": "1.0.0",
    "description": "A test",
    "tags": "test,demo",
    "author_name": "Tester",
    "yaml_content": "openings: []\n",
    "downloads": 0,
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z",
}

MOCK_SEARCH_RESPONSE = {
    "items": [
        {
            "id": 42,
            "name": "Precision Club",
            "namespace": "precision",
            "version": "1.0.0",
            "description": "Standard Precision",
            "tags": "precision,club",
            "author_name": "Alice",
            "downloads": 10,
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "id": 43,
            "name": "SAYC",
            "namespace": "sayc",
            "version": "2.0.0",
            "description": "Standard American",
            "tags": "natural",
            "author_name": "Bob",
            "downloads": 25,
            "created_at": "2025-01-02T00:00:00Z",
        },
    ],
    "total": 2,
    "page": 1,
    "page_size": 20,
}

MOCK_INSTALL_RESPONSE = {
    "id": 42,
    "name": "Precision Club",
    "namespace": "precision",
    "version": "1.0.0",
    "yaml_content": "bbdsl_version: '0.3'\nsystem:\n  name: Precision\n",
}


# ── Publish Tests ───────────────────────────────────────────


class TestRegistryPublish:
    """Tests for ``bbdsl registry publish``."""

    def test_publish_success(
        self, runner: CliRunner, sample_yaml: Path
    ) -> None:
        with patch.object(
            RegistryClient, "publish", return_value=MOCK_PUBLISH_RESPONSE
        ) as mock_pub:
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "fake-token",
                    "publish",
                    str(sample_yaml),
                    "--name", "Test Convention",
                    "--namespace", "test/conv",
                    "--version", "1.0.0",
                    "--description", "A test",
                    "--tags", "test,demo",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Published" in result.output
        assert "Test Convention" in result.output
        assert "test/conv" in result.output
        mock_pub.assert_called_once()

    def test_publish_missing_required_options(
        self, runner: CliRunner, sample_yaml: Path
    ) -> None:
        """Omitting --name or --namespace causes a Click error."""
        result = runner.invoke(
            cli,
            [
                "registry",
                "--token", "fake-token",
                "publish",
                str(sample_yaml),
                # missing --name and --namespace
            ],
        )
        assert result.exit_code != 0

    def test_publish_api_error(
        self, runner: CliRunner, sample_yaml: Path
    ) -> None:
        with patch.object(
            RegistryClient,
            "publish",
            side_effect=RegistryError("HTTP 422: validation failed"),
        ):
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "publish",
                    str(sample_yaml),
                    "--name", "Bad",
                    "--namespace", "x",
                ],
            )
        assert result.exit_code != 0
        assert "422" in result.output


# ── Search Tests ────────────────────────────────────────────


class TestRegistrySearch:
    """Tests for ``bbdsl registry search``."""

    def test_search_table_output(self, runner: CliRunner) -> None:
        with patch.object(
            RegistryClient, "search", return_value=MOCK_SEARCH_RESPONSE
        ):
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "search",
                    "--query", "precision",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Precision Club" in result.output
        assert "SAYC" in result.output
        assert "Found 2" in result.output

    def test_search_json_output(self, runner: CliRunner) -> None:
        with patch.object(
            RegistryClient, "search", return_value=MOCK_SEARCH_RESPONSE
        ):
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "search",
                    "--query", "precision",
                    "--json",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_search_no_results(self, runner: CliRunner) -> None:
        empty = {"items": [], "total": 0, "page": 1, "page_size": 20}
        with patch.object(
            RegistryClient, "search", return_value=empty
        ):
            result = runner.invoke(
                cli,
                ["registry", "--token", "t", "search", "-q", "nonexistent"],
            )

        assert result.exit_code == 0
        assert "No conventions found" in result.output

    def test_search_api_error(self, runner: CliRunner) -> None:
        with patch.object(
            RegistryClient,
            "search",
            side_effect=RegistryError("HTTP 500: server error"),
        ):
            result = runner.invoke(
                cli,
                ["registry", "--token", "t", "search", "-q", "x"],
            )
        assert result.exit_code != 0


# ── Install Tests ───────────────────────────────────────────


class TestRegistryInstall:
    """Tests for ``bbdsl registry install``."""

    def test_install_default_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        with (
            patch.object(
                RegistryClient, "install", return_value=MOCK_INSTALL_RESPONSE
            ),
            runner.isolated_filesystem(temp_dir=tmp_path),
        ):
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "install",
                    "precision",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Installed" in result.output
        assert "precision.bbdsl.yaml" in result.output

    def test_install_specific_version(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        with patch.object(
            RegistryClient, "install", return_value=MOCK_INSTALL_RESPONSE
        ) as mock_inst:
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "install",
                    "precision",
                    "--version", "1.0.0",
                    "--output", str(tmp_path / "out.yaml"),
                ],
            )

        assert result.exit_code == 0, result.output
        assert (tmp_path / "out.yaml").exists()
        mock_inst.assert_called_once_with("precision", version="1.0.0")

    def test_install_custom_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out_file = tmp_path / "subdir" / "my.yaml"
        with patch.object(
            RegistryClient, "install", return_value=MOCK_INSTALL_RESPONSE
        ):
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "install",
                    "precision",
                    "-o", str(out_file),
                ],
            )

        assert result.exit_code == 0, result.output
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "Precision" in content

    def test_install_api_error(self, runner: CliRunner) -> None:
        with patch.object(
            RegistryClient,
            "install",
            side_effect=RegistryError("HTTP 404: not found"),
        ):
            result = runner.invoke(
                cli,
                ["registry", "--token", "t", "install", "nope"],
            )
        assert result.exit_code != 0
        assert "404" in result.output

    def test_install_empty_yaml_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        empty_resp = {**MOCK_INSTALL_RESPONSE, "yaml_content": ""}
        with patch.object(
            RegistryClient, "install", return_value=empty_resp
        ):
            result = runner.invoke(
                cli,
                [
                    "registry",
                    "--token", "t",
                    "install",
                    "precision",
                    "-o", str(tmp_path / "out.yaml"),
                ],
            )
        assert result.exit_code != 0
        assert "empty" in result.output.lower()


# ── RegistryClient Unit Tests ──────────────────────────────


class TestRegistryClient:
    """Unit tests for RegistryClient methods."""

    def test_raise_for_status_success(self) -> None:
        resp = MagicMock()
        resp.is_success = True
        RegistryClient._raise_for_status(resp)  # should not raise

    def test_raise_for_status_error(self) -> None:
        resp = MagicMock()
        resp.is_success = False
        resp.status_code = 403
        resp.json.return_value = {"detail": "Forbidden"}
        resp.text = "Forbidden"
        with pytest.raises(RegistryError, match="403"):
            RegistryClient._raise_for_status(resp)

    def test_token_loaded_from_init(self) -> None:
        client = RegistryClient(token="my-token")
        assert client.token == "my-token"

    def test_headers_with_token(self) -> None:
        client = RegistryClient(token="my-token")
        h = client._headers()
        assert h["Authorization"] == "Bearer my-token"

    def test_headers_without_token(self) -> None:
        client = RegistryClient(token=None)
        # Override post_init token loading
        client.token = None
        h = client._headers()
        assert "Authorization" not in h
