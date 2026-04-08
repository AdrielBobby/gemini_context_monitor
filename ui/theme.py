class Theme:
    # Colors
    BG_DARK = "#050505"
    BG_CARD = "#121212"      # Increased contrast from BG_DARK
    BG_CARD_ACCENT = "#1A1A1A" # Even lighter for dominant metric (Remaining)
    TEXT_MAIN = "#ffffff"
    TEXT_MUTED = "#707070"    # More muted
    
    # Progress Bar / Status Colors
    COLOR_NORMAL = "#7B3FE4"   # Adjusted Purple
    COLOR_CAUTION = "#F59E0B"  # Amber
    COLOR_CRITICAL = "#EF4444" # Red
    
    # Thresholds
    THRESH_CAUTION = 70.0
    THRESH_CRITICAL = 90.0

    @staticmethod
    def get_status_color(percentage: float) -> str:
        if percentage >= Theme.THRESH_CRITICAL:
            return Theme.COLOR_CRITICAL
        elif percentage >= Theme.THRESH_CAUTION:
            return Theme.COLOR_CAUTION
        return Theme.COLOR_NORMAL
