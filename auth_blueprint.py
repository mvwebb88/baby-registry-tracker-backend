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
    try:
        new_user_data = request.get_json()

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Check if username already exists
        cursor.execute(
            "SELECT id FROM users WHERE username = %s;",
            (new_user_data["username"],),
        )
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            connection.close()
            return jsonify({"err": "Username already taken"}), 400

        # Hash password
        hashed_password = bcrypt.hashpw(
            new_user_data["password"].encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        # ✅ Insert into password_digest (NOT password)
        cursor.execute(
            "INSERT INTO users (username, password_digest) VALUES (%s, %s) RETURNING id, username;",
            (new_user_data["username"], hashed_password),
        )
        created_user = cursor.fetchone()

        connection.commit()
        cursor.close()
        connection.close()

        payload = {"username": created_user["username"], "id": created_user["id"]}
        token = jwt.encode({"payload": payload}, os.getenv("JWT_SECRET"))

        return jsonify({"token": token}), 201

    except Exception as err:
        return jsonify({"err": str(err)}), 401


@authentication_blueprint.route("/auth/sign-in", methods=["POST"])
def sign_in():
    connection = None
    try:
        sign_in_form_data = request.get_json()

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "SELECT * FROM users WHERE username = %s;",
            (sign_in_form_data["username"],),
        )
        existing_user = cursor.fetchone()

        if existing_user is None:
            cursor.close()
            return jsonify({"err": "Invalid credentials."}), 401

        # ✅ Compare against password_digest (NOT password)
        password_is_valid = bcrypt.checkpw(
            sign_in_form_data["password"].encode("utf-8"),
            existing_user["password_digest"].encode("utf-8"),
        )

        if not password_is_valid:
            cursor.close()
            return jsonify({"err": "Invalid credentials."}), 401

        payload = {"username": existing_user["username"], "id": existing_user["id"]}
        token = jwt.encode({"payload": payload}, os.getenv("JWT_SECRET"))

        cursor.close()
        return jsonify({"token": token}), 200

    except Exception as err:
        return jsonify({"err": str(err)}), 500
    finally:
        if connection:
            connection.close()

