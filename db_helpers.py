import os
import psycopg2


def get_db_connection():
    """
    ✅ Works locally AND on Heroku
    - Heroku provides DATABASE_URL automatically
    - Local uses POSTGRES_* env vars
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Heroku Postgres requires SSL
        return psycopg2.connect(database_url, sslmode="require")

    # Local dev connection (WSL / Ubuntu)
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USERNAME"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def consolidate_comments_in_hoots(hoots_with_comments):
    """
    Legacy helper from earlier project naming (hoot).
    Safe to keep if other code imports it.
    """
    consolidated_hoots = []
    for hoot in hoots_with_comments:
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

        if not hoot_exists:
            hoot["comments"] = []
            if hoot.get("comment_id") is not None:
                hoot["comments"].append(
                    {
                        "comment_text": hoot["comment_text"],
                        "comment_id": hoot["comment_id"],
                        "comment_created_at": hoot["comment_created_at"],
                        "comment_author_username": hoot["comment_author_username"],
                    }
                )

            # Clean up flattened keys
            for k in ("comment_id", "comment_text", "comment_author_username", "comment_created_at"):
                if k in hoot:
                    del hoot[k]

            consolidated_hoots.append(hoot)

    return consolidated_hoots


