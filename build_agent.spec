# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec for User Agent
Builds: Agent.exe (User interactive process)
"""

block_cipher = None

a = Analysis(
    ['src/user_agent.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'socket',
        'json',
        'threading',
        'queue',
        'struct',
        'cryptography',
        'cryptography.fernet',
        'mss',
        'mss.tools',
        'mss.windows',
        'pyperclip',
        'pystray',
        'PIL',
        'PIL.Image',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter',
        'wx',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console for user agent
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico' if os.path.exists('resources/icon.ico') else None,
)
