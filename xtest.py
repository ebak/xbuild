#!/usr/bin/python

import os
import sys
from unittest import TextTestRunner
import unittest
from xbuild import builder
from xbuild.fs import dirName, absPath


def main():
    loader = unittest.TestLoader()
    tests = loader.discover(start_dir=dirName(absPath(__file__)) + '/xtest')
    return TextTestRunner(verbosity=2).run(tests)

# used to detect race conditions
def loopRun(iters=1024, workers=2):
    
    def calcWorkers(w):
        return workers

    failed = 0
    i = 0
    with open(os.devnull, 'wb') as null:
        stdout = sys.stdout
        savedFn = builder.calcNumOfWorkers
        try:
            builder.calcNumOfWorkers = calcWorkers
            sys.stdout = null
            while iters > 0:
                result = main()
                if not result.wasSuccessful():
                    stdout.write('iteration:{} errors:{} failures:{}\n'.format(i, result.errors, result.failures))
                    failed += 1
                iters -= 1
                i += 1
        finally:
            stdout.flush()
            sys.stdout = stdout
            builder.calcNumOfWorkers = savedFn
    sys.stdout.write('failures: {} for {} iterations.\n'.format(failed, i))
    return failed

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--iters",
        dest="iters", action="store", required=False,
        help="Number of iterations.")
    parser.add_argument(
        "--workers",
        dest="workers", action="store", default=2, required=False,
        help="Number of worker threads. Default is 2.")
    args = parser.parse_args()
    if args.iters:
        sys.exit(loopRun(int(args.iters), int(args.workers)))
    else:
        result = main()
        sys.exit(result.errors + result.failures)
