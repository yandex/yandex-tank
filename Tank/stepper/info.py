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

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.info = {
            'loop_count': None,
            'steps': None,
            'loadscheme': None,
            'duration': None,
            'ammo_count': None,
        }

    def publish(self, key, value):
        if key not in self.info:
            raise RuntimeError(
                "Tryed to publish to a non-existent key: %s" % key)
        self.log.info('Published %s to %s', (value, key))
        self.info[key] = value

    def get_stepper_info(self):
        for key in self.info:
            if self.info[key] is None:
                raise RuntimeError(
                    "Information for %s is not published yet." % key)
        return StepperInfo(**self.info)

STATUS = StepperStatus()
