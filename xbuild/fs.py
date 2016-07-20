import os

'''This is a wrapper over the filesystem. It makes possible to map other kind of resources
   as FS resources. It is also comfortable for mocking.'''
class FS(object):

    def __init__(self):
        pass
    
    def tokenizePath(self, fpath):
        res = []
        head = fpath
        while len(head) and head not in ('/', '\\'):
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


class DirEnt(object):

    def __init__(self):
        self.folders = {}   # {name: DirEnt}
        self.files = set()


class Cleaner(object):
    '''It accepts a list of removable paths, removes the paths
    and their empty parent directories.'''

    def __init__(self, fs, absPaths=[]):
        self.fs = fs
        self.root = DirEnt()
        for ap in absPaths:
            self.add(ap)

    def add(self, absPath):
        ents = self.fs.tokenizePath(absPath)
        isFileList = [False for _ in range(len(ents) - 1)]
        isFileList += [self.fs.isfile(absPath)]
        curDir = self.root
        for ent, isFile in zip(ents, isFileList):
            if isFile:
                curDir.files.add(ent)
            else:
                subDir = curDir.folders.get(ent)
                # TODO check for file with same name
                if subDir is None:
                    subDir = DirEnt()
                    curDir.folders[ent] = subDir
                curDir = subDir

    def clean(self):
        '''Returns ([removedDirs], [removedFiles])'''
        def cleanDir(dirPath, dirEnt):
            '''Returns (isEmpty, [removedDirs], [removedFiles])'''
            removedDirs, removedFiles = [], []
            for f in dirEnt.files:
                fpath = os.path.join(dirPath, f)
                self.fs.remove(fpath)
                removedFiles.append(fpath)
            for dname, dent in dirEnt.folders.items():
                subPath = os.path.join(dirPath, dname)
                isEmpty, subRemovedDirs, subRemovedFiles = cleanDir(subPath, dent)
                if isEmpty:
                    self.fs.rmdir(subPath)
                    removedDirs.append(subPath)
                else:
                    removedDirs += subRemovedDirs
                    removedFiles += subRemovedFiles
            return len(self.fs.listdir(dirPath)) == 0, removedDirs, removedFiles

        _, removedDirs, removedFiles = cleanDir('', self.root)
        return removedDirs, removedFiles

            
            