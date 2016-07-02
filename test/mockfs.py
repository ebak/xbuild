import os
from xbuild import FS
from StringIO import StringIO


# TODO use StringIO
class MyIO(StringIO):
    
    def __init__(self):
        StringIO.__init__(self) # StringIO is old style class

    def reset(self):
        self.truncate(size=0)

    def close(self):
        self.seek(0)
        
    def __enter__(self):
        return self

    def __exit__(self, eType, eValue, eTrace):
        return False


class MockFS(FS):
    
    @staticmethod
    def tokenize(fpath):
        npath = os.path.normpath(fpath)
        return [ent for ent in npath.split('/') if ent and ent != '.']

    def __init__(self):
        super(MockFS, self).__init__()
        self.root = {}   # {folderName:{}} {fileName: MyIO}

    def show(self):
        
        def showEnt(out, indent, folder):
            for name, ent in folder.items():
                if isinstance(ent, MyIO):
                    print >>out, "{}{}:{}".format(indent, name, ent.getvalue())
                else:
                    print >>out, "{}dir {}:".format(indent, name)
                    showEnt(out, indent + ' ', ent)
        
        out = StringIO()
        showEnt(out, '', self.root)
        return out.getvalue()

    def _walkDown(self, fpath):
        entries = MockFS.tokenize(fpath)
        curPath = self.root
        for ent in entries:
            curPath = curPath.get(ent)
            if curPath is None:
                return None
        return curPath

    def isfile(self, fpath):
        ent = self._walkDown(fpath)
        return isinstance(ent, MyIO)
    
    def isdir(self, fpath):
        ent = self._walkDown(fpath)
        return type(ent) is dict

    def exists(self, fpath):
        return self._walkDown(fpath) is not None

    def open(self, fpath, mode='r'):
        dPath, fName = os.path.split(fpath)
        ent = self._walkDown(dPath)
        if type(ent) is not dict:
            raise IOError("Cannot open '{}'!".format(fpath))
        subEnt = ent.get(fName)
        if type(subEnt) is dict:
            raise IOError("'{}' is a directory!".format(fpath))
        if 'r' in mode:
            if isinstance(subEnt, MyIO):
                subEnt.seek(0)
                return subEnt
            raise IOError("'{}' is a folder!".format(fpath))
        elif 'w' in mode:
            if subEnt is None:
                ent[fName] = subEnt = MyIO()
                subEnt.reset()
                return subEnt
            else:
                subEnt.reset()
                return subEnt
    
    def mkdirs(self, dpath):
        entries = MockFS.tokenize(dpath)
        curPath = self.root
        for ent in entries:
            nextPath = curPath.get(ent)
            if nextPath is None:
                curPath[ent] = nextPath = {}
            elif isinstance(nextPath, MyIO):
                raise IOError("mkdirs: invalid path '{}'".format(dpath))
            curPath = nextPath
            
            
