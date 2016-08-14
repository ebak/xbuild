import sys
import unittest
from unittest import SkipTest
from cStringIO import StringIO
from mockfs import MockFS
from helper import XTest
from xbuild import Builder, HashEnt, Task, targetUpToDate
from xbuild.console import setOut

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


class Test(XTest):
    
    @SkipTest
    def testRace(self):
        '''This doesn't induce race condition.'''
        
        def createBldr(fs):
            bldr = Builder(workers=1, fs=fs)
            bldr.addTask(
                targets=['out/concat.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=concat)
            return bldr
        
        fs = MockFS()
        fs.write('src/a.txt', "aFile\n", mkDirs=True)
        fs.write('src/b.txt', "bFile\n", mkDirs=True)
        createBldr(fs).buildOne('out/concat.txt')
        print '--- rebuild ---'
        createBldr(fs).buildOne('out/concat.txt')
        print '--- modify a source ---'
        fs.write('src/b.txt', "__bFile\n", mkDirs=True)
        # print fs.show()
        createBldr(fs).buildOne('out/concat.txt')
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))
        print '--- TODO: remove target ----'
        fs.remove('out/concat.txt')
        createBldr(fs).buildOne('out/concat.txt')
        print '--- modify target ----'
        fs.write('out/concat.txt', "Lofasz es estifeny", mkDirs=True)
        createBldr(fs).buildOne('out/concat.txt')
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))

    def test1(self):

        def createBldr(fs):
            bldr = Builder(workers=2, fs=fs)
            bldr.addTask(
                targets=['out/concat.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=targetUpToDate,
                action=concat)
            return bldr
        
        def expectBuild():
            bldr = createBldr(fs)
            self.assertEquals(
                self.buildAndCheckOutput(
                    bldr,
                    'out/concat.txt',
                    mustHave=['INFO: Building out/concat.txt.', 'INFO: BUILD PASSED!'],
                    forbidden=['INFO: out/concat.txt is up-to-date.']), 0)
        
        def expectUpToDate():
            bldr = createBldr(fs)
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
            

        def createBldr(fs):
            bldr = Builder(workers=2, fs=fs)
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
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
                'out/hash.txt',
                mustHave=['INFO: Building out/concat.txt.', 'INFO: Building all.', 'INFO: BUILD PASSED!'],
                forbidden=[]),
            0)
        # print fs.show()
        self.assertEquals('aFile\nbFile\n', fs.read('out/concat.txt'))
        self.assertTrue(fs.isfile('out/hash.txt'))
        print "--- rebuild ---"
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
                'out/hash.txt',
                mustHave=['INFO: out/concat.txt is up-to-date.', 'INFO: all is up-to-date.', 'INFO: BUILD PASSED!'],
                forbidden=[]),
            0)
        print "--- modify a source ---"
        fs.write('src/b.txt', 'brrrr\n', mkDirs=True)
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
                'out/hash.txt',
                mustHave=['INFO: Building out/concat.txt.', 'INFO: Building all.', 'INFO: BUILD PASSED!'],
                forbidden=[]),
            0)
        # print fs.show()
        self.assertEquals('aFile\nbrrrr\n', fs.read('out/concat.txt'))
        self.assertTrue(fs.isfile('out/hash.txt'))
        print "--- remove a top level target ---"
        fs.remove('out/hash.txt')
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
                'out/hash.txt',
                mustHave=['INFO: out/concat.txt is up-to-date.', 'INFO: Building all.', 'INFO: BUILD PASSED!'],
                forbidden=[]),
            0)

    def test3(self):
        '''Testing when more targets depends on the same file.'''
        def createBldr(fs):
            bldr = Builder(workers=2, fs=fs)
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
            return bldr
    
        print '>>>--- Test3 ---<<<'
        fs = MockFS()
        fs.write('src/a.txt', 'aFile\n', mkDirs=True)
        fs.write('src/b.txt', 'bFile\n', mkDirs=True)
        fs.write('src/c.txt', 'cFile\n', mkDirs=True)
        fs.write('src/d.txt', 'dFile\n', mkDirs=True)
        fs.write('src/e.txt', 'eFile\n', mkDirs=True)
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
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
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
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
        self.assertEquals(
            self.buildAndCheckOutput(
                createBldr(fs),
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
