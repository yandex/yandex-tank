from progressbar import ProgressBar, ETA, ReverseBar, Bar
from collections import namedtuple
import logging


class DefaultProgressBar(ProgressBar):

    """
    progressbar with predefined parameters
    """

    def __init__(self, maxval, caption=''):
        widgets = [caption, Bar('>'), ' ', ETA(), ' ', ReverseBar('<')]
        super(DefaultProgressBar, self).__init__(
            widgets=widgets, maxval=maxval)


def progress(gen, caption='', pb_class=DefaultProgressBar):
    """
    Make a generator that displays a progress bar from
    generator gen, set caption and choose the class to
    use (DefaultProgressBar by default)

    Generator should have __len__ method returning it's
    size.

    Progress bar class constructor should take two
    parameters:
      * generator size
      * progress bar caption.

    It also should have start, update and finish methods.
    """
    pbar = None
    if len(gen):
        pbar = pb_class(len(gen), caption).start() if pb_class else None
    i = 0
    for elem in gen:
        if pbar:
            pbar.update(i)
        i += 1
        yield(elem)
    if pbar:
        pbar.finish()


StepperInfo = namedtuple(
    'StepperInfo',
    'loop_count,steps,loadscheme,duration,ammo_count'
)


class StepperStatus(object):
    '''
    Raises StopIteration when limits are reached.
    '''

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.info = {
            'loop_count': None,
            'steps': None,
            'loadscheme': None,
            'duration': None,
            'ammo_count': None,
        }
        self.loop_limit = None
        self.ammo_limit = None

    def publish(self, key, value):
        if key not in self.info:
            raise RuntimeError(
                "Tryed to publish to a non-existent key: %s" % key)
        self.log.debug('Published %s to %s', value, key)
        self.info[key] = value

    @property
    def ammo_count(self):
        #return self._ammo_count
        return self.info['ammo_count']

    @ammo_count.setter
    def ammo_count(self, value):
        #self._ammo_count = value
        self.info['ammo_count'] = value
        if self.ammo_limit and value > self.ammo_limit:
            raise StopIteration

    @property
    def loop_count(self):
        #return self._loop_count
        return self.info['loop_count']

    @loop_count.setter
    def loop_count(self, value):
        #self._loop_count = value
        self.info['loop_count'] = value
        if self.loop_limit and value > self.loop_limit:
            raise StopIteration

    def get_info(self):
        for key in self.info:
            if self.info[key] is None:
                raise RuntimeError(
                    "Information for %s is not published yet." % key)
        return StepperInfo(**self.info)

STATUS = StepperStatus()
