import argparse
import sys
import os
import json
import time
from rich.console import Console
from core import session_reader, calculator, display, db

console = Console()

def export_to_markdown(filename, stats, raw_data_dict):
    out_file = f"export_{os.path.basename(filename)}.md"
    try:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(f"# Gemini Session Export: {os.path.basename(filename)}\n\n")
            f.write(f"**Model:** {stats['model']}\n")
            f.write(f"**Total Turns:** {stats['turns']}\n")
            f.write(f"**Tokens Used:** {stats['used']:,} ({stats['percent_used']:.1f}%)\n")
            f.write(f"**Tokens Remaining:** {stats['remaining']:,}\n\n")
            f.write("## Metrics Breakdown\n")
            f.write(f"- **Input:** {stats['input']:,}\n")
            f.write(f"- **Output:** {stats['output']:,}\n")
            f.write(f"- **Cached:** {stats['cached']:,}\n\n")
            
            f.write("## Conversation History\n\n")
            messages = raw_data_dict.get("messages", [])
            for i, m in enumerate(messages):
                role = m.get("role", "user")
                f.write(f"### Turn {i+1}: {role.capitalize()}\n")
                for part in m.get("parts", []):
                    if "text" in part:
                        f.write(f"{part['text']}\n\n")
                    elif "functionCall" in part:
                        f.write(f"*(Tool Call: {part['functionCall'].get('name')})*\n\n")
                    elif "functionResponse" in part:
                        f.write(f"*(Tool Response: {part['functionResponse'].get('name')})*\n\n")
        console.print(f"[bold green]Session exported successfully to {out_file}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to export: {e}[/bold red]")

def rename_all_sessions(session_dir):
    sessions = session_reader.list_sessions(session_dir)
    renamed_count = 0
    # Sort sessions by mtime to identify the latest active one
    sessions.sort(key=lambda x: x['mtime'], reverse=True)
    
    for i, s in enumerate(sessions):
        # Safety: skip renaming the very latest session if it was modified in the last 2 minutes
        if i == 0 and (time.time() - s['mtime'] < 120):
            console.print(f"[yellow]Skipping renaming of active session: {s['name']}[/yellow]")
            continue
            
        new_path = session_reader.rename_session_file(s['path'])
        if new_path and new_path != s['path']:
            renamed_count += 1
    console.print(f"[bold green]Successfully renamed {renamed_count} sessions based on their first prompts.[/bold green]")

def main():
    parser = argparse.ArgumentParser(description="Gemini CLI Context Monitor")
    parser.add_argument("--list", action="store_true", help="List all sessions")
    parser.add_argument("--session", type=str, help="Stats for a specific session file")
    parser.add_argument("--lifetime", action="store_true", help="Show lifetime usage")
    parser.add_argument("--watch", action="store_true", help="Auto-refresh every 10s")
    parser.add_argument("--config", type=str, help="Manually set session directory path")
    parser.add_argument("--export", action="store_true", help="Export session state to a Markdown file")
    parser.add_argument("--rename-all", action="store_true", help="Rename all default session files based on content")
    args = parser.parse_args()

    # 1. Handle Configuration
    config_file = "config.json"
    if args.config:
        with open(config_file, 'w') as f:
            json.dump({"session_dir": args.config}, f)
        console.print(f"[green]Session directory set to: {args.config}[/green]")
        return

    # 2. Find Session Directory
    session_dir = session_reader.get_session_dir(config_file)
    if not session_dir:
        console.print("[bold red]Error: Could not find Gemini session directory.[/bold red]")
        console.print("Please use [bold cyan]--config <path>[/bold cyan] to set it manually.")
        return

    # 3. Rename All Logic
    if args.rename_all:
        rename_all_sessions(session_dir)
        return

    # 4. Execution Logic
    if args.lifetime:
        data = calculator.calc_lifetime_usage(session_dir)
        db.log_daily_usage(data['input'], data['output'], data['cached'], data['sessions'])
        history_rows = db.get_history(7)
        display.show_lifetime_report(data, history_rows)
        return

    if args.list:
        sessions = session_reader.list_sessions(session_dir)
        display.show_sessions_table(sessions)
        return

    # Default: Show specific or latest session
    def run_check():
        if args.session:
            # Look for exact path or just filename in session_dir
            target = args.session if os.path.exists(args.session) else os.path.join(session_dir, args.session)
        else:
            target = session_reader.get_latest_session(session_dir)

        if not target or not os.path.exists(target):
            console.print(f"[red]Error: Session file not found: {target}[/red]")
            return False

        session_obj = session_reader.read_session(target)
        if not session_obj: return False

        stats = calculator.calc_session_context(session_obj)
        if not stats:
            console.print("[yellow]No token data found in this session yet.[/yellow]")
            return False

        # Clear screen for watch mode
        if args.watch:
            os.system('cls' if os.name == 'nt' else 'clear')

        try:
            with open(target, 'r', encoding='utf-8') as f:
                raw_data_dict = json.load(f)
        except Exception:
            raw_data_dict = {}

        display.show_context_panel(stats, os.path.basename(target), raw_data_dict)
        
        # Derived stats
        avg = calculator.calc_avg_tokens_per_turn(session_obj)
        est = calculator.calc_est_turns_remaining(stats["remaining"], avg)
        
        console.print(f" Turns in session : {stats['turns']}")
        console.print(f" Avg tokens/turn  : {int(avg):,}")
        console.print(f" Est. turns left  : ~{est}")
        console.print("-" * 40)
        
        display.warn_if_high_usage(stats["percent_used"])

        display.suggest_compaction(raw_data_dict)

        if args.export:
            export_to_markdown(target, stats, raw_data_dict)
            return "EXIT"

        return True

    if args.watch:
        try:
            while True:
                res = run_check()
                if res == "EXIT": break
                time.sleep(10)
        except KeyboardInterrupt:
            console.print("\n[yellow]Watch mode stopped.[/yellow]")
    else:
        run_check()

if __name__ == "__main__":
    main()
