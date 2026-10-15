# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = [('module_1', 'module_1/'), ('module_2', 'module_2/'), ('module_3', 'module_3/'), ('module_4', 'module_4/'), ('module_5', 'module_5/'), ('module_6', 'module_6/'), ('Administrator', 'Administrator/'), ('_source', '_source/'), ('app_logger', 'app_logger/'), ('app_utils', 'app_utils/'), ('workspace_weights', 'workspace_weights/')]
binaries = []
hiddenimports = []
datas += copy_metadata('torch')
datas += copy_metadata('torchvision')
tmp_ret = collect_all('mysql')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pypylon')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['module_2\\run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='VisionProInspector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['module_3\\assert\\icon\\artificial-intelligence.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VisionProInspector',
)
