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


import sys
import unittest
from StringIO import StringIO
from xbuild.console import setOut

class XTest(unittest.TestCase):

    def buildAndCheckOutput(self, bldr, trg, mustHave=[], forbidden=[]):
        mustHave = {line: [] for line in mustHave}
        forbidden = {line: [] for line in forbidden}
        capture = StringIO()
        setOut(capture)
        try:
            rc = bldr.buildOne(trg)
        finally:
            setOut(sys.stdout)
        lines = capture.getvalue().splitlines()
        for i, line in enumerate(lines):
            print ">" + line
            if line in mustHave:
                mustHave[line].append(i)
            if line in forbidden:
                forbidden[line].append(i)
        for line, idxs in mustHave.items():
            cnt = len(idxs)
            self.assertEquals(1, cnt, "Occurrence of '{}' = {}, expected 1".format(line, cnt))
        for line, idxs in forbidden.items():
            cnt = len(idxs)
            self.assertEquals(0, cnt, "Occurrence of '{}' = {}, expected 0".format(line, cnt))
        return rc

    def buildAndFetchOutput(self, bldr, trg):
        capture = StringIO()
        setOut(capture)
        try:
            rc = bldr.build(trg) if isinstance(trg, list) else bldr.buildOne(trg)
        finally:
            setOut(sys.stdout)
        output = capture.getvalue()
        lines = output.splitlines()
        for line in lines:
            print ">" + line
        return rc, output

    def buildAndMatchOutput(self, bldr, trgs, refOutput):
        rc, output = self.buildAndFetchOutput(bldr, trgs)
        matched = 0
        lines = output.splitlines()
        for line in lines:
            if line in refOutput:
                matched += 1
        self.assertTrue(len(refOutput) == matched, 'refOutput:{}\n != output:{}'.format(refOutput, lines))
        return rc

    def cleanAndFetchOutput(self, bldr, trgs):
        capture = StringIO()
        setOut(capture)
        try:
            rc = bldr.clean(targetOrNameList=trgs) if isinstance(trgs, list) else bldr.cleanOne(trgs)
        finally:
            setOut(sys.stdout)
        output = capture.getvalue()
        lines = output.splitlines()
        for line in lines:
            print ">" + line
        return rc, output

    def cleanAndMatchOutput(self, bldr, trgs, refOutput):
        rc, output = self.cleanAndFetchOutput(bldr, trgs)
        matched = 0
        lines = output.splitlines()
        for line in lines:
            if line in refOutput:
                matched += 1
        self.assertTrue(len(lines) == len(refOutput) == matched, 'refOutput:{}\n != output:{}'.format(refOutput, lines))
        return rc
