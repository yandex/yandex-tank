from module_exceptions import StepperConfigurationError
import load_plan as lp
import instance_plan as ip
import missile
from mark import get_marker
import info


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
        ammo_type='phantom'
    ):
        generators = {
            'phantom': missile.AmmoFileReader,
            'slowlog': missile.SlowLogReader,
        }
        if ammo_type in generators:
            self.ammo_generator_class = generators[ammo_type]
        else:
            raise NotImplementedError(
                'No such ammo type implemented: "%s"' % ammo_type)
        self.rps_schedule = rps_schedule
        self.http_ver = http_ver
        self.ammo_file = ammo_file
        self.instances_schedule = instances_schedule
        loop_limit = int(loop_limit)
        if loop_limit == -1:  # -1 means infinite
            loop_limit = None
        ammo_limit = int(ammo_limit)
        if ammo_limit == -1:  # -1 means infinite
            ammo_limit = None
        if loop_limit is None and ammo_limit is None and instances_schedule:
            loop_limit = 1  # we should have only one loop if we have instance_schedule
        info.status.loop_limit = loop_limit
        info.status.ammo_limit = ammo_limit
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
            info.status.publish('loadscheme', self.rps_schedule)
            return lp.create(self.rps_schedule)
        elif self.instances_schedule:
            info.status.publish('loadscheme', self.instances_schedule)
            return ip.create(self.instances_schedule)
        else:
            #raise StepperConfigurationError('Schedule is not specified')
            self.instances_schedule = []
            info.status.publish('loadscheme', self.instances_schedule)
            return ip.create(self.instances_schedule)

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
                http_ver=self.http_ver
            )
        elif self.ammo_file:
            
            ammo_gen = self.ammo_generator_class(self.ammo_file)
        else:
            raise StepperConfigurationError(
                'Ammo not found. Specify uris or ammo file')
        return ammo_gen

    def get_marker(self):
        return self.marker
