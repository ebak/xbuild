from unittest import TextTestRunner
import unittest


def main():
    loader = unittest.TestLoader()
    tests = loader.discover(start_dir='xtest')
    TextTestRunner(verbosity=2).run(tests)


if __name__ == '__main__':
    main()
