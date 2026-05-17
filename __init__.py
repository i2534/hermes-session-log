"""Session Log - record every session's conversation as JSONL."""

import json
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".hermes" / "session-log" / "sessions"
INDEX_FILE = Path.home() / ".hermes" / "session-log" / "index.jsonl"

# Curator auto-prompts to skip
_SKIP_PREFIXES = (
    "Review the conversation above",
    "You are a helpful",
)

# In-memory cache: session_id -> meta dict
_cache: dict = {}


def register(ctx):
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("post_llm_call", _post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)


def _ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _meta_file(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.meta.json"


def _turns_file(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_assistant(text: str) -> str:
    """Remove TUI status lines."""
    if not text:
        return text
    lines = text.split("\n")
    cleaned = [
        line for line in lines
        if not (line.strip().startswith("\u26a0\ufe0f") or line.strip().startswith("⚠"))
        and not (line.strip().startswith("[tool") and "]" in line.strip())
    ]
    result = "\n".join(cleaned).strip()
    return result if result else text


def _is_skip_message(user_message: str) -> bool:
    """Check if user message is an internal auto-prompt."""
    text = user_message.strip()
    return any(text.startswith(p) for p in _SKIP_PREFIXES)


def _write_meta(entry: dict):
    """Write metadata file."""
    mf = _meta_file(entry["session_id"])
    tmp = mf.with_suffix(".meta.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    tmp.rename(mf)


def _append_turn(user: str, assistant: str, session_id: str):
    """Append one turn to JSONL file."""
    tf = _turns_file(session_id)
    line = json.dumps({"user": user, "assistant": assistant}, ensure_ascii=False)
    with open(tf, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _on_session_start(session_id: str, model: str, platform: str, **kwargs):
    """New session started — initialize meta."""
    _ensure_dirs()
    entry = {
        "session_id": session_id,
        "started_at": _now_iso(),
        "updated_at": None,
        "model": model,
        "platform": platform,
        "turn_count": 0,
        "completed": False,
        "interrupted": False,
        "topic": None,
    }
    _cache[session_id] = entry
    _write_meta(entry)


def _post_llm_call(
    session_id: str,
    user_message,
    assistant_response,
    conversation_history: list,
    model: str,
    platform: str,
    **kwargs,
):
    """Each turn completed — append one line to JSONL."""
    _ensure_dirs()

    # Skip internal auto-prompts
    if _is_skip_message(str(user_message)):
        return

    if session_id not in _cache:
        entry = {
            "session_id": session_id,
            "started_at": _now_iso(),
            "updated_at": None,
            "model": model,
            "platform": platform,
            "turn_count": 0,
            "completed": False,
            "interrupted": False,
            "topic": None,
        }
        _cache[session_id] = entry

    entry = _cache[session_id]
    entry["updated_at"] = _now_iso()
    entry["model"] = model
    entry["platform"] = platform
    entry["turn_count"] += 1

    if entry["topic"] is None:
        entry["topic"] = str(user_message).strip()[:100]

    # Clean and truncate
    user_text = str(user_message)[:10000]
    assistant_text = _clean_assistant(str(assistant_response))[:10000] if assistant_response else None

    # Append turn to JSONL (fast, no full file rewrite)
    _append_turn(user_text, assistant_text, session_id)

    # Update meta less frequently (every turn is fine for small file)
    _write_meta(entry)


def _on_session_end(
    session_id: str,
    completed: bool,
    interrupted: bool,
    model: str,
    platform: str,
    **kwargs,
):
    """Session ended — update meta and write index."""
    if session_id not in _cache:
        return

    entry = _cache[session_id]
    entry["completed"] = completed
    entry["interrupted"] = interrupted
    entry["updated_at"] = _now_iso()
    _write_meta(entry)

    # Only write index if there are actual turns
    if entry["turn_count"] > 0:
        _append_index(entry)


def _append_index(entry: dict):
    """Append/update index entry."""
    line = json.dumps({
        "session_id": entry["session_id"],
        "started_at": entry["started_at"],
        "updated_at": entry["updated_at"],
        "model": entry["model"],
        "platform": entry["platform"],
        "turn_count": entry["turn_count"],
        "topic": entry.get("topic") or "",
        "completed": entry["completed"],
        "interrupted": entry["interrupted"],
    }, ensure_ascii=False)

    if INDEX_FILE.exists():
        lines = INDEX_FILE.read_text(encoding="utf-8").strip().split("\n")
        found = False
        for i, l in enumerate(lines):
            try:
                existing = json.loads(l)
                if existing.get("session_id") == entry["session_id"]:
                    lines[i] = line
                    found = True
                    break
            except json.JSONDecodeError:
                continue
        if not found:
            lines.append(line)
        INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        INDEX_FILE.write_text(line + "\n", encoding="utf-8")
