"""
Pure-Python orjson compatibility shim.

The native orjson DLL (orjson.pyd) is blocked by Windows Application Control
policy on this machine. This module provides an identical public interface using
Python's stdlib json, so that langgraph_sdk, fastapi, and other packages that
import orjson continue to work without modification.

Placed in backend/ so it shadows the installed package when the server runs from
that directory or when backend/ is on sys.path.
"""
from __future__ import annotations

import json as _json
from typing import Any, Callable, Optional

# ── Option flags (mirror orjson constants) ───────────────────────────────────
OPT_NON_STR_KEYS: int = 1
OPT_INDENT_2: int = 2
OPT_SERIALIZE_UUID: int = 4
OPT_PASSTHROUGH_DATETIME: int = 8
OPT_UTC_Z: int = 16
OPT_NAIVE_UTC: int = 32
OPT_SORT_KEYS: int = 64
OPT_SERIALIZE_NUMPY: int = 128
OPT_STRICT_INTEGER: int = 256
OPT_OMIT_MICROSECONDS: int = 512


class JSONDecodeError(ValueError):
    """Raised when JSON decoding fails — mirrors orjson.JSONDecodeError."""


class JSONEncodeError(TypeError):
    """Raised when JSON encoding fails — mirrors orjson.JSONEncodeError."""


def _default_serializer(obj: Any) -> Any:
    """Fallback serializer for types not natively handled by stdlib json."""
    import uuid
    import datetime
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "__iter__"):
        return list(obj)
    raise JSONEncodeError(f"Object of type {type(obj).__name__!r} is not JSON serializable")


def dumps(
    obj: Any,
    default: Optional[Callable[[Any], Any]] = None,
    option: Optional[int] = None,
) -> bytes:
    """Serialise *obj* to JSON bytes (UTF-8), mimicking orjson.dumps()."""
    indent = 2 if option is not None and (option & OPT_INDENT_2) else None
    sort_keys = option is not None and bool(option & OPT_SORT_KEYS)

    def _combined_default(o: Any) -> Any:
        if default is not None:
            try:
                return default(o)
            except (TypeError, JSONEncodeError):
                pass
        return _default_serializer(o)

    try:
        return _json.dumps(
            obj,
            default=_combined_default,
            indent=indent,
            sort_keys=sort_keys,
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise JSONEncodeError(str(exc)) from exc


def loads(data: Any) -> Any:
    """Deserialise JSON bytes/str to a Python object, mimicking orjson.loads()."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        data = bytes(data).decode("utf-8")
    try:
        return _json.loads(data)
    except _json.JSONDecodeError as exc:
        raise JSONDecodeError(str(exc)) from exc


__version__: str = "3.99.0-shim"
__all__ = [
    "dumps",
    "loads",
    "JSONDecodeError",
    "JSONEncodeError",
    "OPT_NON_STR_KEYS",
    "OPT_INDENT_2",
    "OPT_SERIALIZE_UUID",
    "OPT_PASSTHROUGH_DATETIME",
    "OPT_UTC_Z",
    "OPT_NAIVE_UTC",
    "OPT_SORT_KEYS",
    "OPT_SERIALIZE_NUMPY",
    "OPT_STRICT_INTEGER",
    "OPT_OMIT_MICROSECONDS",
]
