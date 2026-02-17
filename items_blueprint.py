# items_blueprint.py

from flask import Blueprint, jsonify, request, g
import psycopg2.extras
from datetime import datetime

from auth_middleware import token_required
from db_helpers import get_db_connection, consolidate_comments_in_hoots

items_blueprint = Blueprint("items_blueprint", __name__)

# ============================================================
# ITEMS API (JSON now, FormData later for images)
#
# DB tables:
#   items: id, item_name, description, user_id, created_at, image_url, due_date
#   comments: id, text, item_id, user_id, created_at
#
# Notes:
# - We are reusing consolidate_comments_in_hoots() to keep the project close
#   to the hoots example (it just "consolidates comments into a list").
# ============================================================


# -------------------------
# CREATE ITEM (JSON or FormData)
# -------------------------
@items_blueprint.route("/items", methods=["POST"])
@token_required
def create_item():
    try:
        # JSON (example-style)
        if request.is_json:
            data = request.get_json(silent=True) or {}
            item_name = data.get("item_name")
            description = data.get("description")
            due_date = data.get("due_date")  # expects "YYYY-MM-DD" or None
            image_url = data.get("image_url")  # optional string for now
        else:
            # FormData (later when you add image uploads)
            item_name = request.form.get("item_name")
            description = request.form.get("description")
            due_date = request.form.get("due_date")
            image_url = request.form.get("image_url")

        if not item_name or not description:
            return jsonify({"error": "item_name and description are required"}), 400

        user_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            INSERT INTO items (item_name, description, user_id, created_at, image_url, due_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (item_name, description, user_id, datetime.utcnow(), image_url, due_date),
        )
        item_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              i.id,
              i.item_name,
              i.description,
              i.image_url,
              i.due_date,
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
              i.item_name,
              i.description,
              i.image_url,
              i.due_date,
              i.created_at,
              i.user_id AS item_owner_id,
              u_item.username AS owner_username,

              c.id AS comment_id,
              c.text AS comment_text,
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
# SHOW ONE ITEM
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
              i.item_name,
              i.description,
              i.image_url,
              i.due_date,
              i.created_at,
              i.user_id AS item_owner_id,
              u_item.username AS owner_username,

              c.id AS comment_id,
              c.text AS comment_text,
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
# UPDATE ITEM (JSON)
# -------------------------
@items_blueprint.route("/items/<item_id>", methods=["PUT"])
@token_required
def update_item(item_id):
    try:
        data = request.get_json(silent=True) or {}

        item_name = data.get("item_name")
        description = data.get("description")
        due_date = data.get("due_date")
        image_url = data.get("image_url")

        if not item_name or not description:
            return jsonify({"error": "item_name and description are required"}), 400

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
            SET item_name = %s,
                description = %s,
                due_date = %s,
                image_url = %s
            WHERE id = %s
            RETURNING id;
            """,
            (item_name, description, due_date, image_url, item_id),
        )
        updated_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              i.id,
              i.item_name,
              i.description,
              i.image_url,
              i.due_date,
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



