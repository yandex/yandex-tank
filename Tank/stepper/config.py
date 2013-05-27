from exceptions import StepperConfigurationError
import load_plan as lp
import missile
import util
from uuid import uuid4


def mark_by_uri(missile):
    return missile.split('\n', 1)[0].split(' ', 2)[1].split('?', 1)[0]


class ComponentFactory():
    markers = {
        'uniq': lambda m: uuid4().hex,
        'uri': mark_by_uri,
    }

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
        self.loop_limit = loop_limit
        self.ammo_limit = ammo_limit
        self.uris = uris
        self.headers = headers
        self.autocases = autocases

    def get_load_plan(self):
        """
        return load plan (timestamps generator)
        """
        if self.rps_schedule and self.instances_schedule:
            raise StepperConfigurationError('Both rps and instances schedules specified. You must specify only one of them')
        elif self.rps_schedule:
            return lp.create(self.rps_schedule)
        elif self.instances_schedule:
            raise NotImplementedError('We have no support for instances_schedule yet')
        else:
            raise StepperConfigurationError('Schedule is not specified')

    def get_ammo_generator(self):
        """
        return ammo generator
        """
        if self.uris and self.ammo_file:
            raise StepperConfigurationError('Both uris and ammo file specified. You must specify only one of them')
        else:
            if self.uris:
                return util.Limiter(
                    missile.UriStyleGenerator(
                        self.uris,
                        self.headers,
                        loop_limit=self.loop_limit,
                        http_ver=self.http_ver
                    ),
                    self.ammo_limit
                )
            elif self.ammo_file:
                return util.Limiter(
                    missile.AmmoFileReader(
                        self.ammo_file,
                        loop_limit=self.loop_limit
                    ),
                    self.ammo_limit
                )
            else:
                raise StepperConfigurationError('Ammo not found. Specify uris or ammo file')

    def get_marker(self):
        if self.autocases:
            if self.autocases in ComponentFactory.markers:
                return ComponentFactory.markers[self.autocases]
            else:
                raise NotImplementedError('No such marker')
        else:
            return lambda m: 'None'
