"""
email_utils.py
--------------
Sends real emails to parents using SMTP (works with Gmail, Outlook, or
any SMTP provider — see .env.example for the settings you need).

Two things live here:
1. send_email()                -> low-level: sends any HTML email
2. send_vaccination_reminder()  -> builds the vaccine-reminder email and sends it

Design note: the email uses inline CSS and table-based layout because
that is what actually renders correctly across Gmail, Outlook, and
mobile mail apps — modern CSS (flexbox, external stylesheets) is
unreliable in email clients, so this is the professional approach,
not a step backward.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "SmartVax")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")

BRAND_COLOR = "#123B36"
ACCENT_COLOR = "#E2A33B"
DANGER_COLOR = "#C1533E"


def send_email(to_email, subject, html_body):
    """
    Sends one HTML email. Returns True if it went out, False if it
    failed for any reason (also prints the error so you can see why
    during development — e.g. wrong password, no internet).
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("[email_utils.py] SMTP not configured — skipping real send.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_USERNAME}>"
    message["To"] = to_email

    # Plain-text fallback for mail clients that don't render HTML.
    plain_text = "Please view this email in an HTML-capable mail client."
    message.attach(MIMEText(plain_text, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()  # encrypts the connection
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, to_email, message.as_string())
        return True
    except Exception as e:
        print(f"[email_utils.py] Failed to send email to {to_email}: {e}")
        return False


def build_reminder_email_html(parent_name, child_name, vaccine_name, due_date, status):
    """
    Builds the HTML for a vaccination reminder email.
    status is either "due" (upcoming) or "overdue".
    """
    is_overdue = status == "overdue"
    status_color = DANGER_COLOR if is_overdue else ACCENT_COLOR
    status_label = "OVERDUE" if is_overdue else "UPCOMING"
    headline = (
        f"{child_name}'s dose is overdue"
        if is_overdue
        else f"{child_name} has an upcoming vaccine"
    )
    due_date_str = due_date.strftime("%d %B %Y")

    return f"""
    <div style="font-family: Arial, sans-serif; background:#F3F7F4; padding:24px;">
      <div style="max-width:520px; margin:0 auto; background:#ffffff; border-radius:12px; overflow:hidden; border:1px solid #E2E9E4;">

        <!-- Header / logo -->
        <div style="background:{BRAND_COLOR}; padding:22px 28px;">
          <table cellpadding="0" cellspacing="0"><tr>
            <td style="background:{ACCENT_COLOR}; width:34px; height:34px; border-radius:8px; text-align:center; vertical-align:middle; font-size:18px; font-weight:bold; color:{BRAND_COLOR}; font-family:Georgia, serif;">+</td>
            <td style="padding-left:10px; color:#ffffff; font-family:Georgia, serif; font-size:16px; font-weight:bold;">SmartVax</td>
          </tr></table>
        </div>

        <!-- Body -->
        <div style="padding:28px;">
          <span style="display:inline-block; background:{status_color}22; color:{status_color}; font-size:11px; font-weight:bold; letter-spacing:0.05em; padding:4px 10px; border-radius:20px; text-transform:uppercase;">{status_label}</span>

          <h2 style="font-family:Georgia, serif; color:{BRAND_COLOR}; margin:14px 0 4px;">{headline}</h2>
          <p style="color:#5B6B66; font-size:14px; margin:0 0 20px;">Dear {parent_name},</p>

          <p style="font-size:14px; color:#16221F; line-height:1.6;">
            This is a reminder that <strong>{child_name}</strong>'s dose of
            <strong>{vaccine_name}</strong> was due on
            <strong>{due_date_str}</strong>.
            {"Please visit your nearest health center as soon as possible." if is_overdue else "Please plan a visit to your nearest health center around this date."}
          </p>

          <div style="text-align:center; margin:26px 0 10px;">
            <a href="{APP_BASE_URL}/dashboard" style="background:{BRAND_COLOR}; color:#ffffff; text-decoration:none; padding:12px 26px; border-radius:8px; font-size:14px; font-weight:bold; display:inline-block;">View Vaccine Timeline</a>
          </div>
        </div>

        <!-- Footer -->
        <div style="background:#F3F7F4; padding:16px 28px; text-align:center;">
          <p style="font-size:11px; color:#5B6B66; margin:0;">
            Sent automatically by SmartVax - AI based Vaccination Tracking and dropout prevention.<br>
            Please do not reply directly to this email.
          </p>
        </div>

      </div>
    </div>
    """


def send_vaccination_reminder(parent_email, parent_name, child_name, vaccine_name, due_date, status):
    """Convenience wrapper: builds the reminder email and sends it in one call."""
    is_overdue = status == "overdue"
    subject = (
        f"⚠ Overdue: {child_name}'s {vaccine_name} dose"
        if is_overdue
        else f"Reminder: {child_name}'s {vaccine_name} dose is coming up"
    )
    html_body = build_reminder_email_html(
        parent_name, child_name, vaccine_name, due_date, status
    )
    return send_email(parent_email, subject, html_body)
