"""Sistema narrativo de Echoes (Fase 4).

Expone los componentes principales para ser importados desde Game.py
y otros modulos del proyecto.
"""

from narrative.cinematics import CinematicSystem, Cinematica
from narrative.dialogue_system import DialogueBox, DialogueSystem
from narrative.npc import NPC
from narrative.narrative_manager import NarrativeManager

__all__ = [
    "CinematicSystem",
    "Cinematica",
    "DialogueBox",
    "DialogueSystem",
    "NPC",
    "NarrativeManager",
]
