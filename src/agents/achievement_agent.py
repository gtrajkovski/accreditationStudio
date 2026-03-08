"""Achievement Agent.

Validates and analyzes student outcome data including completion rates,
placement rates, and licensure pass rates.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentSession, now_iso, generate_id
from src.config import Config


# Accreditor benchmarks for student outcomes
ACCREDITOR_BENCHMARKS = {
    "ACCSC": {
        "completion": 67,  # Minimum completion rate
        "placement": 70,   # Minimum placement rate
        "licensure": 70,   # Minimum licensure pass rate
    },
    "ABHES": {
        "completion": 67,
        "placement": 70,
        "licensure": 70,
    },
    "COE": {
        "completion": 60,
        "placement": 70,
        "licensure": 70,
    },
}

DEFAULT_BENCHMARKS = {"completion": 65, "placement": 70, "licensure": 70}


@register_agent(AgentType.ACHIEVEMENT)
class AchievementAgent(BaseAgent):
    """Agent for validating and analyzing student outcome data.

    Provides tools for:
    - Validating completion, placement, licensure rates
    - Detecting declining trends
    - Comparing against accreditor benchmarks
    - Generating achievement reports and disclosures
    """

    def __init__(self, session: AgentSession, workspace_manager=None, on_update=None):
        super().__init__(session, workspace_manager, on_update)

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ACHIEVEMENT

    @property
    def system_prompt(self) -> str:
        return """You are a student outcomes analyst for accreditation compliance.

Your responsibilities:
1. Validate student outcome data (completion, placement, licensure rates)
2. Detect declining trends over multiple years
3. Compare rates against accreditor benchmarks
4. Verify disclosure language includes required elements
5. Generate accurate achievement reports

OUTCOME METRICS:
- Completion Rate: Students completing vs. those who started
- Placement Rate: Graduates employed in field vs. available for employment
- Licensure Rate: Graduates passing required exams vs. those who sat

NEVER fabricate or estimate outcome data. Only report verified figures.
Flag any inconsistencies between reported rates and supporting documentation."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_programs",
                "description": "List programs with achievement data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "year": {"type": "integer"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "get_achievement_data",
                "description": "Get achievement data for a program.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "program_id": {"type": "string"},
                        "year": {"type": "integer"},
                    },
                    "required": ["institution_id", "program_id"],
                },
            },
            {
                "name": "record_achievement_data",
                "description": "Record achievement data for a program year.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "program_id": {"type": "string"},
                        "year": {"type": "integer"},
                        "completion_rate": {"type": "number"},
                        "placement_rate": {"type": "number"},
                        "licensure_rate": {"type": "number"},
                        "enrolled": {"type": "integer"},
                        "completed": {"type": "integer"},
                        "placed": {"type": "integer"},
                        "sat_exam": {"type": "integer"},
                        "passed_exam": {"type": "integer"},
                    },
                    "required": ["institution_id", "program_id", "year"],
                },
            },
            {
                "name": "validate_rates",
                "description": "Validate achievement rates against benchmarks.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "program_id": {"type": "string"},
                        "accreditor": {"type": "string"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "analyze_trends",
                "description": "Analyze 5-year trends for declining rates.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "program_id": {"type": "string"},
                        "years": {"type": "integer", "default": 5},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "generate_disclosure",
                "description": "Generate disclosure language for catalog/website.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "program_id": {"type": "string"},
                        "format": {"type": "string", "enum": ["catalog", "website", "gainful_employment"]},
                    },
                    "required": ["institution_id", "program_id"],
                },
            },
            {
                "name": "generate_report",
                "description": "Generate achievement summary report.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "year": {"type": "integer"},
                        "include_trends": {"type": "boolean", "default": True},
                    },
                    "required": ["institution_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "list_programs": self._tool_list_programs,
            "get_achievement_data": self._tool_get_data,
            "record_achievement_data": self._tool_record_data,
            "validate_rates": self._tool_validate_rates,
            "analyze_trends": self._tool_analyze_trends,
            "generate_disclosure": self._tool_generate_disclosure,
            "generate_report": self._tool_generate_report,
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _load_achievement_data(self, institution_id: str) -> Dict[str, Any]:
        """Load achievement data from workspace."""
        if not self.workspace_manager:
            return {"programs": {}, "updated_at": now_iso()}
        data = self.workspace_manager.load_file(institution_id, "achievements/achievement_data.json")
        return data or {"programs": {}, "updated_at": now_iso()}

    def _save_achievement_data(self, institution_id: str, data: Dict[str, Any]) -> None:
        """Save achievement data to workspace."""
        if not self.workspace_manager:
            return
        data["updated_at"] = now_iso()
        self.workspace_manager.save_file(institution_id, "achievements/achievement_data.json", data)

    def _tool_list_programs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List programs with achievement data."""
        institution_id = params["institution_id"]
        year = params.get("year")

        data = self._load_achievement_data(institution_id)
        programs = data.get("programs", {})

        result = []
        for prog_id, prog_data in programs.items():
            years_available = list(prog_data.get("years", {}).keys())
            if year and str(year) not in years_available:
                continue
            result.append({
                "program_id": prog_id,
                "program_name": prog_data.get("name", prog_id),
                "years_available": years_available,
                "latest_year": max(years_available) if years_available else None,
            })

        return {"success": True, "total": len(result), "programs": result}

    def _tool_get_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get achievement data for a program."""
        institution_id = params["institution_id"]
        program_id = params["program_id"]
        year = params.get("year")

        data = self._load_achievement_data(institution_id)
        prog_data = data.get("programs", {}).get(program_id)

        if not prog_data:
            return {"error": f"No data for program {program_id}"}

        if year:
            year_data = prog_data.get("years", {}).get(str(year))
            if not year_data:
                return {"error": f"No data for year {year}"}
            return {"success": True, "program_id": program_id, "year": year, "data": year_data}

        return {
            "success": True,
            "program_id": program_id,
            "program_name": prog_data.get("name", program_id),
            "years": prog_data.get("years", {}),
        }

    def _tool_record_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Record achievement data for a program year."""
        institution_id = params["institution_id"]
        program_id = params["program_id"]
        year = str(params["year"])

        data = self._load_achievement_data(institution_id)
        if program_id not in data["programs"]:
            data["programs"][program_id] = {"name": program_id, "years": {}}

        # Calculate rates if raw numbers provided
        year_data = {
            "completion_rate": params.get("completion_rate"),
            "placement_rate": params.get("placement_rate"),
            "licensure_rate": params.get("licensure_rate"),
            "enrolled": params.get("enrolled"),
            "completed": params.get("completed"),
            "placed": params.get("placed"),
            "sat_exam": params.get("sat_exam"),
            "passed_exam": params.get("passed_exam"),
            "recorded_at": now_iso(),
        }

        # Calculate rates from raw numbers if rates not provided
        if year_data["completion_rate"] is None and year_data["enrolled"] and year_data["completed"]:
            year_data["completion_rate"] = round((year_data["completed"] / year_data["enrolled"]) * 100, 1)

        if year_data["licensure_rate"] is None and year_data["sat_exam"] and year_data["passed_exam"]:
            year_data["licensure_rate"] = round((year_data["passed_exam"] / year_data["sat_exam"]) * 100, 1)

        data["programs"][program_id]["years"][year] = year_data
        self._save_achievement_data(institution_id, data)

        return {
            "success": True,
            "program_id": program_id,
            "year": year,
            "data": year_data,
        }

    def _tool_validate_rates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate achievement rates against benchmarks."""
        institution_id = params["institution_id"]
        program_id = params.get("program_id")
        accreditor = params.get("accreditor", "ACCSC")

        benchmarks = ACCREDITOR_BENCHMARKS.get(accreditor, DEFAULT_BENCHMARKS)
        data = self._load_achievement_data(institution_id)

        issues = []
        warnings = []
        programs_checked = 0

        programs_to_check = [program_id] if program_id else list(data.get("programs", {}).keys())

        for prog_id in programs_to_check:
            prog_data = data.get("programs", {}).get(prog_id, {})
            years = prog_data.get("years", {})
            if not years:
                continue

            latest_year = max(years.keys())
            latest = years[latest_year]
            programs_checked += 1

            # Check completion
            comp = latest.get("completion_rate")
            if comp is not None and comp < benchmarks["completion"]:
                issues.append({
                    "program": prog_id,
                    "metric": "completion",
                    "rate": comp,
                    "benchmark": benchmarks["completion"],
                    "severity": "critical" if comp < benchmarks["completion"] - 10 else "warning",
                })

            # Check placement
            place = latest.get("placement_rate")
            if place is not None and place < benchmarks["placement"]:
                issues.append({
                    "program": prog_id,
                    "metric": "placement",
                    "rate": place,
                    "benchmark": benchmarks["placement"],
                    "severity": "critical" if place < benchmarks["placement"] - 10 else "warning",
                })

            # Check licensure
            lic = latest.get("licensure_rate")
            if lic is not None and lic < benchmarks["licensure"]:
                issues.append({
                    "program": prog_id,
                    "metric": "licensure",
                    "rate": lic,
                    "benchmark": benchmarks["licensure"],
                    "severity": "critical" if lic < benchmarks["licensure"] - 10 else "warning",
                })

        return {
            "success": True,
            "accreditor": accreditor,
            "benchmarks": benchmarks,
            "programs_checked": programs_checked,
            "issues_count": len(issues),
            "issues": issues,
            "is_compliant": len([i for i in issues if i["severity"] == "critical"]) == 0,
        }

    def _tool_analyze_trends(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze multi-year trends for declining rates."""
        institution_id = params["institution_id"]
        program_id = params.get("program_id")
        num_years = params.get("years", 5)

        data = self._load_achievement_data(institution_id)
        trends = []
        declining = []

        programs_to_check = [program_id] if program_id else list(data.get("programs", {}).keys())

        for prog_id in programs_to_check:
            prog_data = data.get("programs", {}).get(prog_id, {})
            years = prog_data.get("years", {})
            if len(years) < 2:
                continue

            sorted_years = sorted(years.keys())[-num_years:]

            for metric in ["completion_rate", "placement_rate", "licensure_rate"]:
                values = [years[y].get(metric) for y in sorted_years if years[y].get(metric) is not None]
                if len(values) < 2:
                    continue

                # Check for declining trend
                is_declining = all(values[i] >= values[i+1] for i in range(len(values)-1))
                change = values[-1] - values[0] if len(values) >= 2 else 0

                trend_data = {
                    "program": prog_id,
                    "metric": metric.replace("_rate", ""),
                    "years": sorted_years,
                    "values": values,
                    "change": round(change, 1),
                    "is_declining": is_declining and change < -5,
                }
                trends.append(trend_data)

                if trend_data["is_declining"]:
                    declining.append(trend_data)

        return {
            "success": True,
            "years_analyzed": num_years,
            "total_trends": len(trends),
            "declining_count": len(declining),
            "declining": declining,
            "all_trends": trends[:20],  # Limit output
        }

    def _tool_generate_disclosure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate disclosure language for catalog/website."""
        institution_id = params["institution_id"]
        program_id = params["program_id"]
        format_type = params.get("format", "catalog")

        data = self._load_achievement_data(institution_id)
        prog_data = data.get("programs", {}).get(program_id)

        if not prog_data:
            return {"error": f"No data for program {program_id}"}

        years = prog_data.get("years", {})
        if not years:
            return {"error": "No achievement data recorded"}

        latest_year = max(years.keys())
        latest = years[latest_year]

        comp = latest.get("completion_rate", "N/A")
        place = latest.get("placement_rate", "N/A")
        lic = latest.get("licensure_rate", "N/A")

        if format_type == "catalog":
            disclosure = f"""Student Achievement Data ({latest_year})

The following rates are calculated in accordance with accreditor requirements:

Completion Rate: {comp}%
This represents the percentage of students who completed the program within 150% of normal time.

Placement Rate: {place}%
This represents the percentage of graduates employed in their field of study within six months of graduation.

{"Licensure Pass Rate: " + str(lic) + "%" if lic != "N/A" else ""}
{"This represents the percentage of graduates who passed the required licensure examination on their first attempt." if lic != "N/A" else ""}

For questions about student outcomes, contact the school administration."""

        elif format_type == "website":
            disclosure = f"""Student Outcomes ({latest_year}): Completion: {comp}% | Placement: {place}%{" | Licensure: " + str(lic) + "%" if lic != "N/A" else ""}"""

        else:  # gainful_employment
            disclosure = f"""Gainful Employment Disclosure - {prog_data.get('name', program_id)}
Reporting Year: {latest_year}
On-Time Completion Rate: {comp}%
Job Placement Rate: {place}%
{"Licensure Examination Pass Rate: " + str(lic) + "%" if lic != "N/A" else ""}"""

        return {
            "success": True,
            "program_id": program_id,
            "year": latest_year,
            "format": format_type,
            "disclosure": disclosure,
        }

    def _tool_generate_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate achievement summary report."""
        institution_id = params["institution_id"]
        year = params.get("year")
        include_trends = params.get("include_trends", True)

        data = self._load_achievement_data(institution_id)
        programs = data.get("programs", {})

        if not programs:
            return {"error": "No achievement data recorded"}

        report_year = str(year) if year else max(
            max(p.get("years", {}).keys(), default="0") for p in programs.values()
        )

        summary = []
        for prog_id, prog_data in programs.items():
            year_data = prog_data.get("years", {}).get(report_year)
            if not year_data:
                continue
            summary.append({
                "program": prog_data.get("name", prog_id),
                "program_id": prog_id,
                "completion": year_data.get("completion_rate"),
                "placement": year_data.get("placement_rate"),
                "licensure": year_data.get("licensure_rate"),
            })

        # Calculate averages
        comps = [s["completion"] for s in summary if s["completion"]]
        places = [s["placement"] for s in summary if s["placement"]]
        lics = [s["licensure"] for s in summary if s["licensure"]]

        report = {
            "id": generate_id("rpt"),
            "year": report_year,
            "generated_at": now_iso(),
            "programs_count": len(summary),
            "averages": {
                "completion": round(sum(comps) / len(comps), 1) if comps else None,
                "placement": round(sum(places) / len(places), 1) if places else None,
                "licensure": round(sum(lics) / len(lics), 1) if lics else None,
            },
            "programs": summary,
        }

        # Add trends if requested
        if include_trends:
            trends = self._tool_analyze_trends({"institution_id": institution_id, "years": 5})
            report["declining_trends"] = trends.get("declining", [])

        # Save report
        if self.workspace_manager:
            self.workspace_manager.save_file(
                institution_id, f"achievements/report_{report_year}.json", report
            )

        return {"success": True, "report": report}
