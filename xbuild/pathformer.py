

class NoPathFormer(object):
    '''You have to provide your own implementation for path forming.'''

    def __init__(self):
        pass

    def encode(self, fpath):
        return fpath

    def decode(self, fpath):
        return fpath
