from cdswjoblauncher.cdsw.cdsw_common import ReportFile
from cdswjoblauncher.cdsw.cdsw_config import Include

config = {
    "job_name": "Reviewsync",
    "command_type": "reviewsync",
    "mandatory_env_vars": ["GSHEET_CLIENT_SECRET", "GSHEET_SPREADSHEET", "MAIL_ACC_USER"],
    "optional_env_vars": ["BRANCHES", "GSHEET_JIRA_COLUMN"],
    "main_script_arguments": [
        "--debug",
        "REVIEWSYNC",
        "--gsheet",
        lambda conf: f"--gsheet-client-secret {conf.env('GSHEET_CLIENT_SECRET')}",
        lambda conf: f"--gsheet-spreadsheet {conf.env('GSHEET_SPREADSHEET')}",
        lambda conf: f"--gsheet-jira-column {conf.env('GSHEET_JIRA_COLUMN')}",
        lambda conf: f"{Include.when(conf.var('omitJobSummary'), '--omit-job-summary', '')}",
        lambda conf: f"{Include.when(conf.var('downloadUncachedJobData'), '--download-uncached-job-data', '')}",
        lambda conf: f"{Include.when(conf.var('forceSendingMail'), '--force-sending-email', '')}",
        lambda conf: f"{Include.when(conf.var('useGoogleDriveCache'), '--cache-type google_drive', '')}",
    ],
    "global_variables": {
        "algorithm": "testAlgorithm",
        "commandDataFileName": lambda conf: f"command_data_{conf.var('algorithm')}_{conf.job_start_date()}.zip",
        "omitJobSummary": False,
        "downloadUncachedJobData": False,
        "useGoogleDriveCache": True,
        "forceSendingMail": True,
    },
    "runs": [
        {
            "name": "dummy",
            "email_settings": {
                "enabled": False,
                "send_attachment": True,
                "email_body_file_from_command_data": ReportFile.SHORT_HTML.value,
                "attachment_file_name": "attachment_file_name",
                "subject": "testSubject",
                "sender": "testSender",
            },
            "drive_api_upload_settings": {"enabled": False, "file_name": "simple"},
            "variables": {},
            "main_script_arguments": [],
        }
    ],
}
