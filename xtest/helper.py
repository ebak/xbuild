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
            rc = bldr.buildOne(trg)
        finally:
            setOut(sys.stdout)
        output = capture.getvalue()
        lines = output.splitlines()
        for line in lines:
            print ">" + line
        return rc, output