# Copyright (c) 2016 Endre Bak
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


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
