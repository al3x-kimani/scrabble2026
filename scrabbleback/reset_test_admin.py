import sqlite3
from pathlib import Path
from getpass import getpass
from werkzeug.security import generate_password_hash

db_path = Path(__file__).resolve().parent / "tileup.db"
email = "tileuptest@example.com"

connection = sqlite3.connect(db_path)
connection.row_factory = sqlite3.Row

admin = connection.execute(
    "SELECT id, email, status FROM admins WHERE email = ?",
    (email,)
).fetchone()

if not admin:
    print("Test administrator account was not found.")
elif admin["status"] != "approved":
    print("Account is not approved. Current status:", admin["status"])
else:
    password = getpass("Enter a new password (at least 8 characters): ")
    confirm = getpass("Confirm the new password: ")

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
    elif password != confirm:
        print("Passwords do not match.")
    else:
        connection.execute(
            "UPDATE admins SET password_hash = ? WHERE email = ?",
            (generate_password_hash(password), email)
        )
        connection.commit()
        print("Test administrator password reset successfully.")

connection.close()
