import dataclasses
import logging
import os
import site
import sys
from enum import Enum
from typing import Dict

# https://stackoverflow.com/a/50255019/1106893
from googleapiwrapper.common import ServiceType
from googleapiwrapper.google_auth import GoogleApiAuthorizer
from googleapiwrapper.google_drive import (
    DriveApiWrapper,
    DriveApiWrapperSessionSettings,
    FileFindMode,
    DuplicateFileWriteResolutionMode,
    DriveApiScope,
    DriveApiFile,
)
from pythoncommons.constants import ExecutionMode
from pythoncommons.file_utils import FileUtils
from pythoncommons.logging_setup import SimpleLoggingSetup, SimpleLoggingSetupConfig
from pythoncommons.object_utils import ObjUtils
from pythoncommons.os_utils import OsUtils
from pythoncommons.project_utils import (
    ProjectUtils,
    ProjectRootDeterminationStrategy,
    PROJECTS_BASEDIR,
    PROJECTS_BASEDIR_NAME,
)

from cdswjoblauncher.cdsw.constants import CdswEnvVar, SECRET_PROJECTS_DIR, PROJECT_NAME


class ReportFile(Enum):
    SHORT_TXT = "report-short.txt"
    DETAILED_TXT = "report-detailed.txt"
    SHORT_HTML = "report-short.html"
    DETAILED_HTML = "report-detailed.html"


# MAKE SURE THIS PRECEDES IMPORT TO pythoncommons

CDSW_PROJECT = "cdsw"


class TestExecMode(Enum):
    CLOUDERA = "cloudera"
    UPSTREAM = "upstream"


DEFAULT_TEST_EXECUTION_MODE = TestExecMode.CLOUDERA.value


LOG = logging.getLogger(__name__)
CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
BASEDIR = None
PY3 = "python3"
BASH = "bash"
BASHX = "bash -x"
MAIL_ADDR_SNEMETH = "snemeth@cloudera.com"


class CommonDirs:
    CDSW_BASEDIR = FileUtils.join_path("home", "cdsw")
    SCRIPTS_BASEDIR = FileUtils.join_path(CDSW_BASEDIR, "scripts")
    JOBS_BASEDIR = os.path.join(CDSW_BASEDIR, "jobs")
    USER_DEV_ROOT = FileUtils.join_path("/", "Users", "snemeth", "development")
    MODULE_ROOT = None


class CommonFiles:
    MAIN_SCRIPT = None


class PythonModuleMode(Enum):
    USER = "user"
    GLOBAL = "global"


@dataclasses.dataclass
class CdswSetupResult:
    basedir: str
    output_basedir: str
    env_vars: Dict[str, str]
    module_root: str


class CdswSetup:
    @staticmethod
    def initial_setup(module_name: str, main_script_name: str, env_vars: Dict[str, str] = None):
        enable_handler_sanity_check = OsUtils.is_env_var_true(
            CdswEnvVar.ENABLE_LOGGER_HANDLER_SANITY_CHECK.value, default_val=True
        )

        ProjectUtils.set_root_determine_strategy(ProjectRootDeterminationStrategy.SYS_PATH, allow_overwrite=False)
        output_basedir = ProjectUtils.get_output_basedir(
            module_name, basedir=PROJECTS_BASEDIR, project_name_hint=module_name
        )
        logging_config: SimpleLoggingSetupConfig = SimpleLoggingSetup.init_logger(
            project_name=PROJECT_NAME,
            logger_name_prefix=module_name,
            execution_mode=ExecutionMode.PRODUCTION,
            console_debug=True,
            sanity_check_number_of_handlers=enable_handler_sanity_check,
        )
        LOG.info("Logging to files: %s", logging_config.log_file_paths)
        LOG.info(f"Python version info: {sys.version}")
        env_vars = CdswSetup._prepare_env_vars(env_vars)
        basedir = CdswSetup._determine_basedir()

        # This must happen before other operations as it sets: CommonDirs.MODULE_ROOT
        CdswSetup._setup_python_module_root_and_main_script_path(module_name, main_script_name)
        LOG.info("Using basedir for scripts: %s", basedir)
        LOG.debug("Common dirs after setup: %s", ObjUtils.get_class_members(CommonDirs))
        LOG.debug("Common files after setup: %s", ObjUtils.get_class_members(CommonFiles))
        return CdswSetupResult(basedir, output_basedir, env_vars, CommonDirs.MODULE_ROOT)

    @staticmethod
    def _determine_basedir():
        if CdswEnvVar.OVERRIDE_SCRIPT_BASEDIR.value in os.environ:
            basedir = OsUtils.get_env_value(CdswEnvVar.OVERRIDE_SCRIPT_BASEDIR.value)
        else:
            basedir = CommonDirs.SCRIPTS_BASEDIR
        return basedir

    @staticmethod
    def _prepare_env_vars(env_var_dict):
        if not env_var_dict:
            env_var_dict = {}
        for k, v in env_var_dict.items():
            OsUtils.set_env_value(k, v)
        return env_var_dict

    @staticmethod
    def _setup_python_module_root_and_main_script_path(module_name: str, main_script_name: str):
        python_site = CdswSetup.determine_python_site_dir()
        CommonDirs.MODULE_ROOT = FileUtils.join_path(python_site, module_name)
        CommonFiles.MAIN_SCRIPT = os.path.join(CommonDirs.MODULE_ROOT, main_script_name)

    @staticmethod
    def determine_python_site_dir():
        # For CDSW execution, user python module mode is preferred.
        # For test execution, it depends on how the initial-cdsw-setup.sh script was executed in the container.
        module_mode_env = OsUtils.get_env_value(CdswEnvVar.PYTHON_MODULE_MODE.value, PythonModuleMode.USER.value)
        python_module_mode = PythonModuleMode[module_mode_env.upper()]
        LOG.info("Using Python module mode: %s", python_module_mode.value)
        if python_module_mode == PythonModuleMode.GLOBAL:
            python_site = site.getsitepackages()[0]
            LOG.info("Using global python-site basedir: %s", python_site)
        elif python_module_mode == PythonModuleMode.USER:
            python_site = site.USER_SITE
            LOG.info("Using user python-site basedir: %s", python_site)
        else:
            raise ValueError("Invalid python module mode: {}".format(python_module_mode))
        return python_site


class CommonMailConfig:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 465
        self.account_user = OsUtils.get_env_value(CdswEnvVar.MAIL_ACC_USER.value)
        self.account_password = OsUtils.get_env_value(CdswEnvVar.MAIL_ACC_PASSWORD.value)

    def as_arguments(self):
        return (
            f'--smtp_server "{self.smtp_server}" '
            f"--smtp_port {self.smtp_port} "
            f'--account_user "{self.account_user}" '
            f'--account_password "{self.account_password}" '
        )


class GoogleDriveCdswHelper:
    def __init__(self, module_name: str):
        self.authorizer = self.create_authorizer()
        session_settings = DriveApiWrapperSessionSettings(
            FileFindMode.JUST_UNTRASHED, DuplicateFileWriteResolutionMode.FAIL_FAST, enable_path_cache=True
        )
        self.drive_wrapper = DriveApiWrapper(self.authorizer, session_settings=session_settings)
        self.drive_command_data_basedir = FileUtils.join_path(
            PROJECTS_BASEDIR_NAME, module_name, CDSW_PROJECT, "command-data"
        )

    def upload(self, cmd_type_real_name: str, local_file_path: str, drive_filename: str) -> DriveApiFile:
        drive_path = FileUtils.join_path(self.drive_command_data_basedir, cmd_type_real_name, drive_filename)
        drive_api_file: DriveApiFile = self.drive_wrapper.upload_file(local_file_path, drive_path)
        return drive_api_file

    def create_authorizer(self):
        return GoogleApiAuthorizer(
            ServiceType.DRIVE,
            project_name=CDSW_PROJECT,
            secret_basedir=SECRET_PROJECTS_DIR,
            account_email="snemeth@cloudera.com",
            scopes=[DriveApiScope.DRIVE_PER_FILE_ACCESS.value],
        )
