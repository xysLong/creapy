# Entry script for the PyInstaller bundle (keeps the package import path identical to `creapy-io`).
import multiprocessing
import sys

from creapy.io.main import main

if __name__ == '__main__':
    multiprocessing.freeze_support()  # harmless on macOS/Linux, required for frozen Windows builds
    sys.exit(main())
