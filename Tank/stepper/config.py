from module_exceptions import StepperConfigurationError
import load_plan as lp
import instance_plan as ip
import missile
import util
from mark import get_marker
from info import STATUS


class ComponentFactory():

    def __init__(
        self,
        rps_schedule=None,
        http_ver='1.1',
        ammo_file=None,
        instances_schedule=None,
        loop_limit=0,
        ammo_limit=0,
        uris=None,
        headers=None,
        autocases=None,
    ):
        self.rps_schedule = rps_schedule
        self.http_ver = http_ver
        self.ammo_file = ammo_file
        self.instances_schedule = instances_schedule
        self.loop_limit = int(loop_limit)
        if self.loop_limit == -1:  # -1 means infinite
            self.loop_limit = 0
        self.ammo_limit = int(ammo_limit)
        if self.ammo_limit == -1:  # -1 means infinite
            self.ammo_limit = 0
        if self.loop_limit is 0 and self.ammo_limit is 0:
            self.loop_limit = 1  # we should have only one loop if we have instance_schedule
        self.uris = uris
        self.headers = headers
        self.marker = get_marker(autocases)

    def get_load_plan(self):
        """
        return load plan (timestamps generator)
        """
        if self.rps_schedule and self.instances_schedule:
            raise StepperConfigurationError(
                'Both rps and instances schedules specified. You must specify only one of them')
        elif self.rps_schedule:
            STATUS.publish('loadscheme', self.rps_schedule)
            return lp.create(self.rps_schedule)
        elif self.instances_schedule:
            STATUS.publish('loadscheme', self.instances_schedule)
            return ip.create(self.instances_schedule)
        else:
            raise StepperConfigurationError('Schedule is not specified')

    def get_ammo_generator(self):
        """
        return ammo generator
        """
        if self.uris and self.ammo_file:
            raise StepperConfigurationError(
                'Both uris and ammo file specified. You must specify only one of them')
        elif self.uris:
            ammo_gen = missile.UriStyleGenerator(
                self.uris,
                self.headers,
                loop_limit=self.loop_limit,
                http_ver=self.http_ver
            )
        elif self.ammo_file:
            ammo_gen = missile.AmmoFileReader(
                self.ammo_file,
                loop_limit=self.loop_limit
            )
        else:
            raise StepperConfigurationError(
                'Ammo not found. Specify uris or ammo file')
        return util.limiter(ammo_gen,
                            self.ammo_limit
                            )

    def get_marker(self):
        return self.marker
