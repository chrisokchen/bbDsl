"""YAML loader: read BBDSL YAML files into Pydantic models."""

from __future__ import annotations

import io
import json
from pathlib import Path

from ruamel.yaml import YAML

from bbdsl.models.system import BBDSLDocument


def load_yaml(path: str | Path) -> dict:
    """Read a YAML file and return raw dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    yaml = YAML(typ="safe")
    with open(path, encoding="utf-8") as f:
        data = yaml.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected YAML mapping at top level, got {type(data).__name__}"
        )
    return data


def load_yaml_from_string(content: str) -> dict:
    """Parse a YAML string and return raw dict.

    Args:
        content: YAML text content.

    Returns:
        Parsed dict.

    Raises:
        ValueError: If the content is not a YAML mapping.
    """
    yaml = YAML(typ="safe")
    data = yaml.load(io.StringIO(content))
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected YAML mapping at top level, got {type(data).__name__}"
        )
    return data


def load_document(path: str | Path) -> BBDSLDocument:
    """Load a BBDSL YAML file into a validated BBDSLDocument."""
    data = load_yaml(path)
    return BBDSLDocument.model_validate(data)


def load_document_from_string(content: str) -> BBDSLDocument:
    """Load a BBDSL YAML string into a validated BBDSLDocument.

    This is useful for platform/API usage where YAML content
    is received as a string rather than a file path.

    Args:
        content: YAML text content of a BBDSL document.

    Returns:
        Validated BBDSLDocument instance.
    """
    data = load_yaml_from_string(content)
    return BBDSLDocument.model_validate(data)


def print_summary(doc: BBDSLDocument) -> None:
    """Print a human-readable summary of a loaded document."""
    name = doc.system.name
    if isinstance(name, dict):
        name = name.get("en") or name.get("zh-TW") or next(iter(name.values()))

    print(f"System: {name}")
    if doc.system.version:
        print(f"Version: {doc.system.version}")
    if doc.system.authors:
        authors = ", ".join(a.name for a in doc.system.authors)
        print(f"Authors: {authors}")

    print(f"Openings: {len(doc.openings)}")
    if doc.conventions:
        print(f"Conventions: {len(doc.conventions)}")
    if doc.definitions and doc.definitions.patterns:
        print(f"Patterns: {len(doc.definitions.patterns)}")
    if doc.system.completeness:
        fields = doc.system.completeness.model_dump(exclude_none=True)
        if fields:
            status = ", ".join(f"{k}={v}" for k, v in fields.items())
            print(f"Completeness: {status}")


def generate_json_schema(output_path: str | Path | None = None) -> dict:
    """Generate JSON Schema from the BBDSLDocument Pydantic model."""
    schema = BBDSLDocument.model_json_schema()
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
    return schema
