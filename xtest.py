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
def loopRun(iters=1024, workers=2, verbose=False):
    
    def calcWorkers(w):
        return workers

    def loop(iters, outStream=sys.stdout):
        try:
            stdout = sys.stdout
            savedFn = builder.calcNumOfWorkers
            builder.calcNumOfWorkers = calcWorkers
            sys.stdout = outStream
            failed, i = 0, 0
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
        return failed, i

    if verbose:
        failed, i = loop(iters)
    else:
        with open(os.devnull, 'wb') as null:
            failed, i = loop(iters, outStream=null)
    sys.stdout.write('failures: {} for {} iterations.\n'.format(failed, i))
    return failed

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--iters",
        dest="iters", action="store", type=int, required=False,
        help="Number of iterations.")
    parser.add_argument(
        "--workers",
        dest="workers", action="store", type=int, default=2, required=False,
        help="Number of worker threads. Default is 2.")
    parser.add_argument(
        '-v', '--verbose', dest='verbose', action="store_true", default=False, required=False)
    args = parser.parse_args()
    if args.iters:
        sys.exit(loopRun(args.iters, args.workers, args.verbose))
    else:
        result = main()
        print 'bye...'
        sys.exit(len(result.errors) + len(result.failures))
