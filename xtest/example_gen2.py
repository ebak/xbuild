import json
from mockfs import MockFS
from xbuild import Task, Builder, targetUpToDate
import xbuild.fs as xfs


class EndFilter(object):

    def __init__(self, end):
        self.end = end

    def filter(self, fpath):
        return fpath.lower().endswith(self.end)


# It's an action function.
def concatAction(bldr, task):
    res = ''
    # Read and append all file dependencies.
    # Task.getFileDeps() returns all file dependencies and
    # all generated and provided files from the task dependencies.
    for src in task.getFileDeps(bldr):
        res += bldr.fs.read(src)
    # Write targets.
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0


# Action function for the generator.
def mainGeneratorAction(bldr, task):
    assert len(task.fileDeps) == 1
    cfgPath = task.fileDeps[0]
    cfgValue = int(bldr.fs.read(cfgPath).strip())
    for i in range(cfgValue):
        # generate .txt file
        fpath = 'gen/gen{}.txt'.format(i)
        bldr.fs.write(fpath, 'Generated file {}\n'.format(i * '*'), mkDirs=True)
        task.generatedFiles.append(fpath)
        # generate .json file
        fpath = 'gen/gen{}.json'.format(i)
        jsonStr = json.dumps({'list': [ 'list entry: ' + i * '*' for j in range(i)]}, indent=2)
        bldr.fs.write(fpath, jsonStr, mkDirs=True)
        task.generatedFiles.append(fpath)
    return 0    # success


# Action for the size and lines generator.
def subGeneratorAction(bldr, task, srcExt, dstExt):
    genFiles = task.getFileDeps(bldr, EndFilter(srcExt).filter)
    task.providedFiles = ['out/' + xfs.splitExt(xfs.baseName(g))[0] + dstExt for g in genFiles]
    return 0

# Action function for size and lines file building
def countAction(bldr, task, prefix, countFn):
    assert len(task.fileDeps) == 1
    src = task.fileDeps[0]
    cnt = countFn(bldr.fs.read(src))
    content = '{} {} = {}\n'.format(prefix, src, cnt)
    for trg in task.targets:
        bldr.fs.write(trg, content, mkDirs=True)
    return 0


def countTaskFactory(bldr, task, prefix, srcExt, countFn):
    tasks = []
    for trg, src in zip(task.providedFiles, task.getFileDeps(bldr, EndFilter(srcExt).filter)):
        tasks.append(
            Task(
                 targets=[trg],
                 fileDeps=[src],
                 upToDate=targetUpToDate,
                 action=(countAction, {'prefix': prefix, 'countFn': countFn})))
    return tasks


def countLines(text):
    return len(text.splitlines())


# This example runs on a virtual (mock) filesystem.
fs = MockFS()
# Creating a generator configuration file.
# Here content 2 means the number of files, the generator creates.
fs.write('cfg/cfg.txt', '2', mkDirs=True)
# Create a Builder.
bldr = Builder(fs=fs)
# Create the generator task.
bldr.addTask(
    name='generator',
    fileDeps=['cfg/cfg.txt'],
    upToDate=targetUpToDate,    # It is a common up-to-date function which is good for most purposes.
    action=mainGeneratorAction)
# Create generator for creating .size files from .txt files
bldr.addTask(
    name='sizeGenerator',
    taskDeps=['generator'],
    upToDate=targetUpToDate,
    action=(subGeneratorAction, {'srcExt': '.txt', 'dstExt': '.size'}),
    taskFactory=(countTaskFactory, {'prefix': 'size of', 'srcExt': '.txt', 'countFn': len}))
# Create generator for creating .lines files from .json files
bldr.addTask(
    name='linesGenerator',
    taskDeps=['generator'],
    upToDate=targetUpToDate,
    action=(subGeneratorAction, {'srcExt': '.json', 'dstExt': '.lines'}),
    taskFactory=(countTaskFactory, {'prefix': 'lines in', 'srcExt': '.json', 'countFn': countLines}))
# Create a task for concatenating the .size files
bldr.addTask(
    targets=['out/txtInfo.txt'],
    taskDeps=['sizeGenerator'],
    upToDate=targetUpToDate,
    action=concatAction)
# Create a task for concatenating the .lines files
bldr.addTask(
    targets=['out/jsonInfo.txt'],
    taskDeps=['linesGenerator'],
    upToDate=targetUpToDate,
    action=concatAction)
# Create a main task.
bldr.addTask(
    name='all',
    fileDeps=['out/txtInfo.txt', 'out/jsonInfo.txt'],
    upToDate=targetUpToDate)
# Build the main task.
bldr.buildOne('all')
# Print the target.
print "Content of out/txtInfo.txt:\n{}".format(fs.read('out/txtInfo.txt'))
print "Content of out/jsonInfo.txt:\n{}".format(fs.read('out/jsonInfo.txt'))
# Print the PlantUML representation of the after-build dependency graph.
print bldr.db.genPlantUML()
