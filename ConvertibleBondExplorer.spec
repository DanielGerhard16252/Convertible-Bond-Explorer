# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import blpapi
from PyInstaller.utils.hooks import collect_all

# Bundle only AI credentials/model settings, not unrelated secrets or local paths.
from dotenv import dotenv_values

settings = dotenv_values('.env')
if not (settings.get('OPENAI_API_KEY') or '').strip():
    raise ValueError('Building requires OPENAI_API_KEY in the project .env.')
bundle_environment = Path('build/bundled-config/.env')
bundle_environment.parent.mkdir(parents=True, exist_ok=True)
from dotenv import set_key

bundle_environment.write_text('', encoding='utf-8')
for name in ('OPENAI_API_KEY', 'OPENAI_MODEL'):
    if settings.get(name):
        set_key(str(bundle_environment), name, settings[name])
datas = [(str(bundle_environment), '.')]
datas += [(f'data/{name}', 'data') for name in ('bond_data.csv', 'search_demo.csv', 'option_demo.csv')]
binaries = []
hiddenimports = ['polars_bloomberg']
tmp_ret = collect_all('polars_bloomberg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('blpapi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# blpapi loads ffiutils with ctypes using a filename glob, so PyInstaller
# cannot discover it as a normal Python import. Bundle it explicitly beside
# the rest of the blpapi package or Element.toPy() fails at runtime.
blpapi_directory = Path(blpapi.__file__).resolve().parent
ffiutils_files = list(blpapi_directory.glob('ffiutils.*.pyd'))
if not ffiutils_files:
    raise FileNotFoundError(
        f"Bloomberg ffiutils binary was not found in {blpapi_directory}."
    )
binaries += [(str(path), 'blpapi') for path in ffiutils_files]


a = Analysis(
    ['desktop/__main__.py'],
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
    a.binaries,
    a.datas,
    [],
    name='ConvertibleBondExplorer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
