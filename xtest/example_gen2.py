import json
from mockfs import MockFS
from xbuild import Task, Builder, FetchDynFileDeps, EndFilter

# It's an action function.
def concatAction(bldr, task):
    res = ''
    # Read and append all file dependencies (static + dynamic dependencies).
    for src in task.getFileDeps():
        res += bldr.fs.read(src)
    # Write targets.
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0


# Action function for the generator.
def generatorAction(bldr, task):
    assert len(task.fileDeps) == 1
    cfgPath = task.fileDeps[0]
    cfgValue = int(bldr.fs.read(cfgPath).strip())
    for i in range(cfgValue):
        # generate .txt file
        fpath = 'gen/gen{}.txt'.format(i)
        bldr.fs.write(fpath, 'Generated file {}\n'.format(i * '*'), mkDirs=True)
        task.generatedFiles.append(fpath)
        task.providedFiles.append('out/gen{}.size'.format(i))
        # generate .json file
        fpath = 'gen/gen{}.json'.format(i)
        jsonStr = json.dumps({'list': [ 'list entry: ' + i * '*' for j in range(i)]}, indent=2)
        bldr.fs.write(fpath, jsonStr, mkDirs=True)
        task.generatedFiles.append(fpath)
        task.providedFiles.append('out/gen{}.lines'.format(i))
    return 0    # success


# Action function for size and lines file building
def countAction(bldr, task, prefix, countFn):
    assert len(task.fileDeps) == 1
    src = task.fileDeps[0]
    cnt = countFn(bldr.fs.read(src))
    content = '{} {} = {}\n'.format(prefix, src, cnt)
    for trg in task.targets:
        bldr.fs.write(trg, content, mkDirs=True)
    return 0


def taskFactory(bldr, task):

    def countLines(text):
        return len(text.splitlines())

    tasks = []
    for trg, src in zip(task.providedFiles, task.generatedFiles):
        if trg.endswith('.size'):
            assert src.endswith('.txt')
            prefix, countFn = 'size of', len
        elif trg.endswith('.lines'):
            assert src.endswith('.json')
            prefix, countFn = 'number of lines in', countLines
        tasks.append(
            Task(
                 targets=[trg],
                 fileDeps=[src],
                 action=(countAction, {'prefix': prefix, 'countFn': countFn})))
    return tasks


# This example runs on a virtual (mock) filesystem.
fs = MockFS()
# Creating a generator configuration file.
# Here content 2 means the number of files, the generator creates.
fs.write('cfg/cfg.txt', '2', mkDirs=True)
# Create a Builder.
with Builder(fs=fs) as bldr:
    # Create the generator task.
    bldr.addTask(
        name='generator',
        fileDeps=['cfg/cfg.txt'],
        action=generatorAction,
        taskFactory=taskFactory)
    # Create a task for concatenating the .size files
    bldr.addTask(
        name='concatSizeFiles',
        targets=['out/txtInfo.txt'],
        taskDeps=['generator'],
        dynFileDepFetcher=FetchDynFileDeps(EndFilter('.size'), fetchProv=True),
        action=concatAction)
    # Create a task for concatenating the .lines files
    bldr.addTask(
        name='concatLinesFiles',
        targets=['out/jsonInfo.txt'],
        taskDeps=['generator'],
        dynFileDepFetcher=FetchDynFileDeps(EndFilter('.lines'), fetchProv=True),
        action=concatAction)
    # Create a main task.
    bldr.addTask(
        name='all',
        fileDeps=['out/txtInfo.txt', 'out/jsonInfo.txt'])
    # Print the PlantUML representation of the before-build dependency graph.
    print 'Before-build PlantUML:\n' + bldr.genPlantUML()
    # Build the main task.
    bldr.buildOne('all')
    # Print the target.
    print "Content of out/txtInfo.txt:\n{}".format(fs.read('out/txtInfo.txt'))
    print "Content of out/jsonInfo.txt:\n{}".format(fs.read('out/jsonInfo.txt'))
    # Print the PlantUML representation of the after-build dependency graph.
    print 'After-build PlantUML:\n' + bldr.db.genPlantUML()
