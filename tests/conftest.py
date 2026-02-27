"""Shared pytest fixtures for BBDSL tests."""

from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES_DIR
