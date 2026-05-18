"""Shared JSON persistence helpers for database repositories."""

import json
import math
import os
import tempfile


_JSON_SAFE_SCALAR_TYPES = (str, int, bool, type(None))


def json_path_for(storage_path):
    """Return the JSON sibling path for a legacy storage path."""
    base_path, _extension = os.path.splitext(storage_path)
    return f"{base_path}.json"


def validate_json_safe(data):
    """Validate that data can be persisted without changing JSON structure."""
    _validate_json_safe_value(data, "$")
    json.dumps(data, ensure_ascii=False, allow_nan=False)
    return data


def _validate_json_safe_value(value, path):
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise ValueError(f"JSON object keys must be strings at {path}")
            _validate_json_safe_value(nested_value, f"{path}.{key}")
        return

    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            _validate_json_safe_value(nested_value, f"{path}[{index}]")
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"JSON numbers must be finite at {path}")
        return

    if isinstance(value, _JSON_SAFE_SCALAR_TYPES):
        return

    raise ValueError(f"Unsupported JSON value at {path}: {type(value).__name__}")


def load_json_file(path):
    """Load and validate UTF-8 JSON from path."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return validate_json_safe(data)


def atomic_write_json(path, data):
    """Atomically write data as UTF-8 JSON using tmp -> flush -> os.replace."""
    validate_json_safe(data)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=directory,
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(data, temporary_file, ensure_ascii=False, allow_nan=False)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
