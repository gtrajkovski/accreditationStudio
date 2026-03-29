from flask import Blueprint, jsonify, request
from src.accreditors.registry import AccreditorRegistry

accreditors_bp = Blueprint("accreditors", __name__, url_prefix="/api/accreditors")


@accreditors_bp.route("", methods=["GET"])
def list_accreditors():
    """List all available accreditor packages."""
    packages = AccreditorRegistry.list_all()
    return jsonify({"accreditors": [p.to_dict() for p in packages]})


@accreditors_bp.route("/<code>", methods=["GET"])
def get_accreditor(code: str):
    """Get accreditor package details."""
    manifest = AccreditorRegistry.get(code.upper())
    if not manifest:
        return jsonify({"error": "Accreditor not found"}), 404

    # Try to get sources and parser modules
    sources_module = AccreditorRegistry.get_sources_module(code.upper())
    parser_module = AccreditorRegistry.get_parser_module(code.upper())

    sources = []
    if sources_module and hasattr(sources_module, "get_sources"):
        try:
            source_list = sources_module.get_sources()
            sources = [{"url": s.url, "format": s.format, "name": s.name} for s in source_list]
        except Exception:
            pass

    # Check for crosswalk seeds
    has_crosswalk = False
    if code.upper() == "ACCSC":
        try:
            from src.accreditors.accsc.mappings import ACCSC_CROSSWALK_SEEDS
            has_crosswalk = True
        except ImportError:
            pass

    return jsonify({
        "manifest": manifest.to_dict(),
        "sources": sources,
        "has_parser": parser_module is not None,
        "has_crosswalk": has_crosswalk
    })


@accreditors_bp.route("/<code>/fetch", methods=["POST"])
def fetch_standards(code: str):
    """Trigger standards fetch for accreditor."""
    manifest = AccreditorRegistry.get(code.upper())
    if not manifest:
        return jsonify({"error": "Accreditor not found"}), 404

    sources_module = AccreditorRegistry.get_sources_module(code.upper())
    if not sources_module:
        return jsonify({"error": "No sources available for this accreditor"}), 404

    # Enqueue fetch task
    # This would integrate with standards harvester
    return jsonify({"status": "queued", "accreditor": code.upper()})
