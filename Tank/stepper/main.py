'''
Module contains top-level generators.
'''
from itertools import izip
import format as fmt
from config import ComponentFactory
import info


class AmmoFactory(object):

    '''
    A generator that produces ammo.
    '''

    def __init__(self, factory):
        '''
        Factory parameter is a configured ComponentFactory that
        is able to produce load plan and ammo generator.
        '''
        self.factory = factory
        self.load_plan = factory.get_load_plan()
        self.ammo_generator = factory.get_ammo_generator()
        self.filter = lambda missile: True
        self.marker = factory.get_marker()

    def __iter__(self):
        '''
        Returns a generator of (timestamp, marker, missile) tuples
        where missile is in a string representation. Load Plan (timestamps
        generator) and ammo generator are taken from the previously
        configured ComponentFactory, passed as a parameter to the
        __init__ method of this class.
        '''
        for ammo_tuple in (
            (timestamp, marker or self.marker(missile), missile)
            for timestamp, (missile, marker)
            in izip(self.load_plan, self.ammo_generator)
        ):
            yield ammo_tuple


class Stepper(object):

    def __init__(self, **kwargs):
        info.status = info.StepperStatus()
        self.af = AmmoFactory(ComponentFactory(**kwargs))
        self.ammo = fmt.Stpd(self.af)

    def write(self, f):
        for missile in self.ammo:
            f.write(missile)
