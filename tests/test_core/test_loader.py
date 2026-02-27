"""Tests for bbdsl.core.loader."""

import pytest

from bbdsl.core.loader import generate_json_schema, load_document, load_yaml


class TestLoadYaml:
    def test_load_valid_yaml(self, examples_dir):
        data = load_yaml(examples_dir / "precision.bbdsl.yaml")
        assert isinstance(data, dict)
        assert data["bbdsl"] == "0.3"

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_yaml("nonexistent.yaml")


class TestLoadDocument:
    def test_load_precision(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        assert doc.bbdsl == "0.3"
        assert doc.system.version == "2.0.0"
        assert len(doc.openings) == 9  # 1C, 1D, 1H, 1S, 1NT, 2C, 2D, 2H, 2S

    def test_precision_system_metadata(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        assert doc.system.name["en"] == "Precision Club"
        assert doc.system.name["zh-TW"] == "精準制"
        assert len(doc.system.authors) == 2

    def test_precision_definitions(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        assert "balanced" in doc.definitions.patterns
        assert "hcp" in doc.definitions.strength_methods
        assert "good" in doc.definitions.suit_qualities

    def test_precision_conventions(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        assert "stayman" in doc.conventions
        assert "jacoby_transfer" in doc.conventions
        assert doc.conventions["stayman"].id == "bbdsl/stayman-v1"

    def test_precision_openings_structure(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        # 1C should have responses
        open_1c = doc.openings[0]
        assert open_1c.bid == "1C"
        assert open_1c.meaning.artificial is True
        assert len(open_1c.responses) >= 3

    def test_precision_1nt_conventions(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        # Find 1NT opening
        open_1nt = next(o for o in doc.openings if o.bid == "1NT")
        assert open_1nt.conventions_applied is not None
        assert open_1nt.meaning.hand.shape == {"ref": "balanced"}


class TestGenerateJsonSchema:
    def test_generates_valid_schema(self):
        schema = generate_json_schema()
        assert "properties" in schema
        assert "BBDSLDocument" in schema.get("title", "") or "$defs" in schema

    def test_writes_to_file(self, tmp_path):
        output = tmp_path / "test-schema.json"
        schema = generate_json_schema(output)
        assert output.exists()
        assert schema is not None
