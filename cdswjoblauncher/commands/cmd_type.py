from enum import Enum


# Symlink names
LATEST_DATA_ZIP_LINK_NAME = "latest-command-data-zip"


class CommandType(Enum):
    ZIP_LATEST_COMMAND_DATA = ("zip_latest_command_data", "zip-latest-command-data", False)
    SEND_LATEST_COMMAND_DATA = ("send_latest_command_data", "send-latest-command-data", False)

    def __init__(self, value, output_dir_name, session_based: bool, session_link_name: str = ""):
        self.real_name = value
        self.session_based = session_based
        self.output_dir_name = output_dir_name

        if session_link_name:
            self.session_link_name = session_link_name
        else:
            self.session_link_name = f"latest-session-{value}"

        self.log_link_name = f"latest-log-{value}"
        self.command_data_name = f"latest-command-data-{value}"
        self.command_data_zip_name: str = f"{LATEST_DATA_ZIP_LINK_NAME}-{value}"

    @staticmethod
    def from_str(val):
        allowed_values = {ct.name: ct for ct in CommandType}
        return CommandType._validate(val, allowed_values, "Invalid enum key")

    @staticmethod
    def by_real_name(val):
        allowed_values = {ct.real_name: ct for ct in CommandType}
        return CommandType._validate(val, allowed_values, "Invalid enum value by real name")

    @staticmethod
    def by_output_dir_name(val):
        allowed_values = {ct.output_dir_name: ct for ct in CommandType}
        return CommandType._validate(val, allowed_values, "Invalid enum value by output dir name")

    @classmethod
    def _validate(cls, val, allowed_values, err_message_prefix):
        if val in allowed_values:
            return allowed_values[val]
        else:
            raise ValueError("{}: {}".format(err_message_prefix, val))
