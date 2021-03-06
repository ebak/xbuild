from mockfs import MockFS
from xbuild import Task, Builder, FetchDynFileDeps, fs as fs


# It's an action function.
def concat(bldr, task):
    res = ''
    # Read and append all file dependencies.
    # Task.getFileDeps() returns all file dependencies.
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
        fpath = 'gen/gen{}.txt'.format(i)
        bldr.fs.write(fpath, 'Generated file {}\n'.format(i * '*'), mkDirs=True)
        # Important! All the generated files have to be appended for Task.generatedFiles.
        # In real case, when the generator is an external binary, you can use
        # Task.addGeneratedFiles(fs, dpath) for scanning up the generators output directory.
        task.generatedFiles.append(fpath)
        ppath = 'out/gen{}.size'.format(i)
        # This task will provide .size files. These files need additional build steps, the
        # taskFactory function is responsible for creating tasks to build the providedFiles
        # (the .size files in this case).
        task.providedFiles.append(ppath)
    return 0    # success


# Action function for size file building
def sizeAction(bldr, task, prefix):
    assert len(task.fileDeps) == 1
    src = task.fileDeps[0]
    size = len(bldr.fs.read(src))
    content = '{} {} = {}\n'.format(prefix, src, size)
    for trg in task.targets:
        bldr.fs.write(trg, content, mkDirs=True)
    return 0


def sizeTaskFactory(bldr, task, prefix):
    tasks = []
    for trg, src in zip(task.providedFiles, task.generatedFiles):
        tasks.append(
            Task(
                 targets=[trg],
                 fileDeps=[src],
                 action=(sizeAction, {'prefix': prefix})))  # Note: this way you can pass kwargs to callbacks
    return tasks


# This example runs on a virtual (mock) filesystem.
fs = MockFS()
# Creating a generator configuration file.
# Here content 3 means the number of files, the generator creates.
fs.write('cfg/cfg.txt', '3', mkDirs=True)
# Create a Builder.
with Builder(fs=fs) as bldr:
    # Create the generator task.
    bldr.addTask(
        name='generator',
        fileDeps=['cfg/cfg.txt'],
        action=generatorAction,
        taskFactory=(sizeTaskFactory, {'prefix': 'size of'}))    # Note how to pass kwargs.
    # Create a task for concatenating files.
    bldr.addTask(
        name='all',     # It is just a short alias name for the task.
        targets=['out/concat.txt'],
        taskDeps=['generator'],
        dynFileDepFetcher=FetchDynFileDeps(fetchProv=True),    # Fetches all provided files.
        action=concat)
    # Print the PlantUML representation of the before-build dependency graph.
    print 'Before-build PlantUML:\n' + bldr.genPlantUML()
    # Build the target. It is the same as bldr.buildOne('out/concat.txt')
    bldr.buildOne('all')
    # Print the target.
    print "Content of target:\n{}".format(fs.read('out/concat.txt'))
    # Print the PlantUML representation of the after-build dependency graph.
    print 'After-build PlantUML:\n' + bldr.db.genPlantUML()
