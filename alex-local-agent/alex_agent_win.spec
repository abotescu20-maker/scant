# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows .exe
# Build: pyinstaller alex_agent_win.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['agent_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include all connector files
        ('connectors/*.py', 'connectors'),
        # Include readme
        ('README.md', '.'),
    ],
    hiddenimports=[
        # Core imports
        'asyncio',
        'concurrent.futures',
        'threading',
        'logging',
        'json',
        'uuid',
        'platform',
        'pathlib',
        'webbrowser',
        # Local modules
        'config',
        'registry',
        'main',
        'connectors.base',
        'connectors.connector_web_generic',
        'connectors.connector_desktop_generic',
        'connectors.connector_cedam',
        # Playwright
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        # Network
        'requests',
        'requests.adapters',
        'urllib3',
        # GUI
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        # Optional AI
        'anthropic',
        'google.generativeai',
        'pyautogui',
        # dotenv
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'pytest',
        # Exclude heavy ML frameworks not needed by agent
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'keras',
        'sklearn',
        'cv2',
        'jax',
        'transformers',
        'diffusers',
        'accelerate',
        'datasets',
        'tokenizers',
        'huggingface_hub',
        'safetensors',
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
    name='AlexAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # No terminal window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows icon (place alex_icon.ico in same folder)
    icon='alex_icon.ico' if Path('alex_icon.ico').exists() else None,
    version='version_info.txt' if Path('version_info.txt').exists() else None,
)
