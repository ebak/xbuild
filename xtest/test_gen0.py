import os
from helper import XTest
from mockfs import MockFS
from xbuild import Builder, Task, targetUpToDate, FetchDynFileDeps, StartFilter


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

A_BIN_SPI_HACK = (
    'VHDL Object, built from: vhdl/core.vhdl\n'
    'VHDL Source file: core\n'
    'VHDL Object, built from: vhdl/CzokCodec.vhdl\n'
    'VHDL Source file: CzokCodec\n'
    'VHDL Object, built from: vhdl/SPI.vhdl\n'
    'lofasz es estifeny\n'
    'VHDL Object, built from: gen/pupak/vhdl/add8_8_C.vhdl\n'
    'Generated VHDL file: add8_8_C\n'
    'VHDL Object, built from: gen/pupak/vhdl/mul16_16.vhdl\n'
    'Generated VHDL file: mul16_16\n'
    'VHDL Object, built from: gen/pupak/vhdl/CzokEngiene.vhdl\n'
    'Generated VHDL file: CzokEngiene\n')

A_BIN_SPI_HACK2 = (
    'VHDL Object, built from: vhdl/core.vhdl\n'
    'VHDL Source file: core\n'
    'VHDL Object, built from: vhdl/CzokCodec.vhdl\n'
    'VHDL Source file: CzokCodec\n'
    'VHDL Object, built from: vhdl/SPI.vhdl\n'
    'lofasz es estifeny\n'
    'VHDL Object, built from: gen/pupak/vhdl/add8_8_C.vhdl\n'
    'Generated VHDL file: add8_8_C\n'
    'VHDL Object, built from: gen/pupak/vhdl/mul16_16.vhdl\n'
    'Generated VHDL file: mul16_16\n'
    'VHDL Object, built from: gen/pupak/vhdl/ALU.vhdl\n'
    'Generated VHDL file: ALU\n')

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


def createBldr(fs):
    return Builder(fs=fs, printUpToDate=True)


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
        return bldr

    def createContent(self):
        return ContentHelper(
            cEnts=['main', 'helper', 'mgr'],
            vEnts=['core', 'CzokCodec', 'SPI'],
            libPath='out/sw/liba.so',
            binPath='out/hw/a.bin',
            cfgPath='cfg/pupak.desc',
            cfg=('c: mp3\nc: ogg\nc: avi\nc:mp4\n'
                 'v:add8_8_C\nv:mul16_16\nv: CzokEngiene: 10'))

    def test0(self):

        def createTasks(bldr, cont):
            return self.createTasks(bldr, cont)

        print '--- 1st build ---'
        cont = self.createContent()
        fs = MockFS()
        cont.create(fs)
        # print 'FS content before build:\n' + fs.show()
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            bldr.buildOne('all')
        # hwTask = bldr._getTaskByName('hwTask')
        # print 'FS content after build:\n' + fs.show()
        # print 'a.bin:\n' + fs.read('out/hw/a.bin')
        self.assertEquals(A_BIN_REF, fs.read('out/hw/a.bin'))
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        # return
        print '--- rebuild ---'
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            self.buildAndCheckOutput(
                bldr, 'all',
                mustHave=[
                    'INFO: generator is up-to-date.',
                    'INFO: out/hw/core.o is up-to-date.',
                    'INFO: out/hw/SPI.o is up-to-date.',
                    'INFO: out/hw/CzokCodec.o is up-to-date.',
                    'INFO: hwTask is up-to-date.',
                    'INFO: out/sw/main.o is up-to-date.',
                    'INFO: out/sw/helper.o is up-to-date.',
                    'INFO: out/sw/mgr.o is up-to-date.',
                    'INFO: swTask is up-to-date.',
                    'INFO: all is up-to-date.',
                    'INFO: BUILD PASSED!'],
                forbidden=[])
        self.assertEquals(A_BIN_REF, fs.read('out/hw/a.bin'))
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))

        print '--- modify static dependency ---'
        fs.write('vhdl/SPI.vhdl', 'lofasz es estifeny\n')
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            self.buildAndCheckOutput(
                bldr, 'all',
                mustHave=[
                    'INFO: generator is up-to-date.',
                    'INFO: out/hw/core.o is up-to-date.',
                    'INFO: Building out/hw/SPI.o.',
                    'INFO: out/hw/CzokCodec.o is up-to-date.',
                    'INFO: Building hwTask.',
                    'INFO: out/sw/main.o is up-to-date.',
                    'INFO: out/sw/helper.o is up-to-date.',
                    'INFO: out/sw/mgr.o is up-to-date.',
                    'INFO: swTask is up-to-date.',
                    'INFO: all is up-to-date.',
                    'INFO: BUILD PASSED!'],
                forbidden=[])
        # print fs.read('out/hw/a.bin')
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        self.assertEquals(A_BIN_SPI_HACK, fs.read('out/hw/a.bin'))

        print '--- modify config ---'
        fs.write(
            'cfg/pupak.desc',
            ('c: mp3\nc: ogg\nc: avi\nc:mp4\n'
            'v:add8_8_C\nv:mul16_16\nv: ALU: 10'))
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            self.buildAndCheckOutput(
                bldr, 'all',
                mustHave=[
                    'INFO: Building generator.',
                    'INFO: out/hw/core.o is up-to-date.',
                    'INFO: out/hw/SPI.o is up-to-date.',
                    'INFO: out/hw/CzokCodec.o is up-to-date.',
                    'INFO: Building out/hw/ALU.o.',
                    'INFO: out/hw/add8_8_C.o is up-to-date.',
                    'INFO: out/hw/mul16_16.o is up-to-date.',
                    'INFO: Building hwTask.',
                    'INFO: out/sw/main.o is up-to-date.',
                    'INFO: out/sw/helper.o is up-to-date.',
                    'INFO: out/sw/mgr.o is up-to-date.',
                    'INFO: out/sw/mp3.o is up-to-date.',
                    'INFO: out/sw/ogg.o is up-to-date.',
                    'INFO: out/sw/avi.o is up-to-date.',
                    'INFO: out/sw/mp4.o is up-to-date.',
                    'INFO: swTask is up-to-date.',
                    'INFO: all is up-to-date.',
                    'INFO: BUILD PASSED!'],
                forbidden=[])
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        self.assertEquals(A_BIN_SPI_HACK2, fs.read('out/hw/a.bin'))

        print '--- modify source of dynamic dependency ---'
        fs.write('gen/pupak/vhdl/ALU.vhdl', 'Macsonya bacsi')
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            self.buildAndCheckOutput(
                bldr, 'all',
                mustHave=[
                    'INFO: Building generator.',
                    'INFO: out/hw/core.o is up-to-date.',
                    'INFO: out/hw/SPI.o is up-to-date.',
                    'INFO: out/hw/CzokCodec.o is up-to-date.',
                    'INFO: Building out/hw/ALU.o.',
                    'INFO: out/hw/add8_8_C.o is up-to-date.',
                    'INFO: out/hw/mul16_16.o is up-to-date.',
                    'INFO: hwTask is up-to-date.',
                    'INFO: out/sw/main.o is up-to-date.',
                    'INFO: out/sw/helper.o is up-to-date.',
                    'INFO: out/sw/mgr.o is up-to-date.',
                    'INFO: out/sw/mp3.o is up-to-date.',
                    'INFO: out/sw/ogg.o is up-to-date.',
                    'INFO: out/sw/avi.o is up-to-date.',
                    'INFO: out/sw/mp4.o is up-to-date.',
                    'INFO: swTask is up-to-date.',
                    'INFO: all is up-to-date.',
                    'INFO: BUILD PASSED!'],
                forbidden=[])
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        self.assertEquals(A_BIN_SPI_HACK2, fs.read('out/hw/a.bin'))

        print '--- modify object of dynamic dependency ---'
        fs.write('out/hw/ALU.o', 'Macsonya bacsi')
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            self.buildAndCheckOutput(
                bldr, 'all',
                mustHave=[
                    'INFO: Building generator.',
                    'INFO: out/hw/core.o is up-to-date.',
                    'INFO: out/hw/SPI.o is up-to-date.',
                    'INFO: out/hw/CzokCodec.o is up-to-date.',
                    'INFO: Building out/hw/ALU.o.',
                    'INFO: out/hw/add8_8_C.o is up-to-date.',
                    'INFO: out/hw/mul16_16.o is up-to-date.',
                    'INFO: hwTask is up-to-date.',
                    'INFO: out/sw/main.o is up-to-date.',
                    'INFO: out/sw/helper.o is up-to-date.',
                    'INFO: out/sw/mgr.o is up-to-date.',
                    'INFO: out/sw/mp3.o is up-to-date.',
                    'INFO: out/sw/ogg.o is up-to-date.',
                    'INFO: out/sw/avi.o is up-to-date.',
                    'INFO: out/sw/mp4.o is up-to-date.',
                    'INFO: swTask is up-to-date.',
                    'INFO: all is up-to-date.',
                    'INFO: BUILD PASSED!'],
                forbidden=[])
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        self.assertEquals(A_BIN_SPI_HACK2, fs.read('out/hw/a.bin'))

        print '--- remove object of dynamic dependency ---'
        fs.remove('out/hw/ALU.o')
        with createBldr(fs) as bldr:
            createTasks(bldr, cont)
            print bldr.show()
            self.buildAndCheckOutput(
                bldr, 'all',
                mustHave=[
                    'INFO: generator is up-to-date.',
                    'INFO: out/hw/core.o is up-to-date.',
                    'INFO: out/hw/SPI.o is up-to-date.',
                    'INFO: out/hw/CzokCodec.o is up-to-date.',
                    'INFO: Building out/hw/ALU.o.',
                    'INFO: out/hw/add8_8_C.o is up-to-date.',
                    'INFO: out/hw/mul16_16.o is up-to-date.',
                    'INFO: hwTask is up-to-date.',
                    'INFO: out/sw/main.o is up-to-date.',
                    'INFO: out/sw/helper.o is up-to-date.',
                    'INFO: out/sw/mgr.o is up-to-date.',
                    'INFO: out/sw/mp3.o is up-to-date.',
                    'INFO: out/sw/ogg.o is up-to-date.',
                    'INFO: out/sw/avi.o is up-to-date.',
                    'INFO: out/sw/mp4.o is up-to-date.',
                    'INFO: swTask is up-to-date.',
                    'INFO: all is up-to-date.',
                    'INFO: BUILD PASSED!'],
                forbidden=[])
        self.assertEquals(LIBA_SO_REF, fs.read('out/sw/liba.so'))
        self.assertEquals(A_BIN_SPI_HACK2, fs.read('out/hw/a.bin'))

    def testTryPlantUML(self):
        print '--- try PlantUML ---'
        fs = MockFS()
        cont = self.createContent()
        cont.create(fs)
        with createBldr(fs) as bldr:
            self.createTasks(bldr, cont)
            bldr.buildOne('all')
            print bldr.db.genPlantUML()

