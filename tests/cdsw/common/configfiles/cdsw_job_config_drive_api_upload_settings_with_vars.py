from cdswjoblauncher.cdsw.cdsw_common import ReportFile

config = {
    "job_name": "Reviewsync",
    "command_type": "reviewsync",
    "mandatory_env_vars": ["GSHEET_CLIENT_SECRET", "GSHEET_SPREADSHEET", "MAIL_ACC_USER"],
    "optional_env_vars": ["BRANCHES", "GSHEET_JIRA_COLUMN"],
    "main_script_arguments": ["--gsheet-client-secret"],
    "global_variables": {"testVar1": "v1", "testVar2": "v2", "testVar3": "v3", "testVar4": "v4"},
    "runs": [
        {
            "name": "dummy",
            "email_settings": {
                "enabled": False,
                "send_attachment": True,
                "email_body_file_from_command_data": ReportFile.SHORT_HTML.value,
                "attachment_file_name": lambda conf: f"attachmentFileName+{conf.var('testVar3')}+{conf.var('testVar4')}",
                "subject": lambda conf: f"testSubject+{conf.var('testVar2')}+{conf.var('testVar1')}",
                "sender": "testSender",
            },
            "drive_api_upload_settings": {
                "enabled": False,
                "file_name": lambda conf: f"constant1_{conf.var('testVar1')}_constant2_{conf.var('testVar3')}_constant3",
            },
            "variables": {},
            "main_script_arguments": [],
        }
    ],
}
