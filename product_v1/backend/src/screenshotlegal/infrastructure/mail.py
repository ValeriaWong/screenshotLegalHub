"""SMTP delivery for registration codes; account verification owns code validity."""
import smtplib
import ssl
from email.headerregistry import Address
from email.message import EmailMessage
from screenshotlegal.settings import Settings


class MailUnavailable(RuntimeError):
    pass


class MailDeliveryError(RuntimeError):
    pass


class RegistrationMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self):
        s = self.settings
        return bool(s.smtp_host and s.smtp_from and
                    bool(s.smtp_username) == bool(s.smtp_password.get_secret_value()))

    def send_code(self, recipient: str, code: str, expires_in_minutes: int):
        s = self.settings
        if not self.configured:
            raise MailUnavailable('尚未配置注册邮件服务，请联系管理员')
        message = EmailMessage()
        message['Subject'] = 'ScreenshotLegal 注册邮箱验证码'
        message['From'] = Address(display_name='ScreenshotLegal', addr_spec=s.smtp_from)
        message['To'] = Address(addr_spec=recipient)
        message.set_content(
            f'你的 ScreenshotLegal 注册验证码是：{code}\n\n'
            f'验证码将在 {expires_in_minutes} 分钟后失效，仅用于注册邮箱验证。\n'
            '如果你没有发起注册，请忽略此邮件。\n'
        )
        context = ssl.create_default_context()
        try:
            connection = (smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds, context=context)
                          if s.smtp_security == 'ssl'
                          else smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds))
            with connection as smtp:
                if s.smtp_security == 'starttls':
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if s.smtp_username:
                    smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
                refused = smtp.send_message(message, from_addr=s.smtp_from, to_addrs=[recipient])
                if refused:
                    raise MailDeliveryError('邮件服务未接受验证码，请稍后重试')
        except OSError:
            # Convert provider errors at the delivery boundary without exposing credentials.
            raise MailDeliveryError('验证码发送失败，请稍后重试或联系管理员') from None
