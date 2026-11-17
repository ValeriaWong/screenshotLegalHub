import smtplib
import pytest
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.mail import RegistrationMailer, MailUnavailable, MailDeliveryError


def settings(**changes):
    values=dict(smtp_host='smtp.example.test', smtp_from='sender@example.test', smtp_port=587,
                smtp_username='sender@example.test', smtp_password='SYNTHETIC_SMTP_SECRET', smtp_security='starttls')
    return Settings(_env_file=None, **(values | changes))


def test_unconfigured_mail_does_not_attempt_delivery(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Unconfigured SMTP must not be contacted')
    monkeypatch.setattr(smtplib, 'SMTP', forbidden)
    monkeypatch.setattr(smtplib, 'SMTP_SSL', forbidden)
    mailer = RegistrationMailer(Settings(_env_file=None, smtp_host='', smtp_from='', smtp_username='', smtp_password=''))
    assert not mailer.configured
    with pytest.raises(MailUnavailable):
        mailer.send_code('person@example.test', '123456', 10)


@pytest.mark.parametrize('security', ['ssl', 'starttls'])
def test_verification_email_is_sent_over_verified_tls_before_credentials(monkeypatch, security):
    captured = {}
    class Connection:
        encrypted = security == 'ssl'
        def __init__(self, host, port, **kwargs):
            captured['host'] = host
            if security == 'ssl':
                assert kwargs['context'].check_hostname
                assert kwargs['context'].verify_mode != 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ehlo(self): pass
        def starttls(self, context):
            assert context.check_hostname and context.verify_mode != 0
            self.encrypted = True
        def login(self, username, password):
            assert self.encrypted
            assert password == 'SYNTHETIC_SMTP_SECRET'
        def send_message(self, message, from_addr, to_addrs):
            assert self.encrypted
            captured.update(message=message, recipient=to_addrs)
            return {}
    monkeypatch.setattr(smtplib, 'SMTP_SSL' if security == 'ssl' else 'SMTP', Connection)
    RegistrationMailer(settings(smtp_security=security)).send_code('person@example.test', '123456', 10)
    assert captured['recipient'] == ['person@example.test']
    body = captured['message'].get_content()
    assert '123456' in body and '10' in body
    assert 'SYNTHETIC_SMTP_SECRET' not in captured['message'].as_string()


def test_provider_failure_does_not_report_success_or_expose_secret(monkeypatch):
    def failure(*args, **kwargs):
        raise smtplib.SMTPAuthenticationError(535, b'SYNTHETIC_SMTP_SECRET')
    monkeypatch.setattr(smtplib, 'SMTP', failure)
    with pytest.raises(MailDeliveryError) as error:
        RegistrationMailer(settings()).send_code('person@example.test', '123456', 10)
    assert 'SYNTHETIC_SMTP_SECRET' not in str(error.value)


def test_half_configured_credentials_do_not_enable_mail():
    mailer = RegistrationMailer(Settings(_env_file=None, smtp_host='smtp.example.test',
                                smtp_from='sender@example.test', smtp_username='sender@example.test', smtp_password=''))
    assert not mailer.configured
