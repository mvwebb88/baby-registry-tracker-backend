from flask import Blueprint, jsonify, request, g
import psycopg2.extras
from datetime import datetime

from auth_middleware import token_required
from db_helpers import get_db_connection, consolidate_comments_in_hoots

hoots_blueprint = Blueprint("hoots_blueprint", __name__)

# ============================================================
# NOTE
# - Supports JSON now (same as the example).
# - Also supports FormData later (for image uploads).
# - DB columns we are using (based on your DB):
#     hoots: id, title, content, user_id, created_at
#     comments: id, text, hoot_id, user_id, created_at
# ============================================================


# -------------------------
# CREATE HOOT (JSON or FormData)
# -------------------------
@hoots_blueprint.route("/hoots", methods=["POST"])
@token_required
def create_hoot():
    try:
        # If you're sending FormData, request.is_json will be False.
        if request.is_json:
            data = request.get_json(silent=True) or {}
            title = data.get("title")
            content = data.get("content")
        else:
            # FormData (later, for images)
            title = request.form.get("title")
            content = request.form.get("content")

        if not title or not content:
            return jsonify({"error": "title and content are required"}), 400

        user_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            INSERT INTO hoots (title, content, user_id, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (title, content, user_id, datetime.utcnow()),
        )
        hoot_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u.username AS author_username
            FROM hoots h
            JOIN users u ON h.user_id = u.id
            WHERE h.id = %s;
            """,
            (hoot_id,),
        )
        created_hoot = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(created_hoot), 201

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# LIST HOOTS (+ COMMENTS)
# -------------------------
@hoots_blueprint.route("/hoots", methods=["GET"])
def hoots_index():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u_hoot.username AS author_username,

              c.id AS comment_id,
              c.text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username

            FROM hoots h
            JOIN users u_hoot ON h.user_id = u_hoot.id
            LEFT JOIN comments c ON h.id = c.hoot_id
            LEFT JOIN users u_comment ON c.user_id = u_comment.id
            ORDER BY h.created_at DESC, c.created_at ASC;
            """
        )

        hoots = cursor.fetchall()
        consolidated_hoots = consolidate_comments_in_hoots(hoots)

        connection.close()
        return jsonify(consolidated_hoots), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# SHOW ONE HOOT
# -------------------------
@hoots_blueprint.route("/hoots/<hoot_id>", methods=["GET"])
def show_hoot(hoot_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u_hoot.username AS author_username,

              c.id AS comment_id,
              c.text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username

            FROM hoots h
            JOIN users u_hoot ON h.user_id = u_hoot.id
            LEFT JOIN comments c ON h.id = c.hoot_id
            LEFT JOIN users u_comment ON c.user_id = u_comment.id
            WHERE h.id = %s
            ORDER BY c.created_at ASC;
            """,
            (hoot_id,),
        )

        rows = cursor.fetchall()
        connection.close()

        if not rows:
            return jsonify({"error": "Hoot not found"}), 404

        processed_hoot = consolidate_comments_in_hoots(rows)[0]
        return jsonify(processed_hoot), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# UPDATE HOOT (JSON)
# -------------------------
@hoots_blueprint.route("/hoots/<hoot_id>", methods=["PUT"])
@token_required
def update_hoot(hoot_id):
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        content = data.get("content")

        if not title or not content:
            return jsonify({"error": "title and content are required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM hoots WHERE id = %s;", (hoot_id,))
        hoot = cursor.fetchone()

        if hoot is None:
            connection.close()
            return jsonify({"error": "Hoot not found"}), 404

        if hoot["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute(
            """
            UPDATE hoots
            SET title = %s, content = %s
            WHERE id = %s
            RETURNING id;
            """,
            (title, content, hoot_id),
        )
        updated_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u.username AS author_username
            FROM hoots h
            JOIN users u ON h.user_id = u.id
            WHERE h.id = %s;
            """,
            (updated_id,),
        )
        updated_hoot = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(updated_hoot), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# DELETE HOOT
# -------------------------
@hoots_blueprint.route("/hoots/<hoot_id>", methods=["DELETE"])
@token_required
def delete_hoot(hoot_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM hoots WHERE id = %s;", (hoot_id,))
        hoot = cursor.fetchone()

        if hoot is None:
            connection.close()
            return jsonify({"error": "Hoot not found"}), 404

        if hoot["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute("DELETE FROM hoots WHERE id = %s;", (hoot_id,))

        connection.commit()
        connection.close()

        return jsonify(hoot), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500
from flask import Blueprint, jsonify, request, g
import psycopg2.extras
from datetime import datetime

from auth_middleware import token_required
from db_helpers import get_db_connection, consolidate_comments_in_hoots

hoots_blueprint = Blueprint("hoots_blueprint", __name__)

# ============================================================
# NOTE
# - Supports JSON now (same as the example).
# - Also supports FormData later (for image uploads).
# - DB columns we are using (based on your DB):
#     hoots: id, title, content, user_id, created_at
#     comments: id, text, hoot_id, user_id, created_at
# ============================================================


# -------------------------
# CREATE HOOT (JSON or FormData)
# -------------------------
@hoots_blueprint.route("/hoots", methods=["POST"])
@token_required
def create_hoot():
    try:
        # If you're sending FormData, request.is_json will be False.
        if request.is_json:
            data = request.get_json(silent=True) or {}
            title = data.get("title")
            content = data.get("content")
        else:
            # FormData (later, for images)
            title = request.form.get("title")
            content = request.form.get("content")

        if not title or not content:
            return jsonify({"error": "title and content are required"}), 400

        user_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            INSERT INTO hoots (title, content, user_id, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (title, content, user_id, datetime.utcnow()),
        )
        hoot_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u.username AS author_username
            FROM hoots h
            JOIN users u ON h.user_id = u.id
            WHERE h.id = %s;
            """,
            (hoot_id,),
        )
        created_hoot = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(created_hoot), 201

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# LIST HOOTS (+ COMMENTS)
# -------------------------
@hoots_blueprint.route("/hoots", methods=["GET"])
def hoots_index():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u_hoot.username AS author_username,

              c.id AS comment_id,
              c.text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username

            FROM hoots h
            JOIN users u_hoot ON h.user_id = u_hoot.id
            LEFT JOIN comments c ON h.id = c.hoot_id
            LEFT JOIN users u_comment ON c.user_id = u_comment.id
            ORDER BY h.created_at DESC, c.created_at ASC;
            """
        )

        hoots = cursor.fetchall()
        consolidated_hoots = consolidate_comments_in_hoots(hoots)

        connection.close()
        return jsonify(consolidated_hoots), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# SHOW ONE HOOT
# -------------------------
@hoots_blueprint.route("/hoots/<hoot_id>", methods=["GET"])
def show_hoot(hoot_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u_hoot.username AS author_username,

              c.id AS comment_id,
              c.text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username

            FROM hoots h
            JOIN users u_hoot ON h.user_id = u_hoot.id
            LEFT JOIN comments c ON h.id = c.hoot_id
            LEFT JOIN users u_comment ON c.user_id = u_comment.id
            WHERE h.id = %s
            ORDER BY c.created_at ASC;
            """,
            (hoot_id,),
        )

        rows = cursor.fetchall()
        connection.close()

        if not rows:
            return jsonify({"error": "Hoot not found"}), 404

        processed_hoot = consolidate_comments_in_hoots(rows)[0]
        return jsonify(processed_hoot), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# UPDATE HOOT (JSON)
# -------------------------
@hoots_blueprint.route("/hoots/<hoot_id>", methods=["PUT"])
@token_required
def update_hoot(hoot_id):
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        content = data.get("content")

        if not title or not content:
            return jsonify({"error": "title and content are required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM hoots WHERE id = %s;", (hoot_id,))
        hoot = cursor.fetchone()

        if hoot is None:
            connection.close()
            return jsonify({"error": "Hoot not found"}), 404

        if hoot["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute(
            """
            UPDATE hoots
            SET title = %s, content = %s
            WHERE id = %s
            RETURNING id;
            """,
            (title, content, hoot_id),
        )
        updated_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              h.id,
              h.title,
              h.content,
              h.user_id AS hoot_author_id,
              h.created_at,
              u.username AS author_username
            FROM hoots h
            JOIN users u ON h.user_id = u.id
            WHERE h.id = %s;
            """,
            (updated_id,),
        )
        updated_hoot = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(updated_hoot), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# DELETE HOOT
# -------------------------
@hoots_blueprint.route("/hoots/<hoot_id>", methods=["DELETE"])
@token_required
def delete_hoot(hoot_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM hoots WHERE id = %s;", (hoot_id,))
        hoot = cursor.fetchone()

        if hoot is None:
            connection.close()
            return jsonify({"error": "Hoot not found"}), 404

        if hoot["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute("DELETE FROM hoots WHERE id = %s;", (hoot_id,))

        connection.commit()
        connection.close()

        return jsonify(hoot), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


