from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from enterprise_qa.config import AppConfig  # noqa: E402
from enterprise_qa.engine import EnterpriseQA  # noqa: E402


class EnterpriseQATestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        data_root = repo_root / "enterprise-qa-data"
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "enterprise.db"
        connection = sqlite3.connect(cls.db_path)
        try:
            connection.executescript((data_root / "schema.sql").read_text(encoding="utf-8"))
            connection.executescript((data_root / "seed_data.sql").read_text(encoding="utf-8"))
            connection.commit()
        finally:
            connection.close()

        cls.config = AppConfig(
            skill_root=Path(__file__).resolve().parents[1],
            repo_root=repo_root,
            db_path=cls.db_path,
            knowledge_root=data_root / "knowledge",
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

    def test_t01_employee_department(self) -> None:
        answer = self.engine.answer("张三的部门是什么？")
        self.assertIn("研发部", answer)

    def test_t02_employee_manager(self) -> None:
        answer = self.engine.answer("李四的上级是谁？")
        self.assertIn("CEO", answer)
        self.assertIn("EMP-000", answer)

    def test_t03_annual_leave(self) -> None:
        answer = self.engine.answer("年假怎么算？")
        self.assertIn("入职满 1 年享 5 天", answer)
        self.assertIn("上限 15 天", answer)

    def test_t04_late_policy(self) -> None:
        answer = self.engine.answer("迟到几次扣钱？")
        self.assertIn("4-6 次", answer)
        self.assertIn("50 元", answer)

    def test_t05_employee_projects(self) -> None:
        answer = self.engine.answer("张三负责哪些项目？")
        self.assertIn("PRJ-001", answer)
        self.assertIn("PRJ-004", answer)
        self.assertIn("PRJ-002", answer)
        self.assertIn("PRJ-003", answer)

    def test_t06_department_headcount(self) -> None:
        answer = self.engine.answer("研发部有多少人？")
        self.assertIn("4 名在职员工", answer)

    def test_t07_promotion_check(self) -> None:
        answer = self.engine.answer("王五符合 P5 晋升 P6 条件吗？")
        self.assertIn("不符合", answer)
        self.assertIn("80.00", answer)
        self.assertIn("1 个", answer)

    def test_t08_attendance(self) -> None:
        answer = self.engine.answer("张三 2 月迟到几次？")
        self.assertIn("2026-02", answer)
        self.assertIn("2 次", answer)

    def test_t09_missing_employee(self) -> None:
        answer = self.engine.answer("查一下 EMP-999")
        self.assertIn("未找到员工 EMP-999", answer)

    def test_t10_recent_updates(self) -> None:
        answer = self.engine.answer("最近有什么事？")
        self.assertIn("技术同步会", answer)
        self.assertIn("全员大会", answer)

    def test_t11_sql_injection_blocked(self) -> None:
        answer = self.engine.answer("SELECT * FROM users WHERE '1'='1'")
        self.assertIn("已拒绝执行", answer)

    def test_t12_unknown(self) -> None:
        answer = self.engine.answer("xyzabc123 怎么报销")
        self.assertIn("没有找到可核实的相关信息", answer)
