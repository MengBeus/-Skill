---
name: enterprise-qa
description: 在结构化 SQLite 数据和 Markdown 知识库之间进行路由，回答企业内部问答，并返回带来源标注的结果。适用于员工、项目、考勤、绩效、制度、报销、晋升和会议纪要等题包问题。
---

# 企业智能问答

当问题依赖本题提供的企业数据包时，不要凭记忆直接回答，而是使用本 Skill 内置脚本进行查询和生成答案。

## 使用流程

1. 从 `config.yaml` 或环境变量 `ENTERPRISE_QA_DB_PATH`、`ENTERPRISE_QA_KB_PATH` 读取运行路径。
2. 如果 SQLite 数据库尚未生成，先运行 `scripts/prepare_data.py` 初始化数据库。
3. 运行 `scripts/answer.py "<问题>"` 生成最终答案。
4. 回答必须基于实际查询结果，并保留输出中的来源标注。

## 查询路由规则

- 员工、部门、项目、考勤、绩效类问题走 SQLite。
- 制度、报销、FAQ、会议纪要类问题走 Markdown 知识库。
- 晋升判断和“最近有什么事”这类问题需要综合数据库和知识库。
- 遇到明显的 SQL 注入或原始 SQL 输入时直接拒绝，而不是尝试修复。

## 回答要求

- 数据库查询必须使用内置 Python 代码中的参数化查询。
- 优先输出可核实事实，不做猜测。
- 如果缺少必要信息，要明确说明不知道或无法判断。
- 涉及“上个月”等相对时间时，使用 `config.yaml` 中固定的业务参考日期。

## 相关文件

- `scripts/answer.py`：命令行问答入口。
- `scripts/prepare_data.py`：基于题包中的 SQL 文件生成 `enterprise.db`。
- `references/data-sources.md`：数据库表、知识库文件和支持问题类型的速查表。
