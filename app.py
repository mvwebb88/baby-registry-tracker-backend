from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, g
from flask_cors import CORS
import os
import psycopg2
import psycopg2.extras

from auth_middleware import token_required
from auth_blueprint import authentication_blueprint
from hoots_blueprint import hoots_blueprint
from comments_blueprint import comments_blueprint

app = Flask(__name__)

# ✅ CORS for Vite dev server(s). Your screenshot shows 127.0.0.1:5174,
# so we allow both 5173 and 5174 (and localhost + 127.0.0.1).
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]}},
    supports_credentials=True,
)

# ✅ Register blueprints
app.register_blueprint(authentication_blueprint)
app.register_blueprint(hoots_blueprint)
app.register_blueprint(comments_blueprint)


def get_db_connection():
    """Create and return a new DB connection."""
    return psycopg2.connect(
        host="localhost",
        database=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USERNAME"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


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
    # ✅ g is used by token_required middleware, so we must import g (done above)
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


# ✅ IMPORTANT: Use the Flask CLI (python -m flask run).
# Only run app.run() when executing this file directly.
if __name__ == "__main__":
    app.run(debug=True, port=5000)

