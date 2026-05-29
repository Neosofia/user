from flask import Blueprint, jsonify, Response
from src.bootstrap.config import settings
from src.bootstrap.extensions import talisman

bp = Blueprint("health", __name__)

@bp.route("/health", methods=["GET", "HEAD"])
@talisman(force_https=False)
def health() -> Response:
    return jsonify({"status": "ok"})
