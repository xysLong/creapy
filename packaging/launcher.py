import multiprocessing
import sys

from creapy.io.main import main

if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
