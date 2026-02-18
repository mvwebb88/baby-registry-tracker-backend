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
# Supports:
# - JSON requests (application/json)
# - FormData requests (multipart/form-data) for forms (even if file upload is "later")
#
# DB tables (your local DB shows these columns on items):
#   items:
#     id, item_name, description, image_url, due_date, user_id, created_at,
#     quantity, priority, category, store, price, status, link, notes
#
# NOTE:
# - DB column is "item_name"
# - Frontend may send "name" or "item_name" depending on version
#   => we accept BOTH and return BOTH aliases to keep frontend stable
# ============================================================


# -------------------------
# Helper: read input (JSON or FormData)
# -------------------------
def _get_request_data():
    """
    Returns a dict of input fields regardless of JSON vs FormData.
    Accepts both 'item_name' and legacy 'name'.
    Also accepts:
      quantity, priority, category, store, price, status, link, notes
    """
    content_type = request.content_type or ""

    PRIORITIES = {"Low", "Medium", "High"}
    STATUSES = {"Needed", "Purchased"}
    CATEGORIES = {
        "Diapering",
        "Feeding",
        "Clothing",
        "Nursery",
        "Bath",
        "Travel",
        "Health & Safety",
        "Toys",
        "Other",
    }

    def _clean_text(value):
        if value is None:
            return None
        s = str(value).strip()
        return s if s != "" else None

    def _clean_int(value, default=1):
        try:
            n = int(value)
            return n if n >= 1 else default
        except (TypeError, ValueError):
            return default

    def _clean_price(value):
        if value is None or value == "":
            return None
        try:
            p = float(value)
            return p if p >= 0 else None
        except (TypeError, ValueError):
            return None

    def _clean_choice(value, allowed, default):
        v = _clean_text(value)
        return v if v in allowed else default

    if "multipart/form-data" in content_type:
        item_name = request.form.get("item_name") or request.form.get("name")
        description = request.form.get("description")
        image_url = request.form.get("image_url")

        quantity = _clean_int(request.form.get("quantity"), default=1)
        priority = _clean_choice(request.form.get("priority"), PRIORITIES, "Medium")
        category = _clean_choice(request.form.get("category"), CATEGORIES, "Other")
        store = _clean_text(request.form.get("store"))
        price = _clean_price(request.form.get("price"))
        status = _clean_choice(request.form.get("status"), STATUSES, "Needed")
        link = _clean_text(request.form.get("link"))
        notes = _clean_text(request.form.get("notes"))

        return {
            "item_name": _clean_text(item_name),
            "description": _clean_text(description),
            "image_url": _clean_text(image_url),
            "quantity": quantity,
            "priority": priority,
            "category": category,
            "store": store,
            "price": price,
            "status": status,
            "link": link,
            "notes": notes,
        }

    # Otherwise assume JSON
    data = request.get_json(silent=True) or {}

    item_name = data.get("item_name") or data.get("name")
    description = data.get("description")
    image_url = data.get("image_url")

    quantity = _clean_int(data.get("quantity"), default=1)
    priority = _clean_choice(data.get("priority"), PRIORITIES, "Medium")
    category = _clean_choice(data.get("category"), CATEGORIES, "Other")
    store = _clean_text(data.get("store"))
    price = _clean_price(data.get("price"))
    status = _clean_choice(data.get("status"), STATUSES, "Needed")
    link = _clean_text(data.get("link"))
    notes = _clean_text(data.get("notes"))

    return {
        "item_name": _clean_text(item_name),
        "description": _clean_text(description),
        "image_url": _clean_text(image_url),
        "quantity": quantity,
        "priority": priority,
        "category": category,
        "store": store,
        "price": price,
        "status": status,
        "link": link,
        "notes": notes,
    }


# -------------------------
# CREATE ITEM (JSON or FormData)
# -------------------------
@items_blueprint.route("/items", methods=["POST"])
@token_required
def create_item():
    try:
        data = _get_request_data()

        item_name = data.get("item_name")
        description = data.get("description")
        image_url = data.get("image_url")

        quantity = data.get("quantity", 1)
        priority = data.get("priority", "Medium")
        category = data.get("category", "Other")
        store = data.get("store")
        price = data.get("price")
        status = data.get("status", "Needed")
        link = data.get("link")
        notes = data.get("notes")

        if not item_name or not description:
            return jsonify({"error": "item_name and description are required"}), 400

        user_id = g.user["id"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            """
            INSERT INTO items
              (item_name, description, image_url, quantity, priority, category, store, price, status, link, notes, user_id, created_at)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                item_name,
                description,
                image_url,
                quantity,
                priority,
                category,
                store,
                price,
                status,
                link,
                notes,
                user_id,
                datetime.utcnow(),
            ),
        )

        item_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              i.id,
              i.item_name,
              i.item_name AS name,
              i.item_name AS item_name,
              i.description,
              i.image_url,
              i.quantity,
              i.priority,
              i.category,
              i.store,
              i.price,
              i.status,
              i.link,
              i.notes,
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
              i.item_name AS name,
              i.item_name AS item_name,
              i.description,
              i.image_url,
              i.quantity,
              i.priority,
              i.category,
              i.store,
              i.price,
              i.status,
              i.link,
              i.notes,
              i.due_date,
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
              i.item_name,
              i.item_name AS name,
              i.item_name AS item_name,
              i.description,
              i.image_url,
              i.quantity,
              i.priority,
              i.category,
              i.store,
              i.price,
              i.status,
              i.link,
              i.notes,
              i.due_date,
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
# UPDATE ITEM (JSON or FormData)
# -------------------------
@items_blueprint.route("/items/<item_id>", methods=["PUT"])
@token_required
def update_item(item_id):
    try:
        data = _get_request_data()

        item_name = data.get("item_name")
        description = data.get("description")
        image_url = data.get("image_url")

        quantity = data.get("quantity", 1)
        priority = data.get("priority", "Medium")
        category = data.get("category", "Other")
        store = data.get("store")
        price = data.get("price")
        status = data.get("status", "Needed")
        link = data.get("link")
        notes = data.get("notes")

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
                image_url = %s,
                quantity = %s,
                priority = %s,
                category = %s,
                store = %s,
                price = %s,
                status = %s,
                link = %s,
                notes = %s
            WHERE id = %s
            RETURNING id;
            """,
            (
                item_name,
                description,
                image_url,
                quantity,
                priority,
                category,
                store,
                price,
                status,
                link,
                notes,
                item_id,
            ),
        )

        updated_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            SELECT
              i.id,
              i.item_name,
              i.item_name AS name,
              i.item_name AS item_name,
              i.description,
              i.image_url,
              i.quantity,
              i.priority,
              i.category,
              i.store,
              i.price,
              i.status,
              i.link,
              i.notes,
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






