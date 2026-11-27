
import os
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from functools import wraps
from datetime import datetime
import sqlite3
from pathlib import Path
import uuid
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get(
    "TILEUP_SECRET_KEY",
    "tileup-development-secret-change-before-deployment"
)

CORS(app, supports_credentials=True)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Store the database in the backend folder
BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "tileup.db"



def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db_connection()

    # Table for club members
    connection.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            level TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for competition marks
    connection.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            marks REAL NOT NULL CHECK (marks >= 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id)
                REFERENCES players (player_id),
            UNIQUE (player_id, round_number)
        )
    """)

    # Table for administrators
    connection.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for administrator applications
    connection.execute("""
        CREATE TABLE IF NOT EXISTS admin_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reviewed_by) REFERENCES admins(id)
        )
    """)

    # Add account activation fields to existing admins table
    admin_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(admins)").fetchall()
    }

    if "setup_token_hash" not in admin_columns:
        connection.execute("""
            ALTER TABLE admins ADD COLUMN setup_token_hash TEXT
        """)

    if "setup_token_expires_at" not in admin_columns:
        connection.execute("""
            ALTER TABLE admins ADD COLUMN setup_token_expires_at TIMESTAMP
        """)
    # Table for club members
    connection.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            level TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for competition marks
    connection.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            marks REAL NOT NULL CHECK (marks >= 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id)
                REFERENCES players (player_id),
            UNIQUE (player_id, round_number)
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():
    return "TileUp Backend is running!"


@app.route("/api/status")
def status():
    return {
        "status": "success",
        "message": "TileUp API is working"
    }


# Register a new player
@app.route("/api/players", methods=["POST"])
def register_player():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "Please provide player details as JSON."
        }), 400

    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    level = data.get("level", "").strip()

    if not full_name or not email or not level:
        return jsonify({
            "error": "Full name, email, and level are required."
        }), 400

    # Generate a unique player ID
    player_id = "TU-" + uuid.uuid4().hex[:8].upper()

    connection = get_db_connection()

    try:
        connection.execute(
            """
            INSERT INTO players (player_id, full_name, email, level)
            VALUES (?, ?, ?, ?)
            """,
            (player_id, full_name, email, level)
        )

        connection.commit()

        return jsonify({
            "message": "Player registered successfully.",
            "player": {
                "player_id": player_id,
                "full_name": full_name,
                "email": email,
                "level": level
            }
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "This email is already registered."
        }), 409

    finally:
        connection.close()
# Retrieve all registered players
@app.route("/api/players", methods=["GET"])
def get_players():

    connection = get_db_connection()

    players = connection.execute("""
        SELECT *
        FROM players
        ORDER BY full_name ASC
    """).fetchall()

    connection.close()

    return jsonify({
        "total_players": len(players),
        "players": [dict(player) for player in players]
    }), 200
# Retrieve a registered player
@app.route("/api/players/<player_id>", methods=["GET"])
def get_player(player_id):

    connection = get_db_connection()

    player = connection.execute(
        "SELECT * FROM players WHERE player_id = ?",
        (player_id,)
    ).fetchone()

    connection.close()

    if not player:
        return jsonify({
            "error": "Player not found."
        }), 404

    return jsonify({
        "message": "Player retrieved successfully.",
        "player": dict(player)
    }), 200
# Retrieve a player's competition history
@app.route("/api/results/<player_id>", methods=["GET"])
def get_player_results(player_id):

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT round_number, marks, created_at
        FROM results
        WHERE player_id = ?
        ORDER BY round_number ASC
        """,
        (player_id,)
    ).fetchall()

    connection.close()

    return jsonify({
        "player_id": player_id,
        "total_rounds": len(results),
        "total_marks": sum(result["marks"] for result in results),
        "results": [dict(result) for result in results]
    }), 200
# Get the competition leaderboard
@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():

    connection = get_db_connection()

    leaderboard = connection.execute("""
        SELECT
            players.player_id,
            players.full_name,
            players.level,
            COALESCE(SUM(results.marks), 0) AS total_marks,
            COUNT(results.id) AS total_rounds
        FROM players
        LEFT JOIN results
            ON players.player_id = results.player_id
        GROUP BY players.player_id
        ORDER BY total_marks DESC, players.full_name ASC
    """).fetchall()

    connection.close()

    rankings = []

    for position, player in enumerate(leaderboard, start=1):
        rankings.append({
            "position": position,
            "player_id": player["player_id"],
            "full_name": player["full_name"],
            "level": player["level"],
            "total_marks": player["total_marks"],
            "total_rounds": player["total_rounds"]
        })

    return jsonify({
        "message": "Leaderboard retrieved successfully.",
        "total_players": len(rankings),
        "leaderboard": rankings
    }), 200
# Record competition marks
    # Record competition results
# Protect routes that require administrator login
def admin_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):

        admin_id = session.get("admin_id")

        if not admin_id:
            return jsonify({
                "error": "Please log in first."
            }), 401

        connection = get_db_connection()

        try:
            admin = connection.execute("""
                SELECT id, full_name, email, role, status
                FROM admins
                WHERE id = ?
            """, (admin_id,)).fetchone()

            if admin is None or admin["status"] != "approved":
                session.clear()

                return jsonify({
                    "error": "Your administrator account is not active."
                }), 403

            # Refresh administrator information in the session
            session["admin_name"] = admin["full_name"]
            session["admin_role"] = admin["role"]

        finally:
            connection.close()

        return function(*args, **kwargs)

    return decorated_function


# Protect routes that only the Super Admin can access
def super_admin_required(function):
    @wraps(function)
    @admin_required
    def decorated_function(*args, **kwargs):

        if session.get("admin_role") != "super_admin":
            return jsonify({
                "error": "Super Admin access required."
            }), 403

        return function(*args, **kwargs)

    return decorated_function

# Protect routes that only the Super Admin can access

# Update an existing player's details
@app.route("/api/players/<player_id>", methods=["PUT"])
@admin_required
def update_player(player_id):

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Please provide player details as JSON."
        }), 400

    connection = get_db_connection()

    try:
        player = connection.execute(
            "SELECT * FROM players WHERE player_id = ?",
            (player_id,)
        ).fetchone()

        if not player:
            return jsonify({
                "error": "Player not found."
            }), 404

        full_name = data.get("full_name", player["full_name"])
        email = data.get("email", player["email"])
        level = data.get("level", player["level"])

        if not all(isinstance(value, str) for value in
                   [full_name, email, level]):
            return jsonify({
                "error": "Player details must be text."
            }), 400

        full_name = full_name.strip()
        email = email.strip().lower()
        level = level.strip()

        if not full_name or not email or not level:
            return jsonify({
                "error": "Full name, email, and level are required."
            }), 400

        connection.execute("""
            UPDATE players
            SET full_name = ?, email = ?, level = ?
            WHERE player_id = ?
        """, (full_name, email, level, player_id))

        connection.commit()

        return jsonify({
            "message": "Player details updated successfully.",
            "player": {
                "player_id": player_id,
                "full_name": full_name,
                "email": email,
                "level": level
            }
        }), 200

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "This email is already registered."
        }), 409

    finally:
        connection.close()
# Delete a player and their competition history
@app.route("/api/players/<player_id>", methods=["DELETE"])
@admin_required
def delete_player(player_id):

    connection = get_db_connection()

    try:
        player = connection.execute(
            "SELECT * FROM players WHERE player_id = ?",
            (player_id,)
        ).fetchone()

        if not player:
            return jsonify({
                "error": "Player not found."
            }), 404

        connection.execute(
            "DELETE FROM results WHERE player_id = ?",
            (player_id,)
        )

        connection.execute(
            "DELETE FROM players WHERE player_id = ?",
            (player_id,)
        )

        connection.commit()

        return jsonify({
            "message": "Player and associated competition results deleted successfully.",
            "player_id": player_id
        }), 200

    except Exception:
        connection.rollback()
        return jsonify({
            "error": "Unable to delete player."
        }), 500

    finally:
        connection.close()
# Record competition results
@app.route("/api/results", methods=["POST"])
@admin_required
def add_result():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "Please provide JSON data."
        }), 400

    player_id = data.get("player_id")
    round_number = data.get("round_number")
    marks = data.get("marks")

    if not player_id or round_number is None or marks is None:
        return jsonify({
            "error": "Player ID, round number and marks are required."
        }), 400

    try:
        round_number = int(round_number)
        marks = float(marks)

        if round_number <= 0 or marks < 0:
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({
            "error": "Round number must be positive and marks cannot be negative."
        }), 400

    connection = get_db_connection()

    try:
        player = connection.execute(
            "SELECT * FROM players WHERE player_id = ?",
            (player_id,)
        ).fetchone()

        if not player:
            return jsonify({
                "error": "Player not found."
            }), 404

        connection.execute(
            """
            INSERT INTO results (player_id, round_number, marks)
            VALUES (?, ?, ?)
            """,
            (player_id, round_number, marks)
        )

        connection.commit()

        return jsonify({
            "message": "Competition marks recorded successfully.",
            "player_id": player_id,
            "round_number": round_number,
            "marks": marks
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "This player already has marks recorded for this round."
        }), 409

    finally:
        connection.close()
# Get individual competition results for administration
@app.route("/api/results", methods=["GET"])
@admin_required
def get_results():

    connection = get_db_connection()

    try:
        rows = connection.execute("""
            SELECT
                results.id,
                results.player_id,
                players.full_name,
                results.round_number,
                results.marks
            FROM results
            JOIN players
                ON results.player_id = players.player_id
            ORDER BY results.id DESC
        """).fetchall()

        result_list = []

        for row in rows:
            result_list.append({
                "id": row["id"],
                "player_id": row["player_id"],
                "full_name": row["full_name"],
                "round_number": row["round_number"],
                "marks": row["marks"]
            })

        return jsonify({"results": result_list}), 200

    finally:
        connection.close()
# Edit an existing competition result
@app.route("/api/results/<int:result_id>", methods=["PUT"])
@admin_required
def update_result(result_id):

    data = request.get_json(silent=True) or {}

    if "round_number" not in data or "marks" not in data:
        return jsonify({
            "error": "Round number and marks are required."
        }), 400

    try:
        round_number = int(data["round_number"])
        marks = float(data["marks"])

        if round_number <= 0 or marks < 0:
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({
            "error": "Round number must be positive and marks cannot be negative."
        }), 400

    connection = get_db_connection()

    try:
        result = connection.execute(
            "SELECT * FROM results WHERE id = ?",
            (result_id,)
        ).fetchone()

        if not result:
            return jsonify({
                "error": "Result not found."
            }), 404

        connection.execute("""
            UPDATE results
            SET round_number = ?, marks = ?
            WHERE id = ?
        """, (round_number, marks, result_id))

        connection.commit()

        return jsonify({
            "message": "Competition result updated successfully.",
            "result_id": result_id,
            "round_number": round_number,
            "marks": marks
        }), 200

    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({
            "error": "This player already has a result for that round."
        }), 409

    finally:
        connection.close()


# Delete an existing competition result
@app.route("/api/results/<int:result_id>", methods=["DELETE"])
@admin_required
def delete_result(result_id):

    connection = get_db_connection()

    try:
        result = connection.execute(
            "SELECT * FROM results WHERE id = ?",
            (result_id,)
        ).fetchone()

        if not result:
            return jsonify({
                "error": "Result not found."
            }), 404

        connection.execute(
            "DELETE FROM results WHERE id = ?",
            (result_id,)
        )

        connection.commit()

        return jsonify({
            "message": "Competition result deleted successfully.",
            "result_id": result_id
        }), 200

    finally:
        connection.close()

# Apply to become a TileUp administrator
@app.route("/api/admin/apply", methods=["POST"])
def apply_admin():
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    reason = data.get("reason", "").strip()

    if not full_name or not email or not reason:
        return jsonify({
            "error": "Name, email and reason are required."
        }), 400

    connection = get_db_connection()

    try:
        # Check if the email already belongs to an administrator
        existing_admin = connection.execute(
            "SELECT id FROM admins WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_admin:
            return jsonify({
                "error": "This email already has an administrator account."
            }), 409

        # Check for an existing pending application
        pending = connection.execute(
            """
            SELECT id FROM admin_applications
            WHERE email = ? AND status = 'pending'
            """,
            (email,)
        ).fetchone()

        if pending:
            return jsonify({
                "error": "You already have a pending application."
            }), 409

        connection.execute(
            """
            INSERT INTO admin_applications
            (full_name, email, reason)
            VALUES (?, ?, ?)
            """,
            (full_name, email, reason)
        )

        connection.commit()

        return jsonify({
            "message": "Administrator application submitted successfully. Awaiting approval."
        }), 201

    finally:
        connection.close()


# Protect routes that require administrator login
# Administrator login
@app.route("/api/admin/login", methods=["POST"])
def admin_login():

    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "error": "Email and password are required."
        }), 400

    connection = get_db_connection()

    try:
        admin = connection.execute(
            """
            SELECT * FROM admins
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if not admin or not check_password_hash(
            admin["password_hash"], password
        ):
            return jsonify({
                "error": "Invalid email or password."
            }), 401

        if admin["status"] != "approved":
            return jsonify({
                "error": "Your administrator account is not approved."
            }), 403

        session.clear()

        session["admin_id"] = admin["id"]
        session["admin_name"] = admin["full_name"]
        session["admin_role"] = admin["role"]

        return jsonify({
            "message": "Login successful.",
            "admin": {
                "id": admin["id"],
                "full_name": admin["full_name"],
                "email": admin["email"],
                "role": admin["role"]
            }
        }), 200

    finally:
        connection.close()


# Administrator logout
@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():

    session.clear()

    return jsonify({
        "message": "Logout successful."
    }), 200
# Activate a newly approved administrator account
@app.route("/api/admin/activate", methods=["POST"])
def activate_admin():

    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    setup_token = data.get("setup_token", "").strip()
    new_password = data.get("new_password", "")

    if not email or not setup_token or not new_password:
        return jsonify({
            "error": "Email, setup token and new password are required."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "error": "Password must contain at least 8 characters."
        }), 400

    connection = get_db_connection()

    try:
        admin = connection.execute("""
            SELECT id, status, setup_token_hash, setup_token_expires_at
            FROM admins
            WHERE email = ?
        """, (email,)).fetchone()

        if not admin:
            return jsonify({
                "error": "Administrator account not found."
            }), 404

        if admin["status"] != "pending":
            return jsonify({
                "error": "This administrator account is not awaiting activation."
            }), 400

        if not admin["setup_token_hash"] or not admin["setup_token_expires_at"]:
            return jsonify({
                "error": "No valid activation token was found."
            }), 400

        if admin["setup_token_expires_at"] < datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
            return jsonify({
                "error": "Activation token has expired. Contact the Super Admin."
            }), 400

        if not check_password_hash(
            admin["setup_token_hash"], setup_token
        ):
            return jsonify({
                "error": "Invalid activation token."
            }), 400

        connection.execute("""
            UPDATE admins
            SET password_hash = ?,
                status = 'approved',
                setup_token_hash = NULL,
                setup_token_expires_at = NULL
            WHERE id = ?
        """, (
            generate_password_hash(new_password),
            admin["id"]
        ))

        connection.commit()

        return jsonify({
            "message": "Administrator account activated successfully. You can now log in."
        }), 200

    finally:
        connection.close()
# View pending administrator applications
# View pending administrator applications
# View pending administrator applications
@app.route("/api/super-admin/applications", methods=["GET"])
@super_admin_required
def get_admin_applications():

    connection = get_db_connection()

    try:
        applications = connection.execute("""
            SELECT id, full_name, email, reason, status, created_at
            FROM admin_applications
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """).fetchall()

        return jsonify({
            "applications": [dict(application) for application in applications]
        }), 200

    finally:
        connection.close()


# Approve or reject an administrator application

# Approve or reject an administrator application
@app.route("/api/super-admin/applications/<int:application_id>", methods=["PUT"])
@super_admin_required
def review_admin_application(application_id):

    data = request.get_json(silent=True) or {}

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    decision = data.get("decision", "")

    if not isinstance(decision, str):
        return jsonify({"error": "Invalid decision."}), 400

    decision = decision.strip().lower()

    if decision not in ["approve", "reject"]:
        return jsonify({
            "error": "Decision must be approve or reject."
        }), 400

    connection = get_db_connection()

    try:
        # Prevent simultaneous approval requests
        connection.execute("BEGIN IMMEDIATE")

        application = connection.execute("""
            SELECT *
            FROM admin_applications
            WHERE id = ? AND status = 'pending'
        """, (application_id,)).fetchone()

        if not application:
            return jsonify({
                "error": "Pending application not found."
            }), 404

        if decision == "approve":

            existing_admin = connection.execute("""
                SELECT id FROM admins
                WHERE email = ?
            """, (application["email"],)).fetchone()

            if existing_admin:
                return jsonify({
                    "error": "An administrator account already exists for this email."
                }), 409

            # Generate secure activation token
            setup_token = secrets.token_urlsafe(32)

            setup_token_hash = generate_password_hash(setup_token)

            from datetime import timedelta

            expiry_time = (
                datetime.now() + timedelta(hours=24)
            ).strftime("%Y-%m-%d %H:%M:%S")

            # Create pending administrator account
            connection.execute("""
                INSERT INTO admins (
                    full_name,
                    email,
                    password_hash,
                    role,
                    status,
                    setup_token_hash,
                    setup_token_expires_at
                )
                VALUES (?, ?, ?, 'admin', 'pending', ?, ?)
            """, (
                application["full_name"],
                application["email"],
                generate_password_hash(secrets.token_urlsafe(32)),
                setup_token_hash,
                expiry_time
            ))

            new_status = "approved"

        else:
            new_status = "rejected"
            setup_token = None

        # Update application status
        connection.execute("""
            UPDATE admin_applications
            SET status = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
        """, (
            new_status,
            session["admin_id"],
            application_id
        ))

        connection.commit()

        if decision == "approve":
            return jsonify({
                "message": "Application approved successfully.",
                "activation": {
                    "email": application["email"],
                    "setup_token": setup_token,
                    "expires_in": "24 hours"
                }
            }), 200

        return jsonify({
            "message": "Application rejected successfully."
        }), 200

    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({
            "error": "A database conflict occurred. Please try again."
        }), 409

    except Exception:
        connection.rollback()
        app.logger.exception("Administrator application review failed")
        return jsonify({
            "error": "Unable to process the application."
        }), 500

    finally:
        connection.close()



if __name__ == "__main__":
    init_db()
    print("TileUp database initialized.")
    app.run(debug=True)