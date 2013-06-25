'''
Ammo formatters
'''


class Stpd(object):
    '''
    STPD ammo formatter
    '''
    def __init__(self, ammo_factory):
        self.af = ammo_factory

    def __iter__(self):
        return ("%s %s %s\n%s\n" % (len(missile), timestamp, marker, missile) for timestamp, marker, missile in self.af)
