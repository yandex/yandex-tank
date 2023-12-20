import subprocess
import shlex
import logging
from six import string_types


# FIXME poll_period is not used anywhere
def execute(cmd, shell=False, poll_period=1.0, catch_out=False, executable=None):
    """Execute UNIX command and wait for its completion

    Args:
        cmd (str or list): command to execute
        shell (bool): invoke inside shell environment
        catch_out (bool): collect process' output
        executable: custom executable for popen

    Returns:
        returncode (int): process return code
        stdout (str): collected process stdout (only if catch_out set to true)
        stderr (str): collected process stderr (only if catch_out set to true)
    """
    # FIXME: move to module level
    log = logging.getLogger(__name__)
    log.debug("Starting: %s", cmd)

    stdout = ""
    stderr = ""

    if not shell and isinstance(cmd, string_types):
        cmd = shlex.split(cmd)
    if not executable:
        executable = None

    if catch_out:
        process = subprocess.Popen(
            cmd,
            shell=shell,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            close_fds=True,
            executable=executable)
    else:
        process = subprocess.Popen(cmd, shell=shell, close_fds=True, executable=executable)

    stdout, stderr = process.communicate()
    if stderr:
        log.error("There were errors:\n%s", stderr)

    if stdout:
        log.debug("Process output:\n%s", stdout)
    returncode = process.returncode
    log.debug("Process exit code: %s", returncode)
    return returncode, stdout, stderr


# FIXME: remove this dumb popen wrapper
def popen(cmnd):
    return subprocess.Popen(
        cmnd,
        bufsize=0,
        close_fds=True,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE
    )
