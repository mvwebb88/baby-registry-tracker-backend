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
# DB schema (confirmed on Heroku):
#   comments:
#     id, comment_text, user_id, item_id, created_at
#
# Routes supported (to avoid breaking legacy frontend code):
#   POST   /items/<item_id>/comments
#   PUT    /items/<item_id>/comments/<comment_id>
#   DELETE /items/<item_id>/comments/<comment_id>
#
# Legacy aliases still supported:
#   /hoots/<item_id>/comments ...
# ============================================================


def _get_comment_text():
    """
    Accept JSON or FormData.
    Accept either 'comment_text' (new) or 'text' (legacy).
    """
    content_type = request.content_type or ""

    if "multipart/form-data" in content_type:
        return (request.form.get("comment_text") or request.form.get("text") or "").strip()

    data = request.get_json(silent=True) or {}
    return str(data.get("comment_text") or data.get("text") or "").strip()


# -------------------------
# CREATE COMMENT
# -------------------------
@comments_blueprint.route("/items/<int:item_id>/comments", methods=["POST"])
@comments_blueprint.route("/hoots/<int:item_id>/comments", methods=["POST"])
@token_required
def create_comment(item_id):
    try:
        comment_text = _get_comment_text()
        if not comment_text:
            return jsonify({"error": "comment_text is required"}), 400

        user_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            INSERT INTO comments (comment_text, user_id, item_id, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (comment_text, user_id, item_id, datetime.utcnow()),
        )
        comment_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              c.id AS comment_id,
              c.comment_text,
              c.created_at AS comment_created_at,
              u.username AS comment_author_username,
              c.user_id AS comment_author_id,
              c.item_id
            FROM comments c
            JOIN users u ON c.user_id = u.id
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
@comments_blueprint.route("/items/<int:item_id>/comments/<int:comment_id>", methods=["PUT"])
@comments_blueprint.route("/hoots/<int:item_id>/comments/<int:comment_id>", methods=["PUT"])
@token_required
def update_comment(item_id, comment_id):
    try:
        new_text = _get_comment_text()
        if not new_text:
            return jsonify({"error": "comment_text is required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM comments WHERE id = %s;", (comment_id,))
        comment = cursor.fetchone()

        if comment is None:
            connection.close()
            return jsonify({"error": "Comment not found"}), 404

        if comment["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        # Optional safety: ensure comment belongs to the item in the URL
        if comment.get("item_id") != item_id:
            connection.close()
            return jsonify({"error": "Comment does not belong to this item"}), 400

        cursor.execute(
            """
            UPDATE comments
            SET comment_text = %s
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
              c.comment_text,
              c.created_at AS comment_created_at,
              u.username AS comment_author_username,
              c.user_id AS comment_author_id,
              c.item_id
            FROM comments c
            JOIN users u ON c.user_id = u.id
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
@comments_blueprint.route("/items/<int:item_id>/comments/<int:comment_id>", methods=["DELETE"])
@comments_blueprint.route("/hoots/<int:item_id>/comments/<int:comment_id>", methods=["DELETE"])
@token_required
def delete_comment(item_id, comment_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM comments WHERE id = %s;", (comment_id,))
        comment = cursor.fetchone()

        if comment is None:
            connection.close()
            return jsonify({"error": "Comment not found"}), 404

        if comment["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        # Optional safety: ensure comment belongs to the item in the URL
        if comment.get("item_id") != item_id:
            connection.close()
            return jsonify({"error": "Comment does not belong to this item"}), 400

        cursor.execute("DELETE FROM comments WHERE id = %s;", (comment_id,))

        connection.commit()
        connection.close()

        return jsonify({"message": "Comment deleted successfully"}), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


