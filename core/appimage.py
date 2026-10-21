# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Integración de escritorio de la AppImage (issue #17).

Una AppImage es un solo archivo: arranca desde cualquier carpeta pero no
aparece en ninguna parte — sin lanzador en el menú de aplicaciones, sin
icono, y los .db sin su icono de documento. AppImageLauncher o Gear Lever
hacen ese trabajo cuando están instalados; este módulo lo hace desde la
propia app, a pedido o en el primer arranque: escribe un ``.desktop`` y el
icono en los directorios XDG del usuario, apuntando a la ruta de la propia
AppImage, más el tipo MIME de los .db con su icono (lo mismo que registra
``install-linux.sh``). :func:`quitar` lo deshace todo.

Portado de ``core/appimage.py`` de IngeCAD (77ca931) e IngeTrazo (cb9e86f),
que respondieron a la misma revisión externa del 10-09-2026.

El runtime de AppImage exporta ``APPIMAGE`` (la ruta del archivo); si no
está, no corremos como AppImage y nada de esto aplica.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from core.config import BASE_DIR

NOMBRE_DESKTOP = "ingepresupuestos.desktop"
NOMBRE_ICONO = "ingepresupuestos.png"
MIME_PKG = "ingepresupuestos.xml"
# Prefijo de los iconos de documento .db en hicolor/<tam>/mimetypes/.
ICONO_DOC = "application-x-ingepresupuestos-db"


def appimage_path() -> Optional[Path]:
    """La AppImage en ejecución, o ``None`` si no corremos como AppImage."""
    raw = os.environ.get("APPIMAGE", "")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_file() else None


def data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME", "")
    return Path(raw) if raw else Path.home() / ".local" / "share"


def desktop_file() -> Path:
    return data_home() / "applications" / NOMBRE_DESKTOP


def icon_file() -> Path:
    return data_home() / "icons" / "hicolor" / "256x256" / "apps" / NOMBRE_ICONO


def mime_file() -> Path:
    return data_home() / "mime" / "packages" / MIME_PKG


def esta_integrada(appimage: Optional[Path] = None) -> bool:
    """True si nuestro lanzador existe y apunta a ESTA AppImage (un archivo
    movido o renombrado cuenta como no integrado, así el ofrecimiento vuelve)."""
    f = desktop_file()
    if not f.is_file():
        return False
    if appimage is None:
        return True
    try:
        texto = f.read_text(encoding="utf-8")
    except OSError:
        return False
    return str(appimage) in texto


def _entrada_desktop(appimage: Path) -> str:
    exe = str(appimage).replace('"', '\\"')
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=IngePresupuestos\n"
        "GenericName=Presupuestos de Obra\n"
        "Comment=Software para la elaboración de Presupuestos de Obra\n"
        "Comment[en]=Construction budgeting software\n"
        f'Exec="{exe}" %F\n'
        f"TryExec={exe}\n"
        "Icon=ingepresupuestos\n"
        "Terminal=false\n"
        "Categories=Office;Finance;Engineering;Spreadsheet;\n"
        "Keywords=presupuesto;obra;construcción;ingeniería;ACU;cronograma;Gantt;INEI;\n"
        "MimeType=application/x-ingepresupuestos-db;\n"
        "StartupNotify=true\n"
        "StartupWMClass=ingepresupuestos\n"
        "X-AppImage-Integrated=true\n"
    )


def _iconos_documento(base: Path) -> list[tuple[Path, Path]]:
    """Pares (origen, destino) de los iconos de documento .db, por tamaño."""
    hicolor = base / "resources" / "icons" / "hicolor"
    pares = []
    for src in sorted(hicolor.glob(f"*/mimetypes/{ICONO_DOC}.*")):
        rel = src.relative_to(hicolor)
        pares.append((src, data_home() / "icons" / "hicolor" / rel))
    return pares


def integrar(appimage: Path, base: Optional[Path] = None) -> Path:
    """Escribe el lanzador, el icono y el tipo MIME de los .db; devuelve la
    ruta del ``.desktop``. ``base`` es la carpeta de recursos del programa
    (por defecto ``BASE_DIR``, que bajo PyInstaller es ``_internal/``)."""
    base = base or BASE_DIR
    f = desktop_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(_entrada_desktop(appimage), encoding="utf-8")
    try:
        f.chmod(0o755)
    except OSError:
        pass
    origen_icono = base / "resources" / "icons" / "elementary" / "24" / NOMBRE_ICONO
    if origen_icono.is_file():
        ic = icon_file()
        ic.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen_icono, ic)
    origen_mime = base / "resources" / "mime" / MIME_PKG
    if origen_mime.is_file():
        m = mime_file()
        m.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen_mime, m)
        for src, dst in _iconos_documento(base):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    _refrescar_caches()
    return f


def quitar(base: Optional[Path] = None) -> None:
    """Quita el lanzador, el icono y el tipo MIME (Acerca de ▸ Quitar del menú)."""
    base = base or BASE_DIR
    archivos = [desktop_file(), icon_file(), mime_file()]
    archivos += [dst for _src, dst in _iconos_documento(base)]
    for p in archivos:
        try:
            p.unlink()
        except OSError:
            pass
    _refrescar_caches()


def _refrescar_caches() -> None:
    """Mejor esfuerzo: avisar al escritorio de la entrada, el icono y el MIME."""
    for cmd in (["update-desktop-database", str(desktop_file().parent)],
                ["update-mime-database", str(data_home() / "mime")],
                ["gtk-update-icon-cache", "-q", "-t", "-f",
                 str(data_home() / "icons" / "hicolor")]):
        try:
            subprocess.run(cmd, check=False, timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass
