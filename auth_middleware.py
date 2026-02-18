from functools import wraps
from flask import request, jsonify, g
import jwt
import os


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ✅ Let CORS preflight requests through
        if request.method == "OPTIONS":
            return ("", 200)

        authorization_header = request.headers.get("Authorization")
        if not authorization_header:
            return jsonify({"err": "Unauthorized"}), 401

        try:
            token = authorization_header.split(" ")[1]
            token_data = jwt.decode(
                token,
                os.getenv("JWT_SECRET"),
                algorithms=["HS256"],
            )
            g.user = token_data["payload"]
        except jwt.ExpiredSignatureError:
            return jsonify({"err": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"err": "Invalid token"}), 401
        except Exception as err:
            # 500 hides auth mistakes as "server error"—better to keep auth errors 401
            return jsonify({"err": str(err)}), 401

        return f(*args, **kwargs)

    return decorated_function

