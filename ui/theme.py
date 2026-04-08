class Theme:
    # Colors
    BG_DARK = "#050505"
    BG_CARD = "#121212"
    BG_CARD_ACCENT = "#1A1A1A"
    TEXT_MAIN = "#ffffff"
    TEXT_MUTED = "#707070"
    TEXT_DIM = "#404040"
    
    # UI Elements
    PROGRESS_TRACK = "#1e1e2e"
    BADGE_BG = "#1e1e1e"
    
    # Progress Bar / Status Colors
    COLOR_NORMAL = "#8b5cf6"   # Vibrant Violet
    COLOR_CAUTION = "#F59E0B"  # Amber
    COLOR_CRITICAL = "#EF4444" # Red
    COLOR_GREEN = "#10B981"    # Green for dots
    
    # Thresholds
    THRESH_CAUTION = 70.0
    THRESH_CRITICAL = 90.0

    # Fonts
    FONT_MONO = "JetBrains Mono"
    FONT_SANS = "Inter"

    @staticmethod
    def get_status_color(percentage: float) -> str:
        if percentage >= Theme.THRESH_CRITICAL:
            return Theme.COLOR_CRITICAL
        elif percentage >= Theme.THRESH_CAUTION:
            return Theme.COLOR_CAUTION
        return Theme.COLOR_NORMAL
