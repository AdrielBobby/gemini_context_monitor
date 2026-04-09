import customtkinter as ctk
import time
import os
from typing import Dict, Any, Optional, List

from core import session_reader, calculator, monitor_service
from core.model_summary import ModelSummary
from ui.theme import Theme

class ContextMonitorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # App Configuration
        self.title("Gemini Context Monitor")
        self.geometry("680x480")
        self.minsize(520, 420)  # Never shrink below usable size
        self.resizable(True, True)
        
        # Appearance
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=Theme.BG_DARK)
        
        # State
        self.auto_refresh = True
        self.refresh_interval = 10000
        self.session_data_list: List[Dict[str, Any]] = []
        self.active_view = "dash"
        self._resize_job: Optional[str] = None  # after() id for resize debounce
        
        self._build_ui()
        self.refresh_data()
        self._auto_refresh_loop()
        
        # Bind AFTER build so all frames exist
        self.bind("<Configure>", self._on_window_configure)

    def _build_ui(self):
        # 1. Navigation / Tab Header
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=20, pady=(15, 10))
        
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
        
        self.lbl_last_updated = ctk.CTkLabel(self.footer_frame, text="last updated · never", font=(Theme.FONT_SANS, 9), text_color=Theme.TEXT_DIM)
        self.lbl_last_updated.pack(side="left")

        self.btn_refresh = ctk.CTkButton(self.footer_frame, text="Refresh All", width=100, height=28, 
                                         font=(Theme.FONT_SANS, 11), 
                                         fg_color=Theme.BG_CARD, 
                                         hover_color="#1f1f1f", 
                                         border_width=0,
                                         command=self.refresh_data)
        self.btn_refresh.bind("<Enter>", lambda e: self.btn_refresh.configure(border_width=1, border_color=Theme.COLOR_NORMAL))
        self.btn_refresh.bind("<Leave>", lambda e: self.btn_refresh.configure(border_width=0))
        self.btn_refresh.pack(side="right")

    def _create_nav_btn(self, text: str, view_name: str) -> ctk.CTkButton:
        return ctk.CTkButton(self.nav_frame, text=text, width=110, height=34, 
                            corner_radius=12,
                            fg_color=Theme.BG_CARD, font=(Theme.FONT_SANS, 12, "bold"),
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

    def _title_case_model(self, model_name: str) -> str:
        if not model_name: return "Unknown"
        return model_name.replace("-", " ").replace("_", " ").title()

    def _build_dashboard_view(self):
        head = ctk.CTkFrame(self.view_dash, fg_color="transparent")
        head.pack(fill="x", pady=(12, 6))
        self.lbl_model = ctk.CTkLabel(head, text="Model: Unknown", font=(Theme.FONT_SANS, 13, "bold"), text_color=Theme.TEXT_MAIN)
        self.lbl_model.pack(side="left")
        
        # Status Badge (compact pill with dot)
        self.status_badge = ctk.CTkFrame(head, fg_color=Theme.BADGE_BG, corner_radius=12, height=28, border_width=1, border_color=Theme.COLOR_NORMAL)
        self.status_badge.pack(side="right", padx=(0, 10))
        self.status_badge.configure(width=130)
        self.status_badge.pack_propagate(False)
        
        self.status_dot = ctk.CTkLabel(self.status_badge, text="●", font=(Theme.FONT_SANS, 11), text_color=Theme.COLOR_GREEN, width=1, height=1)
        self.status_dot.pack(side="left", padx=(12, 0))
        
        self.status_text = ctk.CTkLabel(self.status_badge, text="Normal", font=(Theme.FONT_SANS, 11, "bold"), text_color=Theme.TEXT_MAIN, height=1)
        self.status_text.pack(side="left", padx=(6, 12))

        self.progress_bar = ctk.CTkProgressBar(self.view_dash, height=10, corner_radius=5, fg_color=Theme.PROGRESS_TRACK, progress_color=Theme.COLOR_NORMAL)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(10, 0))

        self.lbl_usage_summary = ctk.CTkLabel(self.view_dash, text="0 tokens remaining · 0% used", font=(Theme.FONT_SANS, 10), text_color=Theme.TEXT_MUTED)
        self.lbl_usage_summary.pack(anchor="w", pady=(4, 12))

        grid = ctk.CTkFrame(self.view_dash, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 10))
        grid.grid_columnconfigure((0, 1), weight=1)
        grid.grid_rowconfigure((0, 1), weight=0)  # Rows do NOT stretch
        
        self.card_remaining, self.lbl_rem_sub, self.frame_remaining = self._create_metric_card(grid, "REMAINING", "0", 0, 0, is_dominant=True, sub_text="of 0 total")
        self.card_used, self.lbl_used_sub, _ = self._create_metric_card(grid, "USED TOKENS", "0", 0, 1, sub_text="last turn")
        self.card_cached, self.lbl_cached_sub, _ = self._create_metric_card(grid, "CACHED", "0", 1, 0, sub_text="active cache")
        self.card_limit, self.lbl_limit_sub, _ = self._create_metric_card(grid, "TOTAL LIMIT", "0", 1, 1, sub_text="context window")

    def _build_sessions_view(self):
        self.view_sessions.grid_columnconfigure(0, weight=1)
        self.view_sessions.grid_rowconfigure(0, weight=3) # List
        self.view_sessions.grid_rowconfigure(1, weight=2) # Details

        self.list_frame = ctk.CTkScrollableFrame(self.view_sessions, fg_color=Theme.BG_CARD, corner_radius=10, 
                                                 label_text="Active Sessions", label_font=(Theme.FONT_SANS, 11, "bold"), 
                                                 label_text_color=Theme.TEXT_MUTED)
        self.list_frame.grid(row=0, column=0, sticky="nsew", pady=(10, 5))
        self._setup_scroll_binding(self.list_frame)  # Set up once here, not after every list update
        
        self.detail_panel = self._create_detail_panel(self.view_sessions, 1, 0)

    def _build_models_view(self):
        self.view_models.grid_columnconfigure(0, weight=1)
        self.view_models.grid_rowconfigure(0, weight=1)  # Models list fills all space

        self.models_list = ctk.CTkScrollableFrame(self.view_models, fg_color=Theme.BG_CARD, corner_radius=10, 
                                                 label_text="Models Breakdown", label_font=(Theme.FONT_SANS, 11, "bold"),
                                                 label_text_color=Theme.TEXT_MUTED)
        self.models_list.grid(row=0, column=0, sticky="nsew", pady=(10, 10))
        self._setup_scroll_binding(self.models_list)  # Set up once here, not after every list update
        
        # No detail panel here — Models view shows aggregated stats only

    def _create_detail_panel(self, parent, row, col):
        panel = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD_ACCENT, corner_radius=10, border_width=1, border_color="#333333")
        panel.grid(row=row, column=col, sticky="nsew", pady=(5, 10))
        
        empty_lbl = ctk.CTkLabel(panel, text="Select a session to view details", font=(Theme.FONT_SANS, 12), text_color=Theme.TEXT_MUTED)
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
        else:
            for i, s in enumerate(self.session_data_list):
                self._create_session_row(self.list_frame, s, i == 0, self.detail_panel)
        self._rebind_scroll_children(self.list_frame)

    def _update_models_list(self):
        for widget in self.models_list.winfo_children():
            widget.destroy()

        summaries = monitor_service.get_all_models(self.session_data_list)

        active = [s for s in summaries if s.has_sessions]
        inactive = [s for s in summaries if not s.has_sessions]
        show_dividers = bool(active and inactive)

        if not summaries:
            ctk.CTkLabel(self.models_list, text="No models found",
                         font=(Theme.FONT_SANS, 12), text_color=Theme.TEXT_MUTED).pack(pady=20)
            return

        # ── Active models section ────────────────────────────────────────────
        if show_dividers:
            self._render_section_divider("Active Models")
        for summary in active:
            self._render_model_card(summary)

        # ── Inactive models section ──────────────────────────────────────────
        if show_dividers and inactive:
            self._render_section_divider("Other Models")
        for summary in inactive:
            self._render_model_card(summary)

        # Re-bind scroll on all freshly created child widgets
        self._rebind_scroll_children(self.models_list)

    def _setup_scroll_binding(self, scroll_frame: ctk.CTkScrollableFrame):
        """Bind mousewheel on the canvas directly — set up once, never removed.
        Also stores the callback so _rebind_scroll_children can reuse it after list rebuilds."""
        canvas = scroll_frame._parent_canvas

        def _on_scroll(event):
            canvas.yview_scroll(int(-3 * (event.delta / 120)), "units")

        # Store for later use when children are recreated
        scroll_frame._scroll_fn = _on_scroll
        # Bind on the canvas — fires when cursor is over any empty space
        canvas.bind("<MouseWheel>", _on_scroll, add="+")

    def _rebind_scroll_children(self, scroll_frame: ctk.CTkScrollableFrame):
        """After rebuilding list contents, bind mousewheel on every child widget
        so scrolling works when the cursor is over a card/label rather than the canvas."""
        fn = getattr(scroll_frame, "_scroll_fn", None)
        if not fn:
            return

        def _bind_tree(widget):
            widget.bind("<MouseWheel>", fn, add="+")
            for child in widget.winfo_children():
                _bind_tree(child)

        _bind_tree(scroll_frame)

    def _render_section_divider(self, label: str):
        """Renders a thin muted section header divider inside the models list."""
        row = ctk.CTkFrame(self.models_list, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(10, 2))

        ctk.CTkLabel(row, text=label.upper(),
                     font=(Theme.FONT_SANS, 9, "bold"),
                     text_color=Theme.TEXT_DIM).pack(side="left", padx=4)
        line = ctk.CTkFrame(row, fg_color="#2a2a2a", height=1)
        line.pack(side="left", fill="x", expand=True, padx=(6, 4), pady=6)

    def _render_model_card(self, summary: ModelSummary):
        """Renders a model card. Active cards show full stats; inactive show greyed state.
        Widget count is kept intentionally low to avoid CTk resize-lag with many cards."""
        is_active = summary.has_sessions
        bg           = Theme.BG_CARD_ACCENT if is_active else "#111111"
        name_color   = Theme.COLOR_NORMAL   if is_active else "#5a3d87"
        text_color   = Theme.TEXT_MAIN      if is_active else Theme.TEXT_DIM
        muted_color  = Theme.TEXT_MUTED     if is_active else Theme.TEXT_DIM
        border_color = "#222"               if is_active else "#191919"

        card = ctk.CTkFrame(self.models_list, fg_color=bg, corner_radius=12,
                            border_width=1, border_color=border_color)
        card.pack(fill="x", padx=10, pady=4)

        # ── Header: name · meta pill · session count (right) ─────────────────
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))

        ctk.CTkLabel(header, text=summary.display_name,
                     font=(Theme.FONT_SANS, 13, "bold"),
                     text_color=name_color).pack(side="left")

        meta_text = f"{self._format_compact(summary.context_limit)} ctx · {summary.tier}"
        ctk.CTkLabel(header, text=meta_text, font=(Theme.FONT_MONO, 9),
                     text_color=muted_color, fg_color="#1a1a1a",
                     corner_radius=6, padx=6).pack(side="left", padx=8)

        count_text = f"{summary.session_count} session{'s' if summary.session_count != 1 else ''}"
        ctk.CTkLabel(header, text=count_text, font=(Theme.FONT_SANS, 10),
                     text_color=muted_color, fg_color="#1a1a1a",
                     corner_radius=6, padx=8).pack(side="right")

        if not is_active:
            ctk.CTkLabel(card, text="No recent sessions",
                         font=(Theme.FONT_SANS, 11, "italic"),
                         text_color="#3a3a3a").pack(pady=(2, 12))
            return

        # ── Stats: two plain text rows instead of a nested grid of frames ────────
        def fmt(n): return f"{n:,}"
        row1 = (f"INPUT  {fmt(summary.total_input):<12}  "
                f"OUTPUT  {fmt(summary.total_output)}")
        row2 = (f"CACHED  {fmt(summary.total_cached):<11}  "
                f"COMBINED  {fmt(summary.total_combined)}")

        ctk.CTkLabel(card, text=row1, font=(Theme.FONT_MONO, 10),
                     text_color=text_color, anchor="w").pack(fill="x", padx=16, pady=(0, 2))
        ctk.CTkLabel(card, text=row2, font=(Theme.FONT_MONO, 10),
                     text_color=text_color, anchor="w").pack(fill="x", padx=16)

        # ── Progress bar + footer line ─────────────────────────────────────
        ctk.CTkFrame(card, fg_color="#1e1e1e", height=1).pack(fill="x", padx=14, pady=(8, 4))

        pbar = ctk.CTkProgressBar(card, height=7, corner_radius=3,
                                  progress_color=Theme.get_status_color(summary.avg_usage_pct),
                                  fg_color=Theme.PROGRESS_TRACK)
        pbar.set(summary.avg_usage_pct / 100.0)
        pbar.pack(fill="x", padx=14, pady=(0, 4))

        footer = (f"AVG USAGE: {summary.avg_usage_pct:.1f}%     "
                  f"Last active: {summary.last_active}")
        ctk.CTkLabel(card, text=footer, font=(Theme.FONT_SANS, 9),
                     text_color=Theme.TEXT_DIM, anchor="w"
                     ).pack(fill="x", padx=14, pady=(0, 10))

    def _create_session_row(self, parent, s, is_latest, detail_panel, is_sub=False) -> ctk.CTkFrame:
        bg = "#1A1A1A" if is_latest else "transparent"
        border = 1 if is_latest else 0
        h = 45 if is_sub else 55
        
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=8, height=h, border_width=border, border_color=Theme.COLOR_NORMAL)
        row.pack(fill="x", pady=2, padx=5)
        row.pack_propagate(False)
        row.configure(cursor="hand2")
        
        # Hover effect
        row.bind("<Enter>", lambda e: row.configure(fg_color="#1f1f1f" if not is_latest else "#1A1A1A"))
        row.bind("<Leave>", lambda e: row.configure(fg_color="transparent" if not is_latest else "#1A1A1A"))

        row.bind("<Button-1>", lambda e, session=s: self._show_session_detail(session, detail_panel))
        
        name = s.get('name', 'Unknown')
        disp_name = name if len(name) <= (25 if is_sub else 32) else name[:22 if is_sub else 29] + "..."
        
        lbl_name = ctk.CTkLabel(row, text=disp_name, font=(Theme.FONT_SANS, 11 if is_sub else 12, "bold"), text_color=Theme.TEXT_MAIN)
        lbl_name.pack(side="left", padx=15)
        lbl_name.bind("<Button-1>", lambda e, session=s: self._show_session_detail(session, detail_panel))
        
        if not is_sub:
            mtime_str = time.strftime("%b %d, %H:%M", time.localtime(s.get('mtime', 0)))
            lbl_info = ctk.CTkLabel(row, text=mtime_str, font=(Theme.FONT_SANS, 10), text_color=Theme.TEXT_MUTED)
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
        ctk.CTkLabel(top, text=session_meta['name'], font=(Theme.FONT_SANS, 16, "bold"), text_color=Theme.TEXT_MAIN, wraplength=350, justify="left").pack(side="left")
        ctk.CTkLabel(top, text=self._title_case_model(stats['model']), font=(Theme.FONT_MONO, 10), text_color=Theme.TEXT_MUTED).pack(side="right")

        ctk.CTkLabel(detail_panel.content, text=session_meta.get('filename', 'Unknown'), font=(Theme.FONT_SANS, 9), text_color=Theme.TEXT_DIM).pack(anchor="w", pady=(0, 5))
        
        pct = stats.get('percent_used', 0.0)
        color = Theme.get_status_color(pct)
        pbar = ctk.CTkProgressBar(detail_panel.content, height=12, corner_radius=6, progress_color=color, fg_color=Theme.PROGRESS_TRACK)
        pbar.set(pct/100.0)
        pbar.pack(fill="x", pady=(8, 4))
        
        info_text = f"{stats['remaining']:,} remaining • {stats['used']:,} used ({pct:.1f}%)"
        ctk.CTkLabel(detail_panel.content, text=info_text, font=(Theme.FONT_SANS, 10, "bold"), text_color=color).pack(anchor="w")

        tokens_frame = ctk.CTkFrame(detail_panel.content, fg_color="transparent")
        tokens_frame.pack(fill="x", pady=(15, 0))
        def add_stat(label, val):
            f = ctk.CTkFrame(tokens_frame, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkLabel(f, text=label, font=(Theme.FONT_SANS, 9, "bold"), text_color=Theme.TEXT_MUTED).pack()
            ctk.CTkLabel(f, text=f"{val:,}", font=(Theme.FONT_MONO, 12, "bold"), text_color=Theme.TEXT_MAIN).pack()
        add_stat("INPUT", stats['input'])
        add_stat("OUTPUT", stats['output'])
        add_stat("CACHED", stats['cached'])

    def _create_metric_card(self, parent: ctk.CTkFrame, title: str, value: str, row: int, col: int, is_dominant: bool = False, sub_text: str = ""):
        bg = Theme.BG_CARD
        # Fixed height card — never expands vertically
        card = ctk.CTkFrame(parent, fg_color=bg, corner_radius=10, height=84)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="ew")  # ew only, no vertical stretch
        card.pack_propagate(False)
        card.grid_propagate(False)
        
        # Left accent bar for dominant card
        if is_dominant:
            accent = ctk.CTkFrame(card, fg_color=Theme.COLOR_NORMAL, width=3, corner_radius=0)
            accent.place(x=0, y=0, relheight=1.0)  # use place so it doesn't affect layout
            card.accent = accent

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", padx=(16 if is_dominant else 12, 12), pady=10)

        ctk.CTkLabel(inner, text=title.upper(), font=(Theme.FONT_SANS, 9, "bold"), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        
        lbl_val = ctk.CTkLabel(inner, text=value, font=(Theme.FONT_MONO, 20, "bold"), text_color=Theme.TEXT_MAIN)
        lbl_val.pack(anchor="w", pady=(1, 0))
        
        lbl_sub = ctk.CTkLabel(inner, text=sub_text, font=(Theme.FONT_SANS, 9), text_color=Theme.TEXT_DIM)
        lbl_sub.pack(anchor="w")
        
        return lbl_val, lbl_sub, card

    def _update_ui_state(self, stats: Optional[Dict[str, Any]]):
        now_str = time.strftime("%I:%M:%S %p")
        self.lbl_last_updated.configure(text=f"last updated · {now_str}")
        if not stats:
            self.status_text.configure(text="Offline")
            self.status_dot.configure(text_color=Theme.TEXT_DIM)
            self.status_badge.configure(border_color=Theme.TEXT_DIM)
            self.progress_bar.set(0.0)
            for lbl in [self.card_limit, self.card_used, self.card_cached, self.card_remaining]: lbl.configure(text="0")
            return
            
        pct = stats.get('percent_used', 0.0)
        rem = stats.get('remaining', 0)
        limit = stats.get('limit', 0)
        color = Theme.get_status_color(pct)
        
        status_text = "Normal"
        dot_color = Theme.COLOR_GREEN
        if pct >= Theme.THRESH_CRITICAL: 
            status_text = "Critical"
            dot_color = Theme.COLOR_CRITICAL
        elif pct >= Theme.THRESH_CAUTION: 
            status_text = "Caution"
            dot_color = Theme.COLOR_CAUTION
            
        self.status_text.configure(text=status_text)
        self.status_dot.configure(text_color=dot_color)
        self.status_badge.configure(border_color=dot_color)
        
        self.lbl_model.configure(text=f"Model: {self._title_case_model(stats.get('model', ''))}")
        self.progress_bar.set(min(1.0, pct / 100.0))
        self.progress_bar.configure(progress_color=color)
        self.lbl_usage_summary.configure(text=f"{rem:,} remaining · {pct:.1f}% used")
        
        self.card_limit.configure(text=f"{self._format_compact(limit)}")
        self.card_used.configure(text=f"{self._format_compact(stats.get('used', 0))}")
        self.card_cached.configure(text=f"{self._format_compact(stats.get('cached', 0))}")
        self.card_remaining.configure(text=f"{self._format_compact(rem)}")
        
        self.lbl_rem_sub.configure(text=f"of {self._format_compact(limit)} total")
        self.lbl_limit_sub.configure(text="context window")
        self.frame_remaining.accent.configure(fg_color=color)

    def _format_compact(self, num: int) -> str:
        if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
        if num >= 1_000: return f"{num/1_000:.1f}k"
        return str(num)

    # ── Resize debounce ──────────────────────────────────────────────────────

    def _on_window_configure(self, event):
        """Fired on every pixel of a window drag. Hide the active scroll frame
        immediately to stop the Configure cascade through ~50 child CTk widgets,
        then restore it 150 ms after the drag settles."""
        if event.widget is not self:
            return  # Ignore child-widget Configure events
        if self.active_view == "dash":
            return  # Dashboard has no scroll frame — already fast

        if self._resize_job:
            self.after_cancel(self._resize_job)
        else:
            self._hide_active_scroll_frame()

        self._resize_job = self.after(150, self._restore_active_scroll_frame)

    def _hide_active_scroll_frame(self):
        """Remove the scroll frame from the layout manager (non-destructive)."""
        if self.active_view == "models":
            self.models_list.grid_remove()
        elif self.active_view == "sessions":
            self.list_frame.grid_remove()

    def _restore_active_scroll_frame(self):
        """Restore the scroll frame after resize settles."""
        self._resize_job = None
        if self.active_view == "models":
            self.models_list.grid()
        elif self.active_view == "sessions":
            self.list_frame.grid()

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
