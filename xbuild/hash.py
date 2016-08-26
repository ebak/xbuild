import hashlib
from threading import RLock
from collections import defaultdict


class HashEnt(object):

    @staticmethod
    def calcHash(content):
        return hashlib.md5(content).hexdigest()

    @staticmethod
    def _loadJsonObj(jsonObj, warnfFn):
        if type(jsonObj) not in (str, unicode):
            warnfFn("HashEnt._loadJsonObj(): str entry expected! Got: {}", type(jsonObj))
            return None
        return HashEnt(old=str(jsonObj), new=None)
    
    def __init__(self, old=None, new=None):
        self.old, self.new = old, new
        self.lock = RLock()

    def __repr__(self):
        return 'HashEnt:(old={}, new={})'.format(self.old, self.new)

    def matches(self):
        return False if self.old is None else self.old == self.new

    def setByContent(self, content):
        self.new = HashEnt.calcHash(content)

    def setByFile(self, fs, fpath):
        if not fs.isfile(fpath):
            return
        with fs.open(fpath) as f:
            return self.setByContent(f.read())

    def _toJsonObj(self):
        return self.new if self.new else self.old
        

class HashDict(object):


    def __init__(self):
        self.lock = RLock()
        self.nameHashDict = defaultdict(HashEnt)

    def _loadJsonObj(self, jsonObj, warnfFn):
        if type(jsonObj) is not dict:
            warnfFn("HashDict._sloadJsonObj(): dict is expected!")
            return False
        warns = 0
        for name, hashEntObj in jsonObj.items():
            hashEnt = HashEnt._loadJsonObj(hashEntObj, warnfFn)
            if hashEnt:
                self.nameHashDict[str(name)] = hashEnt
            else:
                warns += 1
                
        return False if warns else True
    
    def _toJsonObj(self):
        return {name: hashEnt._toJsonObj() for name, hashEnt in self.nameHashDict.items()}

    def clear(self):
        with self.lock:
            self.nameHashDict.clear()

    def get(self, name):
        with self.lock:
            return self.nameHashDict[name]

    def remove(self, name):
        # No lock, it is called from one thread
        self.nameHashDict.pop(name, None)

    def storeTaskHashes(self, bldr, task):  # TODO: pass FS instead of Builder
        '''Currently it is automatically called when the task build is completed.'''
        def doit(what, files):
            for fpath in files:
                hashEnt = self.nameHashDict[fpath]
                with hashEnt.lock:
                    if not hashEnt.new:
                        if not bldr.fs.isfile(fpath):
                            raise ValueError(
                                '{what}:"{file}" for task "{task}" does not exist!'.format(
                                    what=what, file=fpath, task=task.getId()))
                        hashEnt.setByFile(bldr.fs, fpath)
        with self.lock:
            doit('target', task.targets)
            doit('fileDep', task.getFileDeps())
            doit('generatedFile', task.generatedFiles)
            # doit(task.providedFileDeps) # provided file may not be built here
