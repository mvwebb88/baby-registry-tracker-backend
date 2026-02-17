import os
import jwt
import bcrypt
import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request

from db_helpers import get_db_connection

authentication_blueprint = Blueprint("authentication_blueprint", __name__)


@authentication_blueprint.route("/auth/sign-up", methods=["POST"])
def sign_up():
    connection = None
    cursor = None

    try:
        new_user_data = request.get_json() or {}
        username = (new_user_data.get("username") or "").strip()
        password = new_user_data.get("password") or ""

        if not username or not password:
            return jsonify({"err": "Username and password are required."}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT id FROM users WHERE username = %s;", (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            return jsonify({"err": "Username already taken"}), 400

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # ✅ IMPORTANT: your DB column is password_digest
        cursor.execute(
            """
            INSERT INTO users (username, password_digest)
            VALUES (%s, %s)
            RETURNING id, username;
            """,
            (username, hashed_password),
        )

        created_user = cursor.fetchone()
        connection.commit()

        payload = {"username": created_user["username"], "id": created_user["id"]}
        token = jwt.encode({"payload": payload}, os.getenv("JWT_SECRET"))

        return jsonify({"token": token}), 201

    except Exception as err:
        # Helpful for debugging during deployment
        return jsonify({"err": str(err)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@authentication_blueprint.route("/auth/sign-in", methods=["POST"])
def sign_in():
    connection = None
    cursor = None

    try:
        sign_in_data = request.get_json() or {}
        username = (sign_in_data.get("username") or "").strip()
        password = sign_in_data.get("password") or ""

        if not username or not password:
            return jsonify({"err": "Username and password are required."}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM users WHERE username = %s;", (username,))
        existing_user = cursor.fetchone()

        if existing_user is None:
            return jsonify({"err": "Invalid credentials."}), 401

        # ✅ IMPORTANT: your DB column is password_digest
        password_is_valid = bcrypt.checkpw(
            password.encode("utf-8"),
            existing_user["password_digest"].encode("utf-8"),
        )

        if not password_is_valid:
            return jsonify({"err": "Invalid credentials."}), 401

        payload = {"username": existing_user["username"], "id": existing_user["id"]}
        token = jwt.encode({"payload": payload}, os.getenv("JWT_SECRET"))

        return jsonify({"token": token}), 200

    except Exception as err:
        return jsonify({"err": str(err)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


