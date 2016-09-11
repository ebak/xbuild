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
            rc = bldr.clean(trgs) if isinstance(trgs, list) else bldr.cleanOne(trgs)
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
