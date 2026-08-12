# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec do agent-local (app desktop v2).

Gera um único .exe Windows (--onefile), sem janela de console (app GUI),
com os assets de tema do customtkinter incluídos — sem eles, a janela abre
sem estilos/ícones e pode até falhar ao carregar o tema padrão.

Uso: `pyinstaller agent-local.spec --noconfirm` (ver build.bat).
"""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("customtkinter")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="agent-local",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
