# Copyright (c) 2016 Endre Bak
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import hashlib
import logging
from threading import RLock
from collections import defaultdict
from console import getLoggerAdapter

logger = getLoggerAdapter('xbuild.hash')
logger.setLevel(logging.DEBUG)

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
        # needDebug = fpath.endswith('clang/module_emb/GROUPED_002_FrTp_MT_AddressRange_PB/FrTp_TestUtils.o')
        needDebug = False
        if not fs.isfile(fpath):
            logger.cdebugf(needDebug, '{} does not exist!', fpath)
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
        def doit(what, files, recalc=False):
            for fpath in files:
                # needDebug = fpath.endswith('/ALU.o') or fpath.endswith('/ALU.vhdl')
                needDebug = False
                hashEnt = self.nameHashDict[fpath]
                logger.cdebugf(needDebug, '{} before hashEnt:{}', fpath, hashEnt)
                with hashEnt.lock:
                    if recalc or not hashEnt.new:
                        if not bldr.fs.isfile(fpath):
                            raise ValueError(
                                '{what}:"{file}" for task "{task}" does not exist!'.format(
                                    what=what, file=fpath, task=task.getId()))
                        hashEnt.setByFile(bldr.fs, fpath)
                        logger.cdebugf(needDebug, '{} after hashEnt:{}', fpath, hashEnt)
        with self.lock:
            doit('target', task.targets, recalc=True)
            doit('fileDep', task.getFileDeps())
            doit('generatedFile', task.generatedFiles, recalc=True)
            # doit(task.providedFileDeps) # provided file may not be built here
