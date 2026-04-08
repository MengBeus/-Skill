from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .config import AppConfig
from .db import Database, ensure_database
from .guards import is_potential_sql_injection
from .kb import KnowledgeBase, extract_matching_lines, extract_table_row
from .router import ParsedQuestion, Router


@dataclass(slots=True)
class Answer:
    body: str
    sources: list[str]

    def render(self) -> str:
        source_text = "；".join(self.sources)
        return f"{self.body}\n\n> 来源：{source_text}"


class EnterpriseQA:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.load()
        self.config.validate_runtime()
        ensure_database(self.config.db_path)
        self.db = Database(self.config.db_path)
        self.kb = KnowledgeBase(self.config.knowledge_root)
        employees = [dict(row) for row in self.db.list_employees()]
        self.router = Router(employees, self.config.reference_date)

    def answer(self, question: str) -> str:
        text = question.strip()
        if not text:
            return "请输入一个具体的企业问题。"
        if is_potential_sql_injection(text):
            return (
                "检测到疑似 SQL 注入或原始 SQL 输入，已拒绝执行。"
                "\n\n> 来源：安全策略（仅允许预定义参数化查询）"
            )

        parsed = self.router.parse(text)
        answer = self._dispatch(parsed, text)
        return answer.render()

    def close(self) -> None:
        self.db.close()

    def _dispatch(self, parsed: ParsedQuestion, question: str) -> Answer:
        handlers = {
            "employee_department": self._answer_employee_department,
            "employee_manager": self._answer_employee_manager,
            "employee_email": self._answer_employee_email,
            "employee_lookup": self._answer_employee_lookup,
            "employee_projects": self._answer_employee_projects,
            "department_headcount": self._answer_department_headcount,
            "department_active_projects": self._answer_department_active_projects,
            "attendance_late_count": self._answer_attendance_late_count,
            "promotion_check": self._answer_promotion_check,
            "kb_lookup": self._answer_kb_lookup,
            "recent_updates": self._answer_recent_updates,
            "active_projects": self._answer_active_projects,
            "unknown": self._answer_unknown,
        }
        return handlers[parsed.intent](parsed, question)

    def _get_employee_or_missing(self, employee_ref: str | None) -> tuple[dict[str, str] | None, Answer | None]:
        if not employee_ref:
            return None, Answer("问题里没有识别到员工姓名或员工 ID。", ["输入解析"])
        employee = self.db.find_employee(employee_ref)
        if employee is None:
            return None, Answer(
                f"未找到员工 {employee_ref}。",
                ["employees.employee_id", "employees.name"],
            )
        return dict(employee), None

    def _answer_employee_department(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing
        return Answer(
            f"{employee['name']}的部门是{employee['department']}。",
            [f"employees.department ({employee['employee_id']})"],
        )

    def _answer_employee_manager(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing
        manager = self.db.get_employee_manager(employee["employee_id"])
        if manager is None:
            return Answer(
                f"{employee['name']}当前没有登记上级。",
                [f"employees.manager_id ({employee['employee_id']})"],
            )
        return Answer(
            f"{employee['name']}的上级是{manager['name']}（{manager['employee_id']}）。",
            [f"employees.manager_id ({employee['employee_id']})"],
        )

    def _answer_employee_email(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing
        return Answer(
            f"{employee['name']}的邮箱是 {employee['email']}。",
            [f"employees.email ({employee['employee_id']})"],
        )

    def _answer_employee_lookup(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing
        return Answer(
            (
                f"{employee['name']}当前在{employee['department']}，职级 {employee['level']}，"
                f"状态为 {employee['status']}。"
            ),
            [f"employees ({employee['employee_id']})"],
        )

    def _answer_employee_projects(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing
        projects = self.db.get_employee_projects(employee["employee_id"])
        if not projects:
            return Answer(
                f"{employee['name']}目前没有项目记录。",
                [f"project_members.employee_id ({employee['employee_id']})"],
            )
        items = [f"{row['project_id']} {row['name']}（{row['role']}）" for row in projects]
        return Answer(
            f"{employee['name']}参与的项目有：{'; '.join(items)}。",
            [
                f"project_members.employee_id ({employee['employee_id']})",
                "projects.project_id",
            ],
        )

    def _answer_department_headcount(self, parsed: ParsedQuestion, _: str) -> Answer:
        count = self.db.count_active_department(parsed.department or "")
        members = self.db.get_department_members(parsed.department or "")
        body = f"{parsed.department}当前有 {count} 名在职员工"
        if members:
            body += f"：{'、'.join(members)}。"
        else:
            body += "。"
        return Answer(
            body,
            [f"employees.department ({parsed.department})", "employees.status"],
        )

    def _answer_department_active_projects(self, parsed: ParsedQuestion, _: str) -> Answer:
        projects = self.db.get_active_projects_by_department(parsed.department or "")
        if not projects:
            return Answer(
                f"{parsed.department}当前没有查到在研项目。",
                ["employees.department", "project_members", "projects.status"],
            )
        items = [f"{row['project_id']} {row['name']}" for row in projects]
        return Answer(
            f"{parsed.department}当前涉及的在研项目有：{'；'.join(items)}。",
            ["employees.department", "project_members", "projects.status=active"],
        )

    def _answer_attendance_late_count(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing
        month_prefix = parsed.month_prefix or self._month_prefix(self.config.reference_date)
        count = self.db.count_lates(employee["employee_id"], month_prefix)
        return Answer(
            f"{employee['name']}在 {month_prefix} 迟到 {count} 次。",
            [
                f"attendance.status=late ({employee['employee_id']})",
                f"attendance.date LIKE '{month_prefix}-%'",
            ],
        )

    def _answer_promotion_check(self, parsed: ParsedQuestion, _: str) -> Answer:
        employee, missing = self._get_employee_or_missing(parsed.employee_ref)
        if missing:
            return missing

        current_level = employee["level"]
        if current_level != "P5":
            return Answer(
                (
                    f"{employee['name']}当前职级是 {current_level}。当前实现只对 P5→P6 做完整判断；"
                    "更高职级因缺少完整事故/技术贡献数据，无法可靠下结论。"
                ),
                [
                    f"employees.level ({employee['employee_id']})",
                    "knowledge/promotion_rules.md §晋升条件",
                ],
            )

        hire_date = date.fromisoformat(employee["hire_date"])
        tenure_days = (self.config.reference_date - hire_date).days
        tenure_ok = tenure_days >= 365
        reviews = self.db.get_performance_reviews(employee["employee_id"])
        avg_kpi = sum(row["kpi_score"] for row in reviews) / len(reviews) if reviews else 0.0
        consecutive_ok = self._has_two_consecutive_reviews(reviews, 85)
        performance_ok = consecutive_ok or avg_kpi >= 85
        project_count = self.db.count_core_or_lead_projects(employee["employee_id"])
        projects_ok = project_count >= 3
        known_fail = not (tenure_ok and performance_ok and projects_ok)

        lines = [
            f"- 工作年限：已入职约 {tenure_days // 365}.{(tenure_days % 365) // 30} 年，{'满足' if tenure_ok else '不满足'}",
            (
                f"- 绩效要求：连续 2 季度 KPI≥85 或年度平均≥85；"
                f"当前年度平均 {avg_kpi:.2f}，{'满足' if performance_ok else '不满足'}"
            ),
            f"- 项目经验：主导/核心项目 {project_count} 个，{'满足' if projects_ok else '不满足'}",
            "- 事故记录：题包未提供该数据；若前置硬条件已不满足，结论不受影响",
        ]
        verdict = "符合" if not known_fail else "不符合"
        return Answer(
            f"{employee['name']}目前{verdict} P5→P6 晋升条件。\n\n" + "\n".join(lines),
            [
                "knowledge/promotion_rules.md §P5 → P6",
                f"employees.hire_date ({employee['employee_id']})",
                f"performance_reviews.employee_id ({employee['employee_id']})",
                f"project_members.role ({employee['employee_id']})",
            ],
        )

    def _answer_kb_lookup(self, parsed: ParsedQuestion, question: str) -> Answer:
        topic = parsed.kb_topic
        if topic == "annual_leave":
            section = self.kb.find_best("年假 请假类型", preferred_files=("hr_policies.md",))
            row = extract_table_row(section, "年假") if section else None
            if row and len(row) >= 4:
                body = "根据《人事制度》，年假规则是：" + row[3] + "。"
                return Answer(body, [section.source_label])
        if topic == "late_policy":
            section = self.kb.find_best("迟到规则 扣款", preferred_files=("hr_policies.md",))
            if section:
                rows = [
                    extract_table_row(section, "3 次以内"),
                    extract_table_row(section, "4-6 次"),
                    extract_table_row(section, "7 次以上"),
                ]
                pieces = [f"{row[0]}：{row[1]}" for row in rows if row]
                return Answer(
                    "根据《人事制度》，迟到处理规则是：" + "；".join(pieces) + "。",
                    [section.source_label],
                )
        if topic == "finance_travel":
            section, lines = self._find_section_lines(
                "差旅费标准 酒店 机票 餐补",
                preferred_files=("finance_rules.md",),
                keywords=["机票", "酒店", "餐补"],
            )
            if section and lines:
                body = "根据《财务报销制度》，差旅报销标准包括：" + "；".join(lines) + "。"
                return Answer(body, [section.source_label])
        if topic == "remote_work":
            section, lines = self._find_section_lines(
                "远程办公",
                preferred_files=("faq.md",),
                keywords=["远程办公", "申请时间", "远程要求"],
            )
            if section and lines:
                return Answer("根据 FAQ，" + "；".join(lines) + "。", [section.source_label])
        if topic == "probation":
            section, lines = self._find_section_lines(
                "试用期",
                preferred_files=("faq.md",),
                keywords=["3-6 个月", "P4-P5", "P6-P7"],
            )
            if section and lines:
                return Answer("根据 FAQ，" + "；".join(lines) + "。", [section.source_label])
        if topic == "meeting_allhands":
            section, lines = self._find_section_lines(
                "全员大会 调薪 智能问答",
                preferred_files=("2026-03-01-allhands.md",),
                keywords=["调薪", "智能问答", "AI 实验室"],
            )
            if section and lines:
                return Answer("2026 年 3 月全员大会提到：" + "；".join(lines) + "。", [section.source_label])
        if topic == "meeting_techsync":
            section, lines = self._find_section_lines(
                "技术同步会 代码重构 技术预研小组 类型注解",
                preferred_files=("2026-03-15-tech-sync.md",),
                keywords=["代码重构", "技术预研小组", "类型注解"],
            )
            if section and lines:
                return Answer("2026 年 3 月技术同步会提到：" + "；".join(lines) + "。", [section.source_label])

        section = self.kb.find_best(question)
        if section is None:
            return Answer("没有检索到相关制度或文档信息。", ["knowledge/"])
        lines = extract_matching_lines(section, list(question), limit=2) or extract_matching_lines(
            section, section.heading.split(" > "), limit=2
        )
        snippet = "；".join(lines) if lines else section.text.splitlines()[0].strip()
        return Answer(f"根据文档检索结果：{snippet}", [section.source_label])

    def _answer_recent_updates(self, _: ParsedQuestion, __: str) -> Answer:
        tech, tech_items = self._find_section_lines(
            "代码重构 技术预研小组 类型注解",
            preferred_files=("2026-03-15-tech-sync.md",),
            keywords=["代码重构", "预研小组", "类型注解"],
            limit=2,
        )
        allhands, allhands_items = self._find_section_lines(
            "调薪 智能问答 AI 实验室",
            preferred_files=("2026-03-01-allhands.md",),
            keywords=["调薪", "智能问答", "AI 实验室"],
            limit=2,
        )
        active_projects = self.db.get_active_projects()

        lines: list[str] = []
        sources: list[str] = []
        if tech and tech_items:
            lines.append(f"- 2026-03-15 技术同步会：{'；'.join(tech_items)}")
            sources.append(tech.source_label)
        if allhands and allhands_items:
            lines.append(f"- 2026-03-01 全员大会：{'；'.join(allhands_items)}")
            sources.append(allhands.source_label)
        if active_projects:
            items = [f"{row['name']}（{row['status']}）" for row in active_projects]
            lines.append(f"- 当前推进中的项目：{'；'.join(items)}")
            sources.append("projects.status IN ('active','planning')")

        if not lines:
            return Answer("没有检索到最近的可确认事项。", ["knowledge/", "projects"])
        return Answer("最近可确认的事项有：\n" + "\n".join(lines), sources)

    def _answer_active_projects(self, _: ParsedQuestion, __: str) -> Answer:
        projects = self.db.get_active_projects()
        if not projects:
            return Answer("当前没有进行中的项目。", ["projects.status"])
        items = [f"{row['project_id']} {row['name']}（{row['status']}）" for row in projects]
        return Answer(
            "当前推进中的项目有：" + "；".join(items) + "。",
            ["projects.status IN ('active','planning')"],
        )

    def _answer_unknown(self, _: ParsedQuestion, question: str) -> Answer:
        if re.search(r"[A-Za-z0-9]{6,}", question) and "EMP-" not in question.upper():
            return Answer("没有找到可核实的相关信息，因此不做编造。", ["employees", "projects", "knowledge/"])
        section = self.kb.find_best(question)
        if section:
            lines = extract_matching_lines(section, list(question), limit=2)
            if lines:
                return Answer("我检索到一部分相关信息：" + "；".join(lines) + "。", [section.source_label])
        return Answer("没有找到可核实的相关信息，因此不做编造。", ["employees", "projects", "knowledge/"])

    def _find_section_lines(
        self,
        query: str,
        *,
        preferred_files: tuple[str, ...] = (),
        keywords: list[str],
        limit: int = 3,
    ) -> tuple[object | None, list[str]]:
        for section in self.kb.search(query, preferred_files=preferred_files, limit=5):
            lines = extract_matching_lines(section, keywords, limit=limit)
            if lines:
                return section, lines
        section = self.kb.find_best(query, preferred_files=preferred_files)
        if section is None:
            return None, []
        return section, extract_matching_lines(section, keywords, limit=limit)

    @staticmethod
    def _has_two_consecutive_reviews(reviews: list[dict[str, float]], threshold: int) -> bool:
        streak = 0
        for row in reviews:
            if row["kpi_score"] >= threshold:
                streak += 1
                if streak >= 2:
                    return True
            else:
                streak = 0
        return False

    @staticmethod
    def _month_prefix(value: date) -> str:
        return f"{value.year:04d}-{value.month:02d}"
