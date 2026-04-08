# Enterprise QA Data Sources

## Runtime Assumptions

- Reference date: `2026-03-27`
- Timezone: `Asia/Shanghai`
- Primary data root: `enterprise-qa-data/`

## SQLite Tables

- `employees`: employee profile, department, level, hire date, manager, email, status
- `projects`: project owner, status, dates, budget
- `project_members`: employee-to-project membership and role
- `attendance`: date-level attendance status
- `performance_reviews`: quarterly KPI score and grade

## Knowledge Base Files

- `hr_policies.md`: work hours, late rules, leave, overtime
- `promotion_rules.md`: level definitions and promotion criteria
- `finance_rules.md`: reimbursement scope, standards, process
- `faq.md`: common HR and office questions
- `meeting_notes/2026-03-01-allhands.md`: company-wide updates
- `meeting_notes/2026-03-15-tech-sync.md`: engineering updates

## Supported Query Families

- Employee facts: department, email, manager, profile lookup
- Department facts: active headcount
- Project facts: employee project list, active projects, active projects by department
- Attendance: monthly late counts
- KB lookup: annual leave, late penalties, travel reimbursement, remote work, probation, meeting summaries
- Mixed reasoning: promotion eligibility, recent enterprise updates
