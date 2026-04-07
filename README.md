# 📊 Gemini CLI Context Monitor (V1)

A professional terminal tool to monitor your context window usage while using the Gemini CLI. It parses local session logs to calculate exactly how many tokens you have left before the model starts forgetting.

## 🚀 Features
- **Context Tracking**: Real-time view of input, output, and cached tokens.
- **Visual Progress Bar**: See your 1M token context window occupancy at a glance.
- **Lifetime Analytics (SQLite)**: Aggregate your total token consumption and view historical 7-day trends.
- **Session Explorer**: List all your chat logs with size and last-active timestamps.
- **Markdown Export**: Export your entire session state, including metadata and history, into a clean `.md` file.
- **Compaction Suggestions**: Get warnings if your context history contains massive tool outputs that could be deleted to save space.
- **Watch Mode**: Auto-refreshing dashboard for a split-terminal workflow.

## 🛠 Installation

The project uses a standard `pyproject.toml` and is compatible with `uv` (recommended for speed) or standard `pip`.

### Using `uv` (Recommended)
```bash
uv sync
uv run gemini_context.py
```

### Using standard `venv` & `pip`
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

pip install -e .
```

## 📖 Usage
Run without arguments to see the **latest session**:
```bash
python gemini_context.py
```

List **all sessions**:
```bash
python gemini_context.py --list
```

View **Lifetime Usage & Trends**:
```bash
python gemini_context.py --lifetime
```

Export Session to **Markdown**:
```bash
python gemini_context.py --export
```

Enable **Watch Mode** (refreshes every 10s):
```bash
python gemini_context.py --watch
```

Check a **Specific Session**:
```bash
python gemini_context.py --session session-xxxx.json
```

## 📂 Session Location
The tool auto-detects sessions at:
- `~/.gemini/tmp/.../chats`

If your path is different, set it once:
```bash
python gemini_context.py --config "C:\Path\To\Your\Chats"
```

---
Built as a robust CLI utility for Gemini power users.
