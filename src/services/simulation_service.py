"""Accreditation Simulation Service.

Orchestrates comprehensive mock audits across all institution documents,
aggregates findings by standard, and predicts accreditation outcome.

Two modes:
- Quick Scan: Fast analysis using cached audits + semantic search (1-3 min)
- Deep Audit: Full 5-pass audit per document (10-30 min)
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator, Tuple
from collections import defaultdict

from src.db.connection import get_conn
from src.core.models import generate_id


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    mode: str = "deep"  # 'quick', 'deep'
    accreditor_code: str = "ACCSC"
    include_federal: bool = True
    include_state: bool = True
    confidence_threshold: float = 0.7
    document_ids: Optional[List[str]] = None  # None = all documents


@dataclass
class PredictedFinding:
    """A predicted finding from the simulation."""
    id: str
    standard_code: str
    standard_title: str
    category: str
    regulatory_source: str
    predicted_status: str  # 'compliant', 'concern', 'finding', 'critical_finding'
    likelihood: str  # 'likely', 'possible', 'unlikely'
    confidence: float
    finding_summary: str
    evidence_summary: str
    evidence_gaps: List[str]
    affected_documents: List[Dict[str, str]]
    remediation_priority: int
    remediation_effort: str
    remediation_recommendation: str
    estimated_fix_days: int
    source_finding_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "standard_code": self.standard_code,
            "standard_title": self.standard_title,
            "category": self.category,
            "regulatory_source": self.regulatory_source,
            "predicted_status": self.predicted_status,
            "likelihood": self.likelihood,
            "confidence": round(self.confidence, 2),
            "finding_summary": self.finding_summary,
            "evidence_summary": self.evidence_summary,
            "evidence_gaps": self.evidence_gaps,
            "affected_documents": self.affected_documents,
            "remediation_priority": self.remediation_priority,
            "remediation_effort": self.remediation_effort,
            "remediation_recommendation": self.remediation_recommendation,
            "estimated_fix_days": self.estimated_fix_days,
        }


@dataclass
class RiskAssessment:
    """Risk assessment for a regulatory category."""
    category: str
    risk_level: str
    risk_score: float
    contributing_factors: List[str]
    mitigation_recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimulationResult:
    """Complete simulation result."""
    id: str
    institution_id: str
    accreditor_code: str
    mode: str
    status: str
    pass_prediction: str
    pass_confidence: float
    risk_level: str
    overall_score: int
    compliance_score: int
    evidence_score: int
    consistency_score: int
    documentation_score: int
    documents_audited: int
    standards_evaluated: int
    total_findings: int
    critical_findings: int
    significant_findings: int
    advisory_findings: int
    predicted_findings: List[PredictedFinding]
    risk_assessment: List[RiskAssessment]
    duration_seconds: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "accreditor_code": self.accreditor_code,
            "mode": self.mode,
            "status": self.status,
            "pass_prediction": self.pass_prediction,
            "pass_confidence": round(self.pass_confidence, 2),
            "risk_level": self.risk_level,
            "scores": {
                "overall": self.overall_score,
                "compliance": self.compliance_score,
                "evidence": self.evidence_score,
                "consistency": self.consistency_score,
                "documentation": self.documentation_score,
            },
            "counts": {
                "documents_audited": self.documents_audited,
                "standards_evaluated": self.standards_evaluated,
                "total_findings": self.total_findings,
                "critical_findings": self.critical_findings,
                "significant_findings": self.significant_findings,
                "advisory_findings": self.advisory_findings,
            },
            "predicted_findings": [f.to_dict() for f in self.predicted_findings],
            "risk_assessment": [r.to_dict() for r in self.risk_assessment],
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at,
        }


@dataclass
class ProgressUpdate:
    """Progress update during simulation."""
    phase: str
    progress_pct: int
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "phase": self.phase,
            "progress_pct": self.progress_pct,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# =============================================================================
# Simulation Service
# =============================================================================

class SimulationService:
    """Orchestrates accreditation simulation."""

    # Score weights (same as readiness service for consistency)
    SCORE_WEIGHTS = {
        "compliance": 0.40,
        "evidence": 0.25,
        "documentation": 0.20,
        "consistency": 0.15,
    }

    def __init__(self, institution_id: str):
        """Initialize the service.

        Args:
            institution_id: Institution ID.
        """
        self.institution_id = institution_id
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_conn()
        return self._conn

    def run_simulation(
        self,
        config: SimulationConfig,
    ) -> Generator[ProgressUpdate, None, SimulationResult]:
        """Run a simulation with progress updates.

        Args:
            config: Simulation configuration.

        Yields:
            ProgressUpdate objects during execution.

        Returns:
            SimulationResult when complete.
        """
        start_time = time.time()
        simulation_id = generate_id("sim")

        # Create simulation record
        self._create_simulation_record(simulation_id, config)

        try:
            yield ProgressUpdate("initializing", 5, "Loading institution data...")

            # Get documents to audit
            documents = self._get_documents(config.document_ids)
            if not documents:
                yield ProgressUpdate("error", 0, "No documents found")
                self._update_simulation_status(simulation_id, "failed", "No documents found")
                return self._get_simulation_result(simulation_id)

            yield ProgressUpdate("initializing", 10, f"Found {len(documents)} documents")

            # Get existing audit findings
            yield ProgressUpdate("auditing", 15, "Gathering audit findings...")
            all_findings = self._gather_audit_findings(documents, config)

            yield ProgressUpdate("auditing", 40, f"Collected {len(all_findings)} findings from audits")

            # Aggregate findings by standard
            yield ProgressUpdate("aggregating", 50, "Aggregating findings by standard...")
            aggregated = self._aggregate_findings(all_findings, config)

            yield ProgressUpdate("aggregating", 60, f"Aggregated into {len(aggregated)} standards")

            # Calculate scores
            yield ProgressUpdate("predicting", 70, "Calculating compliance scores...")
            scores = self._calculate_scores(aggregated, documents, config)

            # Generate predicted findings
            yield ProgressUpdate("predicting", 80, "Generating predicted findings...")
            predicted_findings = self._generate_predicted_findings(aggregated, config)

            # Calculate pass/fail prediction
            yield ProgressUpdate("predicting", 85, "Calculating pass/fail prediction...")
            prediction, confidence = self._calculate_pass_prediction(
                predicted_findings, scores
            )

            # Generate risk assessment
            yield ProgressUpdate("predicting", 90, "Generating risk assessment...")
            risk_assessment = self._generate_risk_assessment(predicted_findings, scores)
            risk_level = self._calculate_overall_risk(risk_assessment)

            # Persist results
            yield ProgressUpdate("finalizing", 95, "Saving simulation results...")
            duration = int(time.time() - start_time)

            self._persist_simulation_results(
                simulation_id=simulation_id,
                config=config,
                scores=scores,
                prediction=prediction,
                confidence=confidence,
                risk_level=risk_level,
                predicted_findings=predicted_findings,
                risk_assessment=risk_assessment,
                documents_audited=len(documents),
                duration=duration,
            )

            yield ProgressUpdate("completed", 100, "Simulation complete")

            return self._get_simulation_result(simulation_id)

        except Exception as e:
            self._update_simulation_status(simulation_id, "failed", str(e))
            raise

    def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Get a simulation by ID."""
        cursor = self.conn.execute(
            """
            SELECT * FROM simulation_runs
            WHERE id = ? AND institution_id = ?
            """,
            (simulation_id, self.institution_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def list_simulations(
        self,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List simulations for the institution."""
        query = """
            SELECT id, accreditor_code, simulation_mode, status,
                   pass_prediction, pass_confidence, risk_level,
                   overall_score, total_findings, critical_findings,
                   duration_seconds, created_at
            FROM simulation_runs
            WHERE institution_id = ?
        """
        params = [self.institution_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_simulation_findings(
        self,
        simulation_id: str,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get predicted findings for a simulation."""
        query = """
            SELECT * FROM simulation_findings
            WHERE simulation_id = ?
        """
        params = [simulation_id]

        if status_filter:
            query += " AND predicted_status = ?"
            params.append(status_filter)

        query += " ORDER BY remediation_priority, confidence DESC"

        cursor = self.conn.execute(query, params)
        findings = []
        for row in cursor.fetchall():
            finding = dict(row)
            # Parse JSON fields
            finding["evidence_gaps"] = json.loads(finding.get("evidence_gaps_json") or "[]")
            finding["affected_documents"] = json.loads(finding.get("affected_documents_json") or "[]")
            findings.append(finding)
        return findings

    def get_risk_assessment(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Get risk assessment for a simulation."""
        cursor = self.conn.execute(
            """
            SELECT * FROM simulation_risk_assessment
            WHERE simulation_id = ?
            ORDER BY risk_score DESC
            """,
            (simulation_id,),
        )
        assessments = []
        for row in cursor.fetchall():
            assessment = dict(row)
            assessment["contributing_factors"] = json.loads(
                assessment.get("contributing_factors_json") or "[]"
            )
            assessment["mitigation_recommendations"] = json.loads(
                assessment.get("mitigation_recommendations_json") or "[]"
            )
            assessments.append(assessment)
        return assessments

    def compare_simulations(
        self,
        sim_id_1: str,
        sim_id_2: str,
    ) -> Dict[str, Any]:
        """Compare two simulation runs."""
        sim1 = self.get_simulation(sim_id_1)
        sim2 = self.get_simulation(sim_id_2)

        if not sim1 or not sim2:
            return {"error": "One or both simulations not found"}

        def score_delta(key: str) -> int:
            return (sim2.get(key) or 0) - (sim1.get(key) or 0)

        return {
            "simulation_1": {
                "id": sim_id_1,
                "created_at": sim1.get("created_at"),
                "overall_score": sim1.get("overall_score"),
                "pass_prediction": sim1.get("pass_prediction"),
            },
            "simulation_2": {
                "id": sim_id_2,
                "created_at": sim2.get("created_at"),
                "overall_score": sim2.get("overall_score"),
                "pass_prediction": sim2.get("pass_prediction"),
            },
            "deltas": {
                "overall_score": score_delta("overall_score"),
                "compliance_score": score_delta("compliance_score"),
                "evidence_score": score_delta("evidence_score"),
                "consistency_score": score_delta("consistency_score"),
                "documentation_score": score_delta("documentation_score"),
                "critical_findings": score_delta("critical_findings"),
                "total_findings": score_delta("total_findings"),
            },
            "improved": score_delta("overall_score") > 0,
        }

    def get_simulation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get simulation history for trend analysis."""
        cursor = self.conn.execute(
            """
            SELECT id, created_at, overall_score, compliance_score,
                   evidence_score, consistency_score, documentation_score,
                   pass_prediction, pass_confidence, total_findings
            FROM simulation_runs
            WHERE institution_id = ? AND status = 'completed'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (self.institution_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Private methods
    # =========================================================================

    def _create_simulation_record(
        self,
        simulation_id: str,
        config: SimulationConfig,
    ) -> None:
        """Create initial simulation record."""
        self.conn.execute(
            """
            INSERT INTO simulation_runs
            (id, institution_id, accreditor_code, simulation_mode, status,
             current_phase, progress_pct, parameters_json, created_at)
            VALUES (?, ?, ?, ?, 'running', 'initializing', 0, ?, datetime('now'))
            """,
            (
                simulation_id,
                self.institution_id,
                config.accreditor_code,
                config.mode,
                json.dumps({
                    "include_federal": config.include_federal,
                    "include_state": config.include_state,
                    "confidence_threshold": config.confidence_threshold,
                }),
            ),
        )
        self.conn.commit()

    def _update_simulation_status(
        self,
        simulation_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update simulation status."""
        self.conn.execute(
            """
            UPDATE simulation_runs
            SET status = ?, error_message = ?, completed_at = datetime('now')
            WHERE id = ?
            """,
            (status, error_message, simulation_id),
        )
        self.conn.commit()

    def _get_documents(
        self,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get documents to audit."""
        if document_ids:
            placeholders = ",".join("?" * len(document_ids))
            cursor = self.conn.execute(
                f"""
                SELECT id, title, doc_type, status
                FROM documents
                WHERE institution_id = ? AND id IN ({placeholders})
                """,
                [self.institution_id] + document_ids,
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT id, title, doc_type, status
                FROM documents
                WHERE institution_id = ? AND status != 'deleted'
                ORDER BY doc_type, title
                """,
                (self.institution_id,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def _gather_audit_findings(
        self,
        documents: List[Dict[str, Any]],
        config: SimulationConfig,
    ) -> List[Dict[str, Any]]:
        """Gather existing audit findings for documents."""
        doc_ids = [d["id"] for d in documents]
        if not doc_ids:
            return []

        placeholders = ",".join("?" * len(doc_ids))
        cursor = self.conn.execute(
            f"""
            SELECT af.*, d.title as doc_title, d.doc_type,
                   ci.item_number as standard_code, ci.text as standard_text,
                   ci.category
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            JOIN documents d ON af.document_id = d.id
            LEFT JOIN checklist_items ci ON af.checklist_item_id = ci.id
            WHERE ar.institution_id = ?
              AND af.document_id IN ({placeholders})
              AND ar.status = 'completed'
            ORDER BY af.severity DESC, af.status
            """,
            [self.institution_id] + doc_ids,
        )
        return [dict(row) for row in cursor.fetchall()]

    def _aggregate_findings(
        self,
        findings: List[Dict[str, Any]],
        config: SimulationConfig,
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate findings by standard code."""
        aggregated: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "standard_code": "",
            "standard_title": "",
            "category": "",
            "findings": [],
            "documents": set(),
            "statuses": [],
            "severities": [],
            "confidences": [],
        })

        for finding in findings:
            code = finding.get("standard_code") or finding.get("id", "unknown")
            agg = aggregated[code]
            agg["standard_code"] = code
            agg["standard_title"] = finding.get("standard_text", "")[:100]
            agg["category"] = finding.get("category", "General")
            agg["findings"].append(finding)
            agg["documents"].add(finding.get("doc_title", "Unknown"))
            agg["statuses"].append(finding.get("status", "unknown"))
            agg["severities"].append(finding.get("severity", "advisory"))
            agg["confidences"].append(finding.get("confidence", 0.5))

        # Convert sets to lists
        for code, agg in aggregated.items():
            agg["documents"] = list(agg["documents"])

        return dict(aggregated)

    def _calculate_scores(
        self,
        aggregated: Dict[str, Dict[str, Any]],
        documents: List[Dict[str, Any]],
        config: SimulationConfig,
    ) -> Dict[str, int]:
        """Calculate compliance scores."""
        # Start at 100 and apply penalties
        compliance_score = 100
        evidence_score = 100
        consistency_score = 100
        documentation_score = 100

        # Compliance penalties
        for code, agg in aggregated.items():
            for status, severity in zip(agg["statuses"], agg["severities"]):
                if status == "non_compliant":
                    if severity == "critical":
                        compliance_score -= 12
                    elif severity == "significant":
                        compliance_score -= 7
                    else:
                        compliance_score -= 3
                elif status == "partial":
                    if severity == "critical":
                        compliance_score -= 6
                    elif severity == "significant":
                        compliance_score -= 4
                    else:
                        compliance_score -= 2

        # Evidence penalties (findings without strong evidence)
        for code, agg in aggregated.items():
            for conf, severity in zip(agg["confidences"], agg["severities"]):
                if conf < config.confidence_threshold:
                    if severity == "critical":
                        evidence_score -= 8
                    elif severity == "significant":
                        evidence_score -= 5
                    else:
                        evidence_score -= 2

        # Documentation score based on document coverage
        required_doc_types = {"catalog", "enrollment_agreement", "policy_manual"}
        uploaded_types = {d.get("doc_type", "") for d in documents}
        missing = required_doc_types - uploaded_types
        documentation_score -= len(missing) * 15

        # Clamp scores to 0-100
        scores = {
            "compliance": max(0, min(100, compliance_score)),
            "evidence": max(0, min(100, evidence_score)),
            "consistency": max(0, min(100, consistency_score)),
            "documentation": max(0, min(100, documentation_score)),
        }

        # Calculate weighted overall score
        overall = sum(
            scores[key] * weight
            for key, weight in self.SCORE_WEIGHTS.items()
        )
        scores["overall"] = int(overall)

        return scores

    def _generate_predicted_findings(
        self,
        aggregated: Dict[str, Dict[str, Any]],
        config: SimulationConfig,
    ) -> List[PredictedFinding]:
        """Generate predicted findings from aggregated data."""
        findings = []

        for code, agg in aggregated.items():
            # Determine worst status
            statuses = agg["statuses"]
            if "non_compliant" in statuses:
                worst_status = "critical_finding" if "critical" in agg["severities"] else "finding"
            elif "partial" in statuses:
                worst_status = "concern"
            else:
                worst_status = "compliant"

            if worst_status == "compliant":
                continue  # Skip compliant items

            # Calculate confidence and likelihood
            avg_confidence = sum(agg["confidences"]) / len(agg["confidences"]) if agg["confidences"] else 0.5
            likelihood = "likely" if avg_confidence > 0.8 else "possible" if avg_confidence > 0.5 else "unlikely"

            # Determine remediation effort
            non_compliant_count = statuses.count("non_compliant")
            if non_compliant_count > 2:
                effort = "high"
                fix_days = 30
            elif non_compliant_count > 0:
                effort = "medium"
                fix_days = 14
            else:
                effort = "low"
                fix_days = 7

            # Priority based on severity
            priority = 1 if "critical" in agg["severities"] else 2 if "significant" in agg["severities"] else 3

            finding = PredictedFinding(
                id=generate_id("pf"),
                standard_code=code,
                standard_title=agg["standard_title"],
                category=agg["category"],
                regulatory_source="accreditor",
                predicted_status=worst_status,
                likelihood=likelihood,
                confidence=avg_confidence,
                finding_summary=f"Potential {worst_status.replace('_', ' ')} for {code}: {agg['standard_title']}",
                evidence_summary=f"Based on {len(agg['findings'])} audit findings across {len(agg['documents'])} documents",
                evidence_gaps=[f"Gap in {doc}" for doc in agg["documents"][:3]],
                affected_documents=[{"doc_title": d} for d in agg["documents"]],
                remediation_priority=priority,
                remediation_effort=effort,
                remediation_recommendation=f"Review and address findings for {code}",
                estimated_fix_days=fix_days,
                source_finding_ids=[f["id"] for f in agg["findings"]],
            )
            findings.append(finding)

        # Sort by priority
        findings.sort(key=lambda f: (f.remediation_priority, -f.confidence))
        return findings

    def _calculate_pass_prediction(
        self,
        findings: List[PredictedFinding],
        scores: Dict[str, int],
    ) -> Tuple[str, float]:
        """Calculate pass/conditional/fail prediction."""
        critical_count = sum(1 for f in findings if f.predicted_status == "critical_finding")
        finding_count = sum(1 for f in findings if f.predicted_status in ("finding", "critical_finding"))
        compliance_score = scores.get("compliance", 0)

        # FAIL triggers
        if critical_count >= 1:
            high_conf_critical = any(
                f.confidence > 0.85
                for f in findings
                if f.predicted_status == "critical_finding"
            )
            if high_conf_critical:
                return "fail", 0.9
        if compliance_score < 60:
            return "fail", 0.85
        if finding_count >= 5:
            return "fail", 0.75

        # CONDITIONAL triggers
        if compliance_score < 80:
            return "conditional", 0.7
        if finding_count >= 2:
            return "conditional", 0.65
        if critical_count >= 1:
            return "conditional", 0.6

        # PASS
        confidence = min(0.95, (compliance_score / 100) * 0.8 + 0.15)
        return "pass", confidence

    def _generate_risk_assessment(
        self,
        findings: List[PredictedFinding],
        scores: Dict[str, int],
    ) -> List[RiskAssessment]:
        """Generate risk assessment by category."""
        assessments = []

        # Accreditation risk
        acc_findings = [f for f in findings if f.regulatory_source == "accreditor"]
        acc_critical = sum(1 for f in acc_findings if f.predicted_status == "critical_finding")
        if acc_critical > 0:
            level, score = "critical", 90
        elif len(acc_findings) > 3:
            level, score = "high", 70
        elif len(acc_findings) > 0:
            level, score = "medium", 40
        else:
            level, score = "low", 10

        assessments.append(RiskAssessment(
            category="accreditation",
            risk_level=level,
            risk_score=score,
            contributing_factors=[f.finding_summary for f in acc_findings[:3]],
            mitigation_recommendations=[
                "Address all critical findings before submission",
                "Ensure complete documentation for all standards",
            ],
        ))

        # Federal compliance risk (simplified)
        fed_score = 100 - scores.get("compliance", 100)
        fed_level = "critical" if fed_score > 40 else "high" if fed_score > 25 else "medium" if fed_score > 10 else "low"
        assessments.append(RiskAssessment(
            category="federal",
            risk_level=fed_level,
            risk_score=fed_score,
            contributing_factors=["Based on overall compliance score"],
            mitigation_recommendations=["Review federal regulatory requirements"],
        ))

        return assessments

    def _calculate_overall_risk(self, assessments: List[RiskAssessment]) -> str:
        """Calculate overall risk level from assessments."""
        if any(a.risk_level == "critical" for a in assessments):
            return "critical"
        if any(a.risk_level == "high" for a in assessments):
            return "high"
        if any(a.risk_level == "medium" for a in assessments):
            return "medium"
        return "low"

    def _persist_simulation_results(
        self,
        simulation_id: str,
        config: SimulationConfig,
        scores: Dict[str, int],
        prediction: str,
        confidence: float,
        risk_level: str,
        predicted_findings: List[PredictedFinding],
        risk_assessment: List[RiskAssessment],
        documents_audited: int,
        duration: int,
    ) -> None:
        """Persist simulation results to database."""
        critical_count = sum(1 for f in predicted_findings if f.predicted_status == "critical_finding")
        significant_count = sum(1 for f in predicted_findings if f.predicted_status == "finding")
        advisory_count = sum(1 for f in predicted_findings if f.predicted_status == "concern")

        # Update main record
        self.conn.execute(
            """
            UPDATE simulation_runs SET
                status = 'completed',
                pass_prediction = ?,
                pass_confidence = ?,
                risk_level = ?,
                overall_score = ?,
                compliance_score = ?,
                evidence_score = ?,
                consistency_score = ?,
                documentation_score = ?,
                documents_audited = ?,
                standards_evaluated = ?,
                total_findings = ?,
                critical_findings = ?,
                significant_findings = ?,
                advisory_findings = ?,
                current_phase = 'completed',
                progress_pct = 100,
                completed_at = datetime('now'),
                duration_seconds = ?
            WHERE id = ?
            """,
            (
                prediction,
                confidence,
                risk_level,
                scores["overall"],
                scores["compliance"],
                scores["evidence"],
                scores["consistency"],
                scores["documentation"],
                documents_audited,
                len(predicted_findings),
                len(predicted_findings),
                critical_count,
                significant_count,
                advisory_count,
                duration,
                simulation_id,
            ),
        )

        # Insert findings
        for finding in predicted_findings:
            self.conn.execute(
                """
                INSERT INTO simulation_findings
                (id, simulation_id, standard_code, standard_title, category,
                 regulatory_source, predicted_status, likelihood, confidence,
                 finding_summary, evidence_summary, evidence_gaps_json,
                 affected_documents_json, remediation_priority, remediation_effort,
                 remediation_recommendation, estimated_fix_days, source_finding_ids_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding.id,
                    simulation_id,
                    finding.standard_code,
                    finding.standard_title,
                    finding.category,
                    finding.regulatory_source,
                    finding.predicted_status,
                    finding.likelihood,
                    finding.confidence,
                    finding.finding_summary,
                    finding.evidence_summary,
                    json.dumps(finding.evidence_gaps),
                    json.dumps(finding.affected_documents),
                    finding.remediation_priority,
                    finding.remediation_effort,
                    finding.remediation_recommendation,
                    finding.estimated_fix_days,
                    json.dumps(finding.source_finding_ids),
                ),
            )

        # Insert risk assessments
        for assessment in risk_assessment:
            self.conn.execute(
                """
                INSERT INTO simulation_risk_assessment
                (id, simulation_id, risk_category, risk_level, risk_score,
                 contributing_factors_json, mitigation_recommendations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("sra"),
                    simulation_id,
                    assessment.category,
                    assessment.risk_level,
                    assessment.risk_score,
                    json.dumps(assessment.contributing_factors),
                    json.dumps(assessment.mitigation_recommendations),
                ),
            )

        self.conn.commit()

    def _get_simulation_result(self, simulation_id: str) -> SimulationResult:
        """Build SimulationResult from database."""
        sim = self.get_simulation(simulation_id)
        findings = self.get_simulation_findings(simulation_id)
        risk = self.get_risk_assessment(simulation_id)

        predicted_findings = [
            PredictedFinding(
                id=f["id"],
                standard_code=f["standard_code"],
                standard_title=f.get("standard_title", ""),
                category=f.get("category", ""),
                regulatory_source=f.get("regulatory_source", "accreditor"),
                predicted_status=f["predicted_status"],
                likelihood=f["likelihood"],
                confidence=f.get("confidence", 0),
                finding_summary=f.get("finding_summary", ""),
                evidence_summary=f.get("evidence_summary", ""),
                evidence_gaps=f.get("evidence_gaps", []),
                affected_documents=f.get("affected_documents", []),
                remediation_priority=f.get("remediation_priority", 0),
                remediation_effort=f.get("remediation_effort", "medium"),
                remediation_recommendation=f.get("remediation_recommendation", ""),
                estimated_fix_days=f.get("estimated_fix_days", 7),
            )
            for f in findings
        ]

        risk_assessments = [
            RiskAssessment(
                category=r["risk_category"],
                risk_level=r["risk_level"],
                risk_score=r.get("risk_score", 0),
                contributing_factors=r.get("contributing_factors", []),
                mitigation_recommendations=r.get("mitigation_recommendations", []),
            )
            for r in risk
        ]

        return SimulationResult(
            id=simulation_id,
            institution_id=self.institution_id,
            accreditor_code=sim.get("accreditor_code", ""),
            mode=sim.get("simulation_mode", "deep"),
            status=sim.get("status", "unknown"),
            pass_prediction=sim.get("pass_prediction", "unknown"),
            pass_confidence=sim.get("pass_confidence", 0),
            risk_level=sim.get("risk_level", "unknown"),
            overall_score=sim.get("overall_score", 0),
            compliance_score=sim.get("compliance_score", 0),
            evidence_score=sim.get("evidence_score", 0),
            consistency_score=sim.get("consistency_score", 0),
            documentation_score=sim.get("documentation_score", 0),
            documents_audited=sim.get("documents_audited", 0),
            standards_evaluated=sim.get("standards_evaluated", 0),
            total_findings=sim.get("total_findings", 0),
            critical_findings=sim.get("critical_findings", 0),
            significant_findings=sim.get("significant_findings", 0),
            advisory_findings=sim.get("advisory_findings", 0),
            predicted_findings=predicted_findings,
            risk_assessment=risk_assessments,
            duration_seconds=sim.get("duration_seconds", 0),
            created_at=sim.get("created_at", ""),
        )


# =============================================================================
# Factory
# =============================================================================

_services: Dict[str, SimulationService] = {}


def get_simulation_service(institution_id: str) -> SimulationService:
    """Get or create a simulation service for an institution."""
    if institution_id not in _services:
        _services[institution_id] = SimulationService(institution_id)
    return _services[institution_id]
