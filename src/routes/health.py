from flask import Blueprint, jsonify, Response

from src.bootstrap.extensions import talisman
from src.bootstrap.version import service_version

bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET", "HEAD"])
@talisman(force_https=False)
def health() -> Response:
    return jsonify({"status": "ok", "version": service_version()})
