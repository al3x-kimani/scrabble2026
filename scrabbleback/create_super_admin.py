from getpass import getpass
import sqlite3
from werkzeug.security import generate_password_hash

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "tileup.db"

print("=== TileUp Super Admin Setup ===")

full_name = input("Enter your full name: ").strip()
email = input("Enter your email: ").strip().lower()
password = getpass("Create your password: ")

if not full_name or not email or not password:
    print("All fields are required.")
    exit()

if len(password) < 8:
    print("Password must be at least 8 characters.")
    exit()

connection = sqlite3.connect(DB_PATH)

# Check whether a Super Admin already exists
existing = connection.execute(
    "SELECT id FROM admins WHERE role = 'super_admin'"
).fetchone()

if existing:
    print("A Super Admin already exists. Setup is blocked.")
    connection.close()
    exit()

# Check whether this email already exists
existing_email = connection.execute(
    "SELECT id FROM admins WHERE email = ?", (email,)
).fetchone()

if existing_email:
    print("This email already exists.")
    connection.close()
    exit()

password_hash = generate_password_hash(password)

connection.execute(
    """
    INSERT INTO admins (full_name, email, password_hash, role, status)
    VALUES (?, ?, ?, 'super_admin', 'approved')
    """,
    (full_name, email, password_hash)
)

connection.commit()
connection.close()

print("\nSuper Admin successfully created!")
print("You can now use this account to manage TileUp.")