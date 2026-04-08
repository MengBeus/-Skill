from __future__ import annotations

import sqlite3
from pathlib import Path


def ensure_database(db_path: Path) -> bool:
    if db_path.exists():
        return False

    data_root = db_path.parent
    schema_path = data_root / "schema.sql"
    seed_path = data_root / "seed_data.sql"
    if not schema_path.exists() or not seed_path.exists():
        raise FileNotFoundError(
            f"Database file {db_path} is missing and schema.sql/seed_data.sql were not found in {data_root}"
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        connection.executescript(seed_path.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()
    return True


class Database:
    def __init__(self, db_path: Path) -> None:
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def list_employees(self) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT employee_id, name, department, level, hire_date, manager_id, email, status
            FROM employees
            ORDER BY employee_id
            """
        )
        return cursor.fetchall()

    def find_employee(self, identifier: str) -> sqlite3.Row | None:
        if identifier.upper().startswith("EMP-"):
            cursor = self.connection.execute(
                """
                SELECT employee_id, name, department, level, hire_date, manager_id, email, status
                FROM employees
                WHERE employee_id = ?
                """,
                (identifier.upper(),),
            )
        else:
            cursor = self.connection.execute(
                """
                SELECT employee_id, name, department, level, hire_date, manager_id, email, status
                FROM employees
                WHERE name = ?
                """,
                (identifier,),
            )
        return cursor.fetchone()

    def get_employee_manager(self, employee_id: str) -> sqlite3.Row | None:
        cursor = self.connection.execute(
            """
            SELECT mgr.employee_id, mgr.name
            FROM employees emp
            JOIN employees mgr ON emp.manager_id = mgr.employee_id
            WHERE emp.employee_id = ?
            """,
            (employee_id,),
        )
        return cursor.fetchone()

    def count_active_department(self, department: str) -> int:
        cursor = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM employees
            WHERE department = ? AND status = 'active'
            """,
            (department,),
        )
        return int(cursor.fetchone()[0])

    def get_department_members(self, department: str) -> list[str]:
        cursor = self.connection.execute(
            """
            SELECT name
            FROM employees
            WHERE department = ? AND status = 'active'
            ORDER BY employee_id
            """,
            (department,),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_employee_projects(self, employee_id: str) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT p.project_id, p.name, p.status, pm.role
            FROM project_members pm
            JOIN projects p ON pm.project_id = p.project_id
            WHERE pm.employee_id = ?
            ORDER BY p.project_id
            """,
            (employee_id,),
        )
        return cursor.fetchall()

    def count_lates(self, employee_id: str, month_prefix: str) -> int:
        cursor = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            WHERE employee_id = ? AND status = 'late' AND date LIKE ?
            """,
            (employee_id, f"{month_prefix}-%"),
        )
        return int(cursor.fetchone()[0])

    def get_performance_reviews(self, employee_id: str) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT year, quarter, kpi_score, grade
            FROM performance_reviews
            WHERE employee_id = ?
            ORDER BY year, quarter
            """,
            (employee_id,),
        )
        return cursor.fetchall()

    def count_core_or_lead_projects(self, employee_id: str) -> int:
        cursor = self.connection.execute(
            """
            SELECT COUNT(DISTINCT project_id)
            FROM project_members
            WHERE employee_id = ? AND role IN ('lead', 'core')
            """,
            (employee_id,),
        )
        return int(cursor.fetchone()[0])

    def get_active_projects(self) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT project_id, name, status
            FROM projects
            WHERE status IN ('active', 'planning')
            ORDER BY
                CASE status
                    WHEN 'active' THEN 1
                    WHEN 'planning' THEN 2
                    ELSE 3
                END,
                project_id
            """
        )
        return cursor.fetchall()

    def get_active_projects_by_department(self, department: str) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT DISTINCT p.project_id, p.name, p.status
            FROM projects p
            JOIN project_members pm ON p.project_id = pm.project_id
            JOIN employees e ON e.employee_id = pm.employee_id
            WHERE e.department = ? AND e.status = 'active' AND p.status = 'active'
            ORDER BY p.project_id
            """,
            (department,),
        )
        return cursor.fetchall()
