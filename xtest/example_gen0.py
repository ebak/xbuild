from mockfs import MockFS
from xbuild import Builder, fetchAllDynFileDeps


# It's an action function.
def concat(bldr, task):
    res = ''
    # Read and append all file dependencies.
    # getFileDeps() returns the static and the dynamic file dependencies.
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
    action=generatorAction)
# Create a task for concatenating files.
bldr.addTask(
    name='all',     # It is just a short alias name for the task.
    targets=['out/concat.txt'],
    fileDeps=['src/a.txt', 'src/b.txt'],
    taskDeps=['generator'],     # Note: this task depends on the generator task too.
    dynFileDepFetcher=fetchAllDynFileDeps,  # It is the default, you can skip it.
    action=concat)
# Print the PlantUML representation of the before-build dependency graph.
print "Before-build PlantUML:\n" + bldr.genPlantUML()
# Build the target. It is the same as bldr.buildOne('out/concat.txt')
bldr.buildOne('all')
# Print the target.
print "Content of target:\n{}".format(fs.read('out/concat.txt'))
# Print the PlantUML representation of the after-build dependency graph.
print "After-build PlantUML:\n" + bldr.db.genPlantUML()
