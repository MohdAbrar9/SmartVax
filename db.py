"""
db.py
------
Everything to do with talking to MySQL lives here, so the rest of the
app never has to write raw connection code. This is the ONLY file that
imports mysql.connector directly.
"""

import os
import mysql.connector
from mysql.connector import Error


def get_connection():
    """
    Opens and returns a new connection to the MySQL database.
    Settings are read from environment variables (see .env.example)
    so you never have to hard-code your password in the code.
    """
    try:
        connection = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "smart_vaccination"),
        )
        return connection
    except Error as e:
        print(f"[db.py] Could not connect to MySQL: {e}")
        raise


def run_query(query, params=None, fetch=False, fetch_one=False):
    """
    A single helper used everywhere in the app, so every route follows
    the same simple pattern instead of repeating connect/cursor/close
    code 20 times.

    - query      : the SQL string, with %s placeholders for safety
    - params     : tuple of values to safely insert into the query
    - fetch      : True  -> returns ALL matching rows (for SELECT ... many rows)
    - fetch_one  : True  -> returns ONE row only (for SELECT ... single row)

    If neither fetch flag is set, it's treated as an INSERT/UPDATE/DELETE
    and the new row's auto-increment id is returned instead.
    """
    connection = get_connection()
    # dictionary=True makes rows come back as {"column_name": value}
    # instead of plain tuples — much easier to work with in templates.
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, params or ())

        if fetch_one:
            result = cursor.fetchone()
        elif fetch:
            result = cursor.fetchall()
        else:
            connection.commit()
            result = cursor.lastrowid

        return result
    finally:
        cursor.close()
        connection.close()


def refresh_overdue_statuses():
    """
    A dose's status is stored in the database ('due' / 'overdue' / 'completed'),
    but time keeps passing. This flips any 'due' dose whose due date has gone
    by to 'overdue'. SmartVax calls it automatically (at most every 10 minutes)
    so dashboards, reminders and the Dropout Prevention scores stay correct.
    """
    run_query(
        "UPDATE vaccination_records SET status = 'overdue' "
        "WHERE status = 'due' AND due_date < CURDATE()"
    )
