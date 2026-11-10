"""
create_admin.py
----------------
Run this ONCE to create your first Admin Portal login.
(The public /register page only ever creates 'parent' accounts —
this is deliberate, so random visitors can never make themselves an
admin. Admins are created here, from the server, by you.)

Usage:
    python3 create_admin.py
"""

from getpass import getpass
from dotenv import load_dotenv
load_dotenv()

from werkzeug.security import generate_password_hash
from db import run_query


def main():
    print("=== Create Admin Account ===")
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip()
    phone = input("Phone: ").strip()
    password = getpass("Password: ")

    existing = run_query("SELECT user_id FROM users WHERE email = %s", (email,), fetch_one=True)
    if existing:
        print(f"A user with email '{email}' already exists. Aborting.")
        return

    password_hash = generate_password_hash(password)
    run_query(
        """INSERT INTO users (full_name, email, password_hash, phone, role)
           VALUES (%s, %s, %s, %s, 'admin')""",
        (full_name, email, password_hash, phone),
    )
    print(f"Admin account created for {email}. Log in at /login.")


if __name__ == "__main__":
    main()
