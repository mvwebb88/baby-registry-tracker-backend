import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS

# Blueprints
from auth_blueprint import authentication_blueprint
from items_blueprint import items_blueprint
from comments_blueprint import comments_blueprint


app = Flask(__name__)

# ✅ CORS: allow local dev + your Netlify domain
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
                "https://babyregistry.netlify.app"
            ],
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        }
    },
    supports_credentials=True
)


# ✅ Register routes
app.register_blueprint(authentication_blueprint)
app.register_blueprint(items_blueprint)
app.register_blueprint(comments_blueprint)


# ✅ Quick sanity route so opening the URL doesn't show "Not Found"
@app.get("/")
def root():
    return jsonify({"message": "Baby Registry API is running"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


# Local run only (Heroku uses gunicorn app:app from Procfile)
if __name__ == "__main__":
    app.run(debug=True)





