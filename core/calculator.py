import os
import json
import glob
from core.session_reader import SessionData

CONTEXT_LIMIT = 1048576

def calc_session_context(data: SessionData):
    """Calculates context usage for a single session data object."""
    messages = data.messages
    if not messages:
        return None

    # Get latest message with tokens
    last_tokens = None
    model = "Unknown"
    for msg in reversed(messages):
        if msg.usageMetadata:
            last_tokens = {
                "input": msg.usageMetadata.promptTokenCount,
                "output": msg.usageMetadata.candidatesTokenCount,
                "cached": msg.usageMetadata.cachedContentTokenCount
            }
            if msg.model and msg.model != "Unknown": model = msg.model
            break
        elif msg.tokens:
            last_tokens = {
                "input": msg.tokens.input,
                "output": msg.tokens.output,
                "cached": msg.tokens.cached
            }
            if msg.model and msg.model != "Unknown": model = msg.model
            break

    if not last_tokens:
        return None

    input_tokens = last_tokens.get("input", 0)
    output_tokens = last_tokens.get("output", 0)
    cached_tokens = last_tokens.get("cached", 0)
    
    # In LLMs, current 'used' context is the size of the latest prompt (input)
    used = input_tokens
    remaining = CONTEXT_LIMIT - used
    percent_used = (used / CONTEXT_LIMIT) * 100

    return {
        "input": input_tokens,
        "output": output_tokens,
        "cached": cached_tokens,
        "used": used,
        "remaining": remaining,
        "percent_used": percent_used,
        "model": model,
        "turns": len(messages)
    }

def calc_lifetime_usage(session_dir):
    """Aggregates total token usage across all files."""
    from pydantic import ValidationError
    files = glob.glob(os.path.join(session_dir, "*.json"))
    totals = {"input": 0, "output": 0, "cached": 0, "sessions": len(files)}
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as sf:
                raw_data = json.load(sf)
                data = SessionData.model_validate(raw_data)
                for msg in data.messages:
                    if msg.usageMetadata:
                        totals["input"] += msg.usageMetadata.promptTokenCount
                        totals["output"] += msg.usageMetadata.candidatesTokenCount
                        totals["cached"] += msg.usageMetadata.cachedContentTokenCount
                    elif msg.tokens:
                        totals["input"] += msg.tokens.input
                        totals["output"] += msg.tokens.output
                        totals["cached"] += msg.tokens.cached
        except Exception:
            continue
            
    totals["combined"] = totals["input"] + totals["output"]
    return totals

def calc_avg_tokens_per_turn(data: SessionData):
    """Calculates average input tokens per turn."""
    messages = data.messages
    token_counts = []
    for m in messages:
        if m.usageMetadata:
            token_counts.append(m.usageMetadata.promptTokenCount)
        elif m.tokens:
            token_counts.append(m.tokens.input)
            
    if not token_counts: return 0
    return sum(token_counts) / len(token_counts)

def calc_est_turns_remaining(remaining, avg):
    """Estimates how many turns are left based on average usage."""
    if avg <= 0: return 0
    return int(remaining / avg)
