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

class Test(unittest.TestCase):

    def testOne(self):
        fs = MockFS()
        fs.write('src/a.txt', "aFile\n", mkDirs=True)
        fs.write('src/b.txt', "bFile\n", mkDirs=True)
        bldr = Builder(workers=2, fs=fs)
        bldr.addTask(
            targets=['out/concat.txt'],
            fileDeps=['src/a.txt', 'src/b.txt'],
            upToDate=(targetUpToDate, {}),
            action=(concat, {}))
        bldr.buildOne('out/concat.txt')
        print "queueSize={}".format(len(bldr.queue.sortedList))
        print fs.show()
        self.assertEquals("aFile\nbFile\n", fs.read('out/concat.txt'))
        