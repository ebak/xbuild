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

import os
import re

IncludeReg = re.compile('<!--\s+include\s*:\s*(\S+)\s+-->')
IncludePythonReg = re.compile('<!--\s+includePython\s*:\s*(\S+)\s+-->')

def includeHandler(templ, reg, contentFn):
    res = templ[:]
    for m in reversed(list(reg.finditer(templ))):
        content = contentFn(m.group(1))
        res = res[:m.start(0)] + content + res[m.end(0):]
    return res

def rawContent(fpath):
    with open('intro/src/' + fpath) as f:
        return f.read()

def pythonContent(srcPath):
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
    srcPath = os.path.normpath('../' + srcPath)
    with open(srcPath) as f:
        res = highlight(f.read(), PythonLexer(), HtmlFormatter())
        # print 'res:\n' + res
        return res


def main():
    with open('intro/src/intro.templ.html') as f:
        templ = f.read()
    templ = includeHandler(templ, IncludeReg, rawContent)
    templ = includeHandler(templ, IncludePythonReg, pythonContent)
    with open('intro/intro.html', 'w') as f:
        f.write(templ)


if __name__ == '__main__':
    main()
        
    
