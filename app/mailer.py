"""
Email sender for monthly overtime reports via SMTP (Gmail).
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date


MONTH_NAMES_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def send_monthly_report(
    year: int,
    month: int,
    office_file: str,
    summary: dict,
    test: bool = False,
) -> bool:
    """Send monthly report email with Excel attachment."""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    mail_from = os.environ.get("MAIL_FROM", smtp_user)
    mail_to = os.environ["MAIL_TO"]
    mail_cc = os.environ.get("MAIL_CC", "")
    employee_name = os.environ.get("EMPLOYEE_NAME", "Mitarbeiter")

    month_name = MONTH_NAMES_DE[month]
    subject = f"Arbeitszeitnachweis {month_name} {year} - {employee_name}"

    if test:
        mail_to = mail_from
        mail_cc = ""
        subject = f"[TEST] {subject}"

    html = _build_html(year, month, employee_name, summary)

    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = mail_to
    if mail_cc:
        msg["Cc"] = mail_cc
    msg["Subject"] = subject

    msg.attach(MIMEText(html, "html"))

    # Attach Excel
    if os.path.exists(office_file):
        with open(office_file, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(office_file)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    recipients = [mail_to]
    if mail_cc:
        recipients.extend(addr.strip() for addr in mail_cc.split(","))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(mail_from, recipients, msg.as_string())
        print(f"Email sent to {mail_to}" + (f" (CC: {mail_cc})" if mail_cc else ""))
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def _build_html(year: int, month: int, name: str, summary: dict) -> str:
    month_name = MONTH_NAMES_DE[month]
    actual = summary.get("actual", 0)
    target = summary.get("target", 0)
    diff = actual - target
    overtime_total = summary.get("overtime_total", 0)
    vacation_remaining = summary.get("vacation_remaining", 0)

    diff_color = "#008000" if diff >= 0 else "#FF0000"
    sign = "+" if diff >= 0 else ""

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Arbeitszeitnachweis {month_name} {year}</h2>
        <p>Hallo,</p>
        <p>anbei der Arbeitszeitnachweis für <strong>{name}</strong> für {month_name} {year}.</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 8px 16px; border: 1px solid #ddd;">Ist-Stunden {month_name}:</td>
                <td style="padding: 8px 16px; border: 1px solid #ddd; font-weight: bold;">{actual:.1f}h</td>
            </tr>
            <tr>
                <td style="padding: 8px 16px; border: 1px solid #ddd;">Soll-Stunden {month_name}:</td>
                <td style="padding: 8px 16px; border: 1px solid #ddd; font-weight: bold;">{target:.1f}h</td>
            </tr>
            <tr>
                <td style="padding: 8px 16px; border: 1px solid #ddd;">Differenz:</td>
                <td style="padding: 8px 16px; border: 1px solid #ddd; font-weight: bold; color: {diff_color};">{sign}{diff:.1f}h</td>
            </tr>
            <tr>
                <td style="padding: 8px 16px; border: 1px solid #ddd;">Überstundenkonto Gesamt:</td>
                <td style="padding: 8px 16px; border: 1px solid #ddd; font-weight: bold;">{overtime_total:+.1f}h</td>
            </tr>
            <tr>
                <td style="padding: 8px 16px; border: 1px solid #ddd;">Resturlaub:</td>
                <td style="padding: 8px 16px; border: 1px solid #ddd; font-weight: bold;">{vacation_remaining} Tage</td>
            </tr>
        </table>

        <p>Die vollständige Aufstellung ist als Excel-Datei angehängt.</p>
        <p>Mit freundlichen Grüßen<br/>{name}</p>
    </body>
    </html>
    """
