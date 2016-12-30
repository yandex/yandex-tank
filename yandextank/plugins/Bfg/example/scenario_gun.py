def __init__():
    """
    This is a module initialization function.
    """


"""
Yandex.Tank will call these scenarios
passing 3 parameters to them:

missile: missile from ammo file
marker: marker from ammo file
measure: measuring context
"""


def scenario_1(missile, marker, measure):
    with measure("scenario_1_step_1") as m:
        # make step 1 and set result codes
        m["proto_code"] = 200
        m["net_code"] = 0
    with measure("scenario_1_step_2") as m:
        # make step 2 and set result codes
        m["proto_code"] = 200
        m["net_code"] = 0


def scenario_2(missile, marker, measure):
    with measure("scenario_2_step_1") as m:
        # make step 1 and set result codes
        m["proto_code"] = 200
        m["net_code"] = 0
    with measure("scenario_2_step_2") as m:
        # make step 2 and set result codes
        m["proto_code"] = 200
        m["net_code"] = 0


"""
SCENARIOS module variable is used by Tank to choose the scenario to
shoot with. For each missile Tank will look up missile marker in this dict.
"""
SCENARIOS = {
    "scenario_1": scenario_1,
    "scenario_2": scenario_1,
}
