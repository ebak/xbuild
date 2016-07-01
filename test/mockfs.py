import os
from xbuild import FS


# TODO use StringIO
class MockFile(object):
    
    def __init__(self, content=None):
        self.content = content

    def read(self):
        return self.content
    
    def write(self, content):
        self.content = content
    
    def __enter__(self):
        return self

    def __exit__(self, eType, eValue, eTrace):
        return False


class MockFS(FS):
    
    @staticmethod
    def tokenize(fpath):
        return fpath.split('/')

    def __init__(self):
        super(MockFS, self).__init__()
        self.folders = {}   # {folderName:{}} {fileName: textContent}

    def _walkDown(self, fpath):
        entries = MockFS.tokenize(fpath)
        curPath = self.folders
        for ent in entries:
            curPath = curPath.get(ent)
            if curPath is None:
                return None
        return curPath

    def isfile(self, fpath):
        ent = self._walkDown(fpath)
        return ent and type(ent) is not dict
    
    def isdir(self, fpath):
        ent = self._walkDown(fpath)
        return type(ent) is dict

    def exists(self, fpath):
        return self._walkDown(fpath) is not None

    def open(self, fpath, mode='r'):
        dPath, fName = os.path.split(fpath)
        ent = self.walkDown(dPath)
        if type(ent) is not dict:
            raise IOError("Cannot open '{}'!".format(fpath))
        if 'r' in mode:
            subEnt = ent.get(fName)
         
        return open(fpath, mode)
    
    def mkdirs(self, dpath):
        if not self.exists(dpath):
            os.makedirs(dpath)
