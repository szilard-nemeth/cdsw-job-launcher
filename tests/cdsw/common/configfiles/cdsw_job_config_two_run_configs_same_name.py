from cdswjoblauncher.cdsw.cdsw_common import ReportFile

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
    ],
    "global_variables": {
        "algorithm": "testAlgorithm",
        "commandDataFileName": lambda conf: f"command_data_{conf.var('algorithm')}_{conf.job_start_date()}.zip",
    },
    "runs": [
        {
            "name": "dummy1",
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
        },
        {
            "name": "dummy1",
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
        },
    ],
}
