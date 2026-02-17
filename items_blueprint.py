# items_blueprint.py

from flask import Blueprint, jsonify, request, g
import psycopg2.extras
from datetime import datetime

from auth_middleware import token_required
from db_helpers import get_db_connection, consolidate_comments_in_hoots

items_blueprint = Blueprint("items_blueprint", __name__)

# ============================================================
# ITEMS API
#
# Heroku DB tables (based on what you created):
#   users:    id, username, password_digest, created_at
#   items:    id, name, description, image_url, user_id, created_at
#   comments: id, comment_text, user_id, item_id, created_at
#
# Notes:
# - We keep consolidate_comments_in_hoots() to match the original pattern.
# - We return BOTH "name" and "item_name" for compatibility.
# - due_date is removed because it is NOT in your current items table.
# ============================================================


# -------------------------
# CREATE ITEM
# -------------------------
@items_blueprint.route("/items", methods=["POST"])
@token_required
def create_item():
    try:
        # Accept JSON now (FormData later if you add file uploads)
        data = request.get_json(silent=True) or {}

        # support either key from frontend
        name = data.get("name") or data.get("item_name")
        description = data.get("description")
        image_url = data.get("image_url")

        if not name or not description:
            return jsonify({"error": "name and description are required"}), 400

        user_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            INSERT INTO items (name, description, user_id, created_at, image_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (name, description, user_id, datetime.utcnow(), image_url),
        )
        item_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              i.id,
              i.name,
              i.name AS item_name, -- compatibility for any old frontend usage
              i.description,
              i.image_url,
              i.created_at,
              i.user_id AS item_owner_id,
              u.username AS owner_username
            FROM items i
            JOIN users u ON i.user_id = u.id
            WHERE i.id = %s;
            """,
            (item_id,),
        )
        created_item = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(created_item), 201

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# LIST ITEMS (+ COMMENTS)
# -------------------------
@items_blueprint.route("/items", methods=["GET"])
def items_index():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            SELECT
              i.id,
              i.name,
              i.name AS item_name, -- compatibility
              i.description,
              i.image_url,
              i.created_at,
              i.user_id AS item_owner_id,
              u_item.username AS owner_username,

              c.id AS comment_id,
              c.comment_text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username

            FROM items i
            JOIN users u_item ON i.user_id = u_item.id
            LEFT JOIN comments c ON i.id = c.item_id
            LEFT JOIN users u_comment ON c.user_id = u_comment.id
            ORDER BY i.created_at DESC, c.created_at ASC;
            """
        )

        rows = cursor.fetchall()
        consolidated = consolidate_comments_in_hoots(rows)

        connection.close()
        return jsonify(consolidated), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# SHOW ONE ITEM (+ COMMENTS)
# -------------------------
@items_blueprint.route("/items/<item_id>", methods=["GET"])
def show_item(item_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            SELECT
              i.id,
              i.name,
              i.name AS item_name, -- compatibility
              i.description,
              i.image_url,
              i.created_at,
              i.user_id AS item_owner_id,
              u_item.username AS owner_username,

              c.id AS comment_id,
              c.comment_text AS comment_text,
              c.created_at AS comment_created_at,
              u_comment.username AS comment_author_username

            FROM items i
            JOIN users u_item ON i.user_id = u_item.id
            LEFT JOIN comments c ON i.id = c.item_id
            LEFT JOIN users u_comment ON c.user_id = u_comment.id
            WHERE i.id = %s
            ORDER BY c.created_at ASC;
            """,
            (item_id,),
        )

        rows = cursor.fetchall()
        connection.close()

        if not rows:
            return jsonify({"error": "Item not found"}), 404

        processed_item = consolidate_comments_in_hoots(rows)[0]
        return jsonify(processed_item), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# UPDATE ITEM
# -------------------------
@items_blueprint.route("/items/<item_id>", methods=["PUT"])
@token_required
def update_item(item_id):
    try:
        data = request.get_json(silent=True) or {}

        name = data.get("name") or data.get("item_name")
        description = data.get("description")
        image_url = data.get("image_url")

        if not name or not description:
            return jsonify({"error": "name and description are required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM items WHERE id = %s;", (item_id,))
        item = cursor.fetchone()

        if item is None:
            connection.close()
            return jsonify({"error": "Item not found"}), 404

        if item["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute(
            """
            UPDATE items
            SET name = %s,
                description = %s,
                image_url = %s
            WHERE id = %s
            RETURNING id;
            """,
            (name, description, image_url, item_id),
        )
        updated_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              i.id,
              i.name,
              i.name AS item_name, -- compatibility
              i.description,
              i.image_url,
              i.created_at,
              i.user_id AS item_owner_id,
              u.username AS owner_username
            FROM items i
            JOIN users u ON i.user_id = u.id
            WHERE i.id = %s;
            """,
            (updated_id,),
        )
        updated_item = cursor.fetchone()

        connection.commit()
        connection.close()

        return jsonify(updated_item), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# -------------------------
# DELETE ITEM
# -------------------------
@items_blueprint.route("/items/<item_id>", methods=["DELETE"])
@token_required
def delete_item(item_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM items WHERE id = %s;", (item_id,))
        item = cursor.fetchone()

        if item is None:
            connection.close()
            return jsonify({"error": "Item not found"}), 404

        if item["user_id"] != g.user["id"]:
            connection.close()
            return jsonify({"error": "Unauthorized"}), 403

        cursor.execute("DELETE FROM items WHERE id = %s;", (item_id,))

        connection.commit()
        connection.close()

        return jsonify(item), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500




