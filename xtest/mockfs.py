import os
import xbuild.fs as fs
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
        self.close()
        return False


class MockFS(FS):
    
    @staticmethod
    def tokenize(fpath):
        npath = fs.normPath(fpath)
        return [ent for ent in npath.split('/') if ent and ent != '.']

    def __init__(self):
        super(MockFS, self).__init__()
        self.root = {}   # {folderName:{}} {fileName: MyIO}

    def show(self):
        
        def entcmp(ne0, ne1):
            name0, ent0 = ne0
            name1, ent1 = ne1
            if isinstance(ent0, dict):
                # dirs go top
                if isinstance(ent1, dict):
                    return -1 if name0 < name1 else 1
                else:
                    return -1
            elif isinstance(ent1, dict):
                return 1
            else:
                return -1 if name0 < name1 else 1
                 
            
        
        def showEnt(out, indent, folder):
            for name, ent in sorted(folder.items(), cmp=entcmp):
                if isinstance(ent, MyIO):
                    print >>out, "{}file {}:".format(indent, name)
                    subind = indent + '  '
                    for line in ent.getvalue().splitlines():
                        print >>out, subind + line
                else:
                    print >>out, "{}dir {}:".format(indent, name)
                    showEnt(out, indent + '  ', ent)
        
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
    
    def isdir(self, dpath):
        ent = self._walkDown(dpath)
        return type(ent) is dict

    def abspath(self, fpath):
        return os.path.normpath(fpath)

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

    def listdir(self, dpath):
        curEnt = self._walkDown(dpath)
        assert type(curEnt) is dict, 'path:{}, type:{}'.format(dpath, type(curEnt))
        return curEnt.keys()

    def remove(self, fpath):
        dPath, fName = os.path.split(fpath)
        ent = self._walkDown(dPath)
        if type(ent) is not dict:
            raise IOError("Cannot open '{}'!".format(fpath))
        subEnt = ent.get(fName)
        if subEnt is None:
            raise IOError("'{}' does not exists!".format(fpath))
        elif type(subEnt) is dict:
            raise IOError("'{}' is a directory!".format(fpath))
        else:
            del ent[fName]

    # TODO: test
    def rmdir(self, dpath):
        pDir, folder = os.path.split(dpath)
        ent = self._walkDown(pDir)
        if type(ent) is not dict:
            raise IOError("Cannot open '{}'!".format(dpath))
        subEnt = ent.get(folder)
        if subEnt is None:
            raise IOError("'{}' does not exists!".format(dpath))
        elif type(subEnt) is not dict:
            raise IOError("'{}' is not a directory!".format(dpath))
        elif len(subEnt) > 0:
            raise IOError("'{}' is not empty!".format(dpath))
        else:
            del ent[folder]
        
    
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
            
            