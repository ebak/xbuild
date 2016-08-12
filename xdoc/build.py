import re

TMPLREG = re.compile('<!--\s+include\s*:\s*(.+)\s+-->')

def main():
    with open('intro/src/intro.templ.html') as f:
        templ = f.read()
    res = templ[:]
    for m in reversed(list(TMPLREG.finditer(templ))):
        with open('intro/src/' + m.group(1)) as f:
            content = f.read()
        res = res[:m.start(0)] + content + res[m.end(0):]
    with open('intro/intro.html', 'w') as f:
        f.write(res)


if __name__ == '__main__':
    main()
        
    