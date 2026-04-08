# 企业智能问答 Skill

这是一个面向企业内部场景的问答 Skill，支持同时查询结构化数据和 Markdown 知识库，并返回带来源标注的答案。

项目基于题目包实现，核心能力包括：

- 员工、项目、考勤、绩效等 SQLite 数据查询
- 人事制度、晋升规则、财务制度、FAQ、会议纪要等知识检索
- 按问题类型自动路由到数据库、知识库或混合查询
- 对答案附带来源说明，避免无依据输出

## 目录结构

```text
.
├── .claude/skills/enterprise-qa/   # Skill 实现与测试
├── enterprise-qa-data/             # 数据库、知识库与初始化脚本
├── enterprise-qa-exam.md           # 原始题目说明
├── requirements.txt                # 依赖说明
└── README.md
```

## 快速开始

### 1. 准备数据

```powershell
$env:PYTHONPATH="F:\Programs\project_6\.claude\skills\enterprise-qa\scripts"
python .claude\skills\enterprise-qa\scripts\prepare_data.py
```

### 2. 命令行测试问答

```powershell
$env:PYTHONPATH="F:\Programs\project_6\.claude\skills\enterprise-qa\scripts"
python .claude\skills\enterprise-qa\scripts\answer.py "张三的部门是什么？"
```

### 3. 运行测试

```powershell
python -m unittest discover -s .claude\skills\enterprise-qa\tests -v
```

### 4. 检查覆盖率

```powershell
python .claude\skills\enterprise-qa\tests\run_coverage.py --min 80
```

## 配置

默认配置文件位于 `.claude/skills/enterprise-qa/config.yaml`，也可以通过环境变量覆盖：

```powershell
$env:ENTERPRISE_QA_DB_PATH=".\enterprise-qa-data\enterprise.db"
$env:ENTERPRISE_QA_KB_PATH=".\enterprise-qa-data\knowledge"
```

## 示例问题

- `张三的邮箱是多少？`
- `研发部有多少人？`
- `年假怎么算？`
- `王五符合 P5 晋升 P6 条件吗？`
- `最近有什么事？`

## 说明

- 技能入口脚本：`.claude/skills/enterprise-qa/scripts/answer.py`
- 题目说明文档：`enterprise-qa-exam.md`
- 数据文件位于 `enterprise-qa-data/`
