# CODIGO/ui/Shop.py
"""
Sistema de tienda del juego Echoes.

Ofrece habilidades y mejoras al jugador a cambio de apoyo (moneda).
El inventario es determinístico por seed para garantizar reproducibilidad.
"""
import random
from collections.abc import Callable
import pygame


class Shop:
    WIDTH, HEIGHT = 320, 240
    MAX_ITEMS = 6

    def __init__(self, font=None, on_gold_spent: Callable[[int], None] | None = None):
        # Catálogo completo de habilidades y mejoras disponibles en Echoes.
        # Cada entrada tiene: nombre (visible), precio, tipo, id, peso de aparición, descripción.
        self.catalog = [
            # --- Habilidades (ocupan el slot de arma activa) ---
            {"name": "Bloqueo",          "price": 58,  "type": "weapon",     "id": "bloqueo",        "weight": 1.0, "desc": "Paras los ataques entrantes.\nReduce daño recibido."},
            {"name": "Reportar",         "price": 82,  "type": "weapon",     "id": "reportar",       "weight": 0.8, "desc": "Marca enemigos para eliminarlos.\nMayor velocidad de ataque."},
            {"name": "Apoyo de un amigo","price": 95,  "type": "weapon",     "id": "apoyo_amigo",    "weight": 0.6, "desc": "Ataque que heala aliados.\nFortalece a compañeros cercanos."},
            {"name": "Pausa digital",    "price": 108, "type": "weapon",     "id": "pausa_digital",  "weight": 0.6, "desc": "Congela enemigos brevemente.\nDa tiempo para reagruparse."},
            {"name": "Autoestima",       "price": 78,  "type": "weapon",     "id": "autoestima",     "weight": 0.6, "desc": "Aumenta defensa personal.\nReduce miedo y estrés."},
            {"name": "Evidencia",        "price": 104, "type": "weapon",     "id": "evidencia",      "weight": 0.5, "desc": "Recopila pruebas contra acosadores.\nDaño crítico a enemigos especiales."},
            # --- Mejoras permanentes ---
            {"name": "Vida extra (+1)",            "price": 45, "type": "upgrade",    "id": "hp_up",       "weight": 4, "desc": "Aumenta tu resistencia física.\n+1 máximo HP."},
            {"name": "Mayor resistencia (+5%)",    "price": 30, "type": "upgrade",    "id": "spd_up",      "weight": 3, "desc": "Mejora tu velocidad de movimiento.\n+5% velocidad."},
            {"name": "Escudo reforzado (+1 golpe)","price": 60, "type": "upgrade",    "id": "armor_up",    "weight": 2, "desc": "Fortalece tu defensa.\n+1 al blindaje."},
            {"name": "Enfriamiento rápido (-10%)", "price": 54, "type": "upgrade",    "id": "cdr_charm",   "weight": 3, "desc": "Reduce tiempo entre ataques.\n-10% cooldown de armas."},
            {"name": "Concentración (-12% cd)",    "price": 72, "type": "upgrade",    "id": "cdr_core",    "weight": 2, "desc": "Mejora precisión y enfoque.\n-12% cooldown de habilidades."},
            {"name": "Reflejos (+10% sprint)",     "price": 48, "type": "upgrade",    "id": "sprint_core", "weight": 3, "desc": "Aumenta tu agilidad.\n+10% velocidad de sprint."},
            {"name": "Evasión (-15% cooldown)",    "price": 66, "type": "upgrade",    "id": "dash_core",   "weight": 2, "desc": "Mejora tus esquivas.\n-15% cooldown de dash."},
            {"name": "Impulso (+duración evasión)","price": 56, "type": "upgrade",    "id": "dash_drive",  "weight": 2, "desc": "Prolonga tu invulnerabilidad.\n+0.08s duración de dash."},
            # --- Consumibles ---
            {"name": "Apoyo emocional (+2 HP)",    "price": 28, "type": "consumable", "id": "heal_medium", "amount": 2, "weight": 4, "desc": "Restaura 2 puntos de vida.\nUsable una vez."},
            {"name": "Descanso completo (HP full)", "price": 90, "type": "consumable", "id": "heal_full",   "weight": 1, "desc": "Restaura toda tu vida.\nUsable una vez."},
            # --- Paquetes ---
            {
                "name": "Kit de supervivencia",
                "price": 62,
                "type": "bundle",
                "contents": [
                    {"type": "gold",        "amount": 45},
                    {"type": "consumable",  "id": "heal_small", "amount": 1},
                    {"type": "upgrade",     "id": "spd_up"},
                ],
                "weight": 2,
                "desc": "Pack para empezar fuerte.\nOro + curacion + velocidad.",
            },
            {
                "name": "Paquete de apoyo",
                "price": 64,
                "type": "bundle",
                "contents": [
                    {"type": "gold",        "amount": 40},
                    {"type": "consumable",  "id": "heal_small", "amount": 1},
                    {"type": "upgrade",     "id": "cdr_charm"},
                ],
                "weight": 2,
                "desc": "Pack para combate sostenido.\nOro + curacion + recarga rápida.",
            },
        ]
        self.items: list[dict] = []
        self.active = False
        self.selected = 0
        self.hover_index = None
        self.font = font or pygame.font.SysFont(None, 18)
        self._on_gold_spent = on_gold_spent

        # rng propio para fijar inventario por seed
        self._seed: int | None = None
        self._rng = random.Random()
        self._inventory_generated = False

        # ventana
        self.rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self._item_hitboxes: list[pygame.Rect] = []

    # ------------------------------------------------------------------ #
    # Gestión del inventario
    # ------------------------------------------------------------------ #

    def configure_for_seed(self, seed: int | None) -> None:
        """Genera el inventario inicial usando una seed concreta."""
        self._seed = seed
        if seed is None:
            base_seed = random.randrange(1 << 30)
        else:
            base_seed = int(seed)
        self._rng = random.Random(base_seed ^ 0xBADC0FFE)
        self.items = self._build_inventory()
        self.selected = 0
        self.hover_index = None
        self._inventory_generated = True

    def rotate_inventory(self) -> None:
        """Compatibilidad: asegura que exista inventario pero no lo rerolla."""
        self.ensure_inventory()

    def ensure_inventory(self) -> None:
        if self.items or self._inventory_generated:
            return
        if self._seed is None:
            self.configure_for_seed(None)
        else:
            self.configure_for_seed(self._seed)

    def _build_inventory(self) -> list[dict]:
        available = list(self.catalog)
        weights   = [float(entry.get("weight", 1.0)) for entry in available]
        items: list[dict] = []
        while available and len(items) < self.MAX_ITEMS:
            choice = self._rng.choices(available, weights=weights, k=1)[0]
            idx    = available.index(choice)
            entry  = {k: v for k, v in choice.items() if k != "weight"}
            items.append(entry)
            available.pop(idx)
            weights.pop(idx)
        if not items:
            items = [{k: v for k, v in e.items() if k != "weight"} for e in self.catalog]
        return items

    # ------------------------------------------------------------------ #
    # Control de visibilidad
    # ------------------------------------------------------------------ #

    def open(self, cx, cy):
        self.ensure_inventory()
        self.active = True
        self.rect.center = (cx, cy)
        self.hover_index = None
        if self.items:
            self.selected = min(self.selected, len(self.items) - 1)
        else:
            self.selected = 0

    def close(self):
        self.active = False
        self.hover_index = None

    # ------------------------------------------------------------------ #
    # Interacción con el jugador
    # ------------------------------------------------------------------ #

    def update_hover(self, mouse_pos):
        if not self.active:
            self.hover_index = None
            return
        self.hover_index = None
        for idx, rect in enumerate(self._item_hitboxes):
            if rect.collidepoint(mouse_pos):
                self.hover_index = idx
                self.selected    = idx
                break

    def handle_click(self, mouse_pos, player):
        """Procesa un click izquierdo dentro de la tienda."""
        if not self.active:
            return False, ""
        if not self.rect.collidepoint(mouse_pos):
            self.close()
            return False, ""
        for idx, rect in enumerate(self._item_hitboxes):
            if rect.collidepoint(mouse_pos):
                if self.selected != idx:
                    self.selected    = idx
                    self.hover_index = idx
                    return False, ""
                return self.try_buy(player)
        return False, ""

    def move_selection(self, dy):
        if not self.active or not self.items:
            return
        self.selected    = (self.selected + dy) % len(self.items)
        self.hover_index = self.selected

    def try_buy(self, player):
        """Aplica compra si hay apoyo suficiente. Retorna (comprado: bool, msg: str)."""
        if not self.active or not self.items:
            return False, ""
        item  = self.items[self.selected]
        price = max(0, int(item.get("price", 0)))
        gold  = getattr(player, "gold", 0)
        if gold < price:
            return False, "No tienes suficiente apoyo."

        if item["type"] == "weapon" and hasattr(player, "has_weapon"):
            if player.has_weapon(item["id"]):
                return False, "Ya tienes esta habilidad."

        # Cobro
        setattr(player, "gold", gold - price)
        if price > 0 and callable(self._on_gold_spent):
            try:
                self._on_gold_spent(price)
            except Exception:
                pass

        # Aplicación del efecto
        if item["type"] == "weapon":
            self._apply_weapon(player, item["id"])
        elif item["type"] == "upgrade":
            self._apply_upgrade(player, item["id"])
        elif item["type"] == "consumable":
            self._apply_consumable(player, item.get("id"), item)
        elif item["type"] == "bundle":
            self._apply_bundle(player, item)
        elif item["type"] == "gold":
            self._apply_gold(player, item.get("amount", 0))
        elif item["type"] == "heal":
            self._heal_player(player, int(item.get("amount", 0)))

        name = item.get("name", "Artículo")
        self.items.pop(self.selected)
        if self.items:
            self.selected %= len(self.items)
            self.hover_index = self.selected
        else:
            self.selected    = 0
            self.hover_index = None
        return True, f"Adquiriste: {name}"

    # ------------------------------------------------------------------ #
    # Efectos concretos de cada tipo de ítem
    # ------------------------------------------------------------------ #

    def _apply_weapon(self, player, wid):
        unlock = getattr(player, "unlock_weapon", None)
        if callable(unlock):
            return bool(unlock(wid, auto_equip=True))
        equip = getattr(player, "equip_weapon", None)
        if callable(equip):
            equip(wid)
            return True
        setattr(player, "current_weapon", wid)
        return True

    def _apply_upgrade(self, player, uid):
        register     = getattr(player, "register_upgrade", None)
        has_upgrade  = getattr(player, "has_upgrade", None)
        set_modifier = getattr(player, "set_cooldown_modifier", None)

        if uid == "hp_up":
            max_lives = getattr(player, "max_lives", getattr(player, "lives", 1))
            lives     = getattr(player, "lives", max_lives)
            max_lives += 1
            lives = min(lives + 1, max_lives)
            setattr(player, "max_lives", max_lives)
            setattr(player, "lives", lives)
            if callable(register): register(uid)
            return True

        if uid == "spd_up":
            speed = getattr(player, "speed", 1.0)
            setattr(player, "speed", speed * 1.05)
            if callable(register): register(uid)
            return True

        if uid == "armor_up":
            max_hp = getattr(player, "max_hp", getattr(player, "hp", 3))
            hp     = getattr(player, "hp", max_hp)
            max_hp += 1
            hp = min(hp + 1, max_hp)
            setattr(player, "max_hp", max_hp)
            setattr(player, "hp", hp)
            if hasattr(player, "_hits_taken_current_life"):
                setattr(player, "_hits_taken_current_life", max(0, max_hp - hp))
            if callable(register): register(uid)
            return True

        if uid == "cdr_charm":
            core_active = callable(has_upgrade) and has_upgrade("cdr_core")
            multiplier  = 0.94 if core_active else 0.9
            if callable(register): register(uid)
            if callable(set_modifier):
                set_modifier(uid, multiplier)
            else:
                current   = getattr(player, "cooldown_scale", 1.0)
                new_scale = max(0.35, current * multiplier)
                setattr(player, "cooldown_scale", new_scale)
                refresher = getattr(player, "refresh_weapon_modifiers", None)
                if callable(refresher): refresher()
            return True

        if uid == "cdr_core":
            charm_active = callable(has_upgrade) and has_upgrade("cdr_charm")
            if callable(register): register(uid)
            if callable(set_modifier):
                set_modifier(uid, 0.88)
                if charm_active: set_modifier("cdr_charm", 0.94)
            else:
                current   = getattr(player, "cooldown_scale", 1.0)
                new_scale = max(0.35, current * 0.88)
                setattr(player, "cooldown_scale", new_scale)
                refresher = getattr(player, "refresh_weapon_modifiers", None)
                if callable(refresher): refresher()
            return True

        if uid == "sprint_core":
            sprint = getattr(player, "sprint_multiplier", 1.0)
            setattr(player, "sprint_multiplier", sprint * 1.1)
            speed  = getattr(player, "speed", 1.0)
            setattr(player, "speed", speed * 1.03)
            if hasattr(player, "sprint_control_bonus"):
                player.sprint_control_bonus = max(getattr(player, "sprint_control_bonus", 0.0), 0.15)
            if callable(register): register(uid)
            return True

        if uid == "dash_core":
            cooldown = getattr(player, "dash_cooldown", 0.75)
            setattr(player, "dash_cooldown", max(0.25, cooldown * 0.85))
            if callable(register): register(uid)
            return True

        if uid == "dash_drive":
            duration = getattr(player, "dash_duration", 0.18)
            new_duration = min(0.6, duration + 0.08)
            setattr(player, "dash_duration", new_duration)
            if callable(register): register(uid)
            return True

        return False

    def _apply_consumable(self, player, cid, item) -> bool:
        if not cid:
            return False
        if cid == "heal_full":
            max_hp = getattr(player, "max_hp", getattr(player, "hp", 1))
            setattr(player, "hp", max_hp)
            if hasattr(player, "_hits_taken_current_life"):
                setattr(player, "_hits_taken_current_life", 0)
            return True
        if cid == "heal_medium":
            return self._heal_player(player, random.randint(2, 3))
        if cid == "heal_small":
            return self._heal_player(player, int(item.get("amount", 1) or 1))
        if cid == "life_refill":
            max_lives = getattr(player, "max_lives", getattr(player, "lives", 1))
            setattr(player, "lives", max_lives)
            return True
        return False

    def _apply_bundle(self, player, bundle: dict) -> bool:
        applied_any = False
        for entry in (bundle.get("contents") or []):
            if isinstance(entry, dict):
                applied_any = self._apply_reward_entry(player, entry) or applied_any
        return applied_any

    def _apply_reward_entry(self, player, entry: dict) -> bool:
        rtype = entry.get("type")
        if rtype == "gold":        return self._apply_gold(player, entry.get("amount", 0))
        if rtype == "heal":        return self._heal_player(player, int(entry.get("amount", 0)))
        if rtype == "upgrade":     return self._apply_upgrade(player, entry.get("id"))
        if rtype == "weapon":      return self._apply_weapon(player, entry.get("id")) if entry.get("id") else False
        if rtype == "consumable":  return self._apply_consumable(player, entry.get("id"), entry)
        if rtype == "bundle":      return self._apply_bundle(player, entry)
        return False

    def _apply_gold(self, player, amount) -> bool:
        amount = int(amount)
        if amount <= 0:
            return False
        setattr(player, "gold", getattr(player, "gold", 0) + amount)
        return True

    def _heal_player(self, player, amount: int) -> bool:
        amount = int(amount)
        if amount <= 0:
            return False
        max_hp = getattr(player, "max_hp", getattr(player, "hp", 1))
        hp     = getattr(player, "hp", max_hp)
        new_hp = min(max_hp, hp + amount)
        setattr(player, "hp", new_hp)
        if hasattr(player, "_hits_taken_current_life"):
            setattr(player, "_hits_taken_current_life", max(0, max_hp - new_hp))
        return new_hp != hp

    # ------------------------------------------------------------------ #
    # Tooltip con descripción
    # ------------------------------------------------------------------ #

    def _draw_tooltip(self, surface, desc: str, max_width: int = 180) -> None:
        """Dibuja un tooltip con la descripción del item debajo de la tienda."""
        # Dividir descripción en líneas
        lines = desc.split("\n")

        # Usar una fuente un poco más pequeña para el tooltip
        tooltip_font = pygame.font.SysFont(None, 14)

        # Renderizar líneas
        rendered_lines = [tooltip_font.render(line, True, (220, 220, 200)) for line in lines]

        # Calcular dimensiones del tooltip
        line_height = 16
        padding = 8
        tooltip_height = len(rendered_lines) * line_height + padding * 2
        tooltip_width = max(r.get_width() for r in rendered_lines) + padding * 2 if rendered_lines else 100
        tooltip_width = min(tooltip_width, max_width)

        # Posicionar debajo de la tienda
        tooltip_x = self.rect.x + self.rect.width + 12
        tooltip_y = self.rect.y + 36

        # Ajustar si se sale de pantalla
        screen_width = surface.get_width()
        screen_height = surface.get_height()

        if tooltip_x + tooltip_width > screen_width:
            tooltip_x = self.rect.x - tooltip_width - 12

        if tooltip_y + tooltip_height > screen_height:
            tooltip_y = self.rect.y + self.rect.height - tooltip_height

        # Dibujar fondo del tooltip (semitransparente)
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)

        # Crear surface temporal para el fondo semitransparente
        tooltip_surface = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
        pygame.draw.rect(tooltip_surface, (30, 25, 50, 200), tooltip_surface.get_rect())
        pygame.draw.rect(tooltip_surface, (180, 160, 220), tooltip_surface.get_rect(), 1)

        surface.blit(tooltip_surface, (tooltip_x, tooltip_y))

        # Dibujar texto
        y_offset = tooltip_y + padding
        for line_surf in rendered_lines:
            surface.blit(line_surf, (tooltip_x + padding, y_offset))
            y_offset += line_height

    # ------------------------------------------------------------------ #
    # Renderizado
    # ------------------------------------------------------------------ #

    def draw(self, surface):
        if not self.active:
            return
        pygame.draw.rect(surface, (20, 20, 24), self.rect)
        pygame.draw.rect(surface, (240, 220, 120), self.rect, 2)

        title = self.font.render("TIENDA DE APOYO", True, (255, 240, 180))
        surface.blit(title, (self.rect.x + 12, self.rect.y + 8))

        y = self.rect.y + 36
        self._item_hitboxes = []
        for idx, it in enumerate(self.items):
            item_rect = pygame.Rect(self.rect.x + 12, y - 4, self.rect.width - 24, 22)
            self._item_hitboxes.append(item_rect)

            is_selected = idx == self.selected
            is_hover    = idx == self.hover_index

            if is_selected:
                pygame.draw.rect(surface, (65, 60, 100), item_rect)
            elif is_hover:
                pygame.draw.rect(surface, (50, 45, 75), item_rect)

            line  = f"{it['name']}  -  {it['price']} apoyo"
            color = (255, 240, 180) if is_selected else ((255, 255, 255) if is_hover else (235, 235, 235))
            surface.blit(self.font.render(line, True, color), (self.rect.x + 18, y))
            y += 24

        # --- Tooltip con descripción del item seleccionado ---
        if self.selected < len(self.items):
            item = self.items[self.selected]
            desc = item.get("desc", "")
            if desc:
                self._draw_tooltip(surface, desc)
