"""
ui/selector_modo.py
===================
Pantalla inicial que aparece antes del menú para elegir si esta instancia
es servidor o cliente (multijugador desde el menú).

Solo aparece si no se pasan argumentos --server/--client en CLI.
"""
from __future__ import annotations

import pygame


class SelectorModo:
    """
    Pantalla de selección: ¿Servidor o Cliente?

    Aparece antes del menú principal. El usuario elige:
    - SERVIDOR: Inicia como host, espera conexión de cliente
    - CLIENTE: Se conecta a un servidor (requiere IP)

    Atributos
    ---------
    resultado : str | tuple | None
        "servidor" → modo servidor
        ("cliente", ip_str) → modo cliente con IP especificada
        None → no ha terminado
    terminado : bool
        True cuando el usuario eligió un modo
    """

    def __init__(self, logical_w: int, logical_h: int):
        self.lw = logical_w
        self.lh = logical_h
        self.resultado = None
        self.terminado = False
        self.ip_input = "192.168.1.9"  # IP por defecto
        self.escribiendo_ip = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """Procesa eventos de teclado y mouse."""
        if event.type == pygame.KEYDOWN:
            if self.escribiendo_ip:
                if event.key == pygame.K_RETURN:
                    # Confirmar IP y entrar a cliente
                    self.escribiendo_ip = False
                    self.resultado = ("cliente", self.ip_input)
                    self.terminado = True
                elif event.key == pygame.K_BACKSPACE:
                    self.ip_input = self.ip_input[:-1]
                elif event.key == pygame.K_ESCAPE:
                    # Cancelar edición de IP
                    self.escribiendo_ip = False
                else:
                    # Agregar carácter a la IP
                    if len(self.ip_input) < 20:
                        self.ip_input += event.unicode

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            cx = self.lw // 2
            cy = self.lh // 2

            # Botón SERVIDOR
            rect_srv = pygame.Rect(cx - 250, cy - 30, 200, 60)
            if rect_srv.collidepoint(mx, my):
                self.resultado = "servidor"
                self.terminado = True

            # Botón CLIENTE
            rect_cli = pygame.Rect(cx + 50, cy - 30, 200, 60)
            if rect_cli.collidepoint(mx, my):
                self.escribiendo_ip = True

            # Campo IP
            rect_ip = pygame.Rect(cx - 100, cy + 62, 200, 32)
            if rect_ip.collidepoint(mx, my):
                self.escribiendo_ip = True
            else:
                # Click fuera del campo: deseleccionar
                if not self.escribiendo_ip:
                    self.escribiendo_ip = False

    def render(self, surface: pygame.Surface) -> None:
        """Renderiza la pantalla de selección."""
        surface.fill((4, 2, 8))
        cx = self.lw // 2
        cy = self.lh // 2

        try:
            font_t = pygame.font.SysFont("monospace", 22, bold=True)
            font_b = pygame.font.SysFont("monospace", 16, bold=True)
            font_s = pygame.font.SysFont("monospace", 13)

            # Título
            txt = font_t.render(
                "ECHOES — Seleccionar modo",
                False, (180, 120, 255)
            )
            surface.blit(txt, (
                cx - txt.get_width() // 2, cy - 120
            ))

            # Botón SERVIDOR
            rect_srv = pygame.Rect(cx - 250, cy - 30, 200, 60)
            mx, my = pygame.mouse.get_pos()
            hover_s = rect_srv.collidepoint(mx, my)
            pygame.draw.rect(surface,
                (60, 0, 0) if hover_s else (35, 0, 0),
                rect_srv)
            pygame.draw.rect(surface,
                (150, 0, 0) if hover_s else (80, 0, 0),
                rect_srv, 2)
            t_srv = font_b.render(
                "◈ SERVIDOR", False,
                (255, 150, 150) if hover_s else (180, 100, 100)
            )
            surface.blit(t_srv, (
                rect_srv.centerx - t_srv.get_width() // 2,
                rect_srv.centery - t_srv.get_height() // 2
            ))

            sub_s = font_s.render(
                "HOST / PC principal",
                False, (80, 40, 40)
            )
            surface.blit(sub_s, (
                rect_srv.centerx - sub_s.get_width() // 2,
                rect_srv.bottom + 5
            ))

            # Botón CLIENTE
            rect_cli = pygame.Rect(cx + 50, cy - 30, 200, 60)
            hover_c = rect_cli.collidepoint(mx, my)
            pygame.draw.rect(surface,
                (0, 30, 60) if hover_c else (0, 18, 35),
                rect_cli)
            pygame.draw.rect(surface,
                (0, 80, 150) if hover_c else (0, 45, 90),
                rect_cli, 2)
            t_cli = font_b.render(
                "◈ CLIENTE", False,
                (150, 200, 255) if hover_c else (100, 150, 200)
            )
            surface.blit(t_cli, (
                rect_cli.centerx - t_cli.get_width() // 2,
                rect_cli.centery - t_cli.get_height() // 2
            ))

            sub_c = font_s.render(
                "Unirse a un servidor",
                False, (40, 60, 90)
            )
            surface.blit(sub_c, (
                rect_cli.centerx - sub_c.get_width() // 2,
                rect_cli.bottom + 5
            ))

            # Campo IP para el cliente
            txt_ip_label = font_s.render(
                "IP del servidor:",
                False, (100, 80, 130)
            )
            surface.blit(txt_ip_label, (
                cx - 100, cy + 45
            ))

            rect_ip = pygame.Rect(cx - 100, cy + 62, 200, 32)
            pygame.draw.rect(surface,
                (15, 10, 25) if self.escribiendo_ip else (10, 8, 18),
                rect_ip)
            pygame.draw.rect(surface,
                (100, 70, 150) if self.escribiendo_ip else (50, 35, 75),
                rect_ip, 1)

            cursor = "|" if self.escribiendo_ip else ""
            txt_ip_val = font_s.render(
                self.ip_input + cursor,
                False,
                (200, 170, 255) if self.escribiendo_ip else (130, 110, 170)
            )
            surface.blit(txt_ip_val, (
                rect_ip.x + 8,
                rect_ip.centery - txt_ip_val.get_height() // 2
            ))

            # Hint
            hint = font_s.render(
                "Haz click en IP o presiona ENTER para conectar",
                False, (60, 50, 80)
            )
            surface.blit(hint, (
                cx - hint.get_width() // 2,
                cy + 105
            ))

        except Exception as e:
            print(f"[SELECTOR MODO] Error render: {e}")
