import os

'''This is a wrapper over the filesystem. It makes possible to map other kind of resources
   as FS resources. It is also comfortable for mocking.'''
class FS(object):

    def __init__(self):
        pass

    def isfile(self, fpath):
        return os.path.isfile(fpath)

    def exists(self, fpath):
        return os.path.exists(fpath)

    def open(self, fpath, mode):
        return open(fpath, mode)
