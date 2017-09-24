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


class Worker(object):

    def __init__(self, taskId, waiting):
        self.taskId, self.waiting = taskId, waiting
        self.phase = ''


class Progress(object):

    def __init__(self, numWorkers):
        self.workers = [Worker('init', True) for _ in range(numWorkers)]
        self.rc = None

    def setWorker(self, idx, taskId, waiting):
        w = self.workers[idx]
        w.taskId, w.waiting = taskId, waiting

    def set(self, done, left, total):
        self.done, self.left, self.total = done, left, total

    def finish(self, rc):
        self.rc = rc

    def setWorkerPhase(self, idx, phase):
        w = self.workers[idx]
        w.phase = phase
