"""Standards Harvester API endpoints.

Provides endpoints for:
- Fetching standards via web scraping, PDF parsing, or manual upload
- Uploading PDF files
- Listing versions
- Viewing diffs between versions
"""

import json
import logging
import os
from pathlib import Path
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from src.harvesters import create_harvester, HarvesterType
from src.services.standards_versioning_service import (
    store_version,
    get_versions,
    get_latest_version,
    detect_change,
    generate_diff,
    get_version_text,
)


logger = logging.getLogger(__name__)


# Create Blueprint
standards_harvester_bp = Blueprint('standards_harvester', __name__, url_prefix='/api/standards-harvester')

# Module-level references (set during initialization)
_workspace_manager = None


def init_standards_harvester_bp(workspace_manager):
    """Initialize the standards harvester blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return standards_harvester_bp


# ========================================================================
# Fetch Endpoints
# ========================================================================

@standards_harvester_bp.route('/fetch', methods=['POST'])
def fetch_standards():
    """Trigger a standards harvest.

    Request JSON:
        {
            "accreditor_code": str (e.g., "ACCSC"),
            "source_type": "web_scrape" | "pdf_parse" | "manual_upload",
            "url": str (optional, for web_scrape or remote PDF),
            "text": str (optional, for manual_upload),
            "file_path": str (optional, for local PDF),
            "version_date": str (optional, ISO format)
        }

    Returns:
        201: {
            "version": {...},
            "change_detected": bool
        }
        400: Invalid request
        500: Fetch error
    """
    try:
        data = request.get_json()

        accreditor_code = data.get('accreditor_code')
        source_type = data.get('source_type')

        if not accreditor_code or not source_type:
            return jsonify({
                'error': 'Missing required fields: accreditor_code, source_type'
            }), 400

        # Validate source_type
        try:
            harvester_type = HarvesterType(source_type)
        except ValueError:
            return jsonify({
                'error': f'Invalid source_type: {source_type}. Must be web_scrape, pdf_parse, or manual_upload'
            }), 400

        # Build source_config based on source_type
        source_config = {}

        if harvester_type == HarvesterType.WEB_SCRAPER:
            url = data.get('url')
            if not url:
                return jsonify({'error': 'url required for web_scrape'}), 400
            source_config['url'] = url

        elif harvester_type == HarvesterType.PDF_PARSER:
            file_path = data.get('file_path')
            url = data.get('url')
            if not file_path and not url:
                return jsonify({'error': 'file_path or url required for pdf_parse'}), 400
            if file_path:
                source_config['file_path'] = file_path
            if url:
                source_config['url'] = url

        elif harvester_type == HarvesterType.MANUAL_UPLOAD:
            text = data.get('text')
            if not text:
                return jsonify({'error': 'text required for manual_upload'}), 400
            source_config['text'] = text
            source_config['notes'] = data.get('notes', '')

        # Create harvester and fetch
        logger.info(f"Fetching standards for {accreditor_code} via {source_type}")

        harvester = create_harvester(harvester_type)
        result = harvester.fetch(source_config)

        text = result['text']
        metadata = result['metadata']

        # Check for changes
        change_info = detect_change(accreditor_code, text)

        # Store version
        version = store_version(
            accreditor_code=accreditor_code,
            text=text,
            source_type=source_type,
            source_url=source_config.get('url'),
            metadata=metadata,
            version_date=data.get('version_date')
        )

        logger.info(
            f"Stored version {version['id']} for {accreditor_code} "
            f"(changed: {change_info['changed']})"
        )

        return jsonify({
            'version': version,
            'change_detected': change_info['changed']
        }), 201

    except ValueError as e:
        logger.error(f"Fetch error: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error during fetch")
        return jsonify({'error': 'Internal server error'}), 500


@standards_harvester_bp.route('/upload', methods=['POST'])
def upload_pdf():
    """Upload a PDF file for parsing.

    Form data:
        - file: PDF file
        - accreditor_code: str

    Returns:
        201: {
            "version": {...},
            "change_detected": bool
        }
        400: Invalid request
        500: Upload error
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        accreditor_code = request.form.get('accreditor_code')

        if not accreditor_code:
            return jsonify({'error': 'accreditor_code required'}), 400

        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400

        # Save file
        filename = secure_filename(file.filename)
        upload_dir = Path(f"standards_library/uploads/{accreditor_code}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / filename
        file.save(str(file_path))

        logger.info(f"Uploaded PDF to {file_path}")

        # Parse with PdfHarvester
        harvester = create_harvester(HarvesterType.PDF_PARSER)
        result = harvester.fetch({"file_path": str(file_path)})

        text = result['text']
        metadata = result['metadata']

        # Check for changes
        change_info = detect_change(accreditor_code, text)

        # Store version
        version = store_version(
            accreditor_code=accreditor_code,
            text=text,
            source_type="pdf_parse",
            source_url=None,
            metadata=metadata
        )

        logger.info(
            f"Stored version {version['id']} from uploaded PDF "
            f"(changed: {change_info['changed']})"
        )

        return jsonify({
            'version': version,
            'change_detected': change_info['changed']
        }), 201

    except Exception as e:
        logger.exception("Error during PDF upload")
        return jsonify({'error': str(e)}), 500


# ========================================================================
# Version Listing Endpoints
# ========================================================================

@standards_harvester_bp.route('/versions/<accreditor_code>', methods=['GET'])
def list_versions(accreditor_code):
    """List all versions for an accreditor.

    Returns:
        200: {"versions": [...]}
    """
    try:
        versions = get_versions(accreditor_code)
        return jsonify({'versions': versions}), 200
    except Exception as e:
        logger.exception("Error listing versions")
        return jsonify({'error': str(e)}), 500


@standards_harvester_bp.route('/versions/<accreditor_code>/latest', methods=['GET'])
def get_latest(accreditor_code):
    """Get the latest version for an accreditor.

    Returns:
        200: {"version": {...}}
        404: No versions found
    """
    try:
        version = get_latest_version(accreditor_code)

        if not version:
            return jsonify({'error': 'No versions found'}), 404

        return jsonify({'version': version}), 200
    except Exception as e:
        logger.exception("Error getting latest version")
        return jsonify({'error': str(e)}), 500


# ========================================================================
# Diff Endpoints
# ========================================================================

@standards_harvester_bp.route('/diff/<old_version_id>/<new_version_id>', methods=['GET'])
def get_diff_between_versions(old_version_id, new_version_id):
    """Get diff HTML between two specific versions.

    Returns:
        200: {
            "diff_html": str,
            "old_version": {...},
            "new_version": {...}
        }
    """
    try:
        # Load version info (for metadata display)
        old_text = get_version_text(old_version_id)
        new_text = get_version_text(new_version_id)

        if not new_text:
            return jsonify({'error': 'New version not found'}), 404

        # Generate diff
        diff_html = generate_diff(old_version_id, new_version_id, old_text, new_text)

        return jsonify({
            'diff_html': diff_html,
            'old_version': {'id': old_version_id} if old_text else None,
            'new_version': {'id': new_version_id}
        }), 200

    except Exception as e:
        logger.exception("Error generating diff")
        return jsonify({'error': str(e)}), 500


@standards_harvester_bp.route('/diff/<new_version_id>', methods=['GET'])
def get_diff_against_previous(new_version_id):
    """Get diff against the previous version for the same accreditor.

    Returns:
        200: {
            "diff_html": str,
            "old_version": {...} | null,
            "new_version": {...}
        }
    """
    try:
        # Get new version text
        new_text = get_version_text(new_version_id)

        if not new_text:
            return jsonify({'error': 'Version not found'}), 404

        # Find previous version (need to query DB for accreditor_code)
        from src.db.connection import get_conn

        conn = get_conn()
        cursor = conn.execute("""
            SELECT accreditor_code, version_date
            FROM standards_versions
            WHERE id = ?
        """, (new_version_id,))

        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Version not found'}), 404

        accreditor_code = row['accreditor_code']
        version_date = row['version_date']

        # Find previous version
        cursor = conn.execute("""
            SELECT id, version_date
            FROM standards_versions
            WHERE accreditor_code = ? AND version_date < ?
            ORDER BY version_date DESC
            LIMIT 1
        """, (accreditor_code, version_date))

        prev_row = cursor.fetchone()

        if prev_row:
            old_version_id = prev_row['id']
            old_text = get_version_text(old_version_id)
        else:
            old_version_id = None
            old_text = None

        # Generate diff
        diff_html = generate_diff(old_version_id, new_version_id, old_text, new_text)

        return jsonify({
            'diff_html': diff_html,
            'old_version': {'id': old_version_id, 'version_date': prev_row['version_date']} if prev_row else None,
            'new_version': {'id': new_version_id, 'version_date': version_date}
        }), 200

    except Exception as e:
        logger.exception("Error generating diff")
        return jsonify({'error': str(e)}), 500
