import sys
from threading import RLock

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

def setXDebug(val):
    global xDebugEnabled
    xDebugEnabled = val

def write(msg, out=None):
    global outStream
    out = out if out else outStream
    with consoleLock:
        out.write(msg)
        out.flush()
        
def debug(msg):
    write('DEBUG: ' + msg + '\n')

def debugf(msg, *args, **kvargs):
    debug(msg.format(*args, **kvargs))

def xdebug(msg):
    if xDebugEnabled:
        write('xDEBUG: ' + msg + '\n')

def xdebugf(msg, *args, **kvargs):
    xdebug(msg.format(*args, **kvargs))

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

