from typing import List


class CdswLauncherException(Exception):
    pass


class ConfigSetupException(CdswLauncherException):

    def __init__(self, msg: str, attr: str = ""):
        self._msg = msg
        self._attr = attr

    def __str__(self):
        return f"{self._attr}: {self._msg}" if self._attr else self._msg


class CliArgException(CdswLauncherException):
    pass


class CommandExecutionException(CdswLauncherException):
    def __init__(self, msg: str, cmd: str = None, stderr: List[str] = None, stdout: List[str] = None):
        self._msg = msg
        self._cmd = cmd
        self.stdout = stdout if stdout else []
        self.stderr = stderr if stderr else []

    def __str__(self):
        cmd = self._cmd if self._cmd else ""
        stderr = "\n".join(self.stderr)
        stdout = "\n".join(self.stdout)
        return f"{self.__class__.__name__}: {self._msg}\n Command: {cmd} \n stderr: {stderr} \n stdout: {stdout}"


class MultiCommandExecutionException(CdswLauncherException):
    def __init__(self, exceptions: List[CommandExecutionException]):
        self._exceptions = exceptions

    def __str__(self):
        return f"{self.__class__.__name__}: {self._exceptions}"


class CommandTimedOutException(CommandExecutionException):
    def __init__(self, msg: str, cmd: str = None, stderr: List[str] = None, stdout: List[str] = None):
        super().__init__(msg, cmd, stderr, stdout)

    def __str__(self):
        return super().__str__()
