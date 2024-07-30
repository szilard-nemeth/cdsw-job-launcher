import logging
import os
import time
from argparse import ArgumentParser
from enum import Enum
from typing import List, Tuple, Dict, Callable, Optional

from googleapiwrapper.google_drive import DriveApiFile
from pythoncommons.file_utils import FileUtils, FindResultType
from pythoncommons.os_utils import OsUtils
from pythoncommons.process import SubprocessCommandRunner

from cdswjoblauncher.cdsw.cdsw_common import CdswSetupResult, CdswSetup, CMD_LOG, GoogleDriveCdswHelper, BASHX, PY3, \
    CommonFiles, CommonMailConfig
from cdswjoblauncher.cdsw.cdsw_config import CdswJobConfig, CdswRun, CdswJobConfigReader
from cdswjoblauncher.cdsw.constants import CdswEnvVar, PROJECT_OUT_ROOT
from cdswjoblauncher.commands.send_latest_command_data_in_mail import SendLatestCommandDataInEmailConfig, \
    FullEmailConfig, SendLatestCommandDataInEmail
from cdswjoblauncher.commands.zip_latest_command_data import CommandDataZipperConfig, ZipLatestCommandData

LOG = logging.getLogger(__name__)


class ConfigMode(Enum):
    AUTO_DISCOVERY = ("DISCOVER_CONFIG_FILE", "auto_discovery")
    SPECIFIED_CONFIG_FILE = ("SPECIFIED_CONFIG_FILE", "specified_file_config")

    def __init__(self, value, cli_name):
        self.val = value
        self.cli_name = cli_name


class ArgParser:
    @staticmethod
    def parse_args():
        parser = ArgumentParser()
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            dest="verbose",
            default=None,
            required=False,
            help="More verbose log (including gitpython verbose logs)",
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            default=None,
            required=False,
            help="Turn on console debug level logs",
        )
        parser.add_argument(
            "--command-type-real-name",
            default=None,
            required=True,
            help="Command type: real name",
        )
        parser.add_argument(
            "--command-type-name",
            default=None,
            required=True,
            help="Command type: name",
        )
        parser.add_argument(
            "--command-type-session-based",
            action="store_true",
            default=None,
            required=True,
            help="Command type: session based",
        )
        parser.add_argument(
            "--command-type-zip-name",
            default=None,
            required=True,
            help="Command type: zip name",
        )

        parser.add_argument(
            "--command-type-valid-env-vars",
            nargs="+",
            type=str,
            required=True,
            help="List of valid env var names for command",
        )

        parser.add_argument('--env', action='append', help='Additional env vars', required=True)

        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help="Dry run",
        )
        parser.add_argument("--config-file", type=str, help="Full path to job config file (JSON format)")
        parser.add_argument("--config-dir", type=str, help="Full path to the directory of the configs")
        parser.add_argument("--default-email-recipients", type=str, help="Default mail recipients")

        parser.add_argument("--module-name", type=str, help="Name of the module to load for CDSW execution")
        parser.add_argument("--main-script-name", type=str, help="Name of the main script from the module to execute on CDSW")

        parser.add_argument("--job-preparation-callback", action="append", required=False)

        args = parser.parse_args()
        if args.verbose:
            print("Args: " + str(args))
        return args, parser


class CdswConfigReaderAdapter:
    def read_from_file(self, file: str, command_type_valid_env_vars: List[str], setup_result: CdswSetupResult):
        return CdswJobConfigReader.read_from_file(file, command_type_valid_env_vars, setup_result)


class CdswRunnerConfig:
    def __init__(
        self,
        parser,
        args,
        config_reader: CdswConfigReaderAdapter = None,
    ):
        self._validate_args(parser, args)
        self.command_type_real_name = args.command_type_real_name
        self.command_type_name = args.command_type_name
        self.command_type_session_based = args.command_type_session_based
        self.command_type_zip_name = args.command_type_zip_name
        self.command_type_valid_env_vars = args.command_type_valid_env_vars
        self.full_cmd: str = OsUtils.determine_full_command_filtered(filter_password=True)
        self.execution_mode = self.determine_execution_mode(args)
        self.job_config_file = self._determine_job_config_file_location(args)
        self.dry_run = args.dry_run
        self.config_reader = config_reader
        self.default_email_recipients = args.default_email_recipients
        self.envs: Dict[str, str] = self._parse_envs(args)
        self.job_preparation_callbacks: List[Callable] = self._parse_job_preparation_callbacks(args)
        self.module_name = args.module_name
        self.main_script_name = args.main_script_name

    def _determine_job_config_file_location(self, args):
        if self.execution_mode == ConfigMode.SPECIFIED_CONFIG_FILE:
            return args.config_file
        elif self.execution_mode == ConfigMode.AUTO_DISCOVERY:
            LOG.info("Trying to discover config file for command: %s", self.command_type_name)
            return self._discover_config_file()

    def _discover_config_file(self):
        file_paths = FileUtils.find_files(
            self.config_dir,
            find_type=FindResultType.FILES,
            regex=".*\\.py",
            single_level=True,
            full_path_result=True,
        )
        expected_filename = f"{self.command_type_real_name}_job_config.py"
        file_names = [os.path.basename(f) for f in file_paths]
        if expected_filename not in file_names:
            raise ValueError(
                "Auto-discovery failed for command '{}'. Expected file path: {}, Actual files found: {}".format(
                    self.command_type_name, expected_filename, file_paths
                )
            )
        return FileUtils.join_path(self.config_dir, expected_filename)

    def _validate_args(self, parser, args):
        self.config_file = self.config_dir = None
        if hasattr(args, "config_file") and args.config_file:
            self.config_file = args.config_file
        if hasattr(args, "config_dir") and args.config_dir:
            self.config_dir = args.config_dir

        if not self.config_file and not self.config_dir:
            parser.error("Either config file (--config-file) or config dir (--config-dir) need to be provided!")

    @staticmethod
    def determine_execution_mode(args):
        # If there's no --config-file specified, it means auto-discovery
        if not hasattr(args, "config_file") or not args.config_file:
            LOG.info("Config file not specified! Activated mode: %s", ConfigMode.AUTO_DISCOVERY)
            return ConfigMode.AUTO_DISCOVERY
        return ConfigMode.SPECIFIED_CONFIG_FILE

    def __str__(self):
        return f"Full command: {self.full_cmd}\n"

    @staticmethod
    def _parse_envs(args):
        d = {}
        if args.env:
            for env in args.env:
                if "=" not in env:
                    raise ValueError("Invalid env format! Expected format: <env-name>=<env-value>")
                split = env.split("=")
                d[split[0]] = split[1]
        return {}

    @staticmethod
    def _parse_job_preparation_callbacks(args):
        if not hasattr(args, "job_preparation_callback") or not args.job_preparation_callback:
            return []

        result = []
        callbacks = args.job_preparation_callback
        for c in callbacks:
            # TODO cdsw-separation try to load / convert to callable
            result.append(c)
        return result


class CdswRunner:
    def __init__(self, config: CdswRunnerConfig):
        self.executed_commands = []
        self.google_drive_uploads: List[
            Tuple[str, str, DriveApiFile]
        ] = []  # Tuple of: (command_type_real_name, drive_filename, drive_api_file)
        self.common_mail_config = CommonMailConfig()
        self._setup_google_drive(config.module_name)
        self.cdsw_runner_config = config
        self.dry_run = config.dry_run

        # Dynamic fields
        self.job_config = None
        self.output_basedir = None

    def _check_command_type(self):
        if self.cdsw_runner_config.command_type_name != self.job_config.command_type:
            raise ValueError(
                "Specified command line command type is different than job's command type. CLI: {}, Job definition: {}".format(
                    self.cdsw_runner_config.command_type_name, self.job_config.command_type
                )
            )
        return self.job_config.command_type

    def start(self):
        LOG.info("Starting CDSW runner...")
        self.setup_result: CdswSetupResult = CdswSetup.initial_setup(self.cdsw_runner_config.module_name,
                                                                self.cdsw_runner_config.main_script_name,
                                                                self.cdsw_runner_config.envs)
        LOG.info("Setup result: %s", self.setup_result)
        self.job_config: CdswJobConfig = self.cdsw_runner_config.config_reader.read_from_file(
            self.cdsw_runner_config.job_config_file,
            self.cdsw_runner_config.command_type_valid_env_vars,
            self.setup_result
        )
        self._check_command_type()
        self.output_basedir = self.setup_result.output_basedir
        LOG.info("Setup result: %s", self.setup_result)

        for callback in self.cdsw_runner_config.job_preparation_callbacks:
            LOG.info("Calling job preparation callback: %s", callback)
            callback(self, self.job_config, self.setup_result)

        for run in self.job_config.runs:
            self.execute_main_script(" ".join(run.main_script_arguments))
            if self.cdsw_runner_config.command_type_session_based:
                self.execute_command_data_zipper(self.cdsw_runner_config.command_type_name)
                drive_link_html_text = self._upload_command_data_to_google_drive_if_required(run)
                self._send_email_if_required(run, drive_link_html_text)

    def _upload_command_data_to_google_drive_if_required(self, run: CdswRun):
        if not self.is_drive_integration_enabled:
            LOG.info(
                "Google Drive integration is disabled with env var '%s'!",
                CdswEnvVar.ENABLE_GOOGLE_DRIVE_INTEGRATION.value,
            )
            return None
        if not run.drive_api_upload_settings:
            LOG.info("Google Drive upload settings is not defined for run: %s", run.name)
            return None
        if not run.drive_api_upload_settings.enabled:
            LOG.info("Google Drive upload is disabled for run: %s", run.name)
            return None

        drive_filename = run.drive_api_upload_settings.file_name
        if not self.dry_run:
            drive_api_file: DriveApiFile = self.upload_command_data_to_drive(drive_filename)
            self.google_drive_uploads.append((self.cdsw_runner_config.command_type_real_name, drive_filename, drive_api_file))
            return f'<a href="{drive_api_file.link}">Command data file: {drive_filename}</a>'
        else:
            LOG.info(
                "[DRY-RUN] Would upload file for command type '%s' to Google Drive with name '%s'",
                self.cdsw_runner_config.command_type_real_name,
                drive_filename,
            )
            return f'<a href="dummy_link">Command data file: {drive_filename}</a>'

    def _send_email_if_required(self, run: CdswRun, drive_link_html_text: Optional[str]):
        if not run.email_settings:
            LOG.info("Email settings is not defined for run: %s", run.name)
            return
        if not run.email_settings.enabled:
            LOG.info("Email sending is disabled for run: %s", run.name)
            return

        self.send_latest_command_data_in_email(
            sender=run.email_settings.sender,
            subject=run.email_settings.subject,
            attachment_filename=run.email_settings.attachment_file_name,
            email_body_file=run.email_settings.email_body_file_from_command_data,
            send_attachment=True,
            prepend_text_to_email_body=drive_link_html_text
        )

    def _setup_google_drive(self, module_name: str):
        if OsUtils.is_env_var_true(CdswEnvVar.ENABLE_GOOGLE_DRIVE_INTEGRATION.value, default_val=True):
            self.drive_cdsw_helper = GoogleDriveCdswHelper(module_name)
        else:
            self.drive_cdsw_helper = None

    def execute_script(self, script_name: str):
        script = os.path.join(self.setup_result.basedir, script_name)
        cmd = f"{BASHX} {script}"
        self._execute_command(cmd)

    def execute_main_script(self, script_args):
        cmd = f"{PY3} {CommonFiles.MAIN_SCRIPT} {script_args}"
        self._execute_command(cmd)

    def _execute_command(self, cmd):
        self.executed_commands.append(cmd)
        if self.dry_run:
            LOG.info("[DRY-RUN] Would run command: %s", cmd)
        else:
            SubprocessCommandRunner.run_and_follow_stdout_stderr(
                cmd, stdout_logger=CMD_LOG, exit_on_nonzero_exitcode=True
            )

    def execute_command_data_zipper(self, command_type_name: str):
        # TODO cdsw-separation Migrate ZIP_LATEST_COMMAND_DATA to this project from yarndevtools
        # TODO cdsw-separation All files to be zipped should be explicitly declared based on CommandType from yarndevtools
        #   ALL FILES SHOULD BE SPECIFIED VIA CLI
        # Log link name examples:
        # latest-log-unit_test_result_aggregator-INFO.log
        # latest-log-unit_test_result_aggregator-DEBUG.log

        # TODO cdsw-separation This is copied from CommandType.log_link_name --> Better way to specify?
        log_link_name = f"latest-log-{command_type_name}"

        # TODO cdsw-separation This is copied from CommandType.session_link_name --> Better way to specify?
        session_link_name = f"latest-session-{command_type_name}"

        input_files = [log_link_name + "*", session_link_name]
        # TODO cdsw-separation Check old code, when 'dest_filename' was overridden?
        config = CommandDataZipperConfig(dest_dir="/tmp",
                                         ignore_filetypes=["java js"],
                                         input_files=input_files,
                                         project_basedir=PROJECT_OUT_ROOT,
                                         cmd_type_real_name=command_type_name,
                                         dest_filename=None)
        command_data_zipper = ZipLatestCommandData(config)
        command_data_zipper.run()

    def upload_command_data_to_drive(self, drive_filename: str) -> DriveApiFile:
        full_file_path_of_cmd_data = FileUtils.join_path(self.output_basedir, self.cdsw_runner_config.command_type_zip_name)
        return self.drive_cdsw_helper.upload(self.cdsw_runner_config.command_type_real_name, full_file_path_of_cmd_data, drive_filename)

    def send_latest_command_data_in_email(
        self,
        sender: str,
        subject: str,
        recipients: Optional[List[str]] = None,
        attachment_filename: Optional[str] = None,
        email_body_file: Optional[str] = None,
        prepend_text_to_email_body: Optional[str] = None,
        send_attachment: bool = True,
    ):
        LOG.debug("Arguments for send_latest_command_data_in_email: %s", locals().keys())

        if not recipients:
            recipients = self.determine_recipients()

        email_conf: FullEmailConfig = FullEmailConfig(
            account_user=self.common_mail_config.account_user,
            account_password=self.common_mail_config.account_password,
            smtp_server=self.common_mail_config.smtp_server,
            smtp_port=self.common_mail_config.smtp_port,
            sender=sender,
            recipients=recipients,
            subject=subject,
            attachment_filename=attachment_filename
        )
        conf = SendLatestCommandDataInEmailConfig(email_conf,
                                                  send_attachment=send_attachment,
                                                  email_body_file=email_body_file,
                                                  prepend_email_body_with_text=prepend_text_to_email_body)
        send_email_cmd = SendLatestCommandDataInEmail(conf)
        send_email_cmd.run()

    def determine_recipients(self):
        recipients_env = OsUtils.get_env_value(CdswEnvVar.MAIL_RECIPIENTS.value)
        if recipients_env:
            return recipients_env
        return self.cdsw_runner_config.default_email_recipients

    @property
    def is_drive_integration_enabled(self):
        return self.drive_cdsw_helper is not None


def main():
    start_time = time.time()
    args, parser = ArgParser.parse_args()
    # TODO Temporarily removed
    # ProjectUtils.get_output_basedir(CDSW_PROJECT)
    # logging_config: SimpleLoggingSetupConfig = SimpleLoggingSetup.init_logger(
    #     project_name=CDSW_PROJECT,
    #     logger_name_prefix=CDSW_PROJECT,
    #     execution_mode=ExecutionMode.PRODUCTION,
    #     console_debug=args.logging_debug,
    #     postfix=args.cmd_type,
    #     verbose_git_log=args.verbose,
    # )
    # LOG.info("Logging to files: %s", logging_config.log_file_paths)
    config = CdswRunnerConfig(parser, args, CdswConfigReaderAdapter())
    cdsw_runner = CdswRunner(config)
    cdsw_runner.start()
    end_time = time.time()
    LOG.info("Execution of script took %d seconds", end_time - start_time)


if __name__ == "__main__":
    main()
