import hashlib
from threading import Lock
from collections import defaultdict


class HashEnt(object):

    @staticmethod
    def calcHash(content):
        return hashlib.md5(content).hexdigest()

    @staticmethod
    def _loadJsonObj(jsonObj, warnfFn):
        if type(jsonObj) is not str:
            warnfFn("HashEnt._loadJsonObj(): str entry expected!")
            return None
        return HashEnt(jsonObj, None)
    
    def __init__(self, old=None, new=None):
        self.old, self.new = old, new

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
        self.lock = Lock()
        self.nameHashDict = defaultdict(HashEnt)

    def _loadJsonObj(self, jsonObj, warnfFn):
        if type(jsonObj) is not dict:
            warnfFn("HashDict._sloadJsonObj(): dict is expected!")
            return False
        warns = 0
        for name, hashEntObj in jsonObj:
            hashEnt = HashEnt._loadJsonObj(hashEntObj, warnfFn)
            if hashEnt:
                warns += 1
                self.nameHashDict[name] = hashEnt
        return False if warns else True
    
    def _toJsonObj(self):
        return {name: hashEnt._toJsonObj() for name, hashEnt in self.nameHashDict.items()}

    def get(self, name):
        with self.lock:
            return self.nameHashDict.get(name)

    def storeTargetHashes(self, task):
        '''It should be called by the action function at the end.'''
        for trg in task.targets:
            hashEnt = self.nameHashDict.get(trg)
            if not hashEnt.new:
                hashEnt.setByFile(trg)
