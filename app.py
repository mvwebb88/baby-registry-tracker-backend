from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, g
from flask_cors import CORS
import os
import psycopg2
import psycopg2.extras

from auth_middleware import token_required
from auth_blueprint import authentication_blueprint
from items_blueprint import items_blueprint
from comments_blueprint import comments_blueprint

# ------------------------------------------------
# CREATE APP FIRST
# ------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------
# CORS (Vite dev servers)
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
            ]
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
# ------------------------------------------------
def get_db_connection():
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
# RUN SERVER
# ------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)


