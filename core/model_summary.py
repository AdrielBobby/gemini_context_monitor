"""
model_summary.py — Unified data contract for a model's aggregated stats.

Used by monitor_service (producer) and main_window UI (consumer).
"""
from dataclasses import dataclass, field


@dataclass
class ModelSummary:
    model_id: str           # raw key e.g. "gemini-3-flash-preview"
    display_name: str       # "Gemini 3 Flash Preview"
    context_limit: int      # 1048576
    tier: str               # "flash" | "pro" | "unknown"
    has_sessions: bool      # False → show inactive card
    session_count: int      # 0 if no sessions
    total_input: int        # 0 if no sessions
    total_output: int       # 0 if no sessions
    total_cached: int       # 0 if no sessions
    total_combined: int     # 0 if no sessions
    avg_usage_pct: float    # 0.0 if no sessions
    last_active: str        # "" if no sessions; formatted "Apr 08, 15:00"
