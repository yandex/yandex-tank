class PluginImplementationError(RuntimeError):
    """
    Error in plugin implementation
    """
    pass


class PluginNotPrepared(Exception):
    """
    Can't find plugin's info in core.job
    """

    def __init__(self, msg=None):
        self.message = "%s\n%s" % (self.__doc__, msg)


class GeneratorNotFound(Exception):
    """
    Can't find generator in config
    """
    pass
