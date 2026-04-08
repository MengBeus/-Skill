from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class ParsedQuestion:
    intent: str
    employee_ref: str | None = None
    department: str | None = None
    month_prefix: str | None = None
    kb_topic: str | None = None


class Router:
    def __init__(self, employees: list[dict[str, str]], reference_date: date) -> None:
        self.reference_date = reference_date
        self.employee_names = sorted(
            [employee["name"] for employee in employees if employee["name"] != "CEO"],
            key=len,
            reverse=True,
        ) + ["CEO"]
        self.departments = ["研发部", "产品部", "市场部", "管理层"]

    def parse(self, question: str) -> ParsedQuestion:
        employee_ref = self._extract_employee(question)
        department = self._extract_department(question)
        kb_topic = self._extract_kb_topic(question)
        month_prefix = self._extract_month_prefix(question)

        if "最近" in question or "近况" in question or "有什么事" in question:
            return ParsedQuestion("recent_updates")
        if "晋升" in question and ("条件" in question or "符合" in question):
            return ParsedQuestion("promotion_check", employee_ref=employee_ref)
        if department and ("在研项目" in question or ("项目" in question and "哪些" in question)):
            return ParsedQuestion("department_active_projects", department=department)
        if employee_ref and "负责" in question and "项目" in question:
            return ParsedQuestion("employee_projects", employee_ref=employee_ref)
        if employee_ref and ("上级" in question or "主管" in question):
            return ParsedQuestion("employee_manager", employee_ref=employee_ref)
        if employee_ref and ("邮箱" in question or "邮件" in question):
            return ParsedQuestion("employee_email", employee_ref=employee_ref)
        if employee_ref and "部门" in question:
            return ParsedQuestion("employee_department", employee_ref=employee_ref)
        if employee_ref and "迟到" in question and any(token in question for token in ("几次", "多少次")):
            return ParsedQuestion(
                "attendance_late_count",
                employee_ref=employee_ref,
                month_prefix=month_prefix or self._previous_month_prefix(),
            )
        if department and any(token in question for token in ("多少人", "几人", "人数")):
            return ParsedQuestion("department_headcount", department=department)
        if "在研项目" in question or ("项目" in question and "有哪些" in question):
            return ParsedQuestion("active_projects")
        if kb_topic:
            return ParsedQuestion("kb_lookup", kb_topic=kb_topic)
        if employee_ref:
            return ParsedQuestion("employee_lookup", employee_ref=employee_ref)
        return ParsedQuestion("unknown")

    def _extract_employee(self, question: str) -> str | None:
        match = re.search(r"\bEMP-\d{3}\b", question, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
        for name in self.employee_names:
            if name in question:
                return name
        return None

    def _extract_department(self, question: str) -> str | None:
        for department in self.departments:
            if department in question:
                return department
        return None

    def _extract_kb_topic(self, question: str) -> str | None:
        topic_rules = {
            "annual_leave": ["年假"],
            "late_policy": ["迟到", "扣"],
            "finance_travel": ["报销", "差旅"],
            "remote_work": ["远程办公"],
            "probation": ["试用期"],
            "meeting_allhands": ["全员大会"],
            "meeting_techsync": ["技术同步会"],
        }
        for topic, required_tokens in topic_rules.items():
            if all(token in question for token in required_tokens):
                return topic
        if "报销" in question and any(
            token in question
            for token in ("机票", "酒店", "餐补", "差旅", "招待", "办公用品", "培训费", "打车")
        ):
            return "finance_travel"
        if "会议" in question:
            return "meeting_allhands"
        return None

    def _extract_month_prefix(self, question: str) -> str | None:
        if "上个月" in question:
            return self._previous_month_prefix()

        explicit = re.search(r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月", question)
        if not explicit:
            return None
        year = int(explicit.group(1) or self.reference_date.year)
        month = int(explicit.group(2))
        return f"{year:04d}-{month:02d}"

    def _previous_month_prefix(self) -> str:
        year = self.reference_date.year
        month = self.reference_date.month - 1
        if month == 0:
            year -= 1
            month = 12
        return f"{year:04d}-{month:02d}"
