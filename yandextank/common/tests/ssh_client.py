import mock
import paramiko

banner = '###Hellow user!####\n'


def mock_output(stream, out, banner):

    stream.read.return_value = bytes((banner + out).encode('utf-8'))

    return stream


class SSHClient(paramiko.SSHClient):

    connect = mock.Mock(return_value=None)

    def exec_command(self, command, *args, **kwargs):
        stdin = mock.MagicMock()
        stdout = mock.Mock(read=mock.Mock(return_value=b''))
        stderr = mock.Mock(read=mock.Mock(return_value=b''))

        return stdin, stdout, stderr


class SSHClientWithBanner(SSHClient):

    def exec_command(self, command, *args, **kwargs):
        stdin, stdout, stderr = super().exec_command(command, *args, **kwargs)

        if command == 'pwd':
            stdout = mock_output(stdout, '/var/tmp', banner)
        elif command == '\n':
            stdout = mock_output(stdout, '', banner)

        return stdin, stdout, stderr


class SSHClientWithoutBanner(SSHClient):

    def exec_command(self, command, *args, **kwargs):
        stdin, stdout, stderr = super().exec_command(command, *args, **kwargs)

        if command == 'pwd':
            stdout = mock_output(stdout, '/var/tmp', '')
        elif command == '\n':
            stdout = mock_output(stdout, '', '')

        return stdin, stdout, stderr
