"""Modulos de accesibilidad para Echoes (Fase 5).

Expone los componentes principales para ser importados desde Game.py
y otros modulos del proyecto.
"""

from accessibility.subtitles     import SubtitleSystem
from accessibility.visual_alerts import VisualAlertSystem
from accessibility.color_settings import ColorSettings
from accessibility.help_screen   import HelpScreen
from accessibility.crash_guard   import safe_call, CrashGuard, ErrorOverlay

__all__ = [
    "SubtitleSystem",
    "VisualAlertSystem",
    "ColorSettings",
    "HelpScreen",
    "safe_call",
    "CrashGuard",
    "ErrorOverlay",
]
