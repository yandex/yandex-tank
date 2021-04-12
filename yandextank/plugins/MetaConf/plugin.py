''' Plugin that can be used to store options for adjacent CI or scripts in tank config '''
import logging

from ...common.interfaces import AbstractPlugin


logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin):
    """   MetaConf plugin to store and validate options     """

    def __init__(self, core, cfg, name):
        AbstractPlugin.__init__(self, core, cfg, name)
        self.config_content = self.core.config.validated["metaconf"]

    @staticmethod
    def get_key():
        return __file__

    def configure(self):
        logger.debug("Meta config used in test:\n%s", self.config_content)
