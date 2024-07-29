from cdswjoblauncher.cdsw.cdsw_common import ReportFile

config = {
    "job_name": "Reviewsync",
    "command_type": "reviewsync",
    "mandatory_env_vars": ["GSHEET_CLIENT_SECRET", "GSHEET_SPREADSHEET", "MAIL_ACC_USER"],
    "optional_env_vars": ["BRANCHES", "GSHEET_JIRA_COLUMN"],
    "main_script_arguments": [],
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
