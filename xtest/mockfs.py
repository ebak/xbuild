import os
import xbuild.fs as fs
from xbuild import FS
from StringIO import StringIO
from threading import RLock, Lock


# TODO use StringIO
class MyIO(StringIO):
    
    def __init__(self):
        StringIO.__init__(self) # StringIO is old style class
        self.lock = Lock()

    def reset(self):
        self.lock.acquire()
        self.truncate(size=0)

    def close(self):
        self.seek(0)
        self.lock.release()
        
    def __enter__(self):
        return self

    def __exit__(self, eType, eValue, eTrace):
        self.close()
        return False


class MockFS(FS):

    @staticmethod
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
    
    @staticmethod
    def tokenize(fpath):
        npath = fs.normPath(fpath)
        return [ent for ent in npath.split('/') if ent and ent != '.']

    def __init__(self):
        super(MockFS, self).__init__()
        self.root = {}   # {folderName:{}} {fileName: MyIO}
        self.lock =  RLock()

    def getFileList(self):
        res = []
        
        def appendFiles(dirPath, folder):
            for name, ent in sorted(folder.items(), cmp=MockFS.entcmp):
                epath = fs.joinPath(dirPath, name) if dirPath else name
                if isinstance(ent, MyIO):
                    res.append(epath)
                else:
                    appendFiles(epath, ent)
        
        appendFiles('', self.root)
        return res

    def show(self, content=False):
        
        def showEnt(out, indent, folder):
            for name, ent in sorted(folder.items(), cmp=MockFS.entcmp):
                if isinstance(ent, MyIO):
                    print >>out, "{}file {}:".format(indent, name)
                    if content:
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
        entries = self.tokenizePath(fpath) # MockFS.tokenize(fpath)
        #if len(entries) and entries[0].startswith('/'):
        #    entries[0] = entries[0][1:] # /home -> home
        curPath = self.root
        for ent in entries:
            curPath = curPath.get(ent)
            if curPath is None:
                return None
        return curPath

    def isfile(self, fpath):
        with self.lock:
            ent = self._walkDown(fpath)
            return isinstance(ent, MyIO)
    
    def isdir(self, dpath):
        with self.lock:
            ent = self._walkDown(dpath)
            return type(ent) is dict

    def abspath(self, fpath):
        return os.path.normpath(fpath)

    def exists(self, fpath):
        with self.lock:
            return self._walkDown(fpath) is not None

    def open(self, fpath, mode='r'):
        with self.lock:
            dPath, fName = os.path.split(fpath)
            if dPath == '/':
                ent = self.root
                fName = fpath
            else:
                ent = self._walkDown(dPath)
            if type(ent) is not dict:
                raise IOError("Cannot open '{}'!".format(fpath))
            subEnt = ent.get(fName)
            if type(subEnt) is dict:
                raise IOError("'{}' is a directory!".format(fpath))
            if 'r' in mode:
                if subEnt is None:
                    raise IOError("'{}' does not exist!".format(fpath))
                elif isinstance(subEnt, MyIO):
                    subEnt.lock.acquire()
                    return subEnt
                raise IOError("'{}' is a folder!".format(fpath))
            elif 'w' in mode:
                if subEnt is None:
                    ent[fName] = subEnt = MyIO()
                subEnt.reset()
                return subEnt

    def listdir(self, dpath, dontFail=False):
        with self.lock:
            curEnt = self._walkDown(dpath)
            if dontFail:
                return curEnt.keys() if type(curEnt) is dict else []
            else: 
                assert type(curEnt) is dict, 'path:{}, type:{}'.format(dpath, type(curEnt))
                return curEnt.keys()

    def remove(self, fpath):
        with self.lock:
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
        with self.lock:
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
        with self.lock:
            entries = self.tokenizePath(dpath)  # MockFS.tokenize(dpath)
            curPath = self.root
            for ent in entries:
                nextPath = curPath.get(ent)
                if nextPath is None:
                    curPath[ent] = nextPath = {}
                elif isinstance(nextPath, MyIO):
                    raise IOError("mkdirs: invalid path '{}'".format(dpath))
                curPath = nextPath
            
            
