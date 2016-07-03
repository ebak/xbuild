import os
import unittest
from xbuild import Builder, targetUpToDate

def concat(bldr, task, **kvArgs):
    # raise ValueError
    res = ''
    for src in task.getAllFileDeps():
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
        return '{} file: {}'.format(name, ent)

    def getCContent(self, fpath):
        return self.getContent(fpath, 'C Source', self.cEnts)
    
    def getVContent(self, fpath):
        return self.getContent(fpath, 'VHDL Source', self.vEnts)
            

def buildVhdl(bldr, task):
    obj = task.targets[0]
    src = task.getAllFileDeps()[0]
    bldr.fs.write(obj, 'VHDL Object, built from: {}\n{}'.format(src, bldr.fs.read(src)))
    return 0


def buildC(bldr, task):
    obj = task.targets[0]
    src = task.getAllFileDeps()[0]
    bldr.fs.write(obj, 'C Object, built from: {}\n{}'.format(src, bldr.fs.read(src)))
    return 0


class GenCore(object):

    def __init__(self, cfg):
        self.cfg = cfg
        self.genCFiles = None
        self.genVhdlFiles = None

    def generate(self, bldr):
        if self.genCFiles:
            return # already executed
        self.genCFiles = []
        self.genVhdlFiles = []
        cFmt = 'gen/{cfg}/src/{{name}}.c'.format(self.cfg)
        vFmt = 'gen/{cfg}/vhdl/{{name}}.vhdl'.format(self.cfg)
        for line in bldr.fs.read(self.cfg).splitlines():
            items = line.split(':')
            if len(items) >= 3:
                tp, name, prio = items[0].strip(), items[1].strip(), int(items[2].strip())
            elif len(items) >= 2:
                tp, name, prio = items[0].strip(), items[1].strip(), 0
            else:
                continue
            if tp == 'v':
                fpath = vFmt.format(name=name)
                bldr.fs.write(fpath, 'Generated VHDL file: {}'.format(name), mkDirs=True)
                self.genVhdlFiles.append(fpath)
                # add build task
                bldr.addTask(
                    prio=prio,
                    targets=['out/hw/{}.o'.format(name)],
                    fileDeps=[fpath],
                    upToDate=targetUpToDate,
                    action=buildVhdl)
            elif tp == 'c':
                fpath = cFmt.format(name=name)
                bldr.fs.write(fpath, 'Generated C file: {}'.format(name), mkDirs=True)
                self.genCFiles.append(fpath)
                # add build task
                bldr.addTask(
                    prio=prio,
                    targets=['out/sw/{}.o'.format(name)],
                    fileDeps=[fpath],
                    upToDate=targetUpToDate,
                    action=buildC)
            
            
class Generator(object):
    
    def __init__(self):
        self.cfgDict = {}

    def get(self, cfg):
        genCore = self.cfgDict.get(cfg)
        if genCore is None:
            self.cfgDict[cfg]= genCore = GenCore(cfg)
        return genCore

    def genCAction(self, bldr, task):
        cfg = task.getAllFileDeps([0])
        genCore = self.get(cfg)
        genCore.generate()
        task.providedFileDeps = genCore.genCFiles[:]
        return 0

    def genVhdlAction(self, bldr, task):
        cfg = task.getAllFileDeps([0])
        genCore = self.get(cfg)
        genCore.generate()
        task.providedFileDeps = genCore.genVhdlFiles[:]
        return 0
    
        

class Test(unittest.TestCase):

    def test0(self):

        def createBldr(fs, cont):
            bldr = Builder(workers=2, fs=fs)
            '''--- Create top level tasks ---'''
            bldr.addTask(
                name='all',
                taskDeps=['swTask', 'hwTask'])
            bldr.addTask(
                name='swTask',
                targets=[cont.libPath],
                fileDeps=cont.cOBJS,
                taskDeps=['generateCObjs'],
                upToDate=targetUpToDate,
                action=concat)
            bldr.addTask(
                prio=5,
                name='hwTask',
                targets=[cont.binPath],
                fileDeps=cont.vOBJS,
                taskDeps=['generateVhdlObjs'],
                upToDate=targetUpToDate,
                action=concat)
            '''--- Create generator tasks. ---'''
            generator = Generator()
            bldr.addTask(
                name='generateCObjs',
                fileDeps=[cont.cfgPath],
                upToDate=targetUpToDate,
                action=generator.genCAction)
            bldr.addTask(
                name='generateVhdlObjs',
                fileDeps=[cont.cfgPath],
                upToDate=targetUpToDate,
                action=generator.genVhdlAction)
            '''--- Create tasks for static C files ---'''
            for obj, src in zip(cont.cOBJS, cont.cSRCs):
                bldr.addTask(
                    targets=[obj],
                    fileDeps=[src],
                    upToDate=targetUpToDate,
                    action=buildC)
            '''--- Create tasks for static VHDL files ---'''
            for obj, src in zip(cont.vOBJS, cont.vSRCs):
                bldr.addTask(
                    targets=[obj],
                    fileDeps=[src],
                    upToDate=targetUpToDate,
                    action=buildVhdl)
            return bldr
        
        cont = ContentHelper(
            cEnts=['main', 'helper', 'mgr'],
            vEnts=['core', 'CzokCodec', 'SPI'],
            libPath='out/sw/liba.so',
            binPath='out/hw/a.bin')