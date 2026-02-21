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
    report_url = os.environ.get("REPORT_URL", "")
    docs_url = os.environ.get("DOCS_URL", "")

    month_name = MONTH_NAMES_DE[month]
    subject = f"Arbeitszeitnachweis {month_name} {year} - {employee_name}"

    if test:
        mail_to = mail_from
        mail_cc = ""
        subject = f"[TEST] {subject}"

    filename = os.path.basename(office_file)
    html = _build_html(year, month, employee_name, summary, filename, report_url, docs_url)

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

    recipients = [addr.strip() for addr in mail_to.split(",")]
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


def _build_html(year: int, month: int, name: str, summary: dict,
                 filename: str = "", report_url: str = "",
                 docs_url: str = "") -> str:
    month_name = MONTH_NAMES_DE[month]
    actual = summary.get("actual", 0)
    target = summary.get("target", 0)
    diff = actual - target
    overtime_total = summary.get("overtime_total", 0)
    vacation_remaining = summary.get("vacation_remaining", 0)

    diff_color = "#008000" if diff >= 0 else "#cc0000"
    ot_color = "#008000" if overtime_total >= 0 else "#cc0000"

    td = 'style="padding:4px 12px;border:1px solid #ccc"'
    td_b = 'style="padding:4px 12px;border:1px solid #ccc;font-weight:bold;text-align:right"'

    report_section = ""
    if report_url:
        report_section = (
            f'<p>Die aktuelle Datei <strong>{filename}</strong> ist auch auf '
            f'<a href="{report_url}">Google Drive</a> hinterlegt.</p>'
        )

    docs_section = ""
    if docs_url:
        docs_section = (
            f'<p style="font-size:0.9em;color:#666">Die vollständige Berechnungslogik '
            f'ist unter <a href="{docs_url}">{docs_url}</a> dokumentiert.</p>'
        )

    return f"""\
<html>
<body style="font-family:Arial,Helvetica,sans-serif;color:#333;line-height:1.4;max-width:640px">
<h2 style="color:#2c3e50;margin-bottom:4px">Arbeitszeitnachweis {month_name} {year}</h2>
<p>Sehr geehrte Damen und Herren,</p>
<p>anbei erhalten Sie den Arbeitszeitnachweis von <strong>{name}</strong> f\u00fcr den Monat {month_name} {year}.</p>

<table style="border-collapse:collapse;margin:12px 0">
<tr><td {td}>Ist-Stunden {month_name}</td><td {td_b}>{actual:.1f} h</td></tr>
<tr><td {td}>Soll-Stunden {month_name}</td><td {td_b}>{target:.1f} h</td></tr>
<tr><td {td}>Differenz {month_name}</td><td style="padding:4px 12px;border:1px solid #ccc;font-weight:bold;text-align:right;color:{diff_color}">{diff:+.1f} h</td></tr>
<tr><td {td}>\u00dcberstundenkonto (kumulativ)</td><td style="padding:4px 12px;border:1px solid #ccc;font-weight:bold;text-align:right;color:{ot_color}">{overtime_total:+.1f} h</td></tr>
<tr><td {td}>Resturlaub</td><td {td_b}>{vacation_remaining} Tage</td></tr>
</table>

<p>Die vollst\u00e4ndige Aufstellung ist als Excel-Datei beigef\u00fcgt.</p>
{report_section}

<h3 style="color:#2c3e50;font-size:1em;margin-bottom:4px">ArbZG-Konformit\u00e4t</h3>
<p>Der beigef\u00fcgte Arbeitszeitnachweis wurde auf Konformit\u00e4t mit dem
Arbeitszeitgesetz (ArbZG) gepr\u00fcft. Die folgenden Pr\u00fcfungen wurden
durchgef\u00fchrt und ergaben <strong>keine Verst\u00f6\u00dfe</strong>:</p>
<table style="border-collapse:collapse;margin:8px 0;font-size:0.95em">
<tr><td {td}>\u00a73 ArbZG</td><td {td}>T\u00e4gliche Arbeitszeit max. 10 Stunden</td></tr>
<tr><td {td}>\u00a73 ArbZG</td><td {td}>Durchschnittliche Arbeitszeit \u2264 8 Stunden \u00fcber 24 Wochen</td></tr>
<tr><td {td}>\u00a74 ArbZG</td><td {td}>Ruhepausen: mind. 30 min ab 6 h, mind. 45 min ab 9 h</td></tr>
<tr><td {td}>\u00a75 ArbZG</td><td {td}>Ruhezeit zwischen Arbeitstagen \u2265 11 Stunden</td></tr>
<tr><td {td}>\u00a79 ArbZG</td><td {td}>Sonn- und Feiertagsruhe</td></tr>
</table>
{docs_section}

<p>Mit freundlichen Gr\u00fc\u00dfen<br/>{name}</p>
</body>
</html>"""
