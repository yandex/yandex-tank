import logging
import sys
from optparse import OptionParser

from netort.resource import manager as resource_manager
from yandextank.core.consoleworker import ConsoleWorker
from yandextank.core.tankcore import LockError
from yandextank.validator.validator import ValidationError
from yandextank.version import VERSION


def main():
    parser = OptionParser()
    parser.add_option(
        '-c',
        '--config',
        action='append',
        help="Path to INI file containing run options, multiple options accepted",
        default=[]
    )
    parser.add_option(
        '-f',
        '--fail-lock',
        action='store_true',
        dest='lock_fail',
        help="Don't wait for lock to release, fail test instead")
    parser.add_option(
        '-i',
        '--ignore-lock',
        action='store_true',
        dest='ignore_lock',
        help="Ignore lock files from concurrent instances, has precedence before --lock-fail"
    )
    parser.add_option(
        '-k',
        '--lock-dir',
        action='store',
        dest='lock_dir',
        type="string",
        help="Directory for lock file")
    parser.add_option(
        '-l',
        '--log',
        action='store',
        default="tank.log",
        help="Tank log file location")
    parser.add_option(
        '--error_log',
        action='store',
        dest='error_log',
        default="tank_errors.log",
        help="Tank errors log file location")
    parser.add_option(
        '-m',
        '--manual-start',
        action='store_true',
        dest='manual_start',
        help="Wait for Enter key to start the test")
    parser.add_option(
        '-n',
        '--no-rc',
        action='store_true',
        dest='no_rc',
        help="Don't load config files from /etc/yandex-tank and ~/.yandex-tank")
    parser.add_option(
        '-o',
        '--option',
        action='append',
        help="Set config option, multiple options accepted, example: -o 'shellexec.start=pwd'"
    )
    parser.add_option(
        '-q',
        '--quiet',
        action='store_true',
        help="Less console output, only errors and warnings")
    parser.add_option(
        '-s',
        '--scheduled-start',
        action='store',
        dest='scheduled_start',
        help="Start test at specified time, format 'YYYY-MM-DD hh:mm:ss', date part is optional"
    )
    parser.add_option(
        '-v',
        '--verbose',
        action='store_true',
        help="More console output, +debug messages")
    parser.add_option(
        '-p',
        '--patch-cfg',
        action='append',
        help='Patch config with yaml snippet (similar to -o, but has full compatibility to\
        and the exact scheme of yaml format config)',
        dest='patches'
    )
    parser.add_option(
        '--version',
        action='store_true',
        dest='version'
    )
    # FIXME: restore completion helper
    # completion_helper = CompletionHelperOptionParser()
    # completion_helper.handle_request(parser)

    options, ammofiles = parser.parse_args()
    if options.version:
        print('YandexTank/{}'.format(VERSION))
        return

    ammofile = ammofiles[0] if len(ammofiles) > 0 else None

    handlers = init_logging(options.error_log, options.verbose, options.quiet)

    cli_kwargs = {'core': {'lock_dir': options.lock_dir}} if options.lock_dir else {}
    if options.ignore_lock:
        cli_kwargs.setdefault('core', {})['ignore_lock'] = options.ignore_lock

    if ammofile:
        logging.debug("Ammofile: %s", ammofile)
        cli_kwargs['phantom'] = {
            'use_caching': False,
            'ammofile': ammofile
        }
    try:
        worker = ConsoleWorker([resource_manager.resource_filename(cfg) for cfg in options.config],
                               options.option,
                               options.patches,
                               [cli_kwargs],
                               options.no_rc,
                               ammo_file=ammofile if ammofile else None,
                               log_handlers=handlers,
                               debug=options.verbose
                               )
    except (ValidationError, LockError) as e:
        logging.error('Config validation error:\n{}'.format(e.message))
        return
    worker.start()
    try:
        while True:
            worker.join(timeout=2)
            if not worker.is_alive():
                break
    except KeyboardInterrupt:
        worker.stop()
        worker.join()
    sys.exit(worker.retcode)


def init_logging(events_log_fname, verbose, quiet):
    """ Set up logging, as it is very important for console tool """
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # create file handler which logs error messages

    # create console handler with a higher log level
    console_handler = logging.StreamHandler(sys.stdout)
    stderr_hdl = logging.StreamHandler(sys.stderr)

    fmt_verbose = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s"
    )
    fmt_regular = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

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

    if events_log_fname:
        err_file_handler = logging.FileHandler(events_log_fname)
        err_file_handler.setLevel(logging.WARNING)
        err_file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s\t%(message)s"
            ))
        return [err_file_handler, console_handler, stderr_hdl]
    else:
        return [console_handler, stderr_hdl]
        # logger.addHandler(err_file_handler)


class SingleLevelFilter(logging.Filter):
    """Exclude or approve one msg type at a time.    """

    def __init__(self, passlevel, reject):
        logging.Filter.__init__(self)
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return record.levelno != self.passlevel
        else:
            return record.levelno == self.passlevel


if __name__ == '__main__':
    main()
