import sys
from threading import RLock

consoleLock = RLock()

def write(msg, out=sys.stdout):
    with consoleLock:
        out.write(msg)
        
def debug(msg):
    write('DEBUG: ' + msg + '\n')

def debugf(msg, *args, **kvargs):
    debug(msg.format(*args, **kvargs))

def xdebug(msg):
    write('xDEBUG: ' + msg + '\n')

def xdebugf(msg, *args, **kvargs):
    xdebug(msg.format(*args, **kvargs))

def error(msg):
    write('ERROR: ' + msg + '\n', out=sys.stderr)

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

