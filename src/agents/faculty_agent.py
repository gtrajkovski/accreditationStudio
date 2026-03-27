"""Faculty Agent.

Manages faculty credential compliance, verification, and reporting.
Tracks academic credentials, professional licenses, and teaching qualifications.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    FacultyMember,
    AcademicCredential,
    ProfessionalLicense,
    TeachingAssignment,
    FacultyComplianceStatus,
    EmploymentType,
    CredentialType,
    now_iso,
    generate_id,
)
from src.config import Config


@register_agent(AgentType.FACULTY)
class FacultyAgent(BaseAgent):
    """Agent for managing faculty credentials and compliance.

    Provides tools for:
    - Listing and filtering faculty members
    - Managing credentials and licenses
    - Checking teaching qualifications
    - Verifying licenses online
    - Generating compliance reports
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._faculty_cache: Dict[str, FacultyMember] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.FACULTY

    @property
    def system_prompt(self) -> str:
        return """You are a faculty credential compliance specialist. Your responsibilities:

1. Track faculty academic credentials (degrees, certifications)
2. Monitor professional license status and expirations
3. Verify faculty qualifications for their teaching assignments
4. Flag compliance issues before they become problems
5. Generate compliance reports for accreditation reviews

Key compliance requirements:
- Faculty must have appropriate credentials for courses they teach
- Professional licenses must be current and verified
- Foreign credentials need proper evaluation
- Teaching assignments must match qualification basis

When checking compliance, consider:
- Accreditor-specific faculty qualification standards
- State licensing requirements
- Programmatic accreditor requirements
- Professional body expectations

Always cite specific credential gaps and provide actionable recommendations."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_faculty",
                "description": "List faculty members with optional filters.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "status_filter": {
                            "type": "string",
                            "enum": ["all", "compliant", "pending_verification",
                                     "expiring_soon", "expired", "non_compliant"],
                            "default": "all",
                        },
                        "employment_type": {
                            "type": "string",
                            "enum": ["all", "fulltime", "parttime", "adjunct"],
                            "default": "all",
                        },
                        "department": {"type": "string"},
                        "active_only": {"type": "boolean", "default": True},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "get_faculty_member",
                "description": "Get full details of a faculty member.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "faculty_id": {"type": "string"},
                    },
                    "required": ["institution_id", "faculty_id"],
                },
            },
            {
                "name": "add_faculty_member",
                "description": "Add a new faculty member.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "title": {"type": "string"},
                        "department": {"type": "string"},
                        "employment_type": {
                            "type": "string",
                            "enum": ["fulltime", "parttime", "adjunct"],
                            "default": "fulltime",
                        },
                        "employment_start_date": {"type": "string"},
                    },
                    "required": ["institution_id", "first_name", "last_name"],
                },
            },
            {
                "name": "update_faculty_credentials",
                "description": "Add or update credentials/licenses for a faculty member.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "faculty_id": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["add_credential", "add_license", "update_credential", "update_license"],
                        },
                        "credential_data": {
                            "type": "object",
                            "description": "Credential or license data",
                        },
                    },
                    "required": ["institution_id", "faculty_id", "action", "credential_data"],
                },
            },
            {
                "name": "check_teaching_qualifications",
                "description": "Cross-check faculty credentials against their teaching assignments.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "faculty_id": {
                            "type": "string",
                            "description": "Specific faculty ID or 'all' for all faculty",
                        },
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "verify_license_online",
                "description": "Attempt to verify a professional license status online.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "faculty_id": {"type": "string"},
                        "license_id": {"type": "string"},
                    },
                    "required": ["institution_id", "faculty_id", "license_id"],
                },
            },
            {
                "name": "generate_compliance_report",
                "description": "Generate a faculty compliance summary report.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "include_details": {"type": "boolean", "default": True},
                        "format": {
                            "type": "string",
                            "enum": ["summary", "detailed", "export"],
                            "default": "detailed",
                        },
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "update_assignments",
                "description": "Add or remove teaching assignments for a faculty member.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "faculty_id": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["add", "remove"],
                        },
                        "assignment_data": {
                            "type": "object",
                            "description": "Assignment data (course_code, course_name, etc.)",
                        },
                    },
                    "required": ["institution_id", "faculty_id", "action", "assignment_data"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "list_faculty": self._tool_list_faculty,
            "get_faculty_member": self._tool_get_faculty_member,
            "add_faculty_member": self._tool_add_faculty_member,
            "update_faculty_credentials": self._tool_update_credentials,
            "update_assignments": self._tool_update_assignments,
            "check_teaching_qualifications": self._tool_check_qualifications,
            "verify_license_online": self._tool_verify_license,
            "generate_compliance_report": self._tool_generate_report,
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _load_faculty_registry(self, institution_id: str) -> List[FacultyMember]:
        """Load all faculty members for an institution."""
        if not self.workspace_manager:
            return []

        data = self.workspace_manager.load_file(
            institution_id, "faculty/faculty_registry.json"
        )
        if not data:
            return []

        members = []
        for fac_data in data.get("members", []):
            try:
                member = FacultyMember.from_dict(fac_data)
                members.append(member)
                self._faculty_cache[member.id] = member
            except Exception as e:
                logger.debug("Failed to parse faculty member: %s", e)
                continue
        return members

    def _save_faculty_registry(self, institution_id: str, members: List[FacultyMember]) -> None:
        """Save faculty registry to workspace."""
        if not self.workspace_manager:
            return

        data = {
            "members": [m.to_dict() for m in members],
            "updated_at": now_iso(),
        }
        self.workspace_manager.save_file(
            institution_id, "faculty/faculty_registry.json", data
        )

    def _tool_list_faculty(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List faculty members with filters."""
        institution_id = params["institution_id"]
        status_filter = params.get("status_filter", "all")
        employment_type = params.get("employment_type", "all")
        department = params.get("department")
        active_only = params.get("active_only", True)

        members = self._load_faculty_registry(institution_id)

        # Apply filters
        if active_only:
            members = [m for m in members if m.is_active]

        if status_filter != "all":
            members = [m for m in members if m.compliance_status.value == status_filter]

        if employment_type != "all":
            members = [m for m in members if m.employment_type.value == employment_type]

        if department:
            members = [m for m in members if m.department.lower() == department.lower()]

        # Build summary
        faculty_list = []
        for m in members:
            expiring_licenses = self._count_expiring_licenses(m)
            faculty_list.append({
                "id": m.id,
                "name": m.full_name,
                "title": m.title,
                "department": m.department,
                "employment_type": m.employment_type.value,
                "compliance_status": m.compliance_status.value,
                "credential_count": len(m.academic_credentials),
                "license_count": len(m.professional_licenses),
                "expiring_licenses": expiring_licenses,
                "assignment_count": len(m.teaching_assignments),
            })

        return {
            "success": True,
            "total": len(faculty_list),
            "faculty": faculty_list,
        }

    def _count_expiring_licenses(self, member: FacultyMember, days: int = 90) -> int:
        """Count licenses expiring within N days."""
        count = 0
        today = datetime.now(timezone.utc)
        threshold = today + timedelta(days=days)

        for lic in member.professional_licenses:
            if lic.expiration_date:
                try:
                    exp_date = datetime.fromisoformat(lic.expiration_date.replace("Z", ""))
                    if today < exp_date <= threshold:
                        count += 1
                except ValueError:
                    continue
        return count

    def _tool_get_faculty_member(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get full faculty member details."""
        institution_id = params["institution_id"]
        faculty_id = params["faculty_id"]

        # Check cache first
        if faculty_id in self._faculty_cache:
            member = self._faculty_cache[faculty_id]
        else:
            members = self._load_faculty_registry(institution_id)
            member = next((m for m in members if m.id == faculty_id), None)

        if not member:
            return {"error": f"Faculty member {faculty_id} not found"}

        return {
            "success": True,
            "faculty": member.to_dict(),
        }

    def _tool_add_faculty_member(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new faculty member."""
        institution_id = params["institution_id"]

        member = FacultyMember(
            institution_id=institution_id,
            first_name=params["first_name"],
            last_name=params["last_name"],
            email=params.get("email", ""),
            title=params.get("title", ""),
            department=params.get("department", ""),
            employment_type=EmploymentType(params.get("employment_type", "fulltime")),
            employment_start_date=params.get("employment_start_date"),
        )

        members = self._load_faculty_registry(institution_id)
        members.append(member)
        self._save_faculty_registry(institution_id, members)
        self._faculty_cache[member.id] = member

        return {
            "success": True,
            "faculty_id": member.id,
            "name": member.full_name,
            "message": f"Added faculty member: {member.full_name}",
        }

    def _tool_update_credentials(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update credentials/licenses."""
        institution_id = params["institution_id"]
        faculty_id = params["faculty_id"]
        action = params["action"]
        cred_data = params["credential_data"]

        members = self._load_faculty_registry(institution_id)
        member = next((m for m in members if m.id == faculty_id), None)

        if not member:
            return {"error": f"Faculty member {faculty_id} not found"}

        if action == "add_credential":
            credential = AcademicCredential(
                credential_type=CredentialType(cred_data.get("credential_type", "degree")),
                title=cred_data.get("title", ""),
                field_of_study=cred_data.get("field_of_study", ""),
                institution_name=cred_data.get("institution_name", ""),
                year_awarded=cred_data.get("year_awarded"),
                transcript_on_file=cred_data.get("transcript_on_file", False),
                transcript_path=cred_data.get("transcript_path"),
                notes=cred_data.get("notes", ""),
            )
            member.academic_credentials.append(credential)
            result_msg = f"Added credential: {credential.title}"

        elif action == "add_license":
            license_obj = ProfessionalLicense(
                license_type=cred_data.get("license_type", ""),
                license_number=cred_data.get("license_number", ""),
                issuing_authority=cred_data.get("issuing_authority", ""),
                state_code=cred_data.get("state_code", ""),
                issued_date=cred_data.get("issued_date"),
                expiration_date=cred_data.get("expiration_date"),
                status=cred_data.get("status", "active"),
                verification_url=cred_data.get("verification_url"),
            )
            member.professional_licenses.append(license_obj)
            result_msg = f"Added license: {license_obj.license_type}"

        elif action == "update_credential":
            cred_id = cred_data.get("id")
            credential = next(
                (c for c in member.academic_credentials if c.id == cred_id), None
            )
            if not credential:
                return {"error": f"Credential {cred_id} not found"}

            for key, value in cred_data.items():
                if hasattr(credential, key) and key != "id":
                    setattr(credential, key, value)
            result_msg = f"Updated credential: {credential.title}"

        elif action == "update_license":
            lic_id = cred_data.get("id")
            license_obj = next(
                (l for l in member.professional_licenses if l.id == lic_id), None
            )
            if not license_obj:
                return {"error": f"License {lic_id} not found"}

            for key, value in cred_data.items():
                if hasattr(license_obj, key) and key != "id":
                    setattr(license_obj, key, value)
            result_msg = f"Updated license: {license_obj.license_type}"
        else:
            return {"error": f"Unknown action: {action}"}

        member.updated_at = now_iso()
        self._save_faculty_registry(institution_id, members)
        self._faculty_cache[member.id] = member

        # Recheck compliance after credential change
        self._update_compliance_status(member)

        return {
            "success": True,
            "message": result_msg,
            "compliance_status": member.compliance_status.value,
        }

    def _tool_update_assignments(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add or remove teaching assignments."""
        institution_id = params["institution_id"]
        faculty_id = params["faculty_id"]
        action = params["action"]
        assign_data = params["assignment_data"]

        members = self._load_faculty_registry(institution_id)
        member = next((m for m in members if m.id == faculty_id), None)

        if not member:
            return {"error": f"Faculty member {faculty_id} not found"}

        if action == "add":
            assignment = TeachingAssignment(
                program_id=assign_data.get("program_id"),
                course_code=assign_data.get("course_code", ""),
                course_name=assign_data.get("course_name", ""),
                start_date=assign_data.get("start_date"),
                end_date=assign_data.get("end_date"),
                qualification_basis=assign_data.get("qualification_basis", "degree"),
                qualification_notes=assign_data.get("qualification_notes", ""),
            )
            member.teaching_assignments.append(assignment)
            result_msg = f"Added assignment: {assignment.course_code} - {assignment.course_name}"

        elif action == "remove":
            assign_id = assign_data.get("id")
            assignment = next(
                (a for a in member.teaching_assignments if a.id == assign_id), None
            )
            if not assignment:
                return {"error": f"Assignment {assign_id} not found"}

            member.teaching_assignments.remove(assignment)
            result_msg = f"Removed assignment: {assignment.course_code}"

        else:
            return {"error": f"Unknown action: {action}"}

        member.updated_at = now_iso()
        self._save_faculty_registry(institution_id, members)
        self._faculty_cache[member.id] = member

        # Recheck compliance after assignment change
        self._update_compliance_status(member)

        return {
            "success": True,
            "message": result_msg,
            "assignment_count": len(member.teaching_assignments),
            "compliance_status": member.compliance_status.value,
        }

    def _update_compliance_status(self, member: FacultyMember) -> None:
        """Update compliance status based on credentials and licenses."""
        issues = []

        # Check for expired licenses
        today = datetime.now(timezone.utc)
        for lic in member.professional_licenses:
            if lic.expiration_date:
                try:
                    exp_date = datetime.fromisoformat(lic.expiration_date.replace("Z", ""))
                    if exp_date < today:
                        issues.append(f"Expired license: {lic.license_type}")
                    elif exp_date <= today + timedelta(days=90):
                        issues.append(f"License expiring soon: {lic.license_type}")
                except ValueError:
                    pass

        # Check unverified credentials
        unverified = [c for c in member.academic_credentials if not c.verified]
        if unverified:
            issues.append(f"{len(unverified)} unverified credential(s)")

        # Check teaching qualifications
        unqualified = [t for t in member.teaching_assignments if not t.is_qualified]
        if unqualified:
            issues.append(f"{len(unqualified)} unqualified teaching assignment(s)")

        # Update status
        member.compliance_issues = issues

        if any("Expired" in i for i in issues):
            member.compliance_status = FacultyComplianceStatus.EXPIRED
        elif any("unqualified" in i.lower() for i in issues):
            member.compliance_status = FacultyComplianceStatus.NON_COMPLIANT
        elif any("expiring" in i.lower() for i in issues):
            member.compliance_status = FacultyComplianceStatus.EXPIRING_SOON
        elif any("unverified" in i.lower() for i in issues):
            member.compliance_status = FacultyComplianceStatus.PENDING_VERIFICATION
        elif issues:
            member.compliance_status = FacultyComplianceStatus.NEEDS_REVIEW
        else:
            member.compliance_status = FacultyComplianceStatus.COMPLIANT

        member.last_compliance_check = now_iso()

    def _tool_check_qualifications(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check teaching qualifications for faculty."""
        institution_id = params["institution_id"]
        faculty_id = params.get("faculty_id", "all")

        members = self._load_faculty_registry(institution_id)

        if faculty_id != "all":
            members = [m for m in members if m.id == faculty_id]
            if not members:
                return {"error": f"Faculty member {faculty_id} not found"}

        results = []
        for member in members:
            member_result = {
                "faculty_id": member.id,
                "name": member.full_name,
                "assignments": [],
                "issues": [],
            }

            for assignment in member.teaching_assignments:
                # Check if faculty has required credentials
                qualified = self._check_assignment_qualification(member, assignment)
                assignment_result = {
                    "course_code": assignment.course_code,
                    "course_name": assignment.course_name,
                    "is_qualified": qualified,
                    "qualification_basis": assignment.qualification_basis,
                    "notes": assignment.qualification_notes,
                }
                member_result["assignments"].append(assignment_result)

                if not qualified:
                    member_result["issues"].append(
                        f"Not qualified for {assignment.course_code}: {assignment.course_name}"
                    )
                    assignment.is_qualified = False
                else:
                    assignment.is_qualified = True

            # Update compliance
            self._update_compliance_status(member)
            results.append(member_result)

        # Save updates
        self._save_faculty_registry(institution_id, members)

        total_issues = sum(len(r["issues"]) for r in results)
        return {
            "success": True,
            "faculty_checked": len(results),
            "total_issues": total_issues,
            "results": results,
        }

    def _check_assignment_qualification(
        self, member: FacultyMember, assignment: TeachingAssignment
    ) -> bool:
        """Check if faculty is qualified for an assignment."""
        # Basic checks based on qualification_basis
        basis = assignment.qualification_basis.lower()

        if basis == "degree":
            # Check for relevant degree
            return any(
                c.credential_type == CredentialType.DEGREE
                and c.field_of_study.lower() in assignment.course_name.lower()
                for c in member.academic_credentials
            ) or len(member.academic_credentials) > 0

        elif basis == "license":
            # Check for active license
            return any(
                lic.status == "active"
                for lic in member.professional_licenses
            )

        elif basis == "experience":
            # Check for sufficient experience
            return member.work_experience_years >= 3

        elif basis == "combination":
            # Any credential + experience
            has_credential = len(member.academic_credentials) > 0
            has_experience = member.work_experience_years >= 2
            return has_credential and has_experience

        # Default: if they have any credentials, consider qualified
        return len(member.academic_credentials) > 0

    def _tool_verify_license(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to verify a license online."""
        institution_id = params["institution_id"]
        faculty_id = params["faculty_id"]
        license_id = params["license_id"]

        members = self._load_faculty_registry(institution_id)
        member = next((m for m in members if m.id == faculty_id), None)

        if not member:
            return {"error": f"Faculty member {faculty_id} not found"}

        license_obj = next(
            (l for l in member.professional_licenses if l.id == license_id), None
        )
        if not license_obj:
            return {"error": f"License {license_id} not found"}

        # Build verification prompt for AI
        verification_prompt = f"""Verify this professional license:

License Type: {license_obj.license_type}
License Number: {license_obj.license_number}
State: {license_obj.state_code}
Issuing Authority: {license_obj.issuing_authority}

Please provide:
1. Whether this license appears to be valid
2. The verification URL for the state licensing board
3. Any notes about verification status

Note: This is for informational purposes. Manual verification is still required."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": verification_prompt}],
            )
            verification_result = response.content[0].text

            # Update license with verification attempt
            license_obj.last_verified_at = now_iso()
            license_obj.verification_method = "ai_assisted"

            self._save_faculty_registry(institution_id, members)

            return {
                "success": True,
                "license_id": license_id,
                "verification_result": verification_result,
                "verified_at": license_obj.last_verified_at,
                "note": "Manual verification recommended for official compliance",
            }
        except Exception as e:
            return {
                "error": f"Verification failed: {str(e)}",
                "suggestion": "Please verify manually at the state licensing board website",
            }

    def _tool_generate_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate faculty compliance report."""
        institution_id = params["institution_id"]
        include_details = params.get("include_details", True)
        report_format = params.get("format", "detailed")

        members = self._load_faculty_registry(institution_id)

        # Update all compliance statuses
        for member in members:
            self._update_compliance_status(member)
        self._save_faculty_registry(institution_id, members)

        # Calculate statistics
        total = len(members)
        active = len([m for m in members if m.is_active])

        by_status = {}
        for status in FacultyComplianceStatus:
            by_status[status.value] = len(
                [m for m in members if m.compliance_status == status]
            )

        by_employment = {}
        for emp_type in EmploymentType:
            by_employment[emp_type.value] = len(
                [m for m in members if m.employment_type == emp_type]
            )

        # Count expiring licenses
        expiring_30 = sum(self._count_expiring_licenses(m, 30) for m in members)
        expiring_90 = sum(self._count_expiring_licenses(m, 90) for m in members)

        # Build report
        report = {
            "institution_id": institution_id,
            "generated_at": now_iso(),
            "summary": {
                "total_faculty": total,
                "active_faculty": active,
                "by_compliance_status": by_status,
                "by_employment_type": by_employment,
                "licenses_expiring_30_days": expiring_30,
                "licenses_expiring_90_days": expiring_90,
            },
        }

        if include_details and report_format != "summary":
            # Add issue details
            issues_list = []
            for m in members:
                if m.compliance_issues:
                    issues_list.append({
                        "faculty_id": m.id,
                        "name": m.full_name,
                        "status": m.compliance_status.value,
                        "issues": m.compliance_issues,
                    })
            report["issues"] = issues_list

            # Add expiring licenses detail
            expiring_detail = []
            today = datetime.now(timezone.utc)
            threshold = today + timedelta(days=90)
            for m in members:
                for lic in m.professional_licenses:
                    if lic.expiration_date:
                        try:
                            exp_date = datetime.fromisoformat(
                                lic.expiration_date.replace("Z", "")
                            )
                            if today < exp_date <= threshold:
                                expiring_detail.append({
                                    "faculty_id": m.id,
                                    "faculty_name": m.full_name,
                                    "license_type": lic.license_type,
                                    "expiration_date": lic.expiration_date,
                                    "days_remaining": (exp_date - today).days,
                                })
                        except ValueError:
                            continue
            report["expiring_licenses"] = sorted(
                expiring_detail, key=lambda x: x["expiration_date"]
            )

        if report_format == "export":
            # Save report to workspace
            report_path = f"faculty/reports/compliance_report_{now_iso()[:10]}.json"
            self.workspace_manager.save_file(institution_id, report_path, report)
            report["exported_to"] = report_path

        return {
            "success": True,
            "report": report,
        }

    # Workflow methods for direct invocation
    def check_all_faculty_compliance(self, institution_id: str) -> Dict[str, Any]:
        """Check compliance for all faculty members."""
        result = self._tool_check_qualifications({
            "institution_id": institution_id,
            "faculty_id": "all",
        })

        report = self._tool_generate_report({
            "institution_id": institution_id,
            "include_details": True,
            "format": "detailed",
        })

        return {
            "qualification_check": result,
            "compliance_report": report.get("report", {}),
        }

    def get_expiring_licenses(
        self, institution_id: str, days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get list of licenses expiring within N days."""
        members = self._load_faculty_registry(institution_id)
        expiring = []

        today = datetime.now(timezone.utc)
        threshold = today + timedelta(days=days)

        for m in members:
            for lic in m.professional_licenses:
                if lic.expiration_date:
                    try:
                        exp_date = datetime.fromisoformat(
                            lic.expiration_date.replace("Z", "")
                        )
                        if today < exp_date <= threshold:
                            expiring.append({
                                "faculty_id": m.id,
                                "faculty_name": m.full_name,
                                "license_id": lic.id,
                                "license_type": lic.license_type,
                                "expiration_date": lic.expiration_date,
                                "days_remaining": (exp_date - today).days,
                            })
                    except ValueError:
                        continue

        return sorted(expiring, key=lambda x: x["expiration_date"])
