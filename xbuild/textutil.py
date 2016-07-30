from cStringIO import StringIO
from html2text import HTML2Text


def format(text, indent=0, width=80):
    '''Text is a HTML body content.'''
    h2t = HTML2Text(bodywidth=width)
    fmt = h2t.handle('<html><body>' + text + '</body></html>')
    prf = ' ' * indent
    sout = StringIO()
    for line in fmt.splitlines():
        # line = line.strip()
        if line:
            sout.write(prf)
            sout.write(line)
            sout.write('\n')
    return sout.getvalue()


if __name__ == '__main__':
    print format((
        'This task accepts the following command line arguments:'
        '<ul>'
        '<li>embSrcs<ul><li>EmbUnit Sources to build and run. A lot lot lot lot lot lot lot bloated text comes here</li></ul></li>'
        '<li>embCfgs<p>Configuration ARXMLs to build and run.</li>'
        '</ul>'),
        indent=4, width=32) # bullshit! it doesn't work
    print
    print format((
        "<H4>Here's What's For Dinner</H4>"
        "<DL>"
        "<DT>Salad"
        "<DD>Green stuff and dressing"
        "<DT>The Meal"
        "<DD>Mystery meat and mashed yams"
        "<DT>Dessert"
        "<DD>A mint"
        "</DL>"),
        indent=4, width=76)
    pass
