
config = {
    "job_name": "Reviewsync",
    "command_type": "reviewsync",
    "mandatory_env_vars": ["GSHEET_CLIENT_S"],
    "optional_env_vars": ["WRONG_VAR"],
    "runs": [{"name": "dummy", "variables": {}, "main_script_arguments": []}],
}
