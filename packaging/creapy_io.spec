# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the creapy.io desktop app. Build from the repository root:
#   macOS/Linux:  pyinstaller packaging/creapy_io.spec
#   Windows:      pyinstaller packaging\creapy_io.spec
# Output: dist/creapy.io.app (macOS) or dist/creapy.io/ with creapy.io.exe (Windows). See packaging/README.md.
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))
sys.path.insert(0, ROOT)
import creapy  # noqa: E402  (version string)

# heatmatch may be an editable install (pip install -e ~/Projects/HeatMatch) whose import hook PyInstaller cannot
# follow: point it at the package's parent directory and name the modules explicitly
import heatmatch  # noqa: E402
HEATMATCH_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(heatmatch.__file__)))
heatmatch_modules = ['heatmatch'] + ['heatmatch.' + f[:-3] for f in os.listdir(os.path.dirname(heatmatch.__file__))
                                     if f.endswith('.py') and f != '__init__.py']

datas = [(os.path.join(ROOT, 'creapy', 'io', 'style'), os.path.join('creapy', 'io', 'style'))]
datas += collect_data_files('shapely')
datas += collect_data_files('matplotlib', subdir='mpl-data')

hiddenimports = (collect_submodules('creapy') + heatmatch_modules
                 + ['PySide6.QtSvg', 'matplotlib.backends.backend_qtagg', 'matplotlib.backends.backend_qt5agg',
                    'scipy.special._cdflib', 'sklearn.utils._typedefs', 'sklearn.manifold', 'openpyxl', 'PIL'])

a = Analysis(
    [os.path.join(ROOT, 'packaging', 'launcher.py')],
    pathex=[ROOT, HEATMATCH_PARENT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'IPython', 'jupyter', 'notebook', 'pytest', 'torch'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='creapy.io',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # a windowed app; `--selftest` still prints to a terminal when started from one
    icon=os.path.join(ROOT, 'packaging', 'icon.icns') if sys.platform == 'darwin' and os.path.exists(os.path.join(ROOT, 'packaging', 'icon.icns'))
    else (os.path.join(ROOT, 'packaging', 'icon.ico') if os.path.exists(os.path.join(ROOT, 'packaging', 'icon.ico')) else None),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='creapy.io')

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='creapy.io.app',
        icon=os.path.join(ROOT, 'packaging', 'icon.icns') if os.path.exists(os.path.join(ROOT, 'packaging', 'icon.icns')) else None,
        bundle_identifier='at.ac.univie.crea.creapy',
        info_plist={
            'CFBundleShortVersionString': creapy.__version__,
            'CFBundleVersion': creapy.__version__,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '12.0',
        },
    )
