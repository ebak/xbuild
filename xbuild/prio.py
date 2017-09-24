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

class Prio(object):

    def __init__(self, prioList=None, phase=None):
        self.prioList = prioList if prioList else []
        self.phase = phase

    def copyPrioSettings(self, other):
        assert isinstance(other, Prio)
        self.prioList = other.prioList[:]
        self.phase = other.phase

    def isRequested(self):
        if self.prioList:
            return True
        return False


def prioCmp(a, b):
    assert isinstance(a, Prio)
    assert isinstance(b, Prio)
    a = a.prioList
    b = b.prioList
    chkLen = min(len(a), len(b))
    for i in range(chkLen):
        diff = b[i] - a[i]  # reverse compare to achieve high on top in SortedList
        if diff:
            return diff
    return 0
