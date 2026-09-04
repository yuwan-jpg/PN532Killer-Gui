# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

serial_hidden = collect_submodules('serial')

a = Analysis(
    ['pn532_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('mfkey64.exe', '.'),
        ('mfkey32v2.exe', '.'),
        ('ico.png', '.'),
        ('pn532.ico', '.'),
        ('lang', 'lang'),
    ],
    hiddenimports=(
        serial_hidden +
        [
            'serial.tools.list_ports',
            'serial.tools.list_ports_windows',
            'serial.urlhandler',
            'pkg_resources',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL', 'cv2',
        'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner',
        'PyQt6.QtHelp', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNfc', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtPositioning',
        'PyQt6.QtPrintSupport', 'PyQt6.QtQml', 'PyQt6.QtQuick',
        'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets', 'PyQt6.QtRemoteObjects',
        'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtSpatialAudio',
        'PyQt6.QtSql', 'PyQt6.QtTest', 'PyQt6.QtTextToSpeech',
        'PyQt6.QtWebChannel', 'PyQt6.QtWebSockets', 'PyQt6.QtXml',
        'PyQt6.QAxContainer', 'PyQt6.lupdate',
        'qdarkstyle', 'qt_material', 'qtpy', 'pygments',
        'pip',
        'IPython', 'jupyter', 'jupyter_core', 'nbformat',
        'zmq', 'pythonwin',
    ],
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
    name='PN532Killer_GUI_v0.6.1_Beta',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['pn532.ico'],
)
