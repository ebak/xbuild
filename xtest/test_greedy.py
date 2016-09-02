from time import sleep
from mockfs import MockFS
from helper import XTest
from xbuild import Builder
from threading import Lock

class ThreadCnt(object):

    def __init__(self):
        self.cnt = 0
        self.lock = Lock()
        self.parents = set()

    def reset(self):
        self.cnt = 0

    def reg(self, parent):
        with self.lock:
            self.cnt += 1
            parent.threadCnt = self.cnt
            for p in self.parents:
                if self.cnt > p.threadCnt:
                    p.threadCnt = self.cnt
            self.parents.add(parent)
            return self

    def unreg(self, parent):
        with self.lock:
            self.cnt -= 1
            self.parents.remove(parent)
            

gThreadCnt = ThreadCnt()


class Action(object):

    def __init__(self):
        self.threadCnt = 0

    def concat(self, bldr, task):
        gThreadCnt.reg(self)
        res = ''
        for src in task.getFileDeps():
            res += bldr.fs.read(src)
        for trg in task.targets:
            bldr.fs.write(trg, res, mkDirs=True)
        sleep(0.05)
        gThreadCnt.unreg(self)
        return 0    # SUCCESS


class Test(XTest):

    def createFS(self):
        fs = MockFS()
        for n in ('a', 'b', 'c', 'd'):
            fs.write('src/{}.txt'.format(n), '{}File'.format(n), mkDirs=True)
        return fs

    def testOneGreedy(self):
        '''Test one greedy task.'''
        print '''--- Test one greedy task.'''
        fs = self.createFS()
        with Builder(fs=fs, workers=2) as bldr:
            bldr.addTask(
                name='Concat0',
                targets=['out/ab.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                action=Action().concat,
                greedy=True)
            rc = bldr.buildOne('Concat0')
        self.assertEquals(0, rc)
        self.assertEquals('aFilebFile', fs.read('out/ab.txt'))

    def testFirstGreedy(self):
        '''Test when 1st task is greedy.'''
        print '''--- Test when 1st task is greedy.'''
        fs = self.createFS()
        greedyAction, aAction, bAction = Action(), Action(), Action()
        with Builder(fs=fs, workers=2) as bldr:
            bldr.addTask(
                name='Concat0',
                targets=['out/ab.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                action=greedyAction.concat,
                greedy=True,
                prio=1)
            bldr.addTask(
                name='ConcatA',
                targets=['out/cd.txt'],
                fileDeps=['src/c.txt', 'src/d.txt'],
                action=aAction.concat)
            bldr.addTask(
                name='ConcatB',
                targets=['out/ad.txt'],
                fileDeps=['src/a.txt', 'src/d.txt'],
                action=bAction.concat)
            bldr.addTask(
                name='All',
                taskDeps=['Concat0', 'ConcatA', 'ConcatB'])
            rc = bldr.buildOne('All')
            workers = bldr.workers
        self.assertEquals(0, rc)
        self.assertEquals('aFilebFile', fs.read('out/ab.txt'))
        self.assertEquals('cFiledFile', fs.read('out/cd.txt'))
        self.assertEquals('aFiledFile', fs.read('out/ad.txt'))
        self.assertEquals(1, greedyAction.threadCnt)
        if workers > 1:
            self.assertTrue(1 < aAction.threadCnt)
            self.assertTrue(1 < bAction.threadCnt)

    def testLastGreedy(self):
        '''Test when the last task is greedy.'''
        print '''--- Test when the last task is greedy.'''
        fs = self.createFS()
        greedyAction, aAction, bAction = Action(), Action(), Action()
        with Builder(fs=fs, workers=2) as bldr:
            bldr.addTask(
                name='Concat0',
                targets=['out/ab.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                action=greedyAction.concat,
                greedy=True,
                prio=0)
            bldr.addTask(
                name='ConcatA',
                targets=['out/cd.txt'],
                fileDeps=['src/c.txt', 'src/d.txt'],
                action=aAction.concat,
                prio=1)
            bldr.addTask(
                name='ConcatB',
                targets=['out/ad.txt'],
                fileDeps=['src/a.txt', 'src/d.txt'],
                action=bAction.concat,
                prio=1)
            bldr.addTask(
                name='All',
                taskDeps=['Concat0', 'ConcatA', 'ConcatB'])
            rc = bldr.buildOne('All')
            workers = bldr.workers
        self.assertEquals(0, rc)
        self.assertEquals('aFilebFile', fs.read('out/ab.txt'))
        self.assertEquals('cFiledFile', fs.read('out/cd.txt'))
        self.assertEquals('aFiledFile', fs.read('out/ad.txt'))
        self.assertEquals(1, greedyAction.threadCnt)
        if workers > 1:
            self.assertTrue(1 < aAction.threadCnt)
            self.assertTrue(1 < bAction.threadCnt)

    def testMiddleGreedy(self):
        '''Test when the middle task is greedy.'''
        print '''--- Test when the middle task is greedy.'''
        fs = self.createFS()
        cAction, dAction, greedyAction, aAction, bAction = [Action() for _ in range(5)]
        with Builder(fs=fs, workers=4) as bldr:
            bldr.addTask(
                name='ConcatA',
                targets=['out/cd.txt'],
                fileDeps=['src/c.txt', 'src/d.txt'],
                action=aAction.concat,
                prio=2)
            bldr.addTask(
                name='ConcatB',
                targets=['out/ad.txt'],
                fileDeps=['src/a.txt', 'src/d.txt'],
                action=bAction.concat,
                prio=2)
            bldr.addTask(
                name='Concat0',
                targets=['out/ab.txt'],
                fileDeps=['src/a.txt', 'src/b.txt'],
                action=greedyAction.concat,
                greedy=True,
                prio=1)
            bldr.addTask(
                name='ConcatC',
                targets=['out/bc.txt'],
                fileDeps=['src/b.txt', 'src/c.txt'],
                action=cAction.concat)
            bldr.addTask(
                name='ConcatD',
                targets=['out/cb.txt'],
                fileDeps=['src/c.txt', 'src/b.txt'],
                action=dAction.concat)
            bldr.addTask(
                name='All',
                taskDeps=['Concat0', 'ConcatA', 'ConcatB', 'ConcatC', 'ConcatD'])
            rc = bldr.buildOne('All')
            workers = bldr.workers
        self.assertEquals(0, rc)
        self.assertEquals('aFilebFile', fs.read('out/ab.txt'))
        self.assertEquals('cFiledFile', fs.read('out/cd.txt'))
        self.assertEquals('aFiledFile', fs.read('out/ad.txt'))
        self.assertEquals('bFilecFile', fs.read('out/bc.txt'))
        self.assertEquals('cFilebFile', fs.read('out/cb.txt'))
        self.assertEquals(1, greedyAction.threadCnt)
        if workers > 1:
            self.assertTrue(1 < aAction.threadCnt)
            self.assertTrue(1 < bAction.threadCnt)
            self.assertTrue(1 < cAction.threadCnt)
            self.assertTrue(1 < dAction.threadCnt)
