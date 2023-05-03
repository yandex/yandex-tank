"""
Logging initialization AND signals (but why?!)

TODO:
    * move signals to another module
"""
import logging
import sys
import signal

logger = logging.getLogger(__name__)


class SingleLevelFilter(logging.Filter):
    """Reject or approve one exact debug level. """

    def __init__(self, levelno, reject):
        """
        Args:
            levelno (int): which level do we work with (logging.DEBUG, etc.)
            reject (bool): remove messages of this level if true, remove all others if false
        """
        logging.Filter.__init__(self)
        self.levelno = levelno
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return record.levelno != self.levelno
        else:
            return record.levelno == self.levelno


def init_logging(log_filename, verbose, quiet):
    """Set up logging with default parameters:
    * default console logging level is INFO
    * ERROR, WARNING and CRITICAL are redirected to stderr

    Args:
        log_filename (str): if set, will write DEBUG log there
        verbose (bool): DEBUG level in console, overrides 'quiet'
        quiet (bool): WARNING level in console
    """
    # TODO: consider making one verbosity parameter instead of two mutually exclusive
    # TODO: default values for parameters
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)

    # add file handler if needed
    if log_filename:
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        # TODO: initialize all formatters in the beginning of this function
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s"
            ))
        logger.addHandler(file_handler)

    # console stdout and stderr handlers
    console_handler = logging.StreamHandler(sys.stdout)
    stderr_hdl = logging.StreamHandler(sys.stderr)

    # formatters
    fmt_verbose = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s",
        datefmt='%Y-%m-%d,%H:%M:%S.%f'
    )
    fmt_regular = logging.Formatter(
        "%(asctime)s [%(levelname).4s] [%(filename).8s] %(message)s", "%H:%M:%S")

    # set formatters and log levels
    if verbose:
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(fmt_verbose)
        stderr_hdl.setFormatter(fmt_verbose)
    elif quiet:
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(fmt_regular)
        stderr_hdl.setFormatter(fmt_regular)
    else:
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(fmt_regular)
        stderr_hdl.setFormatter(fmt_regular)

    # TODO: do we really need these to be redirected?
    # redirect ERROR, WARNING and CRITICAL to sterr
    f_err = SingleLevelFilter(logging.ERROR, True)
    f_warn = SingleLevelFilter(logging.WARNING, True)
    f_crit = SingleLevelFilter(logging.CRITICAL, True)
    console_handler.addFilter(f_err)
    console_handler.addFilter(f_warn)
    console_handler.addFilter(f_crit)
    logger.addHandler(console_handler)

    f_info = SingleLevelFilter(logging.INFO, True)
    f_debug = SingleLevelFilter(logging.DEBUG, True)
    stderr_hdl.addFilter(f_info)
    stderr_hdl.addFilter(f_debug)
    logger.addHandler(stderr_hdl)


# TODO: describe what are these for, how to use
def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    logger.warning("Got signal %s, going to stop", sig)
    raise KeyboardInterrupt()


def ignore_handler(sig, frame):
    logger.warning("Got signal %s, ignoring", sig)


def set_sig_handler():
    uncatchable = ['SIG_DFL', 'SIGSTOP', 'SIGKILL']
    ignore = ['SIGCHLD', 'SIGCLD']
    all_sig = [s for s in dir(signal) if s.startswith("SIG")]
    for sig_name in ignore:
        try:
            sig_num = getattr(signal, sig_name)
            signal.signal(sig_num, ignore_handler)
        except Exception:
            pass
    for sig_name in [s for s in all_sig if s not in (uncatchable + ignore)]:
        try:
            sig_num = getattr(signal, sig_name)
            signal.signal(sig_num, signal_handler)
        except Exception as ex:
            logger.error("Can't set handler for %s, %s", sig_name, ex)
