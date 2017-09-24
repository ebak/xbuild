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
import sys
import logging
from threading import RLock

# e.g. prefix 'x' -> [xDEBUG ...]

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

    def setLevel(self, level):
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)
        
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
    
    def infof(self, msg, *args, **kwargs):
        self._logit(logging.INFO, msg, args, kwargs)
    
    def warningf(self, msg, *args, **kwargs):
        self._logit(logging.WARN, msg, args, kwargs)

    def errorf(self, msg, *args, **kwargs):
        self._logit(logging.ERROR, msg, args, kwargs)

    def cdebug(self, cond, msg):
        if cond:
            self.debug(msg)

    def cinfo(self, cond, msg):
        if cond:
            self.info(msg)

    def cwarning(self, cond, msg):
        if cond:
            self.warning(msg)

    def cerror(self, cond, msg):
        if cond:
            self.error(msg)

    def cdebugf(self, cond, msg, *args, **kwargs):
        if cond:
            self._logit(logging.DEBUG, msg, args, kwargs)
    
    def cinfof(self, cond, msg, *args, **kwargs):
        if cond:
            self._logit(logging.INFO, msg, args, kwargs)
    
    def cwarningf(self, cond, msg, *args, **kwargs):
        if cond:
            self._logit(logging.WARN, msg, args, kwargs)

    def cerrorf(self, cond, msg, *args, **kwargs):
        if cond:
            self._logit(logging.ERROR, msg, args, kwargs)

    def _logit(self, level, msg, args, kwargs):
        if self.isEnabledFor(level):
            # self.findCaller()
            msg = msg.format(*args, **kwargs)
            kwargs = {n: v for n, v in kwargs.items() if n in ('exc_info', 'extra')}
            self.log(level, msg, **kwargs)


def getLoggerAdapter(name, prefix=''):
    _logger = logging.getLogger(name)
    adapter = StyleAdapter(_logger)
    fmt = logging.Formatter('[{pfix}%(levelname)s thr:%(threadName)s %(funcName)s] %(message)s'.format(pfix=prefix))
    consoleHandler = logging.StreamHandler(stream=sys.stdout)
    consoleHandler.setFormatter(fmt)
    adapter.logger.addHandler(consoleHandler)
    return adapter

def getConsoleAdapter(name, stream=sys.stdout):
    _logger = logging.getLogger(name)
    _logger.handlers = []
    adapter = StyleAdapter(_logger)
    fmt = logging.Formatter('%(levelname)s: %(message)s')
    consoleHandler = logging.StreamHandler(stream=stream)
    consoleHandler.setFormatter(fmt)
    adapter.logger.addHandler(consoleHandler)
    adapter.setLevel(logging.DEBUG)
    return adapter

logger = getLoggerAdapter('xbuild', prefix='x')
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)


console = getConsoleAdapter('xbuild_stdout')


def setOut(stream):
    global console
    console = getConsoleAdapter('xbuild_stdout', stream)

def write(msg):
    console.info(msg)

def error(msg):
    console.error(msg)

def errorf(msg, *args, **kwargs):
    console.errorf(msg, *args, **kwargs)

def info(msg):
    console.info(msg)

def cinfo(cond, msg):
    console.cinfo(cond, msg)

def infof(msg, *args, **kwargs):
    console.infof(msg, *args, **kwargs)

def cinfof(cond, msg, *args, **kwargs):
    console.cinfof(cond, msg, *args, **kwargs)
    
def warn(msg):
    console.warning(msg)

def warnf(msg, *args, **kwargs):
    console.warningf(msg, *args, **kwargs)

