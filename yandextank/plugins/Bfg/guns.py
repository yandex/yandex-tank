import imp
import logging
import time
from contextlib import contextmanager
from random import randint

import requests
from ...common.interfaces import AbstractPlugin

logger = logging.getLogger(__name__)

requests_logger = logging.getLogger('requests')
requests_logger.setLevel(logging.WARNING)

requests.packages.urllib3.disable_warnings()


class AbstractGun(AbstractPlugin):
    def __init__(self, core):
        super(AbstractGun, self).__init__(core)
        self.results = None

    @contextmanager
    def measure(self, marker):
        start_time = time.time()
        data_item = {
            "send_ts": start_time,
            "tag": marker,
            "interval_real": None,
            "connect_time": 0,
            "send_time": 0,
            "latency": 0,
            "receive_time": 0,
            "interval_event": 0,
            "size_out": 0,
            "size_in": 0,
            "net_code": 0,
            "proto_code": 200,
        }
        try:
            yield data_item
        except Exception as e:
            logger.warning("%s failed while measuring with %s", marker, e)
            if data_item["proto_code"] == 200:
                data_item["proto_code"] = 500
            if data_item["net_code"] == 0:
                data_item["net_code"] == 1
            raise
        finally:
            if data_item.get("interval_real") is None:
                data_item["interval_real"] = int(
                    (time.time() - start_time) * 1e6)

            self.results.put(data_item, timeout=1)

    def setup(self):
        pass

    def shoot(self, missile, marker):
        raise NotImplementedError(
            "Gun should implement 'shoot(self, missile, marker)' method")

    def teardown(self):
        pass


class LogGun(AbstractGun):
    SECTION = 'log_gun'

    def __init__(self, core):
        super(LogGun, self).__init__(core)
        param = self.get_option("param", '15')
        logger.info('Initialized log gun for BFG with param = %s' % param)

    def shoot(self, missile, marker):
        logger.info("Missile: %s\n%s", marker, missile)
        rt = randint(2, 30000) * 1000
        with self.measure(marker) as di:
            di["interval_real"] = rt


class HttpGun(AbstractGun):
    SECTION = 'http_gun'

    def __init__(self, core):
        super(HttpGun, self).__init__(core)
        self.base_address = self.get_option("base_address")

    def shoot(self, missile, marker):
        logger.debug("Missile: %s\n%s", marker, missile)
        logger.debug("Sending request: %s", self.base_address + missile)
        with self.measure(marker) as di:
            try:
                r = requests.get(self.base_address + missile, verify=False)
                di["proto_code"] = r.status_code
            except requests.ConnectionError:
                logger.debug("Connection error", exc_info=True)
                di["net_code"] = 1
                di["proto_code"] = 500


class SqlGun(AbstractGun):
    SECTION = 'sql_gun'

    def __init__(self, core):
        super(SqlGun, self).__init__(core)

        from sqlalchemy import create_engine
        from sqlalchemy import exc
        self.exc = exc

        self.engine = create_engine(self.get_option("db"))

    def shoot(self, missile, marker):
        logger.debug("Missile: %s\n%s", marker, missile)
        with self.measure(marker) as di:
            errno = 0
            proto_code = 200
            try:
                cursor = self.engine.execute(missile.replace('%', '%%'))
                cursor.fetchall()
                cursor.close()
            except self.exc.TimeoutError as e:
                logger.debug("Timeout: %s", e)
                errno = 110
            except self.exc.ResourceClosedError as e:
                logger.debug(e)
            except self.exc.SQLAlchemyError as e:
                proto_code = 500
                logger.debug(e.orig.args)
            except self.exc.SAWarning as e:
                proto_code = 400
                logger.debug(e)
            except Exception as e:
                proto_code = 500
                logger.debug(e)
            di["proto_code"] = proto_code
            di["net_code"] = errno


class CustomGun(AbstractGun):
    """
    This gun is deprecated! Use UltimateGun
    """
    SECTION = 'custom_gun'

    def __init__(self, core):
        super(CustomGun, self).__init__(core)
        logger.warning("Custom gun is deprecated. Use Ultimate gun instead")
        module_path = self.get_option("module_path", "").split()
        module_name = self.get_option("module_name")
        fp, pathname, description = imp.find_module(module_name, module_path)
        try:
            self.module = imp.load_module(
                module_name, fp, pathname, description)
        finally:
            if fp:
                fp.close()

    def shoot(self, missile, marker):
        try:
            self.module.shoot(missile, marker, self.measure)
        except Exception as e:
            logger.warning("CustomGun %s failed with %s", marker, e)

    def setup(self):
        if hasattr(self.module, 'init'):
            self.module.init(self)


class ScenarioGun(AbstractGun):
    """
    This gun is deprecated! Use UltimateGun
    """
    SECTION = 'scenario_gun'

    def __init__(self, core):
        super(ScenarioGun, self).__init__(core)
        logger.warning("Scenario gun is deprecated. Use Ultimate gun instead")
        module_path = self.get_option("module_path", "")
        if module_path:
            module_path = module_path.split()
        else:
            module_path = None
        module_name = self.get_option("module_name")
        fp, pathname, description = imp.find_module(module_name, module_path)
        try:
            self.module = imp.load_module(
                module_name, fp, pathname, description)
        finally:
            if fp:
                fp.close()
        self.scenarios = self.module.SCENARIOS

    def shoot(self, missile, marker):
        marker = marker.rsplit("#", 1)[0]  # support enum_ammo
        if not marker:
            marker = "default"
        scenario = self.scenarios.get(marker, None)
        if scenario:
            try:
                scenario(missile, marker, self.measure)
            except Exception as e:
                logger.warning("Scenario %s failed with %s", marker, e)
        else:
            logger.warning("Scenario not found: %s", marker)

    def setup(self):
        if hasattr(self.module, 'init'):
            self.module.init(self)


class UltimateGun(AbstractGun):
    SECTION = "ultimate_gun"

    def __init__(self, core):
        super(UltimateGun, self).__init__(core)
        class_name = self.get_option("class_name", "LoadTest")
        module_path = self.get_option("module_path", "")
        if module_path:
            module_path = module_path.split()
        else:
            module_path = None
        module_name = self.get_option("module_name")
        self.init_param = self.get_option("init_param", "")
        fp, pathname, description = imp.find_module(module_name, module_path)
        #
        # Dirty Hack
        #
        # we will add current unix timestamp to the name of a module each time
        # it is imported to be sure Python won't be able to cache it
        #
        try:
            self.module = imp.load_module(
                "%s_%d" % (module_name, time.time()), fp, pathname, description)
        finally:
            if fp:
                fp.close()
        test_class = getattr(self.module, class_name, None)
        if not isinstance(test_class, type):
            raise NotImplementedError(
                "Class definition for '%s' was not found in '%s' module" %
                (class_name, module_name))
        self.load_test = test_class(self)

    def setup(self):
        if callable(getattr(self.load_test, "setup", None)):
            self.load_test.setup(self.init_param)

    def teardown(self):
        if callable(getattr(self.load_test, "teardown", None)):
            self.load_test.teardown()

    def shoot(self, missile, marker):
        marker = marker.rsplit("#", 1)[0]  # support enum_ammo
        if not marker:
            marker = "default"
        scenario = getattr(self.load_test, marker, None)
        if callable(scenario):
            try:
                scenario(missile)
            except Exception as e:
                logger.warning("Scenario %s failed with %s", marker, e)
        else:
            logger.warning("Scenario not found: %s", marker)
