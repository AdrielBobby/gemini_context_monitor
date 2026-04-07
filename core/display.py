from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import ProgressBar
from rich.text import Text
from datetime import datetime
import os
import re

console = Console()

def get_friendly_name(filename, raw_data_dict=None):
    """Try to extract a title from the session contents or clean the filename."""
    filler_words = ["okay", "so", "can", "you", "i", "want", "please", "could", "help", "with", "we", "were", "planning", "plannin", "on", "a", "an", "the", "for", "about"]
    if raw_data_dict:
        # If we have the data, try to get the first user prompt
        messages = raw_data_dict.get("messages", [])
        for m in messages:
            if m.get("type") == "user":
                content = m.get("content", [])
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    # In our dict conversion, it might be the MessageContent model dump
                    text = " ".join([p.get("text", "") for p in content if isinstance(p, dict)])
                
                if text:
                    # git-style summary: first 8 words after stripping fillers
                    words = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).strip().split()
                    while words and words[0].lower() in filler_words:
                        words.pop(0)
                    
                    summary = " ".join(words[:8])
                    return summary.capitalize()

    # Fallback: Clean up the filename if it's the default format
    if re.match(r'^session-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-[a-f0-9]+\.json$', filename):
        return "Untitled Session (" + filename.split("-")[-1].replace(".json", "") + ")"
    
    return filename

def show_context_panel(data, filename, raw_data_dict=None):
    """Prints the main context dashboard."""
    percent = data["percent_used"]
    color = "green"
    if percent > 75: color = "yellow"
    if percent > 90: color = "red"

    friendly_name = get_friendly_name(filename, raw_data_dict)

    # Header Info
    content = Text()
    content.append(f"Session   : ", style="bold cyan")
    content.append(f"{friendly_name}\n")
    content.append(f"File      : ", style="cyan")
    content.append(f"{filename}\n")
    content.append(f"Model     : ", style="bold cyan")
    content.append(f"{data['model']} / 1M ctx\n")
    content.append("─" * 40 + "\n")

    # Last Turn Stats
    content.append("Last Turn Tokens\n", style="bold magenta")
    content.append(f" • Input   : {data['input']:,}\n")
    content.append(f" • Output  : {data['output']:,}\n")
    content.append(f" • Cached  : {data['cached']:,}\n")
    content.append("─" * 40 + "\n")

    # Context Window
    content.append("Context Window\n", style="bold blue")
    content.append(f" Used      : {data['used']:,}  ({percent:.1f}%)\n")
    content.append(f" Remaining : {data['remaining']:,}  ({100-percent:.1f}%)\n\n")
    
    # Progress Bar
    bar = ProgressBar(total=100, completed=percent, width=40)
    
    panel = Panel(
        content,
        title="[bold white]GEMINI CLI — CONTEXT MONITOR[/bold white]",
        border_style=color,
        padding=(1, 2)
    )
    
    console.print(panel)
    console.print(bar)
    console.print()

def show_sessions_table(sessions):
    """Prints session list as a table."""
    from core import session_reader
    table = Table(title="Gemini CLI Sessions")
    table.add_column("Display Name", style="cyan")
    table.add_column("Filename", style="dim", overflow="ellipsis")
    table.add_column("Size", justify="right")
    table.add_column("Last Active", style="magenta")

    for s in sessions:
        # Try to get data to show friendly name
        data_obj = session_reader.read_session(s['path'])
        friendly = s['name']
        if data_obj:
            # We convert to dict for the helper or just use the model
            raw_data = {"messages": [m.model_dump() for m in data_obj.messages]}
            friendly = get_friendly_name(s['name'], raw_data)

        dt = datetime.fromtimestamp(s['mtime']).strftime('%Y-%m-%d %H:%M')
        table.add_row(friendly, s['name'], f"{s['size']:,} B", dt)

    console.print(table)

def show_lifetime_report(data, history_rows):
    """Prints lifetime usage summary and local history."""
    table = Table(title="Lifetime Token Usage (Current Files)")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total Input Tokens", f"{data['input']:,}")
    table.add_row("Total Output Tokens", f"{data['output']:,}")
    table.add_row("Total Cached Tokens", f"{data['cached']:,}")
    table.add_section()
    table.add_row("Combined Total", f"{data['combined']:,}", style="bold yellow")
    table.add_row("Sessions Scanned", str(data['sessions']))

    console.print(table)
    console.print()

    if history_rows:
        hist_table = Table(title="7-Day Historical Trend (SQLite)")
        hist_table.add_column("Date", style="cyan")
        hist_table.add_column("Input", justify="right")
        hist_table.add_column("Output", justify="right")
        hist_table.add_column("Sessions", justify="right", style="magenta")
        
        for row in history_rows:
            hist_table.add_row(row[0], f"{row[1]:,}", f"{row[2]:,}", str(row[4]))
        console.print(hist_table)

def warn_if_high_usage(percent):
    """Prints threshold warnings."""
    if percent > 90:
        console.print("[bold blink red]⚠️  WARNING: Context nearly full — consider starting a new session.[/bold blink red]")
    elif percent > 75:
        console.print("[bold yellow]🕒 NOTE: Context is over 75% full.[/bold yellow]")

def suggest_compaction(raw_data_dict):
    """Heuristic to suggest removing long tool outputs."""
    messages = raw_data_dict.get("messages", [])
    large_outputs_found = 0
    for m in messages:
        if m.get("role") == "user":
            for part in m.get("parts", []):
                if "functionResponse" in part:
                    resp = part["functionResponse"].get("response", {})
                    out = resp.get("output", "")
                    if isinstance(out, str) and len(out.splitlines()) > 300:
                        large_outputs_found += 1
    
    if large_outputs_found > 0:
        console.print(f"\n[bold yellow]💡 TIP: Found {large_outputs_found} large tool outputs (>300 lines) in history.[/bold yellow]")
        console.print("[yellow]Consider deleting them from the JSON or using a smaller scope to free up tokens.[/yellow]")
