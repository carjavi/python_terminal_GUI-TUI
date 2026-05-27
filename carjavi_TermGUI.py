# CarJavi TermGUI — Interfaz TUI modular (compatible con: CMD, PowerShell, Terminal-VScode)
# @author: Carlos Briceño <carjavi@hotmail.com>
# @date: 26-05-2026
# @copyright: Copyright (c) 2026 www.carjavi.com
# @version: V4.0
# @library:
#   pip install PyTermGUI

from __future__ import annotations

import atexit
import os
import shutil
import signal
import sys
import traceback
from argparse import ArgumentParser, Namespace
from typing import Callable


# ============================================================
# ENTORNO DE COLOR
# ============================================================

os.environ["COLORTERM"] = "truecolor"
os.environ["TERM"] = "xterm-256color"


# ============================================================
# AUTO-INSTALACIÓN DE DEPENDENCIAS
# ============================================================

def _ensure_dependencies() -> None:
    """
    Lee el bloque ``@library:`` del encabezado del propio script,
    detecta librerías faltantes e instala las que no estén disponibles
    usando el mismo intérprete Python activo (respeta virtualenvs).
    Reinicia el proceso tras la instalación para que los imports sean válidos.

    Algoritmo:
        1. Abre ``__file__`` y extrae las líneas ``pip install <paquete>``
           del bloque ``@library:`` (termina al encontrar otro campo ``@``
           o el fin del bloque de comentarios).
        2. Deriva el nombre importable desde el nombre pip:
           - Elimina especificador de versión (``==``, ``>=``, etc.)
           - Convierte a minúsculas y reemplaza ``-`` por ``_``
           - Aplica overrides explícitos para casos irregulares.
        3. Intenta ``importlib.import_module(nombre)``.
        4. Acumula los faltantes e instala en lote con ``pip install``.
        5. Llama ``os.execv`` para reiniciar el proceso limpiamente.

    Raises:
        SystemExit: Si pip falla al instalar alguna dependencia.
    """
    import importlib
    import re
    import subprocess

    _IMPORT_OVERRIDES: dict[str, str] = {
        "pillow":          "PIL",
        "scikit-learn":    "sklearn",
        "python-dateutil": "dateutil",
        "pyyaml":          "yaml",
        "opencv-python":   "cv2",
        "pytermgui":       "pytermgui",
    }

    pip_packages: list[str] = []
    try:
        with open(__file__, encoding="utf-8") as _f:
            in_block = False
            for raw in _f:
                line = raw.strip()
                if not line.startswith("#"):
                    break
                content = line.lstrip("#").strip()
                if content.startswith("@library:"):
                    after = content[len("@library:"):].strip()
                    if after and after != "No external dependencies":
                        m = re.match(r"pip\s+install\s+(.+)", after)
                        if m:
                            pip_packages.append(m.group(1).strip())
                    in_block = True
                    continue
                if in_block:
                    if content.startswith("@"):
                        break
                    m = re.match(r"-?\s*pip\s+install\s+(.+)", content)
                    if m:
                        pip_packages.append(m.group(1).strip())
    except Exception:
        return

    if not pip_packages:
        return

    missing: list[str] = []
    for spec in pip_packages:
        base = re.split(r"[=<>!;]", spec)[0].strip().lower()
        import_name = _IMPORT_OVERRIDES.get(base, base.replace("-", "_"))
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(spec)

    if not missing:
        return

    print("\n[carjavi TUI] Dependencias faltantes detectadas:")
    for pkg in missing:
        print(f"  • {pkg}")

    print()
    for pkg in missing:
        print(f"  Instalando: {pkg} ...", end=" ", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("OK")
        else:
            print("ERROR")
            print(result.stderr.strip())
            sys.exit(1)

    print("\n[carjavi TUI] Dependencias listas. Iniciando...\n")
    os.execv(sys.executable, [sys.executable] + sys.argv)


_ensure_dependencies()

import pytermgui as ptg  # noqa: E402


# ════════════════════════════════════════════════════════════════════════════
#
#   SECCIÓN 1 — CONFIGURACIÓN
#   ► Edita esta sección para personalizar o reutilizar la app.
#   ► No es necesario tocar nada fuera de este bloque.
#
# ════════════════════════════════════════════════════════════════════════════


# ── 1.1  Identidad visual ────────────────────────────────────────────────────

# Texto que aparece en la barra de cabecera (parte superior de la pantalla)
APP_HEADER_TEXT: str = "  carjavi TermGUI  "

# Título de la ventana principal (encima del menú de botones)
APP_WINDOW_TITLE: str = "Main Menu"

# Logo ASCII mostrado dentro de la ventana principal.
# Cada string es una línea; usa "" para líneas en blanco.
# Tip: genera tu logo en https://patorjk.com/software/taag/
APP_LOGO_LINES: list[str] = [
    "                             d8b                   d8b ",
    "                             Y8P                   Y8P",
    "",
    "  .d8888b  8888b.  888d888  8888  8888b.  888  888 888",
    " d88P'        '88b 888P'    '888     '88b 888  888 888 ",
    " 888      .d888888 888       888 .d888888 Y88  88P 888 ",
    " Y88b.    888  888 888       888 888  888  Y8bd8P  888 ",
    "  'Y8888P 'Y888888 888       888 'Y888888   Y88P   888 ",
    "                             888                       ",
    "                            d88P                       ",
    "                          888P'                        ",
    "",
]


# ── 1.2  Funciones del menú ──────────────────────────────────────────────────
#
# Firma obligatoria:
#   def mi_funcion(
#       manager: ptg.WindowManager,
#       set_progress: Callable[[float], None],
#   ) -> None:
#
# • set_progress(0.0 … 1.0) actualiza la barra de progreso en tiempo real.
# • El motor resetea la barra a 0% antes de llamar la función y la lleva
#   a 100% al terminar — no es necesario hacerlo manualmente.
# • Para tareas largas, llama set_progress(0.3), set_progress(0.7), etc.
#   a medida que avanza el trabajo para mostrar progreso real.
# • Si la función es rápida y no necesita progreso intermedio,
#   simplemente ignora set_progress.
#
# Nota: _show_message y _show_error están disponibles (definidas más abajo).

def option_1(
    manager: ptg.WindowManager,
    set_progress: Callable[[float], None],
) -> None:
    """
    Acción de la opción 1 del menú.

    Args:
        manager: WindowManager activo de la TUI.
        set_progress: Callback para actualizar la barra (0.0–1.0).
    """
    _show_message(manager, "Option 1", "Ejecutaste Option 1")


def option_2(
    manager: ptg.WindowManager,
    set_progress: Callable[[float], None],
) -> None:
    """
    Acción de la opción 2 del menú.

    Args:
        manager: WindowManager activo de la TUI.
        set_progress: Callback para actualizar la barra (0.0–1.0).
    """
    _show_message(manager, "Option 2", "Ejecutaste Option 2")


def option_3(
    manager: ptg.WindowManager,
    set_progress: Callable[[float], None],
) -> None:
    """
    Acción de la opción 3 del menú.

    Args:
        manager: WindowManager activo de la TUI.
        set_progress: Callback para actualizar la barra (0.0–1.0).
    """
    _show_message(manager, "Option 3", "Ejecutaste Option 3")


def option_4(
    manager: ptg.WindowManager,
    set_progress: Callable[[float], None],
) -> None:
    """
    Acción de la opción 4 del menú.

    Args:
        manager: WindowManager activo de la TUI.
        set_progress: Callback para actualizar la barra (0.0–1.0).
    """
    _show_message(manager, "Option 4", "Ejecutaste Option 4")


# ── 1.3  Mapa del menú ──────────────────────────────────────────────────────
#
# Cada entrada define una opción del menú:
#   ("Etiqueta del botón",  función,   "atajo de teclado")
#
# Reglas:
#   • El atajo debe ser un carácter único (p. ej. "1", "a", "f").
#   • Usa "" en el atajo si no quieres asignar uno.
#   • El orden aquí define el orden visual de los botones.
#   • El grid se construye en filas de 2 columnas automáticamente.
#   • Para agregar una opción: añade la función arriba y una línea aquí.
#   • Para renombrar: cambia solo la etiqueta.
#   • Para cambiar la acción: cambia solo la función.
#
#    ┌─ Etiqueta del botón ──────┬─ Función ──┬─ Atajo ─┐
MENU_ITEMS: list[tuple[str, Callable, str]] = [
    ("1) Option 1",               option_1,    "1"     ),
    ("2) Option 2",               option_2,    "2"     ),
    ("3) Option 3",               option_3,    "3"     ),
    ("4) Option 4",               option_4,    "4"     ),
]


# ════════════════════════════════════════════════════════════════════════════
#
#   SECCIÓN 2 — MOTOR DE INTERFAZ
#   ► No modificar. Aquí vive el código que construye y ejecuta la TUI.
#
# ════════════════════════════════════════════════════════════════════════════


# ── Paleta de colores ────────────────────────────────────────────────────────

PALETTE_LIGHT:  str = "#d79921"
PALETTE_MID:    str = "#b57614"
PALETTE_DARK:   str = "#3c3836"
PALETTE_DARKER: str = "#1d2021"
TEXT_COLOR:     str = "#ebdbb2"


# ── Restauración del terminal ────────────────────────────────────────────────

def _restore_terminal() -> None:
    """
    Restaura el terminal a su estado normal (modo canónico, cursor visible).
    Se registra en atexit y en señales para cubrir toda salida posible,
    incluidos crashes dentro del event loop de PyTermGUI.
    """
    try:
        sys.stdout.write("\033[?1049l\033[?25h\033[0m")
        sys.stdout.flush()
    except Exception:
        pass


def _signal_handler(sig: int, frame: object) -> None:
    """
    Manejador de señales SIGINT/SIGTERM.

    Args:
        sig: Número de señal recibida.
        frame: Frame de ejecución al momento de la señal.
    """
    _restore_terminal()
    sys.exit(0)


atexit.register(_restore_terminal)
signal.signal(signal.SIGINT, _signal_handler)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _signal_handler)


# ── Patches de estabilidad — PyTermGUI 7.1.0 ────────────────────────────────

def _patch_pytermgui_bugs() -> None:
    """
    Corrige bugs conocidos de PyTermGUI 7.1.0 mediante monkey-patching.

    Bug 1 — KeyError 'scroll_down'/'scroll_up' en Button:
        El loop de input llama a ``{k: 1 for k in widget.keys["scroll_down"]}``
        pero Button nunca define esos entries. Fix: inyectar listas vacías.

    Bug 2 — TypeError en Container/Splitter.handle_key:
        Con ``selected_index=None``, la librería ejecuta
        ``self.selectables[self.selected_index][0]`` y falla.
        Fix: wrap de handle_key que retorna False si selected_index es None
        y absorbe TypeError/IndexError/KeyError residuales.
    """
    import functools

    for scroll_key in ("scroll_down", "scroll_up"):
        if scroll_key not in ptg.Button.keys:
            ptg.Button.keys[scroll_key] = []

    def _wrap_handle_key(cls: type) -> None:
        """
        Reemplaza cls.handle_key con versión protegida contra None index.

        Args:
            cls: Clase de widget a parchear.
        """
        original = cls.handle_key

        @functools.wraps(original)
        def _safe(self: object, key: str) -> bool:
            if getattr(self, "selected_index", None) is None:
                return False
            try:
                return original(self, key)
            except (TypeError, IndexError, KeyError):
                return False

        cls.handle_key = _safe

    for widget_cls in (ptg.Container, ptg.Splitter):
        if hasattr(widget_cls, "handle_key"):
            _wrap_handle_key(widget_cls)


# ── Argumentos CLI ───────────────────────────────────────────────────────────

def _process_arguments(argv: list[str] | None = None) -> Namespace:
    """
    Procesa argumentos de línea de comandos.

    Args:
        argv: Lista de argumentos. Si es None usa sys.argv.

    Returns:
        Namespace con los argumentos parseados.
    """
    parser = ArgumentParser(description="CarJavi TermGUI")
    return parser.parse_args(argv)


# ── Aliases de estilo ────────────────────────────────────────────────────────

def _create_aliases() -> None:
    """
    Define aliases TIM de color y tipografía para el tema de la aplicación.
    Usa paleta Gruvbox-inspired definida en las constantes de paleta.
    """
    ptg.tim.alias("app.text",             TEXT_COLOR)
    ptg.tim.alias("app.header",           f"bold @{PALETTE_MID} {TEXT_COLOR}")
    ptg.tim.alias("app.header.fill",      f"@{PALETTE_LIGHT}")
    ptg.tim.alias("app.title",            f"bold {PALETTE_LIGHT}")
    ptg.tim.alias("app.button.label",     f"bold @{PALETTE_DARK} {TEXT_COLOR}")
    ptg.tim.alias("app.button.highlight", f"bold @{PALETTE_LIGHT} black")
    ptg.tim.alias("app.footer",           f"@{PALETTE_DARKER}")
    ptg.tim.alias("app.error",            "bold red")
    ptg.tim.alias("app.logo",             f"bold {PALETTE_LIGHT}")


# ── Configuración de widgets ─────────────────────────────────────────────────

def _configure_widgets() -> None:
    """
    Configura estilos globales de los widgets y aplica patches de estabilidad.
    Debe llamarse antes de construir cualquier widget de la UI.
    """
    ptg.boxes.DOUBLE.set_chars_of(ptg.Window)
    ptg.boxes.ROUNDED.set_chars_of(ptg.Container)

    ptg.Button.styles.label     = "app.button.label"
    ptg.Button.styles.highlight = "app.button.highlight"
    ptg.Label.styles.value      = "app.text"
    ptg.Window.styles.border__corner    = PALETTE_LIGHT
    ptg.Container.styles.border__corner = PALETTE_MID
    ptg.Splitter.set_char("separator", " ")

    _patch_pytermgui_bugs()


# ── Layout ───────────────────────────────────────────────────────────────────

def _define_layout() -> ptg.Layout:
    """
    Define layout en tres zonas: Header (1 línea), Body, Footer (1 línea).

    Returns:
        Objeto Layout configurado.
    """
    layout = ptg.Layout()
    layout.add_slot("Header", height=1)
    layout.add_break()
    layout.add_slot("Body")
    layout.add_break()
    layout.add_slot("Footer", height=1)
    return layout


# ── Modales ──────────────────────────────────────────────────────────────────

def _show_message(
    manager: ptg.WindowManager,
    title: str,
    message: str,
) -> None:
    """
    Muestra un modal informativo centrado con botón Cerrar.

    Args:
        manager: WindowManager activo.
        title: Título del modal.
        message: Cuerpo del mensaje.
    """
    modal = ptg.Window(
        f"[app.title]{title}",
        "",
        message,
        "",
        ptg.Button("Cerrar", lambda *_: modal.close()),
        width=50,
    ).center()
    modal.select(0)
    manager.add(modal)


def _show_error(
    manager: ptg.WindowManager,
    error: Exception,
) -> None:
    """
    Muestra un modal de error centrado con el mensaje de la excepción.

    Args:
        manager: WindowManager activo.
        error: Excepción capturada.
    """
    modal = ptg.Window(
        "[app.error]ERROR",
        "",
        str(error),
        "",
        ptg.Button("Cerrar", lambda *_: modal.close()),
        width=70,
    ).center()
    modal.select(0)
    manager.add(modal)


# ── Salida ───────────────────────────────────────────────────────────────────

def _quit(manager: ptg.WindowManager) -> None:
    """
    Detiene el WindowManager de forma limpia.

    Args:
        manager: WindowManager activo.
    """
    manager.stop()


def _confirm_quit(manager: ptg.WindowManager) -> None:
    """
    Muestra modal de confirmación antes de salir.

    Args:
        manager: WindowManager activo.
    """
    modal = ptg.Window(
        "[app.title]¿Deseas salir?",
        "",
        ptg.Splitter(
            ptg.Button("Sí", lambda *_: _quit(manager)),
            ptg.Button("No", lambda *_: modal.close()),
        ),
        width=40,
    ).center()
    modal.select(1)
    manager.add(modal)


# ── Barra de progreso ────────────────────────────────────────────────────────

class ProgressTracker:
    """
    Barra de progreso basada en ptg.Label, actualizable en tiempo real.

    Renderiza bloques Unicode coloreados con porcentaje numérico.
    Rango: 0.0 (0%) a 1.0 (100%).

    Attributes:
        widget: Label de PyTermGUI que debe añadirse a la ventana.

    Example:
        tracker = ProgressTracker(bar_width=60)
        window = ptg.Window(tracker.widget)
        tracker.progress = 0.5   # 50%
    """

    def __init__(self, bar_width: int = 40) -> None:
        """
        Inicializa la barra con el ancho dado.

        Args:
            bar_width: Número de columnas del bloque de barras (sin contar etiqueta).
        """
        self._bar_width: int   = max(10, bar_width)
        self._progress: float  = 0.0
        self.widget: ptg.Label = ptg.Label(self._render())

    @property
    def progress(self) -> float:
        """Valor actual de progreso (0.0–1.0)."""
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        """
        Actualiza el progreso y redibuja el widget.

        Args:
            value: Nuevo valor; se clampea entre 0.0 y 1.0.
        """
        self._progress = max(0.0, min(1.0, float(value)))
        self.widget.value = self._render()

    def _render(self) -> str:
        """
        Genera el string con markup PTG para el estado actual.

        Returns:
            String con markup de color listo para ptg.Label.
        """
        filled: int = int(self._bar_width * self._progress)
        empty: int  = self._bar_width - filled
        pct: int    = int(self._progress * 100)

        filled_str = f"[{PALETTE_LIGHT}]" + "█" * filled + "[/]"
        empty_str  = f"[{PALETTE_DARK}]"  + "░" * empty  + "[/]"
        pct_str    = f"[bold {PALETTE_LIGHT}]{pct:3d}%[/]"

        return f"{filled_str}{empty_str}  {pct_str}"

    def reset(self) -> None:
        """Resetea la barra a 0%."""
        self.progress = 0.0

    def complete(self) -> None:
        """Lleva la barra al 100%."""
        self.progress = 1.0


def _calc_bar_width() -> int:
    """
    Calcula el ancho de la barra de progreso como 80% del terminal.
    Usa fallback de 80 columnas si el tamaño no es detectable.
    Se descuentan 6 columnas para la etiqueta de porcentaje y padding.

    Returns:
        Número de columnas para el bloque de barras (mínimo 20).
    """
    cols: int = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(20, int(cols * 0.8) - 6)


# ── Ejecución protegida ──────────────────────────────────────────────────────

def _safe_action(
    manager: ptg.WindowManager,
    tracker: ProgressTracker,
    fn: Callable[[ptg.WindowManager, Callable[[float], None]], None],
) -> None:
    """
    Ejecuta una función de menú con manejo completo del ciclo de progreso:
      1. Resetea la barra a 0%.
      2. Llama fn(manager, set_progress).
      3. Al terminar (éxito o error), lleva la barra a 100%.

    Los errores se muestran en modal sin romper la TUI.
    KeyboardInterrupt se re-lanza para permitir cierre limpio.

    Args:
        manager: WindowManager activo.
        tracker: Barra de progreso a controlar.
        fn: Función de menú a ejecutar (firma: fn(manager, set_progress)).
    """
    tracker.reset()

    def set_progress(value: float) -> None:
        """
        Callback que expone la barra de progreso a la función de menú.

        Args:
            value: Valor de progreso entre 0.0 y 1.0.
        """
        tracker.progress = value

    try:
        fn(manager, set_progress)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        traceback.print_exc()
        _show_error(manager, error)
    finally:
        tracker.complete()


# ── Ventana principal (generada desde MENU_ITEMS) ────────────────────────────

def _create_main_window(
    manager: ptg.WindowManager,
) -> tuple[ptg.Window, ProgressTracker]:
    """
    Construye la ventana del menú principal leyendo MENU_ITEMS, APP_LOGO_LINES
    y APP_WINDOW_TITLE de la sección de configuración.

    Genera dinámicamente:
      - Botones a partir de cada entrada de MENU_ITEMS.
      - Grid de 2 columnas con filas automáticas según cantidad de opciones.
      - Atajos de teclado por cada entry que tenga atajo definido.
      - Barra de progreso al 80% del ancho del terminal.

    Args:
        manager: WindowManager activo.

    Returns:
        Tupla (ventana configurada, ProgressTracker compartido por todas las opciones).
    """
    tracker = ProgressTracker(bar_width=_calc_bar_width())

    # ── Construir botones desde MENU_ITEMS ───────────────────────────────────
    buttons: list[ptg.Button] = []
    for label, fn, _shortcut in MENU_ITEMS:
        btn = ptg.Button(
            label,
            lambda *_, _fn=fn: _safe_action(manager, tracker, _fn),
        )
        buttons.append(btn)

    # ── Grid de 2 columnas: agrupar en filas de a 2 ──────────────────────────
    rows: list[ptg.Widget] = []
    for i in range(0, len(buttons), 2):
        pair = buttons[i : i + 2]
        if len(pair) == 2:
            rows.append(ptg.Splitter(*pair))
        else:
            rows.append(pair[0])
        if i + 2 < len(buttons):
            rows.append("")

    menu = ptg.Container(*rows, static_width=60)

    # ── Logo ─────────────────────────────────────────────────────────────────
    logo_widgets: list[ptg.Label] = [
        ptg.Label(f"[app.logo]{line}" if line else "")
        for line in APP_LOGO_LINES
    ]

    # ── Ventana: logo → título → menú → barra de progreso ───────────────────
    window = ptg.Window(
        *logo_widgets,
        f"[app.title]{APP_WINDOW_TITLE}",
        "",
        menu,
        "",
        ptg.Label(f"[{PALETTE_MID}]Progress:"),
        tracker.widget,
        "",
    )

    window.pos = (2, 2)
    window.select(0)

    # ── Atajos de teclado desde MENU_ITEMS ───────────────────────────────────
    for _label, fn, shortcut in MENU_ITEMS:
        if shortcut:
            window.bind(
                shortcut,
                lambda *_, _fn=fn: _safe_action(manager, tracker, _fn),
            )

    return window, tracker


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    """
    Punto de entrada principal. Inicializa la TUI y lanza el event loop.
    Maneja KeyboardInterrupt y errores inesperados restaurando el terminal.

    Args:
        argv: Argumentos CLI opcionales. Si es None usa sys.argv.
    """
    _process_arguments(argv)
    _create_aliases()
    _configure_widgets()

    try:
        with ptg.WindowManager() as manager:

            manager.layout = _define_layout()

            # ── Header ───────────────────────────────────────────────────────
            header = ptg.Window(
                f"[app.header]{APP_HEADER_TEXT}",
                box="EMPTY",
                is_persistant=True,
            )
            header.styles.fill = "app.header.fill"
            manager.add(header)

            # ── Footer ───────────────────────────────────────────────────────
            footer = ptg.Window(
                ptg.Button("Exit", lambda *_: _confirm_quit(manager)),
                box="EMPTY",
            )
            footer.styles.fill = "app.footer"
            manager.add(footer, assign="footer")

            # ── Body ─────────────────────────────────────────────────────────
            main_window, _tracker = _create_main_window(manager)
            manager.add(main_window, assign="body")

    except KeyboardInterrupt:
        pass

    except Exception as error:
        traceback.print_exc()
        print("\nERROR:", error)

    finally:
        _restore_terminal()


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main(sys.argv[1:])
