import os
from xbuild import Builder, Task, targetUpToDate, FetchDynFileDeps, StartFilter


def concat(bldr, task, **kwargs):
    res = ''
    for src in task.getFileDeps():
        res += bldr.fs.read(src)
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0    # SUCCESS


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


def createTasks(bldr, cont):
    '''--- Create top level tasks ---'''
    bldr.addTask(
        name='all',
        taskDeps=['swTask', 'hwTask'],
        summary='Build all')
    bldr.addTask(
        name='swTask',
        targets=[cont.libPath],
        fileDeps=cont.cOBJS,
        taskDeps=['generator'],
        dynFileDepFetcher=FetchDynFileDeps(StartFilter('out/sw/'), fetchProv=True),
        action=concat,
        summary='Build SW.')
    bldr.addTask(
        prio=5,
        name='hwTask',
        targets=[cont.binPath],
        fileDeps=cont.vOBJS,
        taskDeps=['generator'],
        dynFileDepFetcher=FetchDynFileDeps(StartFilter('out/hw/'), fetchProv=True),
        action=concat,
        summary='Build HW.')
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


cont = ContentHelper(
    cEnts=['main', 'helper', 'mgr'],
    vEnts=['core', 'CzokCodec', 'SPI'],
    libPath='out/sw/liba.so',
    binPath='out/hw/a.bin',
    cfgPath='cfg/pupak.desc',
    cfg=('c: mp3\nc: ogg\nc: avi\nc:mp4\n'
         'v:add8_8_C\nv:mul16_16\nv: CzokEngiene: 10'))

with Builder() as bldr:
    createTasks(bldr, cont)
    print bldr.listTasks()
