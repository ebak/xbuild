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
        
    