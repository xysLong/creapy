import multiprocessing
import os
import sys


def matplotlib_cache_dir():
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache')
    return os.path.join(base, 'creapy.io', 'matplotlib')


def keep_font_cache():
    try:
        folder = matplotlib_cache_dir()
        os.makedirs(folder, exist_ok=True)
        os.environ['MPLCONFIGDIR'] = folder
    except OSError:
        pass


if __name__ == '__main__':
    multiprocessing.freeze_support()
    keep_font_cache()
    from creapy.io.main import main
    sys.exit(main())
