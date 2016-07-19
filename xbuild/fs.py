import os

'''This is a wrapper over the filesystem. It makes possible to map other kind of resources
   as FS resources. It is also comfortable for mocking.'''
class FS(object):

    def __init__(self):
        pass
    
    def tokenizePath(self, fpath):
        # TODO: make it platform independent
        res = []
        head = fpath
        while len(head) and head != os.path.sep:
            head, tail = os.path.split(head)
            res.append(tail)
        res.reverse()
        return res

    def isfile(self, fpath):
        return os.path.isfile(fpath)

    def isdir(self, fpath):
        return os.path.isdir(fpath)

    def exists(self, fpath):
        return os.path.exists(fpath)

    def open(self, fpath, mode='r'):
        return open(fpath, mode)

    def listdir(self, dpath):
        return os.listdir(dpath)

    def remove(self, fpath):
        os.remove(fpath)

    def rmdir(self, dpath):
        os.rmdir(dpath)

    def mkdirs(self, dpath):
        if not self.exists(dpath):
            os.makedirs(dpath)

    def dirname(self, fpath):
        return os.path.dirname(fpath)

    def basename(self, fpath):
        return os.path.basename(fpath)

    def abspath(self, fpath):
        return os.path.normpath(os.path.abspath(fpath))

    def _issubpath(self, fpath, fsubPath):
        return (
            len(fsubPath) > len(fpath) and
            fsubPath.startswith(fpath) and fsubPath[len(fpath)] == os.path.sep)

    def issubpath(self, fpath, fsubPath):
        return self._issubpath(self.abspath(fpath), self.abspath(fsubPath))

    def splitext(self, fpath):
        return os.path.splitext(fpath)

    def split(self, fpath):
        return os.path.split(fpath)

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
