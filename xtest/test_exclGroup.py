
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

from time import sleep
from mockfs import MockFS
from helper import XTest
from xbuild import Builder
from threading import Lock

class ThreadReg(object):

    def __init__(self):
        self.cnt = 0
        self.maxCnt = 0
        self.lock = Lock()

    def reset(self):
        self.cnt, self.maxCnt = 0, 0

    def __enter__(self):
        with self.lock:
            self.cnt += 1
            if self.cnt > self.maxCnt:
                self.maxCnt = self.cnt
            return self

    def __exit__(self, exc_type, exc_value, traceback):
        with self.lock:
            self.cnt -= 1

thrReg = ThreadReg()


def concat(bldr, task, **kwargs):
    with thrReg:
        res = ''
        for src in task.getFileDeps():
            res += bldr.fs.read(src)
        for trg in task.targets:
            bldr.fs.write(trg, res, mkDirs=True)
        sleep(0.01)
        return 0    # SUCCESS


def count(bldr, task, **kwargs):
    res = 0
    for src in task.getFileDeps():
        res += len(bldr.fs.read(src))
    for trg in task.targets:
        bldr.fs.write(trg, str(res), mkDirs=True)
    return 0    # SUCCESS


class Test(XTest):

    def createFS(self):
        fs = MockFS()
        for n in ('a', 'b', 'c', 'd'):
            fs.write('src/{}.txt'.format(n), '{}File'.format(n), mkDirs=True)
        return fs

    def createTasks(self, bldr, exclGroup=True):
        bldr.addTask(
            name='Concat0',
            targets=['out/ab.txt'],
            fileDeps=['src/a.txt', 'src/b.txt'],
            exclGroup=exclGroup,
            action=concat)
        bldr.addTask(
            name='Concat1',
            targets=['out/cd.txt'],
            fileDeps=['src/c.txt', 'src/d.txt'],
            exclGroup=exclGroup,
            action=concat)
        bldr.addTask(
            name='Cnt0',
            targets=['out/ab.cnt'],
            fileDeps=['out/ab.txt'],
            action=count)
        bldr.addTask(
            name='Cnt1',
            targets=['out/cd.cnt'],
            fileDeps=['out/cd.txt'],
            action=count)
        bldr.addTask(
            name='All',
            taskDeps=['Cnt0', 'Cnt1'])

    def testNoGroup(self):
        '''Build without exclude group.'''
        print '''Build without exclude group.'''
        thrReg.reset()
        fs = self.createFS()
        with Builder(fs=fs, workers=2) as bldr:
            self.createTasks(bldr, exclGroup=None)
            rc, output = self.buildAndFetchOutput(bldr, 'All')
            self.assertEquals(0, rc)
            self.assertEquals(2, thrReg.maxCnt)

    def testWithGroup(self):
        '''Build with exclude group.'''
        print '''Build with exclude group.'''
        thrReg.reset()
        fs = self.createFS()
        with Builder(fs=fs, workers=2) as bldr:
            self.createTasks(bldr, exclGroup='Concat')
            rc, output = self.buildAndFetchOutput(bldr, 'All')
            self.assertEquals(0, rc)
            self.assertEquals(1, thrReg.maxCnt)
        
