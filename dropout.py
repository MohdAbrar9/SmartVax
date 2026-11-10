"""
dropout.py
----------
Dropout Prevention engine for SmartVax.

A "dropout" is a child who starts the vaccination schedule and then stops
coming back. This module scores every child's dropout risk (0-100) so the
ASHA worker can visit / call the children who need it MOST, before they
fall off the schedule, instead of working through a flat defaulter list.

How the score works (transparent, explainable weighted model):
    A. How long the worst overdue dose has been waiting ........ up to 40
    B. How many different visits were missed .................... up to 24
    C. History of late doses (given > 14 days after due) ........ up to 15
    D. Overdue but nobody from the health system has reached out  up to 10
    E. Share of doses already due that are still not given ...... up to 11
                                                         Total max = 100

    Score >= 60  -> HIGH risk      30-59 -> MEDIUM      < 30 -> LOW

Every score comes with plain-language REASONS and a recommended ACTION,
so a worker can see *why* a child is flagged. The weights are plain
numbers at the top of score_child(), easy to explain and easy to tune.
It is a rule-based model on purpose: with no historical dropout data to
train on, a transparent model is more trustworthy than a black box. When
real data exists, score_child() can be swapped for a trained model without
changing any page.
"""

from datetime import date

from db import run_query

LATE_DOSE_GRACE_DAYS = 14      # a dose given more than this many days late counts as "late"
CONTACT_WINDOW_DAYS = 14       # "recently contacted" = a worker message within this many days
HIGH_THRESHOLD = 60
MEDIUM_THRESHOLD = 30


def score_child(records, last_contact, today=None):
    """
    records      : list of dicts with 'due_date', 'completed_date', 'vaccine_name'
    last_contact : date/datetime of the last message an ASHA worker sent this
                   child's parent, or None if never
    Returns a dict: score, level, reasons, action, plus the raw counts.
    """
    today = today or date.today()

    overdue, late_given, completed, passed_due = [], 0, 0, 0
    for r in records:
        due = r["due_date"]
        done = r["completed_date"]
        if done is not None:
            completed += 1
            passed_due += 1
            if (done - due).days > LATE_DOSE_GRACE_DAYS:
                late_given += 1
        elif due < today:
            overdue.append(r)
            passed_due += 1

    max_days_overdue = max(((today - r["due_date"]).days for r in overdue), default=0)
    missed_visits = len({r["due_date"] for r in overdue})

    # --- A. severity of the longest wait ---
    if max_days_overdue == 0:
        a = 0
    elif max_days_overdue <= 14:
        a = 10
    elif max_days_overdue <= 30:
        a = 20
    elif max_days_overdue <= 60:
        a = 30
    else:
        a = 40
    # --- B. distinct visits missed ---
    b = min(missed_visits, 3) * 8
    # --- C. pattern of giving doses late ---
    c = min(late_given, 3) * 5
    # --- D. nobody has reached out ---
    contacted_recently = False
    if last_contact is not None:
        last_day = last_contact.date() if hasattr(last_contact, "date") else last_contact
        contacted_recently = (today - last_day).days <= CONTACT_WINDOW_DAYS
    d = 10 if (overdue and not contacted_recently) else 0
    # --- E. completion gap among doses already due ---
    e = round((1 - completed / passed_due) * 11) if passed_due else 0

    score = min(a + b + c + d + e, 100)
    level = "high" if score >= HIGH_THRESHOLD else "medium" if score >= MEDIUM_THRESHOLD else "low"

    reasons = []
    if overdue:
        n = len(overdue)
        reasons.append(f"{n} dose{'s' if n != 1 else ''} overdue (longest wait {max_days_overdue} days)")
    if missed_visits >= 2:
        reasons.append(f"{missed_visits} separate vaccination visits missed")
    if late_given:
        reasons.append(f"Earlier doses were given late {late_given} time{'s' if late_given != 1 else ''}")
    if overdue and not contacted_recently:
        reasons.append("No outreach from the health worker in the last "
                       f"{CONTACT_WINDOW_DAYS} days")
    if not reasons:
        reasons.append("On schedule. No warning signs.")

    # "Dropout" = already started the schedule, then stopped for 2+ months.
    dropped_out = completed > 0 and max_days_overdue > 60

    if level == "high":
        action = "Home visit within 48 hours and call the parent today."
    elif level == "medium":
        action = "Call or message the parent this week and fix a visit date."
    else:
        action = "Routine reminder. No special action needed."

    first_overdue = min(overdue, key=lambda r: r["due_date"]) if overdue else None
    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "action": action,
        "dropped_out": dropped_out,
        "overdue_count": len(overdue),
        "max_days_overdue": max_days_overdue,
        "completed_count": completed,
        "total_count": len(records),
        "next_overdue_vaccine": first_overdue["vaccine_name"] if first_overdue else None,
    }


def get_child_risks(region=None, parent_id=None, today=None):
    """
    Loads children (optionally only one region, or one parent's children),
    scores each, and returns them sorted with the highest risk first.
    """
    where, params = [], []
    if region is not None:
        where.append("c.region = %s")
        params.append(region)
    if parent_id is not None:
        where.append("c.parent_id = %s")
        params.append(parent_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = run_query(
        f"""SELECT c.child_id, c.full_name AS child_name, c.date_of_birth, c.region,
                   c.parent_id, u.full_name AS parent_name, u.phone AS parent_phone,
                   vr.due_date, vr.completed_date, vm.vaccine_name
            FROM children c
            JOIN users u ON c.parent_id = u.user_id
            LEFT JOIN vaccination_records vr ON vr.child_id = c.child_id
            LEFT JOIN vaccine_master vm ON vr.vaccine_id = vm.vaccine_id
            {where_sql}""",
        tuple(params), fetch=True,
    )

    contacts = run_query(
        """SELECT m.receiver_id, MAX(m.created_at) AS last_contact
           FROM messages m JOIN users s ON s.user_id = m.sender_id
           WHERE s.role = 'asha'
           GROUP BY m.receiver_id""",
        fetch=True,
    )
    last_contact_by_parent = {c["receiver_id"]: c["last_contact"] for c in contacts}

    children = {}
    for row in rows:
        child = children.setdefault(row["child_id"], {
            "child_id": row["child_id"], "child_name": row["child_name"],
            "date_of_birth": row["date_of_birth"], "region": row["region"],
            "parent_id": row["parent_id"], "parent_name": row["parent_name"],
            "parent_phone": row["parent_phone"], "records": [],
        })
        if row["due_date"] is not None:
            child["records"].append({
                "due_date": row["due_date"], "completed_date": row["completed_date"],
                "vaccine_name": row["vaccine_name"],
            })

    results = []
    for child in children.values():
        risk = score_child(child["records"], last_contact_by_parent.get(child["parent_id"]), today)
        child["last_contact"] = last_contact_by_parent.get(child["parent_id"])
        child.update(risk)
        del child["records"]
        results.append(child)

    results.sort(key=lambda c: (-c["score"], c["child_name"]))
    return results


def summarize(risks):
    """Counts per level, for stat cards and charts."""
    return {
        "high": sum(1 for r in risks if r["level"] == "high"),
        "medium": sum(1 for r in risks if r["level"] == "medium"),
        "low": sum(1 for r in risks if r["level"] == "low"),
        "dropped_out": sum(1 for r in risks if r["dropped_out"]),
        "total": len(risks),
    }


def reminder_text(child_name, parent_name, vaccine_name, days_overdue, worker_name):
    """Default message an ASHA worker can send (and edit) to a worried-about parent."""
    first = (parent_name or "").split(" ")[0] or "there"
    if vaccine_name and days_overdue > 0:
        body = (f"{child_name}'s {vaccine_name} dose is {days_overdue} days overdue. "
                "It is still not too late. Vaccines can be given late and will still protect your child.")
    else:
        body = f"{child_name}'s next vaccine is coming up soon."
    return (f"Hello {first}, this is {worker_name} (your ASHA worker). {body} "
            "When can I visit or can you come to the health centre this week? Reply here and we will fix a time.")
