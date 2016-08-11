from mockfs import MockFS
from xbuild import Builder, targetUpToDate


# It's an action function.
def concat(bldr, task):

    def filterTxt(fpath):
        # Returns True when the file extension is "txt."
        return fpath.lower().endswith('.txt')

    res = ''
    # Read and append all file dependencies.
    # Task.getFileDeps() returns all matching file dependencies and
    # all matching generated and provided files from the task dependencies.
    for src in task.getFileDeps(bldr, filterTxt):
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
        bldr.fs.write(fpath, 'Generated file {}\n'.format(i), mkDirs=True)
        # Important! All the generated files have to be appended for Task.generatedFiles.
        # In real case, when the generator is an external binary, you can use
        # Task.addGeneratedFiles(fs, dpath) for scanning up the generators output directory.
        task.generatedFiles.append(fpath)
    return 0    # success


# This example runs on a virtual (mock) filesystem.
fs = MockFS()
# Let's create some static files for input.
fs.write('src/a.txt', "aFile\n", mkDirs=True)
fs.write('src/b.txt', "bFile\n", mkDirs=True)
# Creating a generator configuration file.
# Here content 3 means the number of files, the generator creates.
fs.write('cfg/cfg.txt', '3', mkDirs=True)
# Create a Builder.
bldr = Builder(fs=fs)
# Create the generator task.
bldr.addTask(
    name='generator',
    fileDeps=['cfg/cfg.txt'],
    upToDate=targetUpToDate,    # It is a common up-to-date function which is good for most purposes.
    action=generatorAction)
# Create a task for concatenating files.
bldr.addTask(
    name='all',     # It is just a short alias name for the task.
    targets=['out/concat.txt'],
    fileDeps=['src/a.txt', 'src/b.txt'],
    taskDeps=['generator'],     # Note: this task depends on the generator task too.
    upToDate=targetUpToDate,
    action=concat)
# Build the target. It is the same as bldr.buildOne('out/concat.txt')
bldr.buildOne('all')
# Print the target.
print "Content of target:\n{}".format(fs.read('out/concat.txt'))
# Print the PlantUML representation of the after-build dependency graph.
print bldr.db.genPlantUML()
