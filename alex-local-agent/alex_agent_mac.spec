# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for macOS .app bundle
# Build: pyinstaller alex_agent_mac.spec

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
        # Playwright — NOT bundled (too large); installed separately via setup
        # 'playwright',
        # 'playwright.async_api',
        # 'playwright.sync_api',
        # Network
        'requests',
        'requests.adapters',
        'urllib3',
        # GUI
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
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
        # Exclude heavy ML/AI frameworks (optional, not in build venv anyway)
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
        # Exclude AI SDK optional deps (included only if user configures them)
        'anthropic',
        'google.generativeai',
        'google.ai',
        'grpc',
        'pyautogui',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AlexAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,   # Required for macOS .app
    target_arch='arm64',   # Build for Apple Silicon (M1/M2/M3)
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AlexAgent',
)

app = BUNDLE(
    coll,
    name='AlexAgent.app',
    # Mac icon (place alex_icon.icns in same folder)
    icon='alex_icon.icns' if Path('alex_icon.icns').exists() else None,
    bundle_identifier='ro.alexinsurance.agent',
    info_plist={
        'CFBundleName': 'Alex Agent',
        'CFBundleDisplayName': 'Alex Insurance Agent',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        # Allow accessibility for desktop automation
        'NSAccessibilityUsageDescription': 'Alex Agent needs accessibility access for desktop automation.',
        # Allow screen recording for screenshots
        'NSScreenCaptureUsageDescription': 'Alex Agent takes screenshots for desktop automation tasks.',
        # Background app (shows in menu bar, not dock)
        'LSUIElement': True,
        'LSBackgroundOnly': False,
    }
)
