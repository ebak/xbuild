
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

import sys
import unittest
from unittest import SkipTest
from cStringIO import StringIO
from mockfs import MockFS
from helper import XTest
from xbuild import Builder, HashEnt, Task, targetUpToDate
from xbuild.console import setOut

WORKERS=2

def concat(bldr, task, **kwargs):
    # raise ValueError
    res = ''
    for src in task.getFileDeps():
        res += bldr.fs.read(src)
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0    # SUCCESS


# TODO: check
def wrongUpToDate(bldr, task, **kwargs):
    raise ValueError("Sucks")


def createBldr(fs):
    return Builder(fs=fs, workers=WORKERS, printUpToDate=True)


class Test(XTest):
    
    @SkipTest
    def testRace(self):
        '''This doesn't induce race condition.'''
        
        def createTasks(bldr):
            bldr.addTask(
                targets=['out/concat.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=concat)
        
        fs = MockFS()
        fs.write('src/a.txt', "aFile\n", mkDirs=True)
        fs.write('src/b.txt', "bFile\n", mkDirs=True)
        with createBldr(fs) as bldr:
            createTasks(bldr)
            bldr.buildOne('out/concat.txt')
        print '--- rebuild ---'
        with createBldr(fs) as bldr:
            createTasks(bldr)
            bldr.buildOne('out/concat.txt')
        print '--- modify a source ---'
        fs.write('src/b.txt', "__bFile\n", mkDirs=True)
        # print fs.show()
        with createBldr(fs) as bldr:
            createTasks(bldr)
            bldr.buildOne('out/concat.txt')
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))
        print '--- TODO: remove target ----'
        fs.remove('out/concat.txt')
        with createBldr(fs) as bldr:
            createTasks(bldr)
            bldr.buildOne('out/concat.txt')
        print '--- modify target ----'
        fs.write('out/concat.txt', "Lofasz es estifeny", mkDirs=True)
        with createBldr(fs) as bldr:
            createTasks(bldr)
            bldr.buildOne('out/concat.txt')
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))

    def test1(self):

        def createTasks(bldr):
            bldr.addTask(
                targets=['out/concat.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=concat)
        
        def expectBuild():
            with createBldr(fs) as bldr:
                createTasks(bldr)
                self.assertEquals(
                    self.buildAndCheckOutput(
                        bldr,
                        'out/concat.txt',
                        mustHave=['INFO: Building out/concat.txt.', 'INFO: BUILD PASSED!'],
                        forbidden=['INFO: out/concat.txt is up-to-date.']), 0)
            
        def expectUpToDate():
            with createBldr(fs) as bldr:
                createTasks(bldr)
                self.assertEquals(
                    self.buildAndCheckOutput(
                        bldr,
                        'out/concat.txt',
                        mustHave=['INFO: out/concat.txt is up-to-date.', 'INFO: BUILD PASSED!'],
                        forbidden=['INFO: Building out/concat.txt.']), 0)

        print '>>>--- Test1 ---<<<'
        # setXDebug(True)
        fs = MockFS()
        fs.write('src/a.txt', "aFile\n", mkDirs=True)
        fs.write('src/b.txt', "bFile\n", mkDirs=True)
        expectBuild()
        # print fs.show()
        self.assertEquals("aFile\nbFile\n", fs.read('out/concat.txt'))
        # rebuild
        print '--- rebuild ---'
        expectUpToDate()
        self.assertEquals("aFile\nbFile\n", fs.read('out/concat.txt'))
        print '--- modify a source ---'
        fs.write('src/b.txt', "__bFile\n", mkDirs=True)
        # print fs.show()
        expectBuild()
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))
        print '--- TODO: remove target ----'
        fs.remove('out/concat.txt')
        expectBuild()
        print '--- modify target ----'
        fs.write('out/concat.txt', "Lofasz es estifeny", mkDirs=True)
        expectBuild()
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))

    def test2(self):
        
        def countAction(bldr, task, **kwargs):
            
            def countChars(trg, fileDeps):
                res = ''
                for fileDep in fileDeps:
                    content = bldr.fs.read(fileDep)
                    res += 'fileName: {}, chars: {}\n'.format(fileDep, len(content))
                bldr.fs.write(trg, res, mkDirs=True)
            
            def calcHash(trg, fileDeps):
                res = ''
                for fileDep in fileDeps:
                    hashCode = HashEnt.calcHash(bldr.fs.read(fileDep))
                    res += 'fileName: {}, hash: {}\n'.format(fileDep, hashCode)
                bldr.fs.write(trg, res, mkDirs=True)
            
            fileDeps = task.getFileDeps()
            for trg in task.targets:
                if 'charCnt.txt' == bldr.fs.basename(trg):
                    countChars(trg, fileDeps)
                elif 'hash.txt' == bldr.fs.basename(trg):
                    calcHash(trg, fileDeps)
            return 0
            

        def createTasks(bldr):
            bldr.addTask(
                name='all',
                targets=['out/charCnt.txt', 'out/hash.txt'],
                fileDeps=['out/concat.txt', 'src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=countAction)
            bldr.addTask(
                targets=['out/concat.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=concat)
            return bldr
        
        print '>>>--- Test2 ---<<<'
        fs = MockFS()
        fs.write('src/a.txt', 'aFile\n', mkDirs=True)
        fs.write('src/b.txt', 'bFile\n', mkDirs=True)
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'out/hash.txt',
                    mustHave=['INFO: Building out/concat.txt.', 'INFO: Building all.', 'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)
        # print fs.show()
        self.assertEquals('aFile\nbFile\n', fs.read('out/concat.txt'))
        self.assertTrue(fs.isfile('out/hash.txt'))
        print "--- rebuild ---"
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'out/hash.txt',
                    mustHave=['INFO: out/concat.txt is up-to-date.', 'INFO: all is up-to-date.', 'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)
        print "--- modify a source ---"
        fs.write('src/b.txt', 'brrrr\n', mkDirs=True)
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'out/hash.txt',
                    mustHave=['INFO: Building out/concat.txt.', 'INFO: Building all.', 'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)
        # print fs.show()
        self.assertEquals('aFile\nbrrrr\n', fs.read('out/concat.txt'))
        self.assertTrue(fs.isfile('out/hash.txt'))
        print "--- remove a top level target ---"
        fs.remove('out/hash.txt')
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'out/hash.txt',
                    mustHave=['INFO: out/concat.txt is up-to-date.', 'INFO: Building all.', 'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)

    def test3(self):
        '''Testing when more targets depends on the same file.'''
        def createTasks(bldr):
            bldr.addTask(
                targets=['out/c1.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=concat)
            bldr.addTask(
                targets=['out/c2.txt'],
                fileDeps=['src/b.txt', 'src/c.txt'],
                upToDate=targetUpToDate,
                action=concat)
            bldr.addTask(
                targets=['out/c3.txt'],
                fileDeps=['src/d.txt', 'src/e.txt'],
                upToDate=targetUpToDate,
                action=concat)
            bldr.addTask(
                name='all',
                fileDeps=['out/c1.txt', 'out/c2.txt', 'out/c3.txt'],
                upToDate=targetUpToDate)
    
        print '>>>--- Test3 ---<<<'
        fs = MockFS()
        fs.write('src/a.txt', 'aFile\n', mkDirs=True)
        fs.write('src/b.txt', 'bFile\n', mkDirs=True)
        fs.write('src/c.txt', 'cFile\n', mkDirs=True)
        fs.write('src/d.txt', 'dFile\n', mkDirs=True)
        fs.write('src/e.txt', 'eFile\n', mkDirs=True)
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'all',
                    mustHave=[
                        'INFO: Building out/c1.txt.',
                        'INFO: Building out/c2.txt.',
                        'INFO: Building out/c3.txt.',
                        'INFO: Building all.',
                        'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)
        self.assertEquals('aFile\nbFile\n', fs.read('out/c1.txt'))
        self.assertEquals('bFile\ncFile\n', fs.read('out/c2.txt'))
        self.assertEquals('dFile\neFile\n', fs.read('out/c3.txt'))
        print '--- rebuild ---'
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'all',
                    mustHave=[
                        'INFO: out/c1.txt is up-to-date.',
                        'INFO: out/c2.txt is up-to-date.',
                        'INFO: out/c3.txt is up-to-date.',
                        'INFO: all is up-to-date.',
                        'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)
        self.assertEquals('aFile\nbFile\n', fs.read('out/c1.txt'))
        self.assertEquals('bFile\ncFile\n', fs.read('out/c2.txt'))
        self.assertEquals('dFile\neFile\n', fs.read('out/c3.txt'))
        print '--- modify common depend file ---'
        fs.write('src/b.txt', 'brrrFile\n', mkDirs=True)
        with createBldr(fs) as bldr:
            createTasks(bldr)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'all',
                    mustHave=[
                        'INFO: out/c3.txt is up-to-date.',
                        'INFO: Building out/c1.txt.',
                        'INFO: Building out/c2.txt.',
                        'INFO: BUILD PASSED!'],
                    forbidden=[]),
                0)
        self.assertEquals('aFile\nbrrrFile\n', fs.read('out/c1.txt'))
        self.assertEquals('brrrFile\ncFile\n', fs.read('out/c2.txt'))
        self.assertEquals('dFile\neFile\n', fs.read('out/c3.txt'))
