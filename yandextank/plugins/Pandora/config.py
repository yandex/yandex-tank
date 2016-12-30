''' Pandora config generator '''
import json
from pkg_resources import resource_string

from ...stepper.util import parse_duration


def periodic_schedule(batch_size, period, limit):
    return {
        "LimiterType": "periodic",
        "Parameters": {
            "BatchSize": float(batch_size),
            "MaxCount": float(limit),
            "Period": float(period),
        },
    }


def linear_schedule(start_rps, end_rps, period):
    return {
        "LimiterType": "linear",
        "Parameters": {
            "StartRps": float(start_rps),
            "EndRps": float(end_rps),
            "Period": parse_duration(period) / 1000.0,
        },
    }


def unlimited_schedule(*args):
    return {
        "LimiterType": "unlimited",
        "Parameters": {},
    }


step_producers = {
    "periodic": periodic_schedule,
    "linear": linear_schedule,
    "unlimited": unlimited_schedule,
}


def parse_schedule(schedule):
    steps = [
        step.strip() for step in " ".join(schedule.split("\n")).split(')')
        if step.strip()
    ]
    if len(steps) > 1:
        raise NotImplementedError("Composite schedules not implemented yet")
    schedule_type, params = steps[0].split('(')
    params = [p.strip() for p in params.split(',')]
    if schedule_type in step_producers:
        return step_producers[schedule_type](*params)
    else:
        raise NotImplementedError(
            "Step of type %s is not implemented" % schedule_type)


class PandoraConfig(object):
    def __init__(self):
        self.pools = []

    def data(self):
        return {"Pools": [p.data() for p in self.pools]}

    def json(self):
        return json.dumps(self.data(), indent=2)

    def add_pool(self, pool_config):
        self.pools.append(pool_config)


class PoolConfig(object):
    def __init__(self):
        self.config = json.loads(
            resource_string(__name__, 'config/pandora_pool_default.json'))

    def set_ammo(self, ammo):
        self.config["AmmoProvider"]["AmmoSource"] = ammo

    def set_ammo_type(self, ammo_type):
        self.config["AmmoProvider"]["AmmoType"] = ammo_type

    def set_loop(self, loop):
        self.config["AmmoProvider"]["Passes"] = loop

    def set_sample_log(self, sample_log):
        self.config["ResultListener"]["Destination"] = sample_log

    def set_startup_schedule(self, startup_schedule):
        self.config["StartupLimiter"] = startup_schedule

    def set_user_schedule(self, user_schedule):
        self.config["UserLimiter"] = user_schedule

    def set_shared_schedule(self, shared_schedule):
        self.config["SharedSchedule"] = shared_schedule

    def set_target(self, target):
        self.config["Gun"]["Parameters"]["Target"] = target

    def set_ssl(self, ssl):
        self.config["Gun"]["Parameters"]["SSL"] = ssl

    def set_gun_type(self, gun_type):
        self.config["Gun"]["GunType"] = gun_type

    def data(self):
        return self.config


def main():
    pool_config = PoolConfig()
    pool_config.set_loop(1)
    pool_config.set_startup_schedule(parse_schedule("periodic(100, 100, 100)"))
    pool_config.set_target("example.org:443")
    pandora_config = PandoraConfig()
    pandora_config.add_pool(pool_config)
    print(pandora_config.json())


if __name__ == '__main__':
    main()
