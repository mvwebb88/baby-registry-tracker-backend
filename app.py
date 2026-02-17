from dotenv import load_dotenv
load_dotenv()

import os
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, g
from flask_cors import CORS

from auth_middleware import token_required
from auth_blueprint import authentication_blueprint
from items_blueprint import items_blueprint
from comments_blueprint import comments_blueprint

# ------------------------------------------------
# CREATE APP
# ------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------
# CORS
# - Allows local Vite dev servers
# - Allows Netlify production domain
# - Explicitly allows headers + methods so preflight (OPTIONS) succeeds
# ------------------------------------------------
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
                "https://babyregistry.netlify.app",
            ],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
    supports_credentials=True,
)

# ------------------------------------------------
# REGISTER BLUEPRINTS
# ------------------------------------------------
app.register_blueprint(authentication_blueprint)
app.register_blueprint(items_blueprint)
app.register_blueprint(comments_blueprint)

# ------------------------------------------------
# DB CONNECTION
# - Uses Heroku DATABASE_URL if present
# - Falls back to local env vars for development
# ------------------------------------------------
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    # Heroku / production
    if database_url:
        result = urlparse(database_url)
        return psycopg2.connect(
            host=result.hostname,
            database=result.path[1:],  # remove leading "/"
            user=result.username,
            password=result.password,
            port=result.port,
            sslmode="require",
        )

    # Local development
    return psycopg2.connect(
        host="localhost",
        database=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USERNAME"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

# ------------------------------------------------
# USERS ROUTES
# ------------------------------------------------
@app.route("/users", methods=["GET"])
@token_required
def users_index():
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT id, username FROM users;")
    users = cursor.fetchall()

    cursor.close()
    connection.close()
    return jsonify(users), 200


@app.route("/users/<user_id>", methods=["GET"])
@token_required
def users_show(user_id):
    if int(user_id) != g.user["id"]:
        return jsonify({"err": "Unauthorized"}), 403

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT id, username FROM users WHERE id = %s;", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user is None:
        return jsonify({"err": "User not found"}), 404

    return jsonify(user), 200


# ------------------------------------------------
# OPTIONAL: Simple health check (nice for deployments)
# ------------------------------------------------
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


# ------------------------------------------------
# RUN SERVER
# Heroku sets PORT automatically
# ------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)




