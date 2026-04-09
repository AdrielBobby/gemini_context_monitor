"""
monitor_service.py — Service layer for aggregating model stats.

get_all_models() is the single entry point used by the Models tab UI.
It merges live session data with the KNOWN_MODELS registry and returns
a sorted list of ModelSummary objects.
"""
import time
from typing import Any, Dict, List

from core import session_reader, calculator
from core.model_summary import ModelSummary
from core.models_registry import KNOWN_MODELS, get_model_info


def get_all_models(session_data_list: List[Dict[str, Any]]) -> List[ModelSummary]:
    """
    Build a complete list of ModelSummary objects:
      - All models in KNOWN_MODELS are always included.
      - Session models not in KNOWN_MODELS are appended with tier='unknown'.
      - Active models (has_sessions=True) sorted first by last_active desc.
      - Inactive models (has_sessions=False) sorted alphabetically after.
    """
    # ── Step 1: aggregate session stats grouped by model id ──────────────────
    groups: Dict[str, Dict[str, Any]] = {}

    for s in session_data_list:
        sobj = session_reader.read_session(s["path"])
        if not sobj:
            continue
        stats = calculator.calc_session_context(sobj)
        if not stats:
            continue

        mname = stats["model"]
        if mname not in groups:
            groups[mname] = {
                "sessions": [],
                "mtime": 0.0,
            }

        groups[mname]["sessions"].append(stats)
        mtime = s.get("mtime", 0.0)
        if mtime > groups[mname]["mtime"]:
            groups[mname]["mtime"] = mtime

    # ── Step 2: build ModelSummary for every KNOWN model ────────────────────
    active: List[ModelSummary] = []
    inactive: List[ModelSummary] = []

    seen_ids = set()

    for model_id, reg_info in KNOWN_MODELS.items():
        seen_ids.add(model_id)
        summary = _build_summary(model_id, reg_info, groups.get(model_id))
        if summary.has_sessions:
            active.append(summary)
        else:
            inactive.append(summary)

    # ── Step 3: include unknown models found only in sessions ────────────────
    for model_id, group in groups.items():
        if model_id in seen_ids:
            continue
        reg_info = get_model_info(model_id)  # returns fallback dict
        summary = _build_summary(model_id, reg_info, group)
        active.append(summary)  # always has_sessions=True here

    # ── Step 4: sort and merge ───────────────────────────────────────────────
    active.sort(key=lambda s: s.last_active, reverse=True)
    inactive.sort(key=lambda s: s.display_name)

    return active + inactive


def _build_summary(
    model_id: str,
    reg_info: Dict[str, Any],
    group: Dict[str, Any] | None,
) -> ModelSummary:
    """Construct a ModelSummary from registry info + optional session group."""

    display_name = reg_info["display_name"]
    context_limit = reg_info["context_limit"]
    tier = reg_info["tier"]

    if not group or not group.get("sessions"):
        return ModelSummary(
            model_id=model_id,
            display_name=display_name,
            context_limit=context_limit,
            tier=tier,
            has_sessions=False,
            session_count=0,
            total_input=0,
            total_output=0,
            total_cached=0,
            total_combined=0,
            avg_usage_pct=0.0,
            last_active="",
        )

    sessions = group["sessions"]
    total_input = sum(s["input"] for s in sessions)
    total_output = sum(s["output"] for s in sessions)
    total_cached = sum(s["cached"] for s in sessions)
    avg_pct = sum(s["percent_used"] for s in sessions) / len(sessions)
    last_active = time.strftime("%b %d, %H:%M", time.localtime(group["mtime"]))

    return ModelSummary(
        model_id=model_id,
        display_name=display_name,
        context_limit=context_limit,
        tier=tier,
        has_sessions=True,
        session_count=len(sessions),
        total_input=total_input,
        total_output=total_output,
        total_cached=total_cached,
        total_combined=total_input + total_output,
        avg_usage_pct=avg_pct,
        last_active=last_active,
    )
