"""Load partner schemas from YAML files into validated config objects."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.engine.models import SchemaConfig


def load_schema(path: str) -> SchemaConfig:
    """Load a YAML partner schema and return a validated config.

    Args:
        path: Filesystem path to a .yaml schema file.

    Returns:
        Validated SchemaConfig instance.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
        pydantic.ValidationError: If the parsed data does not match
            the SchemaConfig structure.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Schema file not found: {resolved}")

    raw = resolved.read_text(encoding="utf-8")
    return load_schema_from_string(raw)


def load_schema_from_string(yaml_string: str) -> SchemaConfig:
    """Load a schema from a YAML string (for Pyodide use).

    Args:
        yaml_string: Raw YAML content.

    Returns:
        Validated SchemaConfig instance.

    Raises:
        yaml.YAMLError: If the string is not valid YAML.
        pydantic.ValidationError: If the parsed data does not match
            the SchemaConfig structure.
    """
    data = yaml.safe_load(yaml_string)
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a YAML mapping at top level, got {type(data).__name__}"
        )
    return SchemaConfig.model_validate(data)
