import os

'''This is a wrapper over the filesystem. It makes possible to map other kind of resources
   as FS resources. It is also comfortable for mocking.'''
class FS(object):

    def __init__(self):
        pass

    def isfile(self, fpath):
        return os.path.isfile(fpath)

    def isdir(self, fpath):
        return os.path.isdir(fpath)

    def exists(self, fpath):
        return os.path.exists(fpath)

    def open(self, fpath, mode='r'):
        return open(fpath, mode)

    def mkdirs(self, dpath):
        if not self.exists(dpath):
            os.makedirs(dpath)

    # TODO: use it
    def read(self, fpath):
        with self.open(fpath) as f:
            return f.read()

    # TODO: use it
    def write(self, fpath, content, mkDirs=False):
        if mkDirs:
            self.mkdirs(os.path.dirname(fpath)) # TODO: own dirname implementation
        with self.open(fpath, 'w') as f:
            f.write(content)
