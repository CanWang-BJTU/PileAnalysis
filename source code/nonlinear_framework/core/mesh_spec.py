# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List


DEFAULT_ELEMENT_COUNT = 400


def default_mesh_settings() -> Dict:
    return {
        "advanced_enabled": False,
        "mesh_type": "element_number",
        "uniform_element_count": DEFAULT_ELEMENT_COUNT,
        "uniform_element_length_m": 0.1,
        "segments": [],
    }


def normalize_mesh_settings(settings: Dict | None) -> Dict:
    base = default_mesh_settings()
    if isinstance(settings, dict):
        base.update(settings)

    base["advanced_enabled"] = bool(base.get("advanced_enabled", False))

    mesh_type = str(base.get("mesh_type", "element_number")).strip().lower()
    aliases = {
        "count": "element_number",
        "size": "element_length",
        "custom": "user_define",
        "element_count": "element_number",
        "element_size": "element_length",
    }
    mesh_type = aliases.get(mesh_type, mesh_type)
    if mesh_type not in {"element_number", "element_length", "user_define"}:
        mesh_type = "element_number"
    base["mesh_type"] = mesh_type

    base["uniform_element_count"] = max(
        int(round(float(base.get("uniform_element_count", DEFAULT_ELEMENT_COUNT)))),
        1,
    )
    base["uniform_element_length_m"] = max(float(base.get("uniform_element_length_m", 0.1)), 0.0)

    normalized_segments = []
    for segment in base.get("segments", []):
        if not isinstance(segment, dict):
            continue
        normalized_segments.append(
            {
                "start_m": float(segment.get("start_m", 0.0)),
                "end_m": float(segment.get("end_m", 0.0)),
                "element_count": max(int(round(float(segment.get("element_count", 0.0)))), 0),
                "top_length_m": _optional_positive(segment.get("top_length_m")),
                "bottom_length_m": _optional_positive(segment.get("bottom_length_m")),
            }
        )
    base["segments"] = normalized_segments
    return base


def _optional_positive(value) -> float | None:
    if value in (None, "", "None"):
        return None
    number = float(value)
    return number if number > 0.0 else None


def _uniform_positions(total_length: float, element_count: int) -> List[float]:
    count = max(int(element_count), 1)
    return [total_length * i / count for i in range(count + 1)]


def _graded_segment_positions(start: float, end: float, element_count: int, top_length: float, bottom_length: float) -> List[float]:
    count = max(int(element_count), 1)
    segment_length = float(end) - float(start)
    if segment_length <= 0.0:
        raise ValueError("Segment length must be positive.")

    if count == 1:
        return [start, end]

    weights = [
        top_length + (bottom_length - top_length) * i / (count - 1)
        for i in range(count)
    ]
    if any(weight <= 0.0 for weight in weights):
        raise ValueError("User-defined mesh top/bottom lengths must be positive.")

    scale = segment_length / sum(weights)
    current = float(start)
    positions = [current]
    for weight in weights:
        current += weight * scale
        positions.append(current)
    positions[-1] = float(end)
    return positions


def build_mesh_positions(total_length: float, settings: Dict | None) -> List[float]:
    total_length = float(total_length)
    if total_length <= 0.0:
        raise ValueError("Pile length must be positive for mesh generation.")

    spec = normalize_mesh_settings(settings)
    if not spec["advanced_enabled"]:
        return _uniform_positions(total_length, DEFAULT_ELEMENT_COUNT)

    mesh_type = spec["mesh_type"]
    if mesh_type == "element_number":
        return _uniform_positions(total_length, spec["uniform_element_count"])

    if mesh_type == "element_length":
        size = spec["uniform_element_length_m"]
        if size <= 0.0:
            return _uniform_positions(total_length, DEFAULT_ELEMENT_COUNT)
        element_count = max(int(round(total_length / size)), 1)
        return _uniform_positions(total_length, element_count)

    segments = sorted(spec.get("segments", []), key=lambda item: item["start_m"])
    if not segments:
        return _uniform_positions(total_length, DEFAULT_ELEMENT_COUNT)

    positions: List[float] = [0.0]
    cursor = 0.0
    for idx, segment in enumerate(segments, start=1):
        start = float(segment["start_m"])
        end = float(segment["end_m"])
        element_count = max(int(segment.get("element_count", 0)), 1)
        top_length = segment.get("top_length_m")
        bottom_length = segment.get("bottom_length_m")

        if start < -1.0e-8 or end > total_length + 1.0e-8 or end <= start:
            raise ValueError(f"Mesh segment {idx} is out of range or has invalid start/end.")
        if abs(start - cursor) > 1.0e-6:
            raise ValueError("Custom mesh segments must be continuous and start from 0.0 m.")

        if top_length is not None or bottom_length is not None:
            if top_length is None or bottom_length is None:
                raise ValueError(f"Mesh segment {idx} must provide both top and bottom lengths together.")
            local = _graded_segment_positions(start, end, element_count, float(top_length), float(bottom_length))
        else:
            local = _uniform_positions(end - start, element_count)
            local = [start + value for value in local]

        positions.extend(local[1:])
        cursor = end

    if abs(cursor - total_length) > 1.0e-6:
        raise ValueError("Custom mesh segments must end at the pile total length.")

    positions[0] = 0.0
    positions[-1] = total_length
    return positions


def representative_element_size(total_length: float, settings: Dict | None) -> float | None:
    positions = build_mesh_positions(total_length, settings)
    if len(positions) < 2:
        return None
    return total_length / max(len(positions) - 1, 1)
