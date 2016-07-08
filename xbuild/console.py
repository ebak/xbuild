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

if hasattr(sys, '_getframe'): currentframe = lambda: sys._getframe(3)
# done filching

#
# _srcfile is used when walking the stack to check when we've got the first
# caller stack frame.
#
_srcfile = os.path.normcase(currentframe.__code__.co_filename)

class StyleAdapter(logging.LoggerAdapter):

    def __init__(self, logger, extra=None):
        super(StyleAdapter, self).__init__(logger, extra)
        logger.findCaller = self.findCaller
        
    def findCaller(self):
        def getName(co):
            zelf = f.f_locals.get("self")
            mod = os.path.splitext(os.path.basename(co.co_filename))[0]
            if zelf:
                return mod + '.' + zelf.__class__.__name__ + '.' + co.co_name
            else:
                return mod + '.' + co.co_name
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = currentframe()
        #On some versions of IronPython, currentframe() returns None if
        #IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        loggingModule = os.path.sep + 'logging'
        while f and hasattr(f, "f_code"):
            co = f.f_code
            # print 'getName(): {}'.format(getName(co))
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile or os.path.dirname(filename).endswith(loggingModule):
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, getName(co) + "()")
            break
        return rv

    def debugf(self, msg, *args, **kwargs):
        self._logit(logging.DEBUG, msg, args, kwargs)

    def _logit(self, level, msg, args, kwargs):
        if self.isEnabledFor(level):
            # self.findCaller()
            msg = msg.format(*args, **kwargs)
            kwargs = {n: v for n, v in kwargs.items() if n in ('exc_info', 'extra')}
            self.log(level, msg, **kwargs)

level = logging.ERROR

_logger = logging.getLogger('xbuild')
logger = StyleAdapter(_logger)
fmt = logging.Formatter('[%(levelname)s thr:%(threadName)s %(funcName)s] %(message)s')
consoleHandler = logging.StreamHandler(stream=sys.stdout)
consoleHandler.setLevel(level)
consoleHandler.setFormatter(fmt)
_logger.addHandler(consoleHandler)
_logger.setLevel(level)


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

