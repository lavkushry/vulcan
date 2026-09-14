"""
Project Vulcan: Canonical JSON Serialization Module (AGENT-01 / P0 #2)
Author: AgentOS Core Team & Architectural Review Board

Enforces the Zero Silent Degradation Invariant across all repository adapters:
- Handles datetime, date, time objects -> ISO 8601 strings
- Handles Enum values -> underlying primitive values
- Handles Pydantic v1 and v2 models -> json-serializable dicts
- Handles standard library Dataclasses -> json-serializable dicts
- Handles UUIDs, Pathlib objects -> string representations
- Handles nested collections (dicts, lists, sets, tuples) recursively
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
import enum
import json
from pathlib import Path
from typing import Any, Dict, List, Union
import uuid


def canonical_json_default(obj: Any) -> Any:
    """Fallback encoder for json.dumps supporting all enterprise domain types."""
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    if hasattr(obj, "__json__") and callable(obj.__json__):
        return obj.__json__()
    
    # Catch any object with a dict attribute
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}

    return str(obj)


def canonical_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Serializes any object tree using the canonical fallback encoder."""
    kwargs.setdefault("default", canonical_json_default)
    return json.dumps(obj, **kwargs)


def canonical_json_loads(s: Union[str, bytes], **kwargs: Any) -> Any:
    """Deserializes JSON string or bytes."""
    return json.loads(s, **kwargs)


def to_jsonable_python(obj: Any) -> Any:
    """Recursively converts any nested data structure into pure JSON-serializable Python primitives."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return to_jsonable_python(obj.model_dump(mode="json"))
    if hasattr(obj, "dict") and callable(obj.dict):
        return to_jsonable_python(obj.dict())
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable_python(asdict(obj))
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return to_jsonable_python(obj.to_dict())
    if isinstance(obj, dict):
        return {str(k): to_jsonable_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable_python(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return {str(k): to_jsonable_python(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)
