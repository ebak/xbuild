import os
from threading import RLock
from shutil import copyfile
from console import logger


def joinPath(*ents):
    res = ents[0]
    for ent in ents[1:]:
        res += '/' + ent
    return res


def normPath(fpath):
    return goodPath(os.path.normpath(fpath))


def absPath(fpath):
    return normPath(os.path.abspath(fpath))


def dirName(fpath):
    return goodPath(os.path.dirname(fpath))


def baseName(fpath):
    return os.path.basename(fpath)

def splitExt(fpath):
    return os.path.splitext(fpath)

def goodPath(fpath):
    '''No DOSism.'''
    return fpath.replace('\\', '/')


def relPath(basePath, fpath):
    return goodPath(os.path.relpath(fpath, basePath))


def dosPath(fpath):
    return fpath.replace('/', '\\')


'''This is a wrapper over the filesystem. It makes possible to map other kind of resources
   as FS resources. It is also comfortable for mocking.'''
class FS(object):

    def __init__(self):
        self.lock = RLock()
        # TODO: context based locking
    
    def tokenizePath(self, fpath):
        res = [
            ent for ent in fpath.replace('\\', '/').split('/') if ent and ent != '.']
        if len(res) > 1 and len(res[0]) == 2 and res[0][1] == ':':   # DOS drive letter and path
            res[0] = res[0] + '/' + res[1]
            del res[1]
        return res

    # Needed for Windows to handle drive letter as path entry.
    def joinPath(self, *ents):
        return joinPath(*ents)

    def isfile(self, fpath):
        return os.path.isfile(fpath)

    def isdir(self, fpath):
        return os.path.isdir(fpath)

    def exists(self, fpath):
        return os.path.exists(fpath)

    def open(self, fpath, mode='r'):
        return open(fpath, mode)

    def copy(self, spath, dpath):
        copyfile(spath, dpath)

    def listdir(self, dpath):
        try:
            return os.listdir(dpath)
        except:
            print 'dpath={}'.format(dpath)
            raise

    def remove(self, fpath):
        os.remove(fpath)

    def rmdir(self, dpath):
        os.rmdir(dpath)

    def cleandir(self, dpath):
        with self.lock:
            for f in self.listdir(dpath):
                fpath = joinPath(dpath, f)
                if self.isfile(fpath):
                    self.remove(fpath)
                elif self.isdir(fpath):
                    self.cleandir(fpath)
                else:
                    assert False, "Cannot remove entity: {}".format(fpath)

    def mkdirs(self, dpath):
        with self.lock:
            if not self.exists(dpath):
                os.makedirs(dpath)

    def dirname(self, fpath):
        return dirName(fpath)

    def basename(self, fpath):
        return baseName(fpath)

    def abspath(self, fpath):
        return absPath(fpath)

    def _issubpath(self, fpath, fsubPath):
        return (
            len(fsubPath) > len(fpath) and
            fsubPath.startswith(fpath) and fsubPath[len(fpath)] == os.path.sep)

    def issubpath(self, fpath, fsubPath):
        return self._issubpath(self.abspath(fpath), self.abspath(fsubPath))

    def splitext(self, fpath):
        return splitExt(fpath)

    def split(self, fpath):
        # TODO: it is platform dependent
        return os.path.split(fpath)

    def read(self, fpath):
        with self.open(fpath) as f:
            return f.read()

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
        logger.debugf('absPath={}', absPath)
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
            logger.debugf('dirPath={}', dirPath)
            removedDirs, removedFiles = [], []
            for f in dirEnt.files:
                fpath = self.fs.joinPath(dirPath, f)
                if self.fs.isfile(fpath):   # FIXME: assert?
                    # logger.debugf('remove: {}', fpath)
                    self.fs.remove(fpath)
                    removedFiles.append(fpath)
            for dname, dent in dirEnt.folders.items():
                subPath = self.fs.joinPath(dirPath, dname)
                isEmpty, subRemovedDirs, subRemovedFiles = cleanDir(subPath, dent)
                # print "isEmpty:{}, subRemovedDirs:{}, subRemovedFiles:{} = cleanDir(subPath:{}, dent:{})".format(
                #    isEmpty, subRemovedDirs, subRemovedFiles, subPath, dent)
                if isEmpty:
                    logger.debugf('rmdir: {}', subPath)
                    self.fs.rmdir(subPath)
                    removedDirs.append(subPath)
                else:
                    removedDirs += subRemovedDirs
                    removedFiles += subRemovedFiles
            # logger.debugf('dirPath:{} entries:{}', dirPath, len(self.fs.listdir(dirPath)))
            return len(self.fs.listdir(dirPath)) == 0, removedDirs, removedFiles

        removedDirs, removedFiles = [], []
        for dirName, dirEnt in self.root.folders.items():
            removeDir, rDirs, rFiles = cleanDir(dirName, dirEnt)
            # print "removeDir:{}, rDirs:{}, rFiles:{} = cleanDir(dirName:{}, dirEnt:{})".format(
            #    removeDir, rDirs, rFiles, dirName, dirEnt)
            if removeDir:
                self.fs.rmdir(dirName)
                removedDirs.append(dirName)
            else:
                removedDirs += rDirs
                removedFiles += rFiles
        return removedDirs, removedFiles

if __name__ == '__main__':
    fs = FS()
    print fs.joinPath('C:', 'pupak', 'rozi')
    print fs.joinPath('.config', 'pidgin')
    print fs.joinPath('/usr', 'src')      
            