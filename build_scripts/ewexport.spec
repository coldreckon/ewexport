# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files


a = Analysis(
    ['..\\src\\main.py'],
    pathex=[],
    binaries=[],
    # customtkinter ships its theme/asset files as package data
    datas=[('..\\config', 'config')] + collect_data_files('customtkinter'),
    # NOTE: PIL must NOT be excluded - customtkinter imports PIL.Image
    hiddenimports=['tkinter', 'striprtf', 'packaging', 'customtkinter',
                   'darkdetect', 'PIL', 'PIL.Image', 'PIL.ImageTk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ewexport',
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
    # Resolve relative to the spec file, not the build cwd
    version=os.path.join(SPECPATH, 'version_info.py'),
    icon=os.path.join(SPECPATH, '..', 'assets', 'ewexport.ico'),
)
