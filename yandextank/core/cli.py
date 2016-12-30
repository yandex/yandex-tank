import logging
import sys
import traceback
from optparse import OptionParser

from .consoleworker import ConsoleTank, CompletionHelperOptionParser


def main():
    parser = OptionParser()
    parser.add_option(
        '-c',
        '--config',
        action='append',
        help="Path to INI file containing run options, multiple options accepted"
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

    completion_helper = CompletionHelperOptionParser()
    completion_helper.handle_request(parser)

    options, ammofile = parser.parse_args()

    worker = ConsoleTank(options, ammofile)
    worker.init_logging()
    try:
        worker.configure()
        rc = worker.perform_test()
        sys.exit(rc)
    except Exception as ex:
        logging.error("Exception: %s", ex)
        logging.debug("Exception: %s", traceback.format_exc(ex))
        sys.exit(1)


if __name__ == '__main__':
    main()
