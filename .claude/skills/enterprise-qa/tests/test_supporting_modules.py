from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = SKILL_ROOT / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from enterprise_qa.config import AppConfig, parse_simple_yaml  # noqa: E402
from enterprise_qa.db import Database, ensure_database  # noqa: E402
from enterprise_qa.engine import EnterpriseQA  # noqa: E402
from enterprise_qa.router import ParsedQuestion, Router  # noqa: E402


class BaseEnterpriseQATestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[4]
        cls.data_root = cls.repo_root / "enterprise-qa-data"
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "enterprise.db"
        connection = sqlite3.connect(cls.db_path)
        try:
            connection.executescript((cls.data_root / "schema.sql").read_text(encoding="utf-8"))
            connection.executescript((cls.data_root / "seed_data.sql").read_text(encoding="utf-8"))
            connection.commit()
        finally:
            connection.close()

        cls.config = AppConfig(
            skill_root=SKILL_ROOT,
            repo_root=cls.repo_root,
            db_path=cls.db_path,
            knowledge_root=cls.data_root / "knowledge",
            timezone="Asia/Shanghai",
            reference_date=date(2026, 3, 27),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        self.engine = EnterpriseQA(config=self.config)

    def tearDown(self) -> None:
        self.engine.close()


class ConfigAndDatabaseTestCase(unittest.TestCase):
    def test_parse_simple_yaml_expands_environment_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "database:",
                        "  path: ${QA_DB:-./enterprise.db}",
                        "knowledge_base:",
                        "  root_path: ./knowledge",
                        "reference_date: 2026-03-27",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"QA_DB": "custom.db"}, clear=False):
                parsed = parse_simple_yaml(config_path)

        self.assertEqual(parsed["database"]["path"], "custom.db")
        self.assertEqual(parsed["knowledge_base"]["root_path"], "./knowledge")

    def test_load_from_prefers_environment_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_root = root / "skill"
            skill_root.mkdir()
            (root / "env.db").write_text("", encoding="utf-8")
            (root / "env-kb").mkdir()
            config_path = skill_root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "database:",
                        "  path: ./config.db",
                        "knowledge_base:",
                        "  root_path: ./config-kb",
                        "timezone: Asia/Shanghai",
                        "reference_date: 2026-03-27",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ENTERPRISE_QA_DB_PATH": str(root / "env.db"),
                    "ENTERPRISE_QA_KB_PATH": str(root / "env-kb"),
                },
                clear=False,
            ):
                loaded = AppConfig.load_from(config_path=config_path, skill_root=skill_root)

        self.assertEqual(loaded.db_path, (root / "env.db").resolve())
        self.assertEqual(loaded.knowledge_root, (root / "env-kb").resolve())

    def test_validate_runtime_requires_knowledge_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = AppConfig(
                skill_root=root,
                repo_root=root,
                db_path=root / "enterprise.db",
                knowledge_root=root / "missing-kb",
                timezone="Asia/Shanghai",
                reference_date=date(2026, 3, 27),
            )

            with self.assertRaises(FileNotFoundError):
                config.validate_runtime()

    def test_ensure_database_bootstraps_from_schema_files(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        data_root = repo_root / "enterprise-qa-data"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "schema.sql").write_text((data_root / "schema.sql").read_text(encoding="utf-8"), encoding="utf-8")
            (root / "seed_data.sql").write_text((data_root / "seed_data.sql").read_text(encoding="utf-8"), encoding="utf-8")
            db_path = root / "enterprise.db"

            created = ensure_database(db_path)
            created_again = ensure_database(db_path)

            database = Database(db_path)
            try:
                self.assertTrue(created)
                self.assertFalse(created_again)
                self.assertEqual(database.find_employee("EMP-001")["name"], "张三")
            finally:
                database.close()

    def test_ensure_database_requires_schema_and_seed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "enterprise.db"
            with self.assertRaises(FileNotFoundError):
                ensure_database(db_path)


class RouterAndEngineExtraTestCase(BaseEnterpriseQATestCase):
    def test_blank_question_requires_concrete_input(self) -> None:
        self.assertIn("请输入一个具体的企业问题", self.engine.answer("   "))

    def test_employee_email_lookup(self) -> None:
        answer = self.engine.answer("李四的邮箱是什么？")
        self.assertIn("lisi@company.com", answer)

    def test_ceo_has_no_manager(self) -> None:
        answer = self.engine.answer("CEO的上级是谁？")
        self.assertIn("没有登记上级", answer)

    def test_generic_employee_lookup(self) -> None:
        answer = self.engine.answer("查一下张三")
        self.assertIn("职级 P6", answer)

    def test_employee_without_projects(self) -> None:
        answer = self.engine.answer("吴十负责哪些项目？")
        self.assertIn("没有项目记录", answer)

    def test_department_without_active_projects(self) -> None:
        answer = self.engine.answer("市场部有哪些在研项目？")
        self.assertIn("没有查到在研项目", answer)

    def test_active_projects_query(self) -> None:
        answer = self.engine.answer("有哪些在研项目？")
        self.assertIn("PRJ-001", answer)
        self.assertIn("PRJ-002", answer)

    def test_finance_rules_lookup(self) -> None:
        answer = self.engine.answer("机票报销标准是什么？")
        self.assertIn("差旅报销标准", answer)
        self.assertIn("机票", answer)

    def test_remote_work_lookup(self) -> None:
        answer = self.engine.answer("可以远程办公吗？")
        self.assertIn("远程办公", answer)

    def test_probation_lookup(self) -> None:
        answer = self.engine.answer("试用期多久？")
        self.assertIn("3-6 个月", answer)

    def test_allhands_meeting_lookup(self) -> None:
        answer = self.engine.answer("3月全员大会说了什么？")
        self.assertIn("全员大会", answer)
        self.assertTrue("调薪" in answer or "AI 实验室" in answer)

    def test_techsync_meeting_lookup(self) -> None:
        answer = self.engine.answer("技术同步会说了什么？")
        self.assertIn("技术同步会", answer)
        self.assertIn("重构", answer)

    def test_promotion_check_for_non_p5_employee(self) -> None:
        answer = self.engine.answer("李四符合晋升条件吗？")
        self.assertIn("当前职级是 P7", answer)

    def test_generic_kb_fallback(self) -> None:
        answer = self.engine._answer_kb_lookup(ParsedQuestion("kb_lookup"), "代码规范是什么？").render()
        self.assertIn("文档检索结果", answer)

    def test_unknown_query_can_return_partial_retrieval_result(self) -> None:
        answer = self.engine.answer("体检有什么福利？")
        self.assertIn("我检索到一部分相关信息", answer)

    def test_attendance_handler_uses_reference_month_when_missing(self) -> None:
        answer = self.engine._answer_attendance_late_count(
            ParsedQuestion("attendance_late_count", employee_ref="张三", month_prefix=None),
            "",
        ).render()
        self.assertIn("2026-03", answer)

    def test_missing_employee_reference_returns_parse_error(self) -> None:
        answer = self.engine._answer_employee_department(ParsedQuestion("employee_department"), "").render()
        self.assertIn("没有识别到员工姓名", answer)

    def test_router_handles_fallback_meeting_topic_and_year_rollover(self) -> None:
        router = Router([{"name": "张三"}], date(2026, 1, 15))
        parsed = router.parse("会议里说了什么？")
        self.assertEqual(parsed.intent, "kb_lookup")
        self.assertEqual(parsed.kb_topic, "meeting_allhands")
        self.assertEqual(router._previous_month_prefix(), "2025-12")

    def test_router_extracts_email_and_active_project_queries(self) -> None:
        router = Router([{"name": "张三"}], date(2026, 3, 27))
        self.assertEqual(router.parse("张三的邮箱是多少？").intent, "employee_email")
        self.assertEqual(router.parse("项目有哪些？").intent, "active_projects")

    def test_consecutive_review_helper_handles_reset(self) -> None:
        self.assertFalse(
            EnterpriseQA._has_two_consecutive_reviews(
                [{"kpi_score": 84}, {"kpi_score": 90}, {"kpi_score": 84}],
                85,
            )
        )
        self.assertEqual(EnterpriseQA._month_prefix(date(2026, 3, 27)), "2026-03")

    def test_recent_updates_and_active_projects_empty_state(self) -> None:
        engine = object.__new__(EnterpriseQA)

        class EmptyKB:
            def search(self, query: str, preferred_files: tuple[str, ...] = (), limit: int = 5) -> list[object]:
                return []

            def find_best(self, query: str, preferred_files: tuple[str, ...] = ()) -> None:
                return None

        class EmptyDB:
            def get_active_projects(self) -> list[object]:
                return []

        engine.kb = EmptyKB()
        engine.db = EmptyDB()

        recent = engine._answer_recent_updates(ParsedQuestion("recent_updates"), "").render()
        active = engine._answer_active_projects(ParsedQuestion("active_projects"), "").render()

        self.assertIn("没有检索到最近的可确认事项", recent)
        self.assertIn("当前没有进行中的项目", active)
