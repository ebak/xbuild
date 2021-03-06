from mockfs import MockFS
from xbuild import Builder, targetUpToDate


# It's an action function.
def concat(bldr, task):
    res = ''
    # Read and append all file dependencies.
    for src in task.getFileDeps():
        res += bldr.fs.read(src)
    # Write targets.
    for trg in task.targets:
        bldr.fs.write(trg, res, mkDirs=True)
    return 0


# This example runs on a virtual (mock) filesystem.
fs = MockFS()
# Let's create some files for input.
fs.write('src/a.txt', "aFile\n", mkDirs=True)
fs.write('src/b.txt', "bFile\n", mkDirs=True)
# Create a Builder.
with Builder(fs=fs) as bldr:
    # Create a task for concatenating the two files.
    bldr.addTask(
        targets=['out/concat.txt'],
        fileDeps=['src/a.txt', 'src/b.txt'],
        upToDate=targetUpToDate,    # It is the default up-to-date function, can be skipped.
        action=concat)
    # Build the target.
    bldr.buildOne('out/concat.txt')
    # Print the target.
    print "Content of target:\n{}".format(fs.read('out/concat.txt'))
    
    print "After-build PlantUML:\n" + bldr.db.genPlantUML()
