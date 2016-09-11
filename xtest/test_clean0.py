import os
import logging
import unittest
from helper import XTest
from mockfs import MockFS
from xbuild.console import logger
from xbuild import Builder, Task, targetUpToDate, FetchDynFileDeps, StartFilter


# TODO: common code with test_gen0
def concat(bldr, task, **kwargs):
    # raise ValueError
    # print '--->>> concat: {} <<<---'.format(task.getFileDeps())
    res = ''
    for src in task.getFileDeps():
        res += bldr.fs.read(src)
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0    # SUCCESS


class ContentHelper(object):

    def __init__(self, cEnts, vEnts, libPath, binPath, cfgPath, cfg):
        self.cEnts = cEnts
        self.vEnts = vEnts
        self.libPath = libPath
        self.binPath = binPath
        self.cfgPath = cfgPath
        self.cfg = cfg
        self.cSRCS = ['src/{}.c'.format(c) for c in cEnts]
        self.cOBJS = ['out/sw/{}.o'.format(c) for c in cEnts]
        self.vSRCS = ['vhdl/{}.vhdl'.format(v) for v in vEnts]
        self.vOBJS = ['out/hw/{}.o'.format(v) for v in vEnts]

    def create(self, fs):
        '''Creates the pre-build filesystem entities.'''
        for cpath in self.cSRCS:
            fs.write(cpath, self.getCContent(cpath), mkDirs=True)
        for vpath in self.vSRCS:
            fs.write(vpath, self.getVContent(vpath), mkDirs=True)
        fs.write(self.cfgPath, self.cfg, mkDirs=True)

    def getEnt(self, fpath):
        return os.path.splitext(os.path.basename(fpath))[0]
    
    def getContent(self, fpath, name, lst):
        ent = self.getEnt(fpath)
        assert ent in lst
        return '{} file: {}\n'.format(name, ent)

    def getCContent(self, fpath):
        return self.getContent(fpath, 'C Source', self.cEnts)
    
    def getVContent(self, fpath):
        return self.getContent(fpath, 'VHDL Source', self.vEnts)
            

def buildVhdl(bldr, task):
    obj = next(iter(task.targets))
    src = task.getFileDeps()[0]
    bldr.fs.write(obj, 'VHDL Object, built from: {}\n{}'.format(src, bldr.fs.read(src)), mkDirs=True)
    return 0


def buildC(bldr, task):
    obj = next(iter(task.targets))
    src = task.getFileDeps()[0]
    bldr.fs.write(obj, 'C Object, built from: {}\n{}'.format(src, bldr.fs.read(src)), mkDirs=True)
    return 0


def generatorAction(bldr, task):
    cfg = task.fileDeps[0]
    cfgName = os.path.splitext(os.path.basename(cfg))[0]
    cFmt = 'gen/{cfg}/src/{{name}}.c'.format(cfg=cfgName)
    vFmt = 'gen/{cfg}/vhdl/{{name}}.vhdl'.format(cfg=cfgName)
    for line in bldr.fs.read(cfg).splitlines():
        items = line.split(':')
        if len(items) >= 3:
            tp, name, prio = items[0].strip(), items[1].strip(), int(items[2].strip())
        elif len(items) >= 2:
            tp, name, prio = items[0].strip(), items[1].strip(), 0
        else:
            continue
        if tp == 'v':
            fpath = vFmt.format(name=name)
            bldr.fs.write(fpath, 'Generated VHDL file: {}\n'.format(name), mkDirs=True)
            task.generatedFiles.append(fpath)
            trg = 'out/hw/{}.o'.format(name)
            task.providedFiles.append(trg)
        elif tp == 'c':
            fpath = cFmt.format(name=name)
            bldr.fs.write(fpath, 'Generated C file: {}\n'.format(name), mkDirs=True)
            task.generatedFiles.append(fpath)
            trg = 'out/sw/{}.o'.format(name)
            task.providedFiles.append(trg)
        

def genTaskFactory(bldr, task):
    res = []
    for srcPath in task.generatedFiles:
        name, ext = os.path.splitext(os.path.basename(srcPath))
        if ext == '.c':
            trg = 'out/sw/{}.o'.format(name)
            res.append(Task(
                prio=0,
                targets=[trg],
                fileDeps=[srcPath],
                action=buildC))
        elif ext == '.vhdl':
            trg = 'out/hw/{}.o'.format(name)
            res.append(Task(
                prio=0,
                targets=[trg],
                fileDeps=[srcPath],
                action=buildVhdl))
    return res
    

A_BIN_REF = (
    'VHDL Object, built from: vhdl/core.vhdl\n'
    'VHDL Source file: core\n'
    'VHDL Object, built from: vhdl/CzokCodec.vhdl\n'
    'VHDL Source file: CzokCodec\n'
    'VHDL Object, built from: vhdl/SPI.vhdl\n'
    'VHDL Source file: SPI\n'
    'VHDL Object, built from: gen/pupak/vhdl/add8_8_C.vhdl\n'
    'Generated VHDL file: add8_8_C\n'
    'VHDL Object, built from: gen/pupak/vhdl/mul16_16.vhdl\n'
    'Generated VHDL file: mul16_16\n'
    'VHDL Object, built from: gen/pupak/vhdl/CzokEngiene.vhdl\n'
    'Generated VHDL file: CzokEngiene\n')

LIBA_SO_REF = (
    'C Object, built from: src/main.c\n'
    'C Source file: main\n'
    'C Object, built from: src/helper.c\n'
    'C Source file: helper\n'
    'C Object, built from: src/mgr.c\n'
    'C Source file: mgr\n'
    'C Object, built from: gen/pupak/src/mp3.c\n'
    'Generated C file: mp3\n'
    'C Object, built from: gen/pupak/src/ogg.c\n'
    'Generated C file: ogg\n'
    'C Object, built from: gen/pupak/src/avi.c\n'
    'Generated C file: avi\n'
    'C Object, built from: gen/pupak/src/mp4.c\n'
    'Generated C file: mp4\n')

class Test(XTest):


    def createTasks(self, bldr, cont):
        '''--- Create top level tasks ---'''
        bldr.addTask(
            name='all',
            taskDeps=['swTask', 'hwTask'])
        bldr.addTask(
            name='swTask',
            targets=[cont.libPath],
            fileDeps=cont.cOBJS,
            taskDeps=['generator'],
            dynFileDepFetcher=FetchDynFileDeps(StartFilter('out/sw/'), fetchProv=True),
            action=concat)
        bldr.addTask(
            prio=5,
            name='hwTask',
            targets=[cont.binPath],
            fileDeps=cont.vOBJS,
            taskDeps=['generator'],
            dynFileDepFetcher=FetchDynFileDeps(StartFilter('out/hw/'), fetchProv=True),
            action=concat)
        '''--- Create generator tasks. ---'''
        bldr.addTask(
            name='generator',
            fileDeps=[cont.cfgPath],
            upToDate=targetUpToDate,
            action=generatorAction,
            taskFactory=genTaskFactory)
        '''--- Create tasks for static C files ---'''
        for obj, src in zip(cont.cOBJS, cont.cSRCS):
            bldr.addTask(
                targets=[obj],
                fileDeps=[src],
                upToDate=targetUpToDate,
                action=buildC)
        '''--- Create tasks for static VHDL files ---'''
        for obj, src in zip(cont.vOBJS, cont.vSRCS):
            bldr.addTask(
                targets=[obj],
                fileDeps=[src],
                upToDate=targetUpToDate,
                action=buildVhdl)
        
    def test0(self):

        def createTasks(bldr, cont):
            return self.createTasks(bldr, cont)

        cont = ContentHelper(
            cEnts=['main', 'helper', 'mgr'],
            vEnts=['core', 'CzokCodec', 'SPI'],
            libPath='out/sw/liba.so',
            binPath='out/hw/a.bin',
            cfgPath='cfg/pupak.desc',
            cfg=('c: mp3\nc: ogg\nc: avi\nc:mp4\n'
                 'v:add8_8_C\nv:mul16_16\nv: CzokEngiene: 10'))
        print '--- clean all ---'
        fs = MockFS()
        cont.create(fs)
        # print 'FS content before build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            self.assertEquals(0, bldr.buildOne('all'))
        self.assertEquals(A_BIN_REF, fs.read('out/hw/a.bin'))
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        # print 'FS content after build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            # logger.setLevel(logging.DEBUG)
            self.cleanAndMatchOutput(bldr, 'all', ['INFO: Removed folder: gen', 'INFO: Removed folder: out'])
        print 'FS content after clean All:\n' + fs.show()
        # print str(fs.getFileList())
        for d in ('gen', 'out'):
            self.assertFalse(fs.isdir(d))
        files = ['cfg/pupak.desc', 'src/helper.c', 'src/main.c', 'src/mgr.c', 'vhdl/CzokCodec.vhdl', 'vhdl/SPI.vhdl', 'vhdl/core.vhdl', 'default.xbuild']
        for f in files:
            self.assertTrue(fs.isfile(f), '{} does not exist'.format(f))
        # TODO: check DB
        return
        # TODO: enable tests
        print '--- clean hwTask ---'
        fs = MockFS()
        cont.create(fs)
        # print 'FS content before build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            bldr.buildOne('all')
        # print 'FS content after build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            # logger.setLevel(logging.DEBUG)
            bldr.cleanOne('hwTask')
        # TODO: asserts
        print 'FS content after clean All:\n' + fs.show()
        print '--- clean out/hw/CzokEngiene.o ---'
        fs = MockFS()
        cont.create(fs)
        # print 'FS content before build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            bldr.buildOne('all')
        # print 'FS content after build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            # logger.setLevel(logging.DEBUG)
            bldr.cleanOne('out/hw/CzokEngiene.o')
        # TODO: asserts
        print 'FS content after clean out/hw/CzokEngiene.o:\n' + fs.show()
        print '--- cleanAll() ---'
        fs = MockFS()
        cont.create(fs)
        # print 'FS content before build:\n' + fs.show()
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            bldr.buildOne('all')
            print 'topLevelTasks: {}'.format(bldr.db.getTopLevelTaskIds())
        with Builder(fs=fs) as bldr:
            createTasks(bldr, cont)
            # logger.setLevel(logging.DEBUG)
            bldr.db.cleanAll()
        # TODO: asserts
        print 'FS content after cleanAll():\n' + fs.show()
