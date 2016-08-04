from xbuild.console import logger


def fn():
    logger.debugf("lofasz {} {mi}", 'es', mi='estifeny')
    

class Clazz(object):

    def __init__(self):
        logger.debugf("lofasz {} {mi}", 'es', mi='estifeny')

logger.debugf("lofasz {} {mi}", 'es', mi='estifeny')
fn()
Clazz()

