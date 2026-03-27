"""State Regulatory Service.

Business logic for state authorization tracking, catalog compliance,
and program licensing approvals with computed readiness scores per state.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from src.db.connection import get_conn
from src.core.models.helpers import generate_id, now_iso
from src.core.models.state_regulations import (
    StateAuthorization,
    StateCatalogRequirement,
    StateCatalogCompliance,
    StateProgramApproval,
    StateReadinessScore,
    StateSummary,
)


# =============================================================================
# State Name Lookup
# =============================================================================

STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "PR": "Puerto Rico",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "VI": "Virgin Islands",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}


# =============================================================================
# Score Weights
# =============================================================================

STATE_SCORE_WEIGHTS = {
    "authorization": 0.30,
    "catalog": 0.40,
    "program": 0.30,
}


# =============================================================================
# Service Class
# =============================================================================

class StateRegulatoryService:
    """Service for managing state regulatory compliance."""

    # =========================================================================
    # Authorization Methods
    # =========================================================================

    def add_authorization(
        self,
        institution_id: str,
        state_code: str,
        authorization_status: str,
        sara_member: bool = False,
        effective_date: Optional[str] = None,
        renewal_date: Optional[str] = None,
        contact_agency: Optional[str] = None,
        contact_url: Optional[str] = None,
        notes: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> StateAuthorization:
        """Add a new state authorization record."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            auth_id = generate_id("stauth")
            now = now_iso()

            conn.execute("""
                INSERT INTO state_authorizations (
                    id, institution_id, state_code, authorization_status,
                    sara_member, effective_date, renewal_date,
                    contact_agency, contact_url, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                auth_id, institution_id, state_code, authorization_status,
                sara_member, effective_date, renewal_date,
                contact_agency, contact_url, notes, now, now
            ))
            conn.commit()

            return StateAuthorization(
                id=auth_id,
                institution_id=institution_id,
                state_code=state_code,
                authorization_status=authorization_status,
                sara_member=sara_member,
                effective_date=effective_date,
                renewal_date=renewal_date,
                contact_agency=contact_agency,
                contact_url=contact_url,
                notes=notes,
                created_at=now,
                updated_at=now,
            )

        finally:
            if should_close:
                conn.close()

    def get_authorizations(
        self,
        institution_id: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[StateAuthorization]:
        """Get all state authorizations for an institution."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            cursor = conn.execute("""
                SELECT * FROM state_authorizations
                WHERE institution_id = ?
                ORDER BY state_code
            """, (institution_id,))

            return [
                StateAuthorization.from_dict(dict(row))
                for row in cursor.fetchall()
            ]

        finally:
            if should_close:
                conn.close()

    def get_authorization(
        self,
        institution_id: str,
        state_code: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> Optional[StateAuthorization]:
        """Get a specific state authorization."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            cursor = conn.execute("""
                SELECT * FROM state_authorizations
                WHERE institution_id = ? AND state_code = ?
            """, (institution_id, state_code))

            row = cursor.fetchone()
            if row:
                return StateAuthorization.from_dict(dict(row))
            return None

        finally:
            if should_close:
                conn.close()

    def update_authorization(
        self,
        auth_id: str,
        conn: Optional[sqlite3.Connection] = None,
        **updates
    ) -> Optional[StateAuthorization]:
        """Update an existing state authorization."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            # Build dynamic update query
            allowed_fields = [
                "authorization_status", "sara_member", "effective_date",
                "renewal_date", "contact_agency", "contact_url", "notes"
            ]
            set_clauses = []
            params = []

            for field in allowed_fields:
                if field in updates:
                    set_clauses.append(f"{field} = ?")
                    params.append(updates[field])

            if not set_clauses:
                return self._get_authorization_by_id(auth_id, conn)

            set_clauses.append("updated_at = ?")
            params.append(now_iso())
            params.append(auth_id)

            conn.execute(f"""
                UPDATE state_authorizations
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """, params)
            conn.commit()

            return self._get_authorization_by_id(auth_id, conn)

        finally:
            if should_close:
                conn.close()

    def _get_authorization_by_id(
        self,
        auth_id: str,
        conn: sqlite3.Connection
    ) -> Optional[StateAuthorization]:
        """Get authorization by ID (internal helper)."""
        cursor = conn.execute("""
            SELECT * FROM state_authorizations WHERE id = ?
        """, (auth_id,))
        row = cursor.fetchone()
        if row:
            return StateAuthorization.from_dict(dict(row))
        return None

    def delete_authorization(
        self,
        auth_id: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Delete a state authorization."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            cursor = conn.execute("""
                DELETE FROM state_authorizations WHERE id = ?
            """, (auth_id,))
            conn.commit()
            return cursor.rowcount > 0

        finally:
            if should_close:
                conn.close()

    # =========================================================================
    # Catalog Requirements Methods
    # =========================================================================

    def get_requirements_for_state(
        self,
        state_code: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[StateCatalogRequirement]:
        """Get all catalog requirements for a state."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            cursor = conn.execute("""
                SELECT * FROM state_catalog_requirements
                WHERE state_code = ?
                ORDER BY category, requirement_key
            """, (state_code,))

            return [
                StateCatalogRequirement.from_dict(dict(row))
                for row in cursor.fetchall()
            ]

        finally:
            if should_close:
                conn.close()

    def add_requirement(
        self,
        state_code: str,
        requirement_key: str,
        requirement_name: str,
        requirement_text: Optional[str] = None,
        category: str = "disclosure",
        required: bool = True,
        conn: Optional[sqlite3.Connection] = None
    ) -> StateCatalogRequirement:
        """Add a new catalog requirement for a state."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            req_id = generate_id("streq")
            now = now_iso()

            conn.execute("""
                INSERT INTO state_catalog_requirements (
                    id, state_code, requirement_key, requirement_name,
                    requirement_text, category, required, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req_id, state_code, requirement_key, requirement_name,
                requirement_text, category, required, now
            ))
            conn.commit()

            return StateCatalogRequirement(
                id=req_id,
                state_code=state_code,
                requirement_key=requirement_key,
                requirement_name=requirement_name,
                requirement_text=requirement_text,
                category=category,
                required=required,
                created_at=now,
            )

        finally:
            if should_close:
                conn.close()

    def get_compliance_status(
        self,
        institution_id: str,
        state_code: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        """Get compliance status for all requirements in a state."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            cursor = conn.execute("""
                SELECT
                    r.id as requirement_id,
                    r.state_code,
                    r.requirement_key,
                    r.requirement_name,
                    r.requirement_text,
                    r.category,
                    r.required,
                    COALESCE(c.status, 'missing') as status,
                    c.id as compliance_id,
                    c.evidence_doc_id,
                    c.page_reference,
                    c.notes as compliance_notes
                FROM state_catalog_requirements r
                LEFT JOIN state_catalog_compliance c
                    ON c.requirement_id = r.id
                    AND c.institution_id = ?
                WHERE r.state_code = ?
                ORDER BY r.category, r.requirement_key
            """, (institution_id, state_code))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            if should_close:
                conn.close()

    def update_compliance(
        self,
        institution_id: str,
        requirement_id: str,
        status: str,
        evidence_doc_id: Optional[str] = None,
        page_reference: Optional[str] = None,
        notes: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> StateCatalogCompliance:
        """Update or create compliance record for a requirement."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            # Get state_code from requirement
            cursor = conn.execute("""
                SELECT state_code FROM state_catalog_requirements WHERE id = ?
            """, (requirement_id,))
            req_row = cursor.fetchone()
            state_code = req_row["state_code"] if req_row else ""

            now = now_iso()
            comp_id = generate_id("stcomp")

            # Use INSERT OR REPLACE for upsert behavior
            conn.execute("""
                INSERT INTO state_catalog_compliance (
                    id, institution_id, state_code, requirement_id,
                    status, evidence_doc_id, page_reference, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(institution_id, requirement_id) DO UPDATE SET
                    status = excluded.status,
                    evidence_doc_id = excluded.evidence_doc_id,
                    page_reference = excluded.page_reference,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
            """, (
                comp_id, institution_id, state_code, requirement_id,
                status, evidence_doc_id, page_reference, notes, now, now
            ))
            conn.commit()

            # Fetch the actual record (may have different ID if updated)
            cursor = conn.execute("""
                SELECT * FROM state_catalog_compliance
                WHERE institution_id = ? AND requirement_id = ?
            """, (institution_id, requirement_id))
            row = cursor.fetchone()

            return StateCatalogCompliance.from_dict(dict(row))

        finally:
            if should_close:
                conn.close()

    # =========================================================================
    # Program Approval Methods
    # =========================================================================

    def add_program_approval(
        self,
        institution_id: str,
        program_id: str,
        state_code: str,
        board_name: str,
        approved: bool = False,
        approval_date: Optional[str] = None,
        expiration_date: Optional[str] = None,
        license_exam: Optional[str] = None,
        min_pass_rate: Optional[float] = None,
        current_pass_rate: Optional[float] = None,
        board_url: Optional[str] = None,
        notes: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> StateProgramApproval:
        """Add a new program approval record."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            approval_id = generate_id("stprog")
            now = now_iso()

            conn.execute("""
                INSERT INTO state_program_approvals (
                    id, institution_id, program_id, state_code, board_name,
                    board_url, approved, approval_date, expiration_date,
                    license_exam, min_pass_rate, current_pass_rate,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                approval_id, institution_id, program_id, state_code, board_name,
                board_url, approved, approval_date, expiration_date,
                license_exam, min_pass_rate, current_pass_rate,
                notes, now, now
            ))
            conn.commit()

            return StateProgramApproval(
                id=approval_id,
                institution_id=institution_id,
                program_id=program_id,
                state_code=state_code,
                board_name=board_name,
                board_url=board_url,
                approved=approved,
                approval_date=approval_date,
                expiration_date=expiration_date,
                license_exam=license_exam,
                min_pass_rate=min_pass_rate,
                current_pass_rate=current_pass_rate,
                notes=notes,
                created_at=now,
                updated_at=now,
            )

        finally:
            if should_close:
                conn.close()

    def get_program_approvals(
        self,
        institution_id: str,
        state_code: Optional[str] = None,
        program_id: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[StateProgramApproval]:
        """Get program approvals with optional filters."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            query = "SELECT * FROM state_program_approvals WHERE institution_id = ?"
            params: List[Any] = [institution_id]

            if state_code:
                query += " AND state_code = ?"
                params.append(state_code)

            if program_id:
                query += " AND program_id = ?"
                params.append(program_id)

            query += " ORDER BY state_code, board_name"

            cursor = conn.execute(query, params)

            return [
                StateProgramApproval.from_dict(dict(row))
                for row in cursor.fetchall()
            ]

        finally:
            if should_close:
                conn.close()

    def update_program_approval(
        self,
        approval_id: str,
        conn: Optional[sqlite3.Connection] = None,
        **updates
    ) -> Optional[StateProgramApproval]:
        """Update an existing program approval."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            # Build dynamic update query
            allowed_fields = [
                "board_name", "board_url", "approved", "approval_date",
                "expiration_date", "license_exam", "min_pass_rate",
                "current_pass_rate", "notes"
            ]
            set_clauses = []
            params = []

            for field in allowed_fields:
                if field in updates:
                    set_clauses.append(f"{field} = ?")
                    params.append(updates[field])

            if not set_clauses:
                return self._get_program_approval_by_id(approval_id, conn)

            set_clauses.append("updated_at = ?")
            params.append(now_iso())
            params.append(approval_id)

            conn.execute(f"""
                UPDATE state_program_approvals
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """, params)
            conn.commit()

            return self._get_program_approval_by_id(approval_id, conn)

        finally:
            if should_close:
                conn.close()

    def _get_program_approval_by_id(
        self,
        approval_id: str,
        conn: sqlite3.Connection
    ) -> Optional[StateProgramApproval]:
        """Get program approval by ID (internal helper)."""
        cursor = conn.execute("""
            SELECT * FROM state_program_approvals WHERE id = ?
        """, (approval_id,))
        row = cursor.fetchone()
        if row:
            return StateProgramApproval.from_dict(dict(row))
        return None

    def delete_program_approval(
        self,
        approval_id: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Delete a program approval."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            cursor = conn.execute("""
                DELETE FROM state_program_approvals WHERE id = ?
            """, (approval_id,))
            conn.commit()
            return cursor.rowcount > 0

        finally:
            if should_close:
                conn.close()

    # =========================================================================
    # Scoring Methods
    # =========================================================================

    def compute_state_readiness(
        self,
        institution_id: str,
        state_code: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> StateReadinessScore:
        """Compute readiness score for a specific state."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            breakdown = {}

            # 1. Authorization score (0-100)
            auth = self.get_authorization(institution_id, state_code, conn)
            if auth:
                if auth.authorization_status == "authorized":
                    auth_score = 100
                elif auth.authorization_status == "pending":
                    auth_score = 50
                elif auth.authorization_status == "restricted":
                    auth_score = 25
                else:  # denied
                    auth_score = 0
                breakdown["authorization"] = {
                    "status": auth.authorization_status,
                    "sara_member": auth.sara_member,
                    "renewal_date": auth.renewal_date,
                }
            else:
                auth_score = 0
                breakdown["authorization"] = {"status": "not_tracked"}

            # 2. Catalog compliance score (0-100)
            compliance_status = self.get_compliance_status(institution_id, state_code, conn)
            if compliance_status:
                total_required = len([c for c in compliance_status if c.get("required")])
                satisfied = len([c for c in compliance_status if c.get("status") == "satisfied"])
                partial = len([c for c in compliance_status if c.get("status") == "partial"])

                if total_required > 0:
                    catalog_score = int(((satisfied + partial * 0.5) / total_required) * 100)
                else:
                    catalog_score = 100  # No requirements = 100%
                breakdown["catalog"] = {
                    "total_requirements": total_required,
                    "satisfied": satisfied,
                    "partial": partial,
                    "missing": total_required - satisfied - partial,
                }
            else:
                catalog_score = 100  # No requirements = 100%
                breakdown["catalog"] = {"total_requirements": 0}

            # 3. Program approval score (0-100)
            approvals = self.get_program_approvals(institution_id, state_code, conn=conn)
            if approvals:
                total_programs = len(approvals)
                approved_count = 0
                for appr in approvals:
                    if appr.approved:
                        # Check pass rate if applicable
                        if appr.min_pass_rate and appr.current_pass_rate:
                            if appr.current_pass_rate >= appr.min_pass_rate:
                                approved_count += 1
                            else:
                                approved_count += 0.5  # Partial credit
                        else:
                            approved_count += 1

                program_score = int((approved_count / total_programs) * 100) if total_programs > 0 else 100
                breakdown["program"] = {
                    "total_programs": total_programs,
                    "approved": len([a for a in approvals if a.approved]),
                    "meeting_pass_rate": int(approved_count),
                }
            else:
                program_score = 100  # No programs tracked = 100%
                breakdown["program"] = {"total_programs": 0}

            # 4. Weighted total
            total = int(
                auth_score * STATE_SCORE_WEIGHTS["authorization"] +
                catalog_score * STATE_SCORE_WEIGHTS["catalog"] +
                program_score * STATE_SCORE_WEIGHTS["program"]
            )

            return StateReadinessScore(
                state_code=state_code,
                total=total,
                authorization_score=auth_score,
                catalog_score=catalog_score,
                program_score=program_score,
                breakdown=breakdown,
            )

        finally:
            if should_close:
                conn.close()

    def get_all_states_summary(
        self,
        institution_id: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[StateSummary]:
        """Get summary for all states with authorizations."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            # Get all states with authorizations
            cursor = conn.execute("""
                SELECT DISTINCT state_code FROM state_authorizations
                WHERE institution_id = ?
                ORDER BY state_code
            """, (institution_id,))

            summaries = []
            for row in cursor.fetchall():
                state_code = row["state_code"]

                # Get authorization
                auth = self.get_authorization(institution_id, state_code, conn)

                # Get catalog compliance percentage
                compliance_status = self.get_compliance_status(institution_id, state_code, conn)
                total_required = len([c for c in compliance_status if c.get("required")])
                satisfied = len([c for c in compliance_status if c.get("status") == "satisfied"])
                catalog_pct = int((satisfied / total_required) * 100) if total_required > 0 else 100

                # Get program approval counts
                approvals = self.get_program_approvals(institution_id, state_code, conn=conn)
                programs_total = len(approvals)
                programs_approved = len([a for a in approvals if a.approved])

                # Compute overall score
                readiness = self.compute_state_readiness(institution_id, state_code, conn)

                summaries.append(StateSummary(
                    state_code=state_code,
                    state_name=STATE_NAMES.get(state_code, state_code),
                    authorization_status=auth.authorization_status if auth else "not_tracked",
                    sara_member=auth.sara_member if auth else False,
                    renewal_date=auth.renewal_date if auth else None,
                    catalog_compliance_pct=catalog_pct,
                    programs_approved=programs_approved,
                    programs_total=programs_total,
                    overall_score=readiness.total,
                ))

            return summaries

        finally:
            if should_close:
                conn.close()

    # =========================================================================
    # Calendar Integration
    # =========================================================================

    def get_upcoming_renewals(
        self,
        institution_id: str,
        days_ahead: int = 90,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        """Get upcoming authorization renewals and approval expirations."""
        should_close = conn is None
        if conn is None:
            conn = get_conn()

        try:
            today = datetime.now(timezone.utc).date().isoformat()
            cutoff = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date().isoformat()

            results = []

            # Authorization renewals
            cursor = conn.execute("""
                SELECT id, state_code, renewal_date, 'authorization' as type
                FROM state_authorizations
                WHERE institution_id = ?
                  AND renewal_date IS NOT NULL
                  AND renewal_date >= ?
                  AND renewal_date <= ?
                ORDER BY renewal_date
            """, (institution_id, today, cutoff))

            for row in cursor.fetchall():
                renewal_date = row["renewal_date"]
                if renewal_date:
                    due_date = datetime.fromisoformat(renewal_date.replace("Z", "+00:00"))
                    days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                    results.append({
                        "type": "authorization_renewal",
                        "state_code": row["state_code"],
                        "item_name": f"{STATE_NAMES.get(row['state_code'], row['state_code'])} Authorization",
                        "due_date": renewal_date,
                        "days_until": days_until,
                        "id": row["id"],
                    })

            # Program approval expirations
            cursor = conn.execute("""
                SELECT id, state_code, board_name, expiration_date, 'program_approval' as type
                FROM state_program_approvals
                WHERE institution_id = ?
                  AND expiration_date IS NOT NULL
                  AND expiration_date >= ?
                  AND expiration_date <= ?
                ORDER BY expiration_date
            """, (institution_id, today, cutoff))

            for row in cursor.fetchall():
                exp_date = row["expiration_date"]
                if exp_date:
                    due_date = datetime.fromisoformat(exp_date.replace("Z", "+00:00"))
                    days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                    results.append({
                        "type": "program_approval_expiration",
                        "state_code": row["state_code"],
                        "item_name": f"{row['board_name']} Approval",
                        "due_date": exp_date,
                        "days_until": days_until,
                        "id": row["id"],
                    })

            # Sort by due date
            results.sort(key=lambda x: x["due_date"])

            return results

        finally:
            if should_close:
                conn.close()


# =============================================================================
# Module-level convenience functions
# =============================================================================

_service = StateRegulatoryService()


def add_authorization(
    institution_id: str,
    state_code: str,
    authorization_status: str,
    **kwargs
) -> StateAuthorization:
    """Add a state authorization (module-level convenience)."""
    return _service.add_authorization(institution_id, state_code, authorization_status, **kwargs)


def get_authorizations(institution_id: str) -> List[StateAuthorization]:
    """Get all authorizations for an institution (module-level convenience)."""
    return _service.get_authorizations(institution_id)


def compute_state_readiness(
    institution_id: str,
    state_code: str
) -> StateReadinessScore:
    """Compute state readiness score (module-level convenience)."""
    return _service.compute_state_readiness(institution_id, state_code)


def get_all_states_summary(institution_id: str) -> List[StateSummary]:
    """Get all states summary (module-level convenience)."""
    return _service.get_all_states_summary(institution_id)


def get_upcoming_renewals(institution_id: str, days_ahead: int = 90) -> List[Dict[str, Any]]:
    """Get upcoming renewals (module-level convenience)."""
    return _service.get_upcoming_renewals(institution_id, days_ahead)
