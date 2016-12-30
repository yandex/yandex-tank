import logging
import time
from collections import namedtuple
from sys import stdout

log = logging.getLogger(__name__)

StepperInfo = namedtuple(
    'StepperInfo', 'loop_count,steps,loadscheme,duration,ammo_count,instances')


class StepperStatus(object):
    '''
    Raises StopIteration when limits are reached.
    '''

    def __init__(self):
        self.core = None  # dirty hack. StepperWrapper should pass core here.
        self.info = {
            'loop_count': 0,
            'steps': None,
            'loadscheme': None,
            'duration': None,
            'ammo_count': 0,
            'instances': None,
        }
        self._ammo_count = 0
        self._old_ammo_count = 0
        self._loop_count = 0
        self._af_position = None
        self.af_size = None
        self.loop_limit = None
        self.ammo_limit = None
        self.lp_len = None
        self.lp_progress = 0
        self.af_progress = 0
        self._timer = time.time()

    def publish(self, key, value):
        if key not in self.info:
            raise RuntimeError(
                "Tried to publish to a non-existent key: %s" % key)
        log.debug('Published %s to %s', value, key)
        self.info[key] = value

    @property
    def af_position(self):
        return self._af_position

    @af_position.setter
    def af_position(self, value):
        self._af_position = value
        self.update_af_progress()

    @property
    def ammo_count(self):
        return self._ammo_count

    @ammo_count.setter
    def ammo_count(self, value):
        self._ammo_count = value
        self.update_lp_progress()
        if self.ammo_limit and value > self.ammo_limit:
            print
            log.info("Ammo limit reached: %s", self.ammo_limit)
            raise StopIteration

    def inc_ammo_count(self):
        self.ammo_count += 1

    @property
    def loop_count(self):
        return self._loop_count

    @loop_count.setter
    def loop_count(self, value):
        self._loop_count = value
        if self.loop_limit and value >= self.loop_limit:
            print  # do not overwrite status (go to new line)
            log.info("Loop limit reached: %s", self.loop_limit)
            raise StopIteration

    def inc_loop_count(self):
        self.loop_count += 1

    def get_info(self):
        self.info['ammo_count'] = self._ammo_count
        self.info['loop_count'] = self._loop_count
        for key in self.info:
            if self.info[key] is None:
                raise RuntimeError(
                    "Information for %s is not published yet." % key)
        return StepperInfo(**self.info)

    def update_view(self):
        ammo_generated = self._ammo_count - self._old_ammo_count
        self._old_ammo_count = self._ammo_count
        cur_time = time.time()
        time_delta = cur_time - self._timer
        self._timer = cur_time
        if time_delta > 0:
            stdout.write(
                "AF: %3s%%, LP: %3s%%, loops: %10s, speed: %5s Krps\r" % (
                    self.af_progress, self.lp_progress, self.loop_count,
                    int(ammo_generated / time_delta / 1000.0)))
            stdout.flush()
            if self.core:
                self.core.publish("stepper", "progress", self.lp_progress)
                self.core.publish("stepper", "loop_count", self.loop_count)
                self.core.publish(
                    "stepper", "speed",
                    "%s Krps" % int(ammo_generated / time_delta / 1000.0))

    def update_af_progress(self):
        if self.af_size and self.loop_limit and self.af_position is not None:
            bytes_read = self.af_size * self.loop_count + self.af_position
            total_bytes = self.af_size * self.loop_limit
            progress = int(float(bytes_read) / float(total_bytes) * 100.0)
        else:
            progress = 100
        if self.af_progress != progress:
            self.af_progress = progress
            self.update_view()

    def update_lp_progress(self):
        if self.ammo_limit or self.lp_len:
            if self.ammo_limit:
                if self.lp_len:
                    max_ammo = min(self.ammo_limit, self.lp_len)
                else:
                    max_ammo = self.ammo_limit
            else:
                max_ammo = self.lp_len
            progress = int(float(self.ammo_count) / float(max_ammo) * 100.0)
        else:
            progress = 100
        if self.lp_progress != progress:
            self.lp_progress = progress
            self.update_view()


status = StepperStatus()
