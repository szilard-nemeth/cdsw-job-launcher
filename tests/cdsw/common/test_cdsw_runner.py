import argparse
import logging
import os
import random
import string
import tempfile
import unittest
from os.path import expanduser
from typing import List
from unittest.mock import patch, Mock, call as mock_call

from googleapiwrapper.google_drive import DriveApiFile
from pythoncommons.file_utils import FileUtils
from pythoncommons.os_utils import OsUtils
from pythoncommons.project_utils import ProjectUtils
from pythoncommons.string_utils import StringUtils

from cdswjoblauncher.cdsw.cdsw_common import CdswSetup, CommonFiles, GoogleDriveCdswHelper, CommonDirs
from cdswjoblauncher.cdsw.cdsw_config import CdswRun, EmailSettings, CdswJobConfig, DriveApiUploadSettings, \
    CdswJobConfigReader
from cdswjoblauncher.cdsw.cdsw_runner import CdswRunnerConfig, ConfigMode, CdswConfigReaderAdapter
from cdswjoblauncher.cdsw.constants import CdswEnvVar, PYTHON3, YarnDevToolsEnvVar

from cdswjoblauncher.cdsw.testutils.test_utils import FakeCdswRunner, FakeGoogleDriveCdswHelper, CommandExpectations, \
    CdswTestingCommons, Object, TEST_MODULE_NAME, TEST_MODULE_MAIN_SCRIPT_NAME

FAKE_CONFIG_FILE = "fake-config-file.py"
REVIEWSYNC_CONFIG_FILE_NAME = "reviewsync_job_config.py"

DEFAULT_COMMAND_TYPE = "reviewsync"
CDSW_CONFIG_READER_READ_METHOD_PATH = f"cdswjoblauncher.cdsw.cdsw_config.{CdswJobConfigReader.__name__}"
CDSW_RUNNER_DRIVE_CDSW_HELPER_UPLOAD_PATH = f"cdswjoblauncher.cdsw.cdsw_common.{GoogleDriveCdswHelper.__name__}.upload"
SUBPROCESSRUNNER_RUN_METHOD_PATH = "pythoncommons.process.SubprocessCommandRunner.run_and_follow_stdout_stderr"
DRIVE_API_WRAPPER_UPLOAD_PATH = "googleapiwrapper.google_drive.DriveApiWrapper.upload_file"
SEND_EMAIL_COMMAND_RUN_PATH = "cdswjoblauncher.commands.send_latest_command_data_in_mail.SendLatestCommandDataInEmail.run"
LOG = logging.getLogger(__name__)


class TestCdswRunner(unittest.TestCase):
    parser = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._setup_parser()
        OsUtils.clear_env_vars([CdswEnvVar.MAIL_RECIPIENTS.name])
        OsUtils.set_env_value(CdswEnvVar.MAIL_ACC_USER.value, "mailUser")
        OsUtils.set_env_value(CdswEnvVar.MAIL_ACC_PASSWORD.value, "mailPassword")

        # TODO Investigate this later to check why number of loggers are not correct
        OsUtils.set_env_value("ENABLE_LOGGER_HANDLER_SANITY_CHECK", "False")

        # We need the value of 'CommonFiles.MAIN_SCRIPT'
        CdswSetup._setup_python_module_root_and_main_script_path(TEST_MODULE_NAME, TEST_MODULE_MAIN_SCRIPT_NAME)
        cls.main_script_path = CommonFiles.MAIN_SCRIPT
        cls.fake_google_drive_cdsw_helper = FakeGoogleDriveCdswHelper(TEST_MODULE_NAME)

    def setUp(self) -> None:
        self.tmp_dir_name = None
        if CdswEnvVar.ENABLE_GOOGLE_DRIVE_INTEGRATION.value in os.environ:
            del os.environ[CdswEnvVar.ENABLE_GOOGLE_DRIVE_INTEGRATION.value]

    def tearDown(self) -> None:
        if self.tmp_dir_name:
            self.tmp_dir_name.cleanup()

    @classmethod
    def _setup_parser(cls):
        def parser_error_side_effect(message, **kwargs):
            raise Exception(message)

        cls.parser: argparse.ArgumentParser = Mock(spec=argparse.ArgumentParser)
        cls.parser.error.side_effect = parser_error_side_effect

    def _create_args_for_auto_discovery(self, dry_run: bool):
        args = Object()
        args.logging_debug = True
        args.verbose = True
        args.cmd_type = DEFAULT_COMMAND_TYPE
        args.dry_run = dry_run
        self.tmp_dir_name = tempfile.TemporaryDirectory()
        args.config_dir = self.tmp_dir_name.name
        reviewsync_config_file_path = FileUtils.join_path(self.tmp_dir_name.name, REVIEWSYNC_CONFIG_FILE_NAME)
        FileUtils.create_new_empty_file(reviewsync_config_file_path)
        return args, reviewsync_config_file_path

    @staticmethod
    def _create_args_for_specified_file(config_file: str, dry_run: bool, override_cmd_type: str = None):
        args = Object()
        args.module_name = TEST_MODULE_NAME
        args.main_script_name = TEST_MODULE_MAIN_SCRIPT_NAME
        args.config_file = config_file
        args.command_type_real_name = DEFAULT_COMMAND_TYPE
        args.command_type_name = DEFAULT_COMMAND_TYPE
        args.command_type_session_based = True
        args.command_type_zip_name = f"latest-command-data-zip-{DEFAULT_COMMAND_TYPE}"
        args.command_type_valid_env_vars = ["GSHEET_CLIENT_SECRET", "GSHEET_SPREADSHEET", "GSHEET_WORKSHEET",
                              "GSHEET_JIRA_COLUMN", "GSHEET_UPDATE_DATE_COLUMN", "GSHEET_STATUS_INFO_COLUMN",
                              "BRANCHES"]
        HADOOP_UPSTREAM_BASEDIR = FileUtils.join_path(CommonDirs.CDSW_BASEDIR, "repos", "apache", "hadoop")
        HADOOP_CLOUDERA_BASEDIR = FileUtils.join_path(CommonDirs.CDSW_BASEDIR, "repos", "cloudera", "hadoop")
        args.env = [f"{YarnDevToolsEnvVar.ENV_CLOUDERA_HADOOP_ROOT.value}={HADOOP_UPSTREAM_BASEDIR}",
                    f"{YarnDevToolsEnvVar.ENV_HADOOP_DEV_DIR.value}={HADOOP_CLOUDERA_BASEDIR}"]
        args.default_email_recipients = "snemeth@cloudera.com"
        args.logging_debug = True
        args.verbose = True
        if override_cmd_type:
            args.command_type_real_name = override_cmd_type
            args.command_type_name = override_cmd_type
        else:
            args.command_type_real_name = DEFAULT_COMMAND_TYPE
            args.command_type_name = DEFAULT_COMMAND_TYPE
        args.dry_run = dry_run
        return args

    def _create_cdsw_runner_with_mock_config(self, args, mock_job_config):
        mock_job_config_reader: CdswConfigReaderAdapter = Mock(spec=CdswConfigReaderAdapter)
        mock_job_config_reader.read_from_file.return_value = mock_job_config
        cdsw_runner_config = CdswRunnerConfig(self.parser, args, config_reader=mock_job_config_reader)
        cdsw_runner = FakeCdswRunner(cdsw_runner_config)
        cdsw_runner.drive_cdsw_helper = self.fake_google_drive_cdsw_helper
        return cdsw_runner

    @staticmethod
    def _create_mock_job_config(runs: List[CdswRun]):
        mock_job_config: CdswJobConfig = Mock(spec=CdswJobConfig)
        mock_job_config.command_type = DEFAULT_COMMAND_TYPE
        mock_job_config.runs = runs
        return mock_job_config

    @staticmethod
    def _create_mock_cdsw_run(
        name: str,
        email_enabled=False,
        google_drive_upload_enabled=False,
        add_email_settings: bool = True,
        add_google_drive_settings: bool = True,
    ):
        mock_run1: CdswRun = Mock(spec=CdswRun)
        mock_run1.name = name
        mock_run1.main_script_arguments = ["--arg1", "--arg2 bla", "--arg3 bla3"]

        mock_run1.email_settings = None
        mock_run1.drive_api_upload_settings = None
        if add_email_settings:
            mock_run1.email_settings = EmailSettings(
                enabled=email_enabled,
                send_attachment=True,
                attachment_file_name="test_attachment_filename.zip",
                email_body_file_from_command_data="test",
                subject="testSubject",
                sender="testSender",
            )
        if add_google_drive_settings:
            mock_run1.drive_api_upload_settings = DriveApiUploadSettings(
                enabled=google_drive_upload_enabled, file_name="testGoogleDriveApiFilename"
            )
        return mock_run1

    @staticmethod
    def create_mock_drive_api_file(file_link: str):
        mock_drive_file = Mock(spec=DriveApiFile)
        mock_drive_file.link = file_link
        return mock_drive_file

    def test_argument_parsing_into_config_auto_discovery(self):
        args, reviewsync_config_file_path = self._create_args_for_auto_discovery(dry_run=True)
        config = CdswRunnerConfig(self.parser, args)

        self.assertEqual(DEFAULT_COMMAND_TYPE, config.command_type_real_name)
        self.assertTrue(config.dry_run)
        self.assertEqual(ConfigMode.AUTO_DISCOVERY, config.execution_mode)
        self.assertEqual(reviewsync_config_file_path, config.job_config_file)

    def test_argument_parsing_into_config(self):
        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=True)
        config = CdswRunnerConfig(self.parser, args)

        self.assertEqual(DEFAULT_COMMAND_TYPE, config.command_type_real_name)
        self.assertTrue(config.dry_run)
        self.assertEqual(ConfigMode.SPECIFIED_CONFIG_FILE, config.execution_mode)
        self.assertEqual(FAKE_CONFIG_FILE, config.job_config_file)

    # TODO cdsw-separation
    @unittest.skip("Add this back when CdswRunnerConfig validates command type")
    def test_argument_parsing_into_config_invalid_command_type(self):
        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=True, override_cmd_type="WRONGCOMMAND")
        with self.assertRaises(ValueError) as ve:
            CdswRunnerConfig(self.parser, args)
        exc_msg = ve.exception.args[0]
        self.assertIn("Invalid command type specified", exc_msg)

    def test_execute_runs_single_run_with_fake_args(self):
        mock_run1 = self._create_mock_cdsw_run("run1", email_enabled=True, google_drive_upload_enabled=True)
        mock_job_config = self._create_mock_job_config([mock_run1])

        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=True)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        exp_command_1 = (
            CommandExpectations(self)
            .add_expected_ordered_arg("python3")
            .add_expected_ordered_arg(self.main_script_path)
            .add_expected_arg("--arg1")
            .add_expected_arg("--arg2", param="bla")
            .add_expected_arg("--arg3", param="bla3")
            .with_fake_command()
        )

        # TODO cdsw-separation Zip latest command data and send latest command data validation should be performed with mocking, not CLI command
        # exp_command_2 = (
        #     CommandExpectations(self)
        #     .add_expected_ordered_arg("python3")
        #     .add_expected_ordered_arg(self.main_script_path)
        #     .add_expected_ordered_arg("ZIP_LATEST_COMMAND_DATA")
        #     .add_expected_ordered_arg("REVIEWSYNC")
        #     .add_expected_arg("--debug")
        #     .add_expected_arg("--dest_dir", "/tmp")
        #     .add_expected_arg("--ignore-filetypes", "java js")
        #     .with_command_type("zip_latest_command_data")
        # )
        # wrap_d = StringUtils.wrap_to_quotes
        # wrap_s = StringUtils.wrap_to_single_quotes
        # expected_html_link = wrap_s('<a href="dummy_link">Command data file: testGoogleDriveApiFilename</a>')
        # exp_command_3 = (
        #     CommandExpectations(self)
        #     .add_expected_ordered_arg("python3")
        #     .add_expected_ordered_arg(self.main_script_path)
        #     .add_expected_ordered_arg("SEND_LATEST_COMMAND_DATA")
        #     .add_expected_arg("--debug")
        #     .add_expected_arg("--smtp_server", wrap_d("smtp.gmail.com"))
        #     .add_expected_arg("--smtp_port", "465")
        #     .add_expected_arg("--account_user", wrap_d("mailUser"))
        #     .add_expected_arg("--account_password", wrap_d("mailPassword"))
        #     .add_expected_arg("--subject", wrap_d("testSubject"))
        #     .add_expected_arg("--sender", wrap_d("testSender"))
        #     .add_expected_arg("--recipients", wrap_d("yarn_eng_bp@cloudera.com"))
        #     .add_expected_arg("--attachment-filename", "test_attachment_filename.zip")
        #     .add_expected_arg("--file-as-email-body-from-zip", "test")
        #     .add_expected_arg("--prepend_email_body_with_text", expected_html_link)
        #     .add_expected_arg("--send-attachment")
        #     .with_command_type("send_latest_command_data")
        # )

        expectations = [exp_command_1, ]
        CdswTestingCommons.verify_commands(self, expectations, cdsw_runner.executed_commands)

    @patch(SUBPROCESSRUNNER_RUN_METHOD_PATH)
    @patch(CDSW_RUNNER_DRIVE_CDSW_HELPER_UPLOAD_PATH)
    @patch(SEND_EMAIL_COMMAND_RUN_PATH)
    def test_execute_two_runs_with_fake_args(
        self,
        mock_send_email_command_run,
        mock_google_drive_cdsw_helper_upload,
        mock_subprocess_runner,
    ):
        mock_google_drive_cdsw_helper_upload.return_value = self.create_mock_drive_api_file(
            "http://googledrive/link-of-file-in-google-drive"
        )
        mock_run1 = self._create_mock_cdsw_run("run1", email_enabled=True, google_drive_upload_enabled=True)
        mock_run2 = self._create_mock_cdsw_run("run2", email_enabled=False, google_drive_upload_enabled=False)
        mock_job_config = self._create_mock_job_config([mock_run1, mock_run2])

        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=False)
        self.setup_side_effect_on_mock_subprocess_runner(mock_subprocess_runner)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        calls_of_main_script = mock_subprocess_runner.call_args_list
        calls_of_google_drive_uploader = mock_google_drive_cdsw_helper_upload.call_args_list

        self.assertIn(
            f"{PYTHON3} {self.main_script_path} --arg1 --arg2 bla --arg3 bla3",
            self._get_call_arguments_as_str(calls_of_main_script, 0),
        )
        # TODO cdsw-separation Zip latest command data and send latest command data validation should be performed with mocking, not CLI command
        # self.assertIn(
        #     f"{PYTHON3} {self.main_script_path} --debug ZIP_LATEST_COMMAND_DATA reviewsync",
        #     self._get_call_arguments_as_str(calls_of_main_script, 1),
        # )
        # TODO cdsw-separation Zip latest command data and send latest command data validation should be performed with mocking, not CLI command
        # self.assertIn(
        #     f"{PYTHON3} {self.main_script_path} --debug SEND_LATEST_COMMAND_DATA",
        #     self._get_call_arguments_as_str(calls_of_main_script, 2),
        # )
        self.assertEqual(
            calls_of_google_drive_uploader,
            [
                mock_call(
                    "reviewsync",
                    FileUtils.join_path(
                        expanduser("~"), "snemeth-dev-projects", TEST_MODULE_NAME, "latest-command-data-zip-reviewsync"
                    ),
                    "testGoogleDriveApiFilename",
                )
            ],
        )

        self.assertIn(
            f"{PYTHON3} {self.main_script_path} --arg1 --arg2 bla --arg3 bla3",
            self._get_call_arguments_as_str(calls_of_main_script, 1),
        )
        # TODO cdsw-separation Zip latest command data and send latest command data validation should be performed with mocking, not CLI command
        # self.assertIn(
        #     f"{PYTHON3} {self.main_script_path} --debug ZIP_LATEST_COMMAND_DATA reviewsync",
        #     self._get_call_arguments_as_str(calls_of_main_script, 4),
        # )

        # Assert there are no more calls
        self.assertTrue(
            len(calls_of_main_script) == 2,
            msg="Unexpected calls of main script: {}. First 5 calls are okay.".format(calls_of_main_script),
        )
        self.assertTrue(
            len(calls_of_google_drive_uploader) == 1,
            msg="Unexpected calls of Google Drive uploader: {}. First call is okay.".format(
                calls_of_google_drive_uploader
            ),
        )

    @staticmethod
    def _get_call_arguments_as_str(mock, index):
        return " ".join(list(mock[index][0]))

    @staticmethod
    def _get_call_arguments_as_list(mock, index):
        return list(mock[index][0])

    @patch(SUBPROCESSRUNNER_RUN_METHOD_PATH)
    @patch(CDSW_RUNNER_DRIVE_CDSW_HELPER_UPLOAD_PATH)
    def test_google_drive_settings_are_not_defined(
        self,
        mock_google_drive_cdsw_helper_upload,
        mock_subprocess_runner,
    ):
        mock_run1 = self._create_mock_cdsw_run(
            "run1",
            email_enabled=True,
            google_drive_upload_enabled=True,
            add_email_settings=False,
            add_google_drive_settings=False,
        )
        mock_run2 = self._create_mock_cdsw_run(
            "run2",
            email_enabled=True,
            google_drive_upload_enabled=True,
            add_email_settings=False,
            add_google_drive_settings=False,
        )
        mock_job_config = self._create_mock_job_config([mock_run1, mock_run2])

        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=False)
        self.setup_side_effect_on_mock_subprocess_runner(mock_subprocess_runner)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        calls_of_main_script = mock_subprocess_runner.call_args_list
        calls_of_google_drive_uploader = mock_google_drive_cdsw_helper_upload.call_args_list

        self.assertTrue(
            len(calls_of_google_drive_uploader) == 0,
            msg="Unexpected calls to Google Drive uploader: {}".format(calls_of_google_drive_uploader),
        )
        # TODO cdsw-separation Zip latest command data and send latest command data validation should be performed with mocking, not CLI command
        # CdswTestingCommons.assert_no_calls_with_arg(self, calls_of_main_script, "SEND_LATEST_COMMAND_DATA")

    @patch(SUBPROCESSRUNNER_RUN_METHOD_PATH)
    @patch(CDSW_RUNNER_DRIVE_CDSW_HELPER_UPLOAD_PATH)
    def test_google_drive_settings_and_email_settings_are_defined_but_disabled(
        self, mock_google_drive_cdsw_helper_upload, mock_subprocess_runner
    ):
        mock_google_drive_cdsw_helper_upload.return_value = self.create_mock_drive_api_file(
            "http://googledrive/link-of-file-in-google-drive"
        )

        mock_run1 = self._create_mock_cdsw_run(
            "run1",
            email_enabled=False,
            google_drive_upload_enabled=False,
            add_email_settings=True,
            add_google_drive_settings=True,
        )
        mock_run2 = self._create_mock_cdsw_run(
            "run2",
            email_enabled=False,
            google_drive_upload_enabled=False,
            add_email_settings=True,
            add_google_drive_settings=True,
        )
        mock_job_config = self._create_mock_job_config([mock_run1, mock_run2])

        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=False)
        self.setup_side_effect_on_mock_subprocess_runner(mock_subprocess_runner)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        calls_of_main_script = mock_subprocess_runner.call_args_list
        calls_of_google_drive_uploader = mock_google_drive_cdsw_helper_upload.call_args_list

        self.assertTrue(
            len(calls_of_google_drive_uploader) == 0,
            msg="Unexpected calls to Google Drive uploader: {}".format(calls_of_google_drive_uploader),
        )
        # TODO cdsw-separation Zip latest command data and send latest command data validation should be performed with mocking, not CLI command
        # CdswTestingCommons.assert_no_calls_with_arg(self, calls_of_main_script, "SEND_LATEST_COMMAND_DATA")

    @patch(SUBPROCESSRUNNER_RUN_METHOD_PATH)
    @patch(CDSW_RUNNER_DRIVE_CDSW_HELPER_UPLOAD_PATH)
    def test_dry_run_does_not_invoke_anything(self, mock_google_drive_cdsw_helper_upload, mock_subprocess_runner):
        mock_run1 = self._create_mock_cdsw_run(
            "run1",
            email_enabled=True,
            google_drive_upload_enabled=True,
            add_email_settings=False,
            add_google_drive_settings=False,
        )
        mock_run2 = self._create_mock_cdsw_run(
            "run2",
            email_enabled=True,
            google_drive_upload_enabled=True,
            add_email_settings=False,
            add_google_drive_settings=False,
        )
        mock_job_config = self._create_mock_job_config([mock_run1, mock_run2])
        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=True)
        self.setup_side_effect_on_mock_subprocess_runner(mock_subprocess_runner)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        calls_of_main_script = mock_subprocess_runner.call_args_list
        calls_of_google_drive_uploader = mock_google_drive_cdsw_helper_upload.call_args_list

        self.assertTrue(
            len(calls_of_google_drive_uploader) == 0,
            msg="Unexpected calls to Google Drive uploader: {}".format(calls_of_google_drive_uploader),
        )
        self.assertTrue(
            len(calls_of_main_script) == 0,
            msg="Unexpected calls to main script: {}".format(calls_of_main_script),
        )

    @patch(CDSW_RUNNER_DRIVE_CDSW_HELPER_UPLOAD_PATH)
    def test_execute_google_drive_is_disabled_by_env_var(self, mock_google_drive_cdsw_helper_upload):
        mock_google_drive_cdsw_helper_upload.return_value = self.create_mock_drive_api_file(
            "http://googledrive/link-of-file-in-google-drive"
        )

        OsUtils.set_env_value(CdswEnvVar.ENABLE_GOOGLE_DRIVE_INTEGRATION.value, False)
        mock_run1 = self._create_mock_cdsw_run(
            "run1", email_enabled=True, google_drive_upload_enabled=True, add_google_drive_settings=True
        )
        mock_job_config = self._create_mock_job_config([mock_run1])

        # Need to enable dry-run to not fail the whole script
        # But it's hard to differentiate if dry-run or the ENABLE_GOOGLE_DRIVE_INTEGRATION env var disabled the file upload to Google Drive
        # So an additional check is added for the google_drive_uploads
        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=True)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        calls_of_google_drive_uploader = mock_google_drive_cdsw_helper_upload.call_args_list
        self.assertTrue(
            len(calls_of_google_drive_uploader) == 0,
            msg="Unexpected calls to Google Drive uploader: {}".format(calls_of_google_drive_uploader),
        )
        self.assertEqual([], cdsw_runner.google_drive_uploads)

    @patch(SUBPROCESSRUNNER_RUN_METHOD_PATH)
    @patch(DRIVE_API_WRAPPER_UPLOAD_PATH)
    @patch(SEND_EMAIL_COMMAND_RUN_PATH)
    def test_upload_command_data_to_drive(self,
                                          mock_send_email_command_run,
                                          mock_drive_api_wrapper_upload,
                                          mock_subprocess_runner):
        mock_drive_api_wrapper_upload.return_value = self.create_mock_drive_api_file("testLink")
        mock_run1 = self._create_mock_cdsw_run(
            "run1", email_enabled=True, google_drive_upload_enabled=True, add_google_drive_settings=True
        )
        mock_job_config = self._create_mock_job_config([mock_run1])

        args = self._create_args_for_specified_file(FAKE_CONFIG_FILE, dry_run=False)
        cdsw_runner = self._create_cdsw_runner_with_mock_config(args, mock_job_config)
        cdsw_runner.start()

        calls_of_google_drive_uploader = mock_drive_api_wrapper_upload.call_args_list
        self.assertTrue(
            len(calls_of_google_drive_uploader) == 1,
            msg="Unexpected calls to Google Drive uploader: {}".format(calls_of_google_drive_uploader),
        )
        expected_local_file_name = FileUtils.join_path(
            ProjectUtils.get_output_basedir(TEST_MODULE_NAME), "latest-command-data-zip-reviewsync"
        )
        expected_google_drive_file_name = FileUtils.join_path(
            cdsw_runner.drive_cdsw_helper.drive_command_data_basedir, "reviewsync", "testGoogleDriveApiFilename"
        )

        call = self._get_call_arguments_as_list(calls_of_google_drive_uploader, 0)
        self.assertEqual(expected_local_file_name, call[0])
        self.assertEqual(expected_google_drive_file_name, call[1])

    # TODO Add TC: send_latest_command_data_in_email, various testcases
    # TODO Add TC: unknown command type
    @staticmethod
    def setup_side_effect_on_mock_subprocess_runner(mock_subprocess_runner):
        def side_effect(cmd, **kwargs):
            print("Side effect for Mock subprocess runner is started")

            # Set up latest session dir
            output_dir = ProjectUtils.get_output_child_dir("reviewsync", project_name_hint=TEST_MODULE_NAME)
            session_dir = ProjectUtils.get_session_dir_under_child_dir(FileUtils.basename(output_dir))
            project_out_root = ProjectUtils.get_output_basedir(
                TEST_MODULE_NAME, project_name_hint=TEST_MODULE_NAME
            )
            FileUtils.create_symlink_path_dir(
                "latest-session-reviewsync",
                session_dir,
                project_out_root,
            )

            # Set up log link
            gibberish = ''.join(random.choices(string.ascii_uppercase + string.digits, k=200))
            tmp_file_name = FileUtils.write_to_tempfile(gibberish)
            log_level_name = logging.getLevelName(logging.INFO)
            link_name = f"latest-log-reviewsync-{log_level_name}"
            FileUtils.create_symlink_path_dir(link_name, tmp_file_name, project_out_root)

        mock_subprocess_runner.side_effect = side_effect

