import os
import json
import glob
import re
from pathlib import Path
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ValidationError

class UsageMetadata(BaseModel):
    promptTokenCount: int = 0
    candidatesTokenCount: int = 0
    cachedContentTokenCount: int = 0

class Tokens(BaseModel):
    input: int = 0
    output: int = 0
    cached: int = 0

class MessageContent(BaseModel):
    text: Optional[str] = None
    model_config = {"extra": "ignore"}

class Message(BaseModel):
    type: Optional[str] = None # "user" or "gemini"
    model: Optional[str] = "Unknown"
    usageMetadata: Optional[UsageMetadata] = None
    tokens: Optional[Tokens] = None
    content: Optional[Union[str, List[MessageContent]]] = None
    model_config = {"extra": "ignore"}

    def get_text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            return " ".join([p.text for p in self.content if p.text])
        return ""

class SessionData(BaseModel):
    sessionId: str
    messages: List[Message] = Field(default_factory=list)
    model_config = {"extra": "ignore"}

    def get_first_prompt_slug(self) -> str:
        filler_words = ["okay", "so", "can", "you", "i", "want", "please", "could", "help", "with", "we", "were"]
        for m in self.messages:
            if m.type == "user":
                text = m.get_text()
                # Remove special chars and normalize spaces
                clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).strip().lower()
                words = clean.split()
                # Remove filler words from the start
                while words and words[0] in filler_words:
                    words.pop(0)
                # Take first 8 words for a git-style summary
                slug = "-".join(words[:8])
                return slug or "unnamed-session"
        return "unnamed-session"

def get_session_dir(config_path="config.json"):
    """Auto-detects or retrieves the session directory from config."""
    # 1. Check config.json
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                path = data.get("session_dir")
                if path and os.path.exists(path):
                    return path
        except:
            pass

    # 2. Auto-detect based on OS
    home = str(Path.home())
    
    # Check all possible gemini CLI project temp directories first
    base_tmp = os.path.join(home, ".gemini", "tmp")
    if os.path.exists(base_tmp):
        possible_chats = glob.glob(os.path.join(base_tmp, "*", "chats"))
        if possible_chats:
            # Sort by modification time to get the most recent active project chats
            possible_chats.sort(key=os.path.getmtime, reverse=True)
            return possible_chats[0]

    possible_paths = [
        os.path.join(home, ".gemini", "tmp", os.getlogin(), "chats"),
        os.path.join(home, ".gemini", "tmp", "adrie", "chats"),
        os.path.join(os.getenv("APPDATA", ""), "gemini-cli", "chats"),
    ]

    for p in possible_paths:
        if os.path.exists(p):
            return p

    return None

def list_sessions(session_dir):
    """Returns a list of session files with metadata."""
    files = glob.glob(os.path.join(session_dir, "*.json"))
    sessions = []
    for f in files:
        stats = os.stat(f)
        sessions.append({
            "name": os.path.basename(f),
            "path": f,
            "mtime": stats.st_mtime,
            "size": stats.st_size
        })
    # Sort by newest first
    sessions.sort(key=lambda x: x['mtime'], reverse=True)
    return sessions

def get_latest_session(session_dir):
    """Returns the path to the most recently modified session."""
    sessions = list_sessions(session_dir)
    return sessions[0]['path'] if sessions else None

def read_session(filepath) -> Optional[SessionData]:
    """Parses a session JSON and returns a validated SessionData object."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return SessionData.model_validate(data)
    except ValidationError as e:
        print(f"Validation error in {filepath}: {e}")
        return None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def rename_session_file(filepath: str) -> Optional[str]:
    """Renames a session file based on its first prompt if it hasn't been renamed yet."""
    data = read_session(filepath)
    if not data: return None
    
    filename = os.path.basename(filepath)
    # Check if already renamed (contains more than just date/hash)
    # Default format: session-YYYY-MM-DDTHH-mm-HASH.json
    if not re.match(r'^session-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-[a-f0-9]+\.json$', filename):
        return filepath # Likely already renamed or custom

    slug = data.get_first_prompt_slug()
    if slug == "unnamed-session": return filepath
    
    # New name: session-slug-id.json
    # Keep the first part of the original ID (hash) to keep it unique
    original_id = filename.split("-")[-1].replace(".json", "")
    new_filename = f"session-{slug}-{original_id}.json"
    new_path = os.path.join(os.path.dirname(filepath), new_filename)
    
    try:
        if not os.path.exists(new_path):
            os.rename(filepath, new_path)
            return new_path
    except Exception as e:
        print(f"Error renaming {filename}: {e}")
        
    return filepath
