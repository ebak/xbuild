import os
import sys
import logging
from threading import RLock

# next bit filched from 1.5.2's inspect.py
def currentframe():
    """Return the frame object for the caller's stack frame."""
    try:
        raise Exception
    except:
        return sys.exc_info()[2].tb_frame.f_back

if hasattr(sys, '_getframe'): currentframe = lambda: sys._getframe(0)
# done filching

#
# _srcfile is used when walking the stack to check when we've got the first
# caller stack frame.
#
_srcfile = os.path.normcase(currentframe.__code__.co_filename)


class StyleAdapter(logging.LoggerAdapter):

    def __init__(self, logger, extra=None):
        super(StyleAdapter, self).__init__(logger, extra)
        
    def findCaller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = currentframe()
        #On some versions of IronPython, currentframe() returns None if
        #IronPython isn't run with -X:Frames.
        if False and f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while f and hasattr(f, "f_code"):
            co = f.f_code
            zelf = f.f_locals.get("self")
            the_class = zelf.__module__ + '.' + zelf.__class__.__name__ if zelf else 'noClass'
            print "name={}\nclass={}".format(co.co_name, the_class)
            filename = os.path.normcase(co.co_filename)
            if True or filename == _srcfile:
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, co.co_name)
            # break
        return rv

    def debugf(self, msg, *args, **kwargs):
        print 'kwargs={}'.format(kwargs)
        self._logit(logging.DEBUG, msg, args, kwargs)

    def _logit(self, level, msg, args, kwargs):
        if self.isEnabledFor(level):
            print 'currentFrame:{}'.format(currentframe())
            self.findCaller()
            print 'kwargs={}'.format(kwargs)
            msg = msg.format(*args, **kwargs)
            # TODO
            kwargs = {n: v for n, v in kwargs.items() if n in ('exc_info', 'extra')}
            self.log(level, msg, **kwargs)


_logger = logging.getLogger('xbuild')
logger = StyleAdapter(_logger)
# fmt = logging.Formatter('[%(levelname) thr:%(threadName) %(funcName)] %(message)')
fmt = logging.Formatter('[%(levelname)s thr:%(threadName)s %(funcName)s] %(message)s')
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(fmt)
_logger.addHandler(consoleHandler)
_logger.setLevel(logging.DEBUG)

logger.debugf('hello {arg0} {arg1}', arg0=1, arg1=2)

consoleLock = RLock()

outStream = sys.stdout
errStream = sys.stderr
xDebugEnabled = False

def setOut(stream):
    global outStream
    outStream = stream

def setErr(stream):
    global errStream
    errStream = stream

def write(msg, out=None):
    global outStream
    out = out if out else outStream
    with consoleLock:
        out.write(msg)
        out.flush()

def error(msg):
    global errStream
    write('ERROR: ' + msg + '\n', out=errStream)

def errorf(msg, *args, **kvargs):
    error(msg.format(*args, **kvargs))

def info(msg):
    write('INFO: ' + msg + '\n')

def infof(msg, *args, **kvargs):
    info(msg.format(*args, **kvargs))
    
def warn(msg):
    write('WARNING: ' + msg + '\n')

def warnf(msg, *args, **kvargs):
    warn(msg.format(*args, **kvargs))

