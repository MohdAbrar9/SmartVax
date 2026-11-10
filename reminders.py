"""
reminders.py
------------
The "Reminders" engine — this is what powers Email + in-app Push
notifications for parents about upcoming/overdue vaccines.

Two ways to use it:

1. From the Admin Portal — clicking "Send Reminder Emails Now" calls
   run_reminder_engine() directly (see app.py, route /admin/send-reminders).

2. As a scheduled job — run this file once a day with a cron job (or
   Windows Task Scheduler) so reminders go out automatically without
   an admin having to click a button:
       python3 reminders.py

It will never email the same parent about the same dose twice on the
same day — it checks email_logs first (see the NOT EXISTS clause).
"""

import os
from dotenv import load_dotenv
load_dotenv()

from db import run_query, refresh_overdue_statuses
from email_utils import send_vaccination_reminder

# How many days ahead counts as "upcoming" (vs waiting until overdue).
REMINDER_WINDOW_DAYS = 7


def find_children_needing_reminders():
    """
    Returns every (child, vaccine) pair that is either overdue, or due
    within REMINDER_WINDOW_DAYS, that has NOT already been emailed
    today for this exact dose.
    """
    query = """
        SELECT
            vr.record_id, vr.due_date, vr.status,
            vm.vaccine_name,
            c.child_id, c.full_name AS child_name,
            u.user_id AS parent_id, u.full_name AS parent_name, u.email AS parent_email
        FROM vaccination_records vr
        JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
        JOIN children c ON vr.child_id = c.child_id
        JOIN users u ON c.parent_id = u.user_id
        WHERE vr.status IN ('due', 'overdue')
          AND (vr.status = 'overdue' OR DATEDIFF(vr.due_date, CURDATE()) <= %s)
          AND NOT EXISTS (
              SELECT 1 FROM email_logs el
              WHERE el.child_id = c.child_id
                AND el.vaccine_name = vm.vaccine_name
                AND DATE(el.sent_at) = CURDATE()
          )
        ORDER BY vr.due_date ASC
    """
    return run_query(query, (REMINDER_WINDOW_DAYS,), fetch=True)


def create_notification(user_id, title, message):
    """Adds one row to the notifications table (the in-app 'push' feed)."""
    run_query(
        "INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s)",
        (user_id, title, message),
    )


def log_email(parent_id, child_id, vaccine_name, email_type, status):
    run_query(
        """INSERT INTO email_logs (parent_id, child_id, vaccine_name, email_type, status)
           VALUES (%s, %s, %s, %s, %s)""",
        (parent_id, child_id, vaccine_name, email_type, status),
    )


def run_reminder_engine():
    """
    Main entry point. Finds everyone who needs a reminder, emails them,
    logs the result, and drops a matching in-app notification.
    Returns the number of emails successfully sent.
    """
    refresh_overdue_statuses()  # make sure late doses are marked overdue first
    pending = find_children_needing_reminders()
    sent_count = 0

    for row in pending:
        email_type = "overdue" if row["status"] == "overdue" else "upcoming"

        success = send_vaccination_reminder(
            parent_email=row["parent_email"],
            parent_name=row["parent_name"],
            child_name=row["child_name"],
            vaccine_name=row["vaccine_name"],
            due_date=row["due_date"],
            status=row["status"],
        )

        log_email(
            parent_id=row["parent_id"],
            child_id=row["child_id"],
            vaccine_name=row["vaccine_name"],
            email_type=email_type,
            status="sent" if success else "failed",
        )

        # Always create the in-app notification, even if the email
        # failed (e.g. no internet) — the parent still sees it next
        # time they open the app. This is the "Push" channel.
        title = (
            f"{row['vaccine_name']} is overdue"
            if email_type == "overdue"
            else f"{row['vaccine_name']} is coming up"
        )
        message = (
            f"{row['child_name']}'s {row['vaccine_name']} dose was due on "
            f"{row['due_date'].strftime('%d %b %Y')}."
        )
        create_notification(row["parent_id"], title, message)

        if success:
            sent_count += 1

    return sent_count


if __name__ == "__main__":
    total_sent = run_reminder_engine()
    print(f"Reminder engine finished. Emails sent: {total_sent}")
