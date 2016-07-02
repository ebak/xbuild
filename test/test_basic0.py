import unittest
from mockfs import MockFS
from xbuild import Builder, Task, targetUpToDate

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

    def testOne(self):
        def createBldr(fs):
            fs.write('src/a.txt', "aFile\n", mkDirs=True)
            fs.write('src/b.txt', "bFile\n", mkDirs=True)
            bldr = Builder(workers=2, fs=fs)
            bldr.addTask(
                targets=['out/concat.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                upToDate=(targetUpToDate, {}),
                action=(concat, {}))
            return bldr
            
        fs = MockFS()
        bldr = createBldr(fs)
        bldr.buildOne('out/concat.txt')
        print fs.show()
        self.assertEquals("aFile\nbFile\n", fs.read('out/concat.txt'))
        # rebuild
        print '--- rebuild ---'
        bldr = createBldr(fs)
        bldr.buildOne('out/concat.txt')
        self.assertEquals("aFile\nbFile\n", fs.read('out/concat.txt'))
        print '--- modify a source ---'
        fs.write('src/b.txt', "__bFile\n", mkDirs=True)
        bldr = createBldr(fs)
        bldr.buildOne('out/concat.txt')
