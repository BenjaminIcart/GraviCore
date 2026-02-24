# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['centre_de_masse.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('icon.ico', '.'),
    ],
    hiddenimports=[
        'database',
        'recorder',
        'replay_window',
        'web_dashboard',
        'remote_sync',
        'flask',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'markupsafe',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='CentredeMasse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
