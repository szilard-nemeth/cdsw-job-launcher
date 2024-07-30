import logging
import os
from enum import Enum
from smtplib import SMTPAuthenticationError
from typing import List

from pythoncommons.email import EmailService, EmailMimeType, EmailAccount, EmailConfig
from pythoncommons.file_utils import FileUtils
from pythoncommons.os_utils import OsUtils
from pythoncommons.zip_utils import ZipFileUtils

LOG = logging.getLogger(__name__)


class SummaryFile(Enum):
    TXT = "summary.txt"
    HTML = "summary.html"


class EnvVar(Enum):
    IGNORE_SMTP_AUTH_ERROR = "IGNORE_SMTP_AUTH_ERROR"


# TODO cdsw-separation Exact copy from yarndevtools, unify later?
class FullEmailConfig:
    def __init__(self,
                 account_user: str,
                 account_password: str,
                 smtp_server: str,
                 smtp_port: int,
                 sender: str,
                 recipients: List[str],
                 subject=None,
                 attachment_file: str = None,
                 attachment_filename: str = None,
                 allow_empty_subject=False,
                 ):
        """

        :param account_user:
        :param account_password:
        :param smtp_server:
        :param smtp_port:
        :param sender:
        :param recipients:
        :param subject:
        :param attachment_file:
        :param attachment_filename: Override attachment filename
        :param allow_empty_subject:
        """
        mandatory_attrs = [
            ("account_user", "Email account user"),
            ("account_password", "Email account password"),
            ("smtp_server", "Email SMTP server"),
            ("smtp_port", "Email SMTP port"),
            ("sender", "Email sender"),
            ("recipients", "Email recipients"),
        ]
        all_attrs = []
        all_attrs.extend(mandatory_attrs)
        if not allow_empty_subject:
            all_attrs.append(("subject", "Email subject"))

        # TODO cdsw-separation Validate all params for non-emptiness!
        # ObjUtils.ensure_all_attrs_present(
        #     args,
        #     all_attrs,
        # )
        if not isinstance(recipients, list):
            raise ValueError("Email recipients should be a List[str]!")

        self.attachment_file = None
        if attachment_file:
            FileUtils.ensure_file_exists_and_readable(attachment_file)
            self.attachment_file = attachment_file
        self.attachment_filename = attachment_filename
        self.email_account: EmailAccount = EmailAccount(account_user, account_password)
        self.email_conf: EmailConfig = EmailConfig(smtp_server, smtp_port, self.email_account)
        self.sender: str = sender
        self.recipients = recipients
        self.subject = subject

    def __str__(self):
        return (
            f"SMTP server: {self.email_conf.smtp_server}\n"
            f"SMTP port: {self.email_conf.smtp_port}\n"
            f"Account user: {self.email_account.user}\n"
            f"Recipients: {self.recipients}\n"
            f"Sender: {self.sender}\n"
            f"Subject: {self.subject}\n"
            f"Attachment file: {self.attachment_file}\n"
        )


class SendLatestCommandDataInEmailConfig:
    def __init__(self,
                 email_conf: FullEmailConfig,
                 send_attachment=False,
                 email_body_file: str = SummaryFile.HTML.value,
                 prepend_email_body_with_text: str = None):
        """
        :param send_attachment: Send command data as email attachment
        :param prepend_email_body_with_text: Prepend the specified text to the email's body.
        :param email_body_file: The specified file from the latest command data zip will be added to the email body.
        """
        self.email: FullEmailConfig = email_conf
        self.email_body_file: str = email_body_file
        self.prepend_email_body_with_text: str = prepend_email_body_with_text
        self.send_attachment: bool = send_attachment

    def __str__(self):
        return (
            f"Email config: {self.email}\n"
            f"Email body file: {self.email_body_file}\n"
            f"Send attachment: {self.send_attachment}\n"
        )


class SendLatestCommandDataInEmail:
    def __init__(self, config):
        self.config = config

    def run(self):
        LOG.info(f"Starting sending latest command data in email.\n Config: {str(self.config)}")

        zip_extract_dest = FileUtils.join_path(os.sep, "tmp", "extracted_zip")
        ZipFileUtils.extract_zip_file(self.config.email.attachment_file, zip_extract_dest)

        # Pick file from zip that will be the email's body
        email_body_file = FileUtils.join_path(os.sep, zip_extract_dest, self.config.email_body_file)
        FileUtils.ensure_file_exists(email_body_file)
        email_body_contents: str = FileUtils.read_file(email_body_file)

        if self.config.prepend_email_body_with_text:
            LOG.debug("Prepending email body with: %s", self.config.prepend_email_body_with_text)
            email_body_contents = self.config.prepend_email_body_with_text + email_body_contents

        body_mimetype: EmailMimeType = self._determine_body_mimetype_by_attachment(email_body_file)
        email_service = EmailService(self.config.email.email_conf)
        kwargs = {
            "body_mimetype": body_mimetype,
        }

        if self.config.send_attachment:
            kwargs["attachment_file"] = self.config.email.attachment_file
            kwargs["override_attachment_filename"] = self.config.email.attachment_filename

        try:
            email_service.send_mail(
                self.config.email.sender,
                self.config.email.subject,
                email_body_contents,
                self.config.email.recipients,
                **kwargs,
            )
        except SMTPAuthenticationError as smtpe:
            ignore_smtp_auth_env: str = OsUtils.get_env_value(EnvVar.IGNORE_SMTP_AUTH_ERROR.value, "")
            LOG.info(f"Recognized env var '{EnvVar.IGNORE_SMTP_AUTH_ERROR.value}': {ignore_smtp_auth_env}")
            if not ignore_smtp_auth_env:
                raise smtpe
            else:
                # Swallow exception
                LOG.exception(
                    f"SMTP auth error occurred but env var " f"'{EnvVar.IGNORE_SMTP_AUTH_ERROR.value}' was set",
                    exc_info=True,
                )
        LOG.info("Finished sending email to recipients")

    @staticmethod
    def _determine_body_mimetype_by_attachment(email_body_file: str) -> EmailMimeType:
        if email_body_file.endswith(".html"):
            return EmailMimeType.HTML
        else:
            return EmailMimeType.PLAIN
