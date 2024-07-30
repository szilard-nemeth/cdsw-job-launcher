# TODO Add default value of all env vars to enum
# TODO Move all EnvVar classes to commands?
from enum import Enum
from os.path import expanduser

from pythoncommons.file_utils import FileUtils
from pythoncommons.project_utils import ProjectUtils

PROJECT_MODULE_NAME = "cdswjoblauncher"

SECRET_PROJECTS_DIR = FileUtils.join_path(expanduser("~"), ".secret", "projects", "cloudera")
PYTHON3 = "python3"
PROJECT_NAME = "cdsw-job-launcher"

PROJECT_OUT_ROOT = ProjectUtils.get_output_basedir(
    PROJECT_MODULE_NAME, project_name_hint=PROJECT_MODULE_NAME
)


# TODO cdsw-separation Move yarndevtools specific stuff from here
class YarnDevToolsEnvVar(Enum):
    PROJECT_DETERMINATION_STRATEGY = "PROJECT_DETERMINATION_STRATEGY"
    ENV_CLOUDERA_HADOOP_ROOT = "CLOUDERA_HADOOP_ROOT"
    ENV_HADOOP_DEV_DIR = "HADOOP_DEV_DIR"


# TODO cdsw-separation Move yarndevtools specific stuff from here
class CdswEnvVar(Enum):
    MAIL_ACC_PASSWORD = "MAIL_ACC_PASSWORD"
    MAIL_ACC_USER = "MAIL_ACC_USER"
    MAIL_RECIPIENTS = "MAIL_RECIPIENTS"
    # TODO Consider moving these to UnitTestResultFetcherEnvVar
    JENKINS_USER = "JENKINS_USER"
    JENKINS_PASSWORD = "JENKINS_PASSWORD"
    CLOUDERA_HADOOP_ROOT = YarnDevToolsEnvVar.ENV_CLOUDERA_HADOOP_ROOT.value
    HADOOP_DEV_DIR = YarnDevToolsEnvVar.ENV_HADOOP_DEV_DIR.value
    PYTHONPATH = "PYTHONPATH"
    TEST_EXECUTION_MODE = "TEST_EXEC_MODE"
    PYTHON_MODULE_MODE = "PYTHON_MODULE_MODE"
    ENABLE_GOOGLE_DRIVE_INTEGRATION = "ENABLE_GOOGLE_DRIVE_INTEGRATION"
    INSTALL_REQUIREMENTS = "INSTALL_REQUIREMENTS"
    RESTART_PROCESS_WHEN_REQUIREMENTS_INSTALLED = "RESTART_PROCESS_WHEN_REQUIREMENTS_INSTALLED"
    DEBUG_ENABLED = "DEBUG_ENABLED"
    OVERRIDE_SCRIPT_BASEDIR = "OVERRIDE_SCRIPT_BASEDIR"
    ENABLE_LOGGER_HANDLER_SANITY_CHECK = "ENABLE_LOGGER_HANDLER_SANITY_CHECK"
