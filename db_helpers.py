import os
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras


def get_db_connection():
    """
    Connect to Postgres.

    - Heroku: uses DATABASE_URL (automatically set by Heroku Postgres add-on)
    - Local: uses POSTGRES_DATABASE / POSTGRES_USERNAME / POSTGRES_PASSWORD
    """
    database_url = os.getenv("DATABASE_URL")

    # ✅ Heroku / production
    if database_url:
        result = urlparse(database_url)
        return psycopg2.connect(
            host=result.hostname,
            database=result.path[1:],  # remove leading "/"
            user=result.username,
            password=result.password,
            port=result.port,
            sslmode="require",
            cursor_factory=psycopg2.extras.RealDictCursor,
        )

    # ✅ Local development
    return psycopg2.connect(
        host="localhost",
        database=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USERNAME"),
        password=os.getenv("POSTGRES_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def consolidate_comments_in_hoots(hoots_with_comments):
    consolidated_hoots = []
    for hoot in hoots_with_comments:
        # Check if this hoot has already been added to consolidated_hoots
        hoot_exists = False
        for consolidated_hoot in consolidated_hoots:
            if hoot["id"] == consolidated_hoot["id"]:
                hoot_exists = True
                consolidated_hoot["comments"].append(
                    {
                        "comment_text": hoot["comment_text"],
                        "comment_id": hoot["comment_id"],
                        "comment_created_at": hoot["comment_created_at"],
                        "comment_author_username": hoot["comment_author_username"],
                    }
                )
                break

        # If the hoot doesn't exist in consolidated_hoots, add it
        if not hoot_exists:
            hoot["comments"] = []
            if hoot["comment_id"] is not None:
                hoot["comments"].append(
                    {
                        "comment_text": hoot["comment_text"],
                        "comment_id": hoot["comment_id"],
                        "comment_created_at": hoot["comment_created_at"],
                        "comment_author_username": hoot["comment_author_username"],
                    }
                )
            del hoot["comment_id"]
            del hoot["comment_text"]
            del hoot["comment_author_username"]
            del hoot["comment_created_at"]
            consolidated_hoots.append(hoot)

    return consolidated_hoots

