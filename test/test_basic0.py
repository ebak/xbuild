import sys
import unittest
from cStringIO import StringIO
from mockfs import MockFS
from xbuild import Builder, Task, targetUpToDate
from xbuild.console import setOut

def concat(bldr, task, **kvArgs):
    # raise ValueError
    res = ''
    for src in task.getAllFileDeps():
        res += bldr.fs.read(src)
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0    # SUCCESS


def wrongUpToDate(bldr, task, **kvArgs):
    raise ValueError("Sucks")


class Test(unittest.TestCase):

    def buildAndCheckOutput(self, bldr, trg, mustHave=[], forbidden=[]):
        mustHave = {line: [] for line in mustHave}
        forbidden = {line: [] for line in forbidden}
        capture = StringIO()
        setOut(capture)
        try:
            rc = bldr.buildOne(trg)
        finally:
            setOut(sys.stdout)
        lines = capture.getvalue().splitlines()
        for i, line in enumerate(lines):
            print ">" + line
            if line in mustHave:
                mustHave[line].append(i)
            if line in forbidden:
                forbidden[line].append(i)
        for line, idxs in mustHave.items():
            cnt = len(idxs)
            self.assertEquals(1, cnt, "Occurrence of '{}' = {}, expected 1".format(line, cnt))
        for line, idxs in forbidden.items():
            cnt = len(idxs)
            self.assertEquals(0, cnt, "Occurrence of '{}' = {}, expected 0".format(line, cnt))
        return rc

    def testOne(self):
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
        # TODO
        print '--- modify target ----'
        fs.write('out/concat.txt', "Lofasz es estifeny", mkDirs=True)
        expectBuild()
        self.assertEquals("aFile\n__bFile\n", fs.read('out/concat.txt'))
