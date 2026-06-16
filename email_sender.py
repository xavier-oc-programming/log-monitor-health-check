import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from analyser import LogReport

logger = logging.getLogger(__name__)


def send_report(
    html_body: str,
    subject: str,
    config: dict
) -> bool:
    """
    Send the HTML report email via SMTP.

    Uses smtplib with STARTTLS (port 587). Reads SMTP credentials
    from config (which has already loaded them from environment
    variables in config_loader.py).

    # smtplib with STARTTLS is the standard approach for sending
    # authenticated email from a script. The connection is unencrypted
    # until STARTTLS upgrades it — after that all traffic including
    # credentials is encrypted. Never use plain port 25 in production.

    Builds a MIMEMultipart('alternative') message with:
      - Plain text fallback (stripped version of the report)
      - HTML part as the primary body

    # MIMEMultipart('alternative') tells email clients to show the HTML
    # version if they support it, and fall back to plain text if not.
    # This is the correct MIME type for HTML emails — not 'mixed'.

    Logs success or failure to stdout.
    Returns True if sent successfully, False otherwise.
    Does not raise exceptions — a failed email send should not crash
    the script, it should log the error and exit cleanly.
    """
    smtp_cfg  = config['smtp']
    email_cfg = config['email']

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = email_cfg['from']
    msg['To']      = ', '.join(email_cfg['to'])

    plain_text = _build_plain_text_fallback_from_html(html_body)
    msg.attach(MIMEText(plain_text, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(smtp_cfg['host'], smtp_cfg['port']) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_cfg['username'], smtp_cfg['password'])
            server.sendmail(
                smtp_cfg['username'],
                email_cfg['to'],
                msg.as_string(),
            )
        print(f"Report sent to {', '.join(email_cfg['to'])}")
        return True
    except Exception as exc:
        print(f"Failed to send report: {exc}")
        return False


def _build_plain_text_fallback(report: LogReport) -> str:
    """
    Build a plain text version of the report for email clients
    that do not render HTML.
    """
    lines = [
        f"LOG HEALTH REPORT — {report.generated_at}",
        f"Status: {report.status}",
        f"Entries: {report.total_entries} over {report.hours_analysed}h",
        f"Error rate: {report.error_rate_pct}%",
        f"Spikes: {report.spike_count}",
        "",
        "TOP ERRORS:",
    ]

    for i, err in enumerate(report.top_errors, 1):
        lines.append(f"  {i}. {err['message_prefix']} ({err['count']})")

    lines.append("")
    lines.append("RECOMMENDATIONS:")
    for rec in report.recommendations:
        lines.append(f"  - {rec}")

    return '\n'.join(lines)


def _build_plain_text_fallback_from_html(html_body: str) -> str:
    import re
    text = re.sub(r'<[^>]+>', ' ', html_body)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
