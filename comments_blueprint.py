# comments_blueprint.py

from flask import Blueprint, jsonify, request, g
import psycopg2.extras
from datetime import datetime

from db_helpers import get_db_connection
from auth_middleware import token_required

comments_blueprint = Blueprint("comments_blueprint", __name__)

# ============================================================
# COMMENTS API
#
# IMPORTANT:
# - Frontend expects:   /items/<item_id>/comments
# - Older code used:    /hoots/<hoot_id>/comments
#
# To avoid breaking anything, we support BOTH route patterns.
# ============================================================


# -------------------------
# CREATE COMMENT
# -------------------------
@comments_blueprint.route("/items/<item_id>/comments", methods=["POST"])
@comments_blueprint.route("/hoots/<item_id>/comments", methods=["POST"])
@token_required
def create_comment(item_id):
    try:
        new_comment_data = request.get_json(silent=True) or {}

        # Accept either "comment_text" (new) or "text" (legacy)
        comment_text = new_comment_data.get("comment_text") or new_comment_data.get("text")

        if not comment_text or not str(comment_text).strip():
            return jsonify({"error": "comment_text is required"}), 400

        author_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # NOTE: This matches your current DB column naming from legacy code:
        # comments(hoot, author, text, created_at)
        cursor.execute(
            """
            INSERT INTO comments (hoot, author, text, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (item_id, author_id, comment_text, datetime.utcnow()),
        )

        comment_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              c.id AS comment_id,
              c.author AS comment_author_id,
              c.text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username
            FROM comments c
            JOIN users u_comment ON c.author = u_comment.id
            WHERE c.id = %s;
            """,
            (comment_id,),
        )

        created_comment = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(created_comment), 201

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# UPDATE COMMENT
# -------------------------
@comments_blueprint.route("/items/<item_id>/comments/<comment_id>", methods=["PUT"])
@comments_blueprint.route("/hoots/<item_id>/comments/<comment_id>", methods=["PUT"])
@token_required
def update_comment(item_id, comment_id):
    try:
        updated_comment_data = request.get_json(silent=True) or {}

        new_text = updated_comment_data.get("comment_text") or updated_comment_data.get("text")
        if not new_text or not str(new_text).strip():
            return jsonify({"error": "comment_text is required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM comments WHERE id = %s;", (comment_id,))
        comment_to_update = cursor.fetchone()

        if comment_to_update is None:
            connection.close()
            return jsonify({"error": "Comment not found"}), 404

        if comment_to_update["author"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute(
            """
            UPDATE comments
            SET text = %s
            WHERE id = %s
            RETURNING id;
            """,
            (new_text, comment_id),
        )

        updated_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              c.id AS comment_id,
              c.author AS comment_author_id,
              c.text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username
            FROM comments c
            JOIN users u_comment ON c.author = u_comment.id
            WHERE c.id = %s;
            """,
            (updated_id,),
        )

        updated_comment = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(updated_comment), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# DELETE COMMENT
# -------------------------
@comments_blueprint.route("/items/<item_id>/comments/<comment_id>", methods=["DELETE"])
@comments_blueprint.route("/hoots/<item_id>/comments/<comment_id>", methods=["DELETE"])
@token_required
def delete_comment(item_id, comment_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM comments WHERE id = %s;", (comment_id,))
        comment_to_delete = cursor.fetchone()

        if comment_to_delete is None:
            connection.close()
            return jsonify({"error": "Comment not found"}), 404

        if comment_to_delete["author"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute("DELETE FROM comments WHERE id = %s;", (comment_id,))

        connection.commit()
        connection.close()

        return jsonify({"message": "Comment deleted successfully"}), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500

