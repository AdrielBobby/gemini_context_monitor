import customtkinter as ctk
import time
import os
from typing import Dict, Any, Optional, List

from core import session_reader, calculator
from ui.theme import Theme

class ContextMonitorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # App Configuration
        self.title("Gemini Context Monitor")
        self.geometry("650x700") # Slightly wider/taller for better layout
        self.resizable(False, False)
        
        # Appearance
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=Theme.BG_DARK)
        
        # State
        self.auto_refresh = True
        self.refresh_interval = 10000 # ms
        self.session_data_list: List[Dict[str, Any]] = []
        self.active_view = "dash"
        
        self._build_ui()
        self.refresh_data()
        self._auto_refresh_loop()

    def _build_ui(self):
        # 1. Navigation / Tab Header
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=20, pady=(15, 5))
        
        self.btn_dash = self._create_nav_btn("Dashboard", "dash")
        self.btn_sessions = self._create_nav_btn("Sessions", "sessions")
        self.btn_models = self._create_nav_btn("Models", "models")
        
        self.btn_dash.pack(side="left", padx=(0, 10))
        self.btn_sessions.pack(side="left", padx=(0, 10))
        self.btn_models.pack(side="left")

        # 2. Main Content Area
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=5)
        
        # Views
        self.view_dash = ctk.CTkFrame(self.container, fg_color="transparent")
        self.view_sessions = ctk.CTkFrame(self.container, fg_color="transparent")
        self.view_models = ctk.CTkFrame(self.container, fg_color="transparent")
        
        self._build_dashboard_view()
        self._build_sessions_view()
        self._build_models_view()
        
        self._show_view("dash")

        # 3. Common Footer
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=20, pady=(5, 15))
        
        self.lbl_last_updated = ctk.CTkLabel(self.footer_frame, text="LAST UPDATED: Never", font=("Inter", 9), text_color="#404040")
        self.lbl_last_updated.pack(side="left")

        self.btn_refresh = ctk.CTkButton(self.footer_frame, text="Refresh All", width=100, height=28, font=("Inter", 11), 
                                         fg_color=Theme.BG_CARD, hover_color="#1f1f1f", command=self.refresh_data)
        self.btn_refresh.pack(side="right")

    def _create_nav_btn(self, text: str, view_name: str) -> ctk.CTkButton:
        return ctk.CTkButton(self.nav_frame, text=text, width=110, height=34, 
                            fg_color=Theme.BG_CARD, font=("Inter", 12, "bold"),
                            hover_color=Theme.BG_CARD_ACCENT,
                            command=lambda: self._show_view(view_name))

    def _show_view(self, view_name: str):
        self.active_view = view_name
        # Hide all
        for v in [self.view_dash, self.view_sessions, self.view_models]:
            v.pack_forget()
        
        # De-highlight all
        for b in [self.btn_dash, self.btn_sessions, self.btn_models]:
            b.configure(fg_color=Theme.BG_CARD)

        if view_name == "dash":
            self.view_dash.pack(fill="both", expand=True)
            self.btn_dash.configure(fg_color=Theme.COLOR_NORMAL)
        elif view_name == "sessions":
            self.view_sessions.pack(fill="both", expand=True)
            self.btn_sessions.configure(fg_color=Theme.COLOR_NORMAL)
            self._update_sessions_list()
        elif view_name == "models":
            self.view_models.pack(fill="both", expand=True)
            self.btn_models.configure(fg_color=Theme.COLOR_NORMAL)
            self._update_models_list()

    def _build_dashboard_view(self):
        head = ctk.CTkFrame(self.view_dash, fg_color="transparent")
        head.pack(fill="x", pady=(10, 5))
        self.lbl_model = ctk.CTkLabel(head, text="Model: Unknown", font=("Inter", 13), text_color=Theme.TEXT_MUTED)
        self.lbl_model.pack(side="left")
        self.status_badge = ctk.CTkLabel(head, text="NORMAL", font=("Inter", 10, "bold"), 
                                        text_color=Theme.TEXT_MAIN, fg_color=Theme.COLOR_NORMAL,
                                        corner_radius=6, padx=8, pady=2, width=80)
        self.status_badge.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.view_dash, height=20, fg_color="#1A1A1A", progress_color=Theme.COLOR_NORMAL)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(10, 0))

        self.lbl_usage_summary = ctk.CTkLabel(self.view_dash, text="0 tokens remaining · 0% used", font=("Inter", 11), text_color=Theme.TEXT_MUTED)
        self.lbl_usage_summary.pack(anchor="w", pady=(5, 15))

        grid = ctk.CTkFrame(self.view_dash, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1)
        grid.grid_rowconfigure((0, 1), weight=1)
        self.card_remaining, self.frame_remaining = self._create_metric_card(grid, "REMAINING", "0", 0, 0, is_dominant=True)
        self.card_used, _ = self._create_metric_card(grid, "USED TOKENS", "0", 0, 1)
        self.card_cached, _ = self._create_metric_card(grid, "CACHED", "0", 1, 0)
        self.card_limit, _ = self._create_metric_card(grid, "TOTAL LIMIT", "0", 1, 1)

    def _build_sessions_view(self):
        self.view_sessions.grid_columnconfigure(0, weight=1)
        self.view_sessions.grid_rowconfigure(0, weight=3) # List
        self.view_sessions.grid_rowconfigure(1, weight=2) # Details

        self.list_frame = ctk.CTkScrollableFrame(self.view_sessions, fg_color=Theme.BG_CARD, corner_radius=10, label_text="Active Sessions", label_font=("Inter", 11, "bold"), label_text_color=Theme.TEXT_MUTED)
        self.list_frame.grid(row=0, column=0, sticky="nsew", pady=(10, 5))
        
        self.detail_panel = self._create_detail_panel(self.view_sessions, 1, 0)

    def _build_models_view(self):
        self.view_models.grid_columnconfigure(0, weight=1)
        self.view_models.grid_rowconfigure(0, weight=3) # Models List
        self.view_models.grid_rowconfigure(1, weight=2) # Detail Panel

        self.models_list = ctk.CTkScrollableFrame(self.view_models, fg_color=Theme.BG_CARD, corner_radius=10, 
                                                 label_text="Models Breakdown", label_font=("Inter", 11, "bold"),
                                                 label_text_color=Theme.TEXT_MUTED)
        self.models_list.grid(row=0, column=0, sticky="nsew", pady=(10, 5))
        
        self.models_detail_panel = self._create_detail_panel(self.view_models, 1, 0)

    def _create_detail_panel(self, parent, row, col):
        panel = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD_ACCENT, corner_radius=10, border_width=1, border_color="#333333")
        panel.grid(row=row, column=col, sticky="nsew", pady=(5, 10))
        
        empty_lbl = ctk.CTkLabel(panel, text="Select a session to view details", font=("Inter", 12), text_color=Theme.TEXT_MUTED)
        empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        
        content = ctk.CTkFrame(panel, fg_color="transparent")
        # Store for reference
        panel.empty_lbl = empty_lbl
        panel.content = content
        return panel

    def _update_sessions_list(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        if not self.session_data_list:
            ctk.CTkLabel(self.list_frame, text="No sessions found", font=("Inter", 12), text_color=Theme.TEXT_MUTED).pack(pady=20)
            return
        for i, s in enumerate(self.session_data_list):
            self._create_session_row(self.list_frame, s, i == 0, self.detail_panel)

    def _update_models_list(self):
        for widget in self.models_list.winfo_children(): widget.destroy()
        if not self.session_data_list:
            ctk.CTkLabel(self.models_list, text="No models found", font=("Inter", 12), text_color=Theme.TEXT_MUTED).pack(pady=20)
            return

        # Group by model
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for s in self.session_data_list:
            # We need to read the session to get the actual model name
            sobj = session_reader.read_session(s['path'])
            if not sobj: continue
            stats = calculator.calc_session_context(sobj)
            if not stats: continue
            
            mname = stats['model']
            if mname not in groups: groups[mname] = []
            groups[mname].append({"meta": s, "stats": stats})

        for mname, items in groups.items():
            card = ctk.CTkFrame(self.models_list, fg_color=Theme.BG_CARD_ACCENT, corner_radius=10, border_width=1, border_color="#222")
            card.pack(fill="x", padx=10, pady=8)
            
            # Header
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=(12, 8))
            ctk.CTkLabel(header, text=mname.upper(), font=("Inter", 14, "bold"), text_color=Theme.COLOR_NORMAL).pack(side="left")
            ctk.CTkLabel(header, text=f"{len(items)} sessions", font=("Inter", 10), text_color=Theme.TEXT_MUTED).pack(side="right")

            # Aggregate Stats
            total_in = sum(i['stats']['input'] for i in items)
            total_out = sum(i['stats']['output'] for i in items)
            total_cached = sum(i['stats']['cached'] for i in items)
            total_combined = total_in + total_out
            avg_pct = sum(i['stats']['percent_used'] for i in items) / len(items)

            stats_grid = ctk.CTkFrame(card, fg_color="transparent")
            stats_grid.pack(fill="x", padx=15, pady=(0, 10))
            stats_grid.grid_columnconfigure((0, 1), weight=1)

            def add_mini_stat(row, col, label, val):
                f = ctk.CTkFrame(stats_grid, fg_color="transparent")
                f.grid(row=row, column=col, sticky="w", pady=2)
                ctk.CTkLabel(f, text=f"{label}: ", font=("Inter", 9), text_color=Theme.TEXT_MUTED).pack(side="left")
                ctk.CTkLabel(f, text=self._format_compact(val), font=("Inter", 10, "bold"), text_color=Theme.TEXT_MAIN).pack(side="left")

            add_mini_stat(0, 0, "INPUT", total_in)
            add_mini_stat(0, 1, "OUTPUT", total_out)
            add_mini_stat(1, 0, "CACHED", total_cached)
            add_mini_stat(1, 1, "COMBINED", total_combined)

            # Progress Bar
            ctk.CTkLabel(card, text=f"AVG USAGE: {avg_pct:.1f}%", font=("Inter", 9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w", padx=15)
            pbar = ctk.CTkProgressBar(card, height=8, progress_color=Theme.get_status_color(avg_pct), fg_color="#000000")
            pbar.set(avg_pct / 100.0)
            pbar.pack(fill="x", padx=15, pady=(2, 12))

            # Collapsible Session List (Click card to show/hide)
            sessions_sublist = ctk.CTkFrame(card, fg_color="transparent")
            # sessions_sublist.pack(fill="x", padx=10, pady=(0, 10)) # Pack on click
            
            # Use a toggle state
            card.sessions_visible = False
            card.sublist = sessions_sublist
            
            def toggle_sessions(e, c=card):
                if c.sessions_visible:
                    c.sublist.pack_forget()
                    c.sessions_visible = False
                else:
                    c.sublist.pack(fill="x", padx=10, pady=(0, 10))
                    c.sessions_visible = True
            
            card.bind("<Button-1>", toggle_sessions)
            header.bind("<Button-1>", toggle_sessions) # Bubbling doesn't always work in TK

            for item in items:
                row = self._create_session_row(sessions_sublist, item['meta'], False, self.models_detail_panel, is_sub=True)

    def _create_session_row(self, parent, s, is_latest, detail_panel, is_sub=False) -> ctk.CTkFrame:
        bg = "#1A1A1A" if is_latest else "transparent"
        border = 1 if is_latest else 0
        h = 45 if is_sub else 55
        
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=6, height=h, border_width=border, border_color=Theme.COLOR_NORMAL)
        row.pack(fill="x", pady=2, padx=5)
        row.pack_propagate(False)
        row.configure(cursor="hand2")
        row.bind("<Button-1>", lambda e, session=s: self._show_session_detail(session, detail_panel))
        
        name = s.get('name', 'Unknown')
        disp_name = name if len(name) <= (25 if is_sub else 32) else name[:22 if is_sub else 29] + "..."
        
        lbl_name = ctk.CTkLabel(row, text=disp_name, font=("Inter", 11 if is_sub else 12, "bold"), text_color=Theme.TEXT_MAIN)
        lbl_name.pack(side="left", padx=15)
        lbl_name.bind("<Button-1>", lambda e, session=s: self._show_session_detail(session, detail_panel))
        
        if not is_sub:
            mtime_str = time.strftime("%b %d, %H:%M", time.localtime(s.get('mtime', 0)))
            lbl_info = ctk.CTkLabel(row, text=mtime_str, font=("Inter", 10), text_color=Theme.TEXT_MUTED)
            lbl_info.pack(side="right", padx=15)
            lbl_info.bind("<Button-1>", lambda e, session=s: self._show_session_detail(session, detail_panel))
        return row

    def _show_session_detail(self, session_meta: Dict[str, Any], detail_panel):
        detail_panel.empty_lbl.place_forget()
        for w in detail_panel.content.winfo_children(): w.destroy()
        detail_panel.content.pack(fill="both", expand=True, padx=20, pady=15)
        
        session_obj = session_reader.read_session(session_meta['path'])
        if not session_obj: return
        stats = calculator.calc_session_context(session_obj)
        if not stats: return

        top = ctk.CTkFrame(detail_panel.content, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=session_meta['name'], font=("Inter", 13, "bold"), text_color=Theme.TEXT_MAIN, wraplength=350, justify="left").pack(side="left")
        ctk.CTkLabel(top, text=f"Model: {stats['model']}", font=("Inter", 10), text_color=Theme.TEXT_MUTED).pack(side="right")

        ctk.CTkLabel(detail_panel.content, text=f"File: {session_meta.get('filename')}", font=("Inter", 9), text_color=Theme.TEXT_MUTED).pack(anchor="w", pady=(0, 5))
        
        pct = stats.get('percent_used', 0.0)
        color = Theme.get_status_color(pct)
        pbar = ctk.CTkProgressBar(detail_panel.content, height=10, progress_color=color, fg_color="#000000")
        pbar.set(pct/100.0)
        pbar.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(detail_panel.content, text=f"{stats['remaining']:,} remaining • {stats['used']:,} used ({pct:.1f}%)", font=("Inter", 10, "bold"), text_color=color).pack(anchor="w")

        tokens_frame = ctk.CTkFrame(detail_panel.content, fg_color="transparent")
        tokens_frame.pack(fill="x", pady=(12, 0))
        def add_stat(label, val):
            f = ctk.CTkFrame(tokens_frame, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkLabel(f, text=label, font=("Inter", 9, "bold"), text_color=Theme.TEXT_MUTED).pack()
            ctk.CTkLabel(f, text=f"{val:,}", font=("Inter", 12, "bold"), text_color=Theme.TEXT_MAIN).pack()
        add_stat("INPUT", stats['input'])
        add_stat("OUTPUT", stats['output'])
        add_stat("CACHED", stats['cached'])

    def _create_metric_card(self, parent: ctk.CTkFrame, title: str, value: str, row: int, col: int, is_dominant: bool = False):
        bg = Theme.BG_CARD_ACCENT if is_dominant else Theme.BG_CARD
        border_width = 1 if is_dominant else 0
        border_color = Theme.COLOR_NORMAL if is_dominant else None
        card = ctk.CTkFrame(parent, fg_color=bg, corner_radius=10, border_width=border_width, border_color=border_color)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        ctk.CTkLabel(card, text=title, font=("Inter", 9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w", padx=15, pady=(12, 0))
        val_font = ("Inter", 28, "bold") if is_dominant else ("Inter", 24, "bold")
        lbl_val = ctk.CTkLabel(card, text=value, font=val_font, text_color=Theme.TEXT_MAIN)
        lbl_val.pack(anchor="w", padx=15, pady=(0, 12))
        return lbl_val, card

    def _update_ui_state(self, stats: Optional[Dict[str, Any]]):
        now_str = time.strftime("%I:%M:%S %p")
        self.lbl_last_updated.configure(text=f"LAST UPDATED: {now_str}")
        if not stats:
            self.status_badge.configure(text="OFFLINE", fg_color="#333333")
            self.progress_bar.set(0.0)
            for lbl in [self.card_limit, self.card_used, self.card_cached, self.card_remaining]: lbl.configure(text="0")
            return
        pct = stats.get('percent_used', 0.0)
        rem = stats.get('remaining', 0)
        color = Theme.get_status_color(pct)
        status_text = "NORMAL"
        if pct >= Theme.THRESH_CRITICAL: status_text = "CRITICAL"
        elif pct >= Theme.THRESH_CAUTION: status_text = "CAUTION"
        self.status_badge.configure(text=status_text, fg_color=color)
        self.lbl_model.configure(text=f"Model: {stats.get('model', 'Unknown')}")
        self.progress_bar.set(min(1.0, pct / 100.0))
        self.progress_bar.configure(progress_color=color)
        self.lbl_usage_summary.configure(text=f"{rem:,} tokens remaining · {pct:.1f}% used")
        self.card_limit.configure(text=f"{self._format_compact(stats.get('limit', 0))}")
        self.card_used.configure(text=f"{self._format_compact(stats.get('used', 0))}")
        self.card_cached.configure(text=f"{self._format_compact(stats.get('cached', 0))}")
        self.card_remaining.configure(text=f"{self._format_compact(rem)}")
        self.frame_remaining.configure(border_color=color)

    def _format_compact(self, num: int) -> str:
        if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
        if num >= 1_000: return f"{num/1_000:.1f}k"
        return str(num)

    def refresh_data(self):
        config_file = "config.json"
        session_dir = session_reader.get_session_dir(config_file)
        if not session_dir: return
        self.session_data_list = session_reader.list_sessions(session_dir)
        self.session_data_list.sort(key=lambda x: x['mtime'], reverse=True)
        target = session_reader.get_latest_session(session_dir)
        if target:
            sobj = session_reader.read_session(target)
            if sobj:
                stats = calculator.calc_session_context(sobj)
                self._update_ui_state(stats)
        if self.active_view == "sessions": self._update_sessions_list()
        elif self.active_view == "models": self._update_models_list()

    def _auto_refresh_loop(self):
        if self.auto_refresh: self.refresh_data()
        self.after(self.refresh_interval, self._auto_refresh_loop)
