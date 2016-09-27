from helper import XTest
from xbuild.fs import FS
from xbuild.db import DB
from xbuild.depgraph import DepGraph


def createGraph():
    graph = DepGraph()
    graph.addTask(
        name='VSC.gen',
        fileDeps=['cfg0'],
        generatedFiles=['vsc0.h', 'vsc1.h', 'vsc0.c', 'vsc1.c', 'dyn.arxml'])
    graph.addTask(
        name='RTE.gen',
        fileDeps=['cfg0', 'cfg1'],
        taskDeps=['VSC.gen'],
        dynFileDeps=['dyn.arxml'],
        generatedFiles=['rte0.h', 'rte1.h'])
    graph.addTask(
        name='VSC.obj',
        taskDeps=['VSC.gen'],
        dynFileDeps=['vsc0.c', 'vsc1.c'],
        providedFiles=['vsc0.o', 'vsc1.o'])
    graph.addTask(
        targets=['vsc0.o'],
        fileDeps=['vsc0.c'])
    graph.addTask(
        targets=['vsc1.o'],
        fileDeps=['vsc1.c'])
    graph.addTask(
        targets=['src0.o'],
        fileDeps=['src0.c'],
        taskDeps=['VSC.gen', 'RTE.gen'])
    graph.addTask(
        targets=['src1.o'],
        fileDeps=['src1.c'],
        taskDeps=['VSC.gen', 'RTE.gen'])
    graph.addTask(
        name='linker',
        targets=['test.bin'],
        fileDeps=['src0.o', 'src1.o'],
        taskDeps=['VSC.obj'],
        dynFileDeps=['vsc0.o', 'vsc1.o'])
    graph.addTask(
        name='runner',
        taskDeps=['linker'])
    return graph


def printUML(graph, filesToHighLight=set(), tasksToHighLight=set(), fileNotes={}, taskNotes={}):
    db = DB.create('temp', fs=FS())
    db.loadGraph(graph)
    print db.genPlantUML(
        filesToHighLight=filesToHighLight, tasksToHighLight=tasksToHighLight, fileNotes=fileNotes, taskNotes=taskNotes)
    db.forget()


class Test(XTest):
    
    pass


if __name__ == '__main__':
    graph = createGraph()
    graph.calcDepths()
    import xvis.vis as vis
    vis.show(graph)
    if False:

        def getNotes(nodeDict):
            return {name: '{}, {}'.format(n.depth.lower, n.depth.higher) for name, n in nodeDict.items()}
    
        fileNotes, taskNotes = getNotes(graph.fileDict), getNotes(graph.taskDict)
        selectedFiles, selectedTasks = graph.selectRight(['RTE.gen'], exclusiveChilds=True, selectTopOutputs=True, leaveLeaves=True)
        # print 'selectedFiles: {}\nselectedTasks: {}'.format(selectedFiles.keys(), selectedTasks.keys())
        printUML(
            graph, filesToHighLight=set(selectedFiles.keys()), tasksToHighLight=set(selectedTasks.keys()),
            fileNotes=fileNotes, taskNotes=taskNotes)
