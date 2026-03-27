"""Faculty domain models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso


class EmploymentType(str, Enum):
    """Faculty employment types."""
    FULLTIME = "fulltime"
    PARTTIME = "parttime"
    ADJUNCT = "adjunct"


class CredentialType(str, Enum):
    """Types of academic/professional credentials."""
    DEGREE = "degree"
    LICENSE = "license"
    CERTIFICATION = "certification"
    INDUSTRY_EXPERIENCE = "industry_experience"


class FacultyComplianceStatus(str, Enum):
    """Faculty credential compliance status."""
    COMPLIANT = "compliant"
    PENDING_VERIFICATION = "pending_verification"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    NEEDS_REVIEW = "needs_review"
    NON_COMPLIANT = "non_compliant"


@dataclass
class AcademicCredential:
    """An academic degree or credential."""
    id: str = field(default_factory=lambda: generate_id("cred"))
    credential_type: CredentialType = CredentialType.DEGREE
    title: str = ""  # e.g., "Master of Science in Nursing"
    field_of_study: str = ""  # e.g., "Nursing"
    institution_name: str = ""
    year_awarded: Optional[int] = None
    transcript_on_file: bool = False
    transcript_path: Optional[str] = None
    verified: bool = False
    verified_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "credential_type": self.credential_type.value,
            "title": self.title,
            "field_of_study": self.field_of_study,
            "institution_name": self.institution_name,
            "year_awarded": self.year_awarded,
            "transcript_on_file": self.transcript_on_file,
            "transcript_path": self.transcript_path,
            "verified": self.verified,
            "verified_at": self.verified_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcademicCredential":
        return cls(
            id=data.get("id", generate_id("cred")),
            credential_type=CredentialType(data.get("credential_type", "degree")),
            title=data.get("title", ""),
            field_of_study=data.get("field_of_study", ""),
            institution_name=data.get("institution_name", ""),
            year_awarded=data.get("year_awarded"),
            transcript_on_file=data.get("transcript_on_file", False),
            transcript_path=data.get("transcript_path"),
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
            notes=data.get("notes", ""),
        )


@dataclass
class ProfessionalLicense:
    """A professional license or certification."""
    id: str = field(default_factory=lambda: generate_id("lic"))
    license_type: str = ""  # e.g., "RN", "CPA", "PE"
    license_number: str = ""
    issuing_authority: str = ""  # e.g., "Puerto Rico Board of Nursing"
    state_code: str = ""  # e.g., "PR", "FL"
    issued_date: Optional[str] = None
    expiration_date: Optional[str] = None
    status: str = "active"  # active, expired, suspended, pending_renewal
    verification_url: Optional[str] = None
    last_verified_at: Optional[str] = None
    verification_method: str = ""  # "manual", "web_api", "web_scrape"
    document_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "license_type": self.license_type,
            "license_number": self.license_number,
            "issuing_authority": self.issuing_authority,
            "state_code": self.state_code,
            "issued_date": self.issued_date,
            "expiration_date": self.expiration_date,
            "status": self.status,
            "verification_url": self.verification_url,
            "last_verified_at": self.last_verified_at,
            "verification_method": self.verification_method,
            "document_path": self.document_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfessionalLicense":
        return cls(
            id=data.get("id", generate_id("lic")),
            license_type=data.get("license_type", ""),
            license_number=data.get("license_number", ""),
            issuing_authority=data.get("issuing_authority", ""),
            state_code=data.get("state_code", ""),
            issued_date=data.get("issued_date"),
            expiration_date=data.get("expiration_date"),
            status=data.get("status", "active"),
            verification_url=data.get("verification_url"),
            last_verified_at=data.get("last_verified_at"),
            verification_method=data.get("verification_method", ""),
            document_path=data.get("document_path"),
        )


@dataclass
class TeachingAssignment:
    """A teaching assignment for a faculty member."""
    id: str = field(default_factory=lambda: generate_id("assign"))
    program_id: str = ""
    course_code: str = ""
    course_name: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    required_credentials: List[str] = field(default_factory=list)
    qualification_basis: str = ""  # "degree", "license", "experience", "combination"
    is_qualified: bool = True
    qualification_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "program_id": self.program_id,
            "course_code": self.course_code,
            "course_name": self.course_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "required_credentials": self.required_credentials,
            "qualification_basis": self.qualification_basis,
            "is_qualified": self.is_qualified,
            "qualification_notes": self.qualification_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeachingAssignment":
        return cls(
            id=data.get("id", generate_id("assign")),
            program_id=data.get("program_id", ""),
            course_code=data.get("course_code", ""),
            course_name=data.get("course_name", ""),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            required_credentials=data.get("required_credentials", []),
            qualification_basis=data.get("qualification_basis", ""),
            is_qualified=data.get("is_qualified", True),
            qualification_notes=data.get("qualification_notes", ""),
        )


@dataclass
class FacultyMember:
    """A faculty or staff member with credentials."""
    id: str = field(default_factory=lambda: generate_id("fac"))
    institution_id: str = ""
    # Basic info
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    title: str = ""  # e.g., "Program Director", "Instructor"
    department: str = ""
    # Employment
    employment_type: EmploymentType = EmploymentType.FULLTIME
    employment_start_date: Optional[str] = None
    employment_end_date: Optional[str] = None
    is_active: bool = True
    # Credentials
    academic_credentials: List[AcademicCredential] = field(default_factory=list)
    professional_licenses: List[ProfessionalLicense] = field(default_factory=list)
    work_experience_years: int = 0
    work_experience_summary: str = ""
    foreign_credential_evaluation: Optional[Dict[str, Any]] = None
    # Teaching
    teaching_assignments: List[TeachingAssignment] = field(default_factory=list)
    # Professional development
    professional_development: List[Dict[str, Any]] = field(default_factory=list)
    # Compliance
    compliance_status: FacultyComplianceStatus = FacultyComplianceStatus.PENDING_VERIFICATION
    compliance_issues: List[str] = field(default_factory=list)
    last_compliance_check: Optional[str] = None
    # Metadata
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @property
    def full_name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "title": self.title,
            "department": self.department,
            "employment_type": self.employment_type.value,
            "employment_start_date": self.employment_start_date,
            "employment_end_date": self.employment_end_date,
            "is_active": self.is_active,
            "academic_credentials": [c.to_dict() for c in self.academic_credentials],
            "professional_licenses": [lic.to_dict() for lic in self.professional_licenses],
            "work_experience_years": self.work_experience_years,
            "work_experience_summary": self.work_experience_summary,
            "foreign_credential_evaluation": self.foreign_credential_evaluation,
            "teaching_assignments": [t.to_dict() for t in self.teaching_assignments],
            "professional_development": self.professional_development,
            "compliance_status": self.compliance_status.value,
            "compliance_issues": self.compliance_issues,
            "last_compliance_check": self.last_compliance_check,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FacultyMember":
        return cls(
            id=data.get("id", generate_id("fac")),
            institution_id=data.get("institution_id", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            title=data.get("title", ""),
            department=data.get("department", ""),
            employment_type=EmploymentType(data.get("employment_type", "fulltime")),
            employment_start_date=data.get("employment_start_date"),
            employment_end_date=data.get("employment_end_date"),
            is_active=data.get("is_active", True),
            academic_credentials=[
                AcademicCredential.from_dict(c)
                for c in data.get("academic_credentials", [])
            ],
            professional_licenses=[
                ProfessionalLicense.from_dict(lic)
                for lic in data.get("professional_licenses", [])
            ],
            work_experience_years=data.get("work_experience_years", 0),
            work_experience_summary=data.get("work_experience_summary", ""),
            foreign_credential_evaluation=data.get("foreign_credential_evaluation"),
            teaching_assignments=[
                TeachingAssignment.from_dict(t)
                for t in data.get("teaching_assignments", [])
            ],
            professional_development=data.get("professional_development", []),
            compliance_status=FacultyComplianceStatus(
                data.get("compliance_status", "pending_verification")
            ),
            compliance_issues=data.get("compliance_issues", []),
            last_compliance_check=data.get("last_compliance_check"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
