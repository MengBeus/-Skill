# 企业智能问答 Skill

这个 Skill 用来回答企业内部问答，数据来源是仓库中的 `enterprise-qa-data/` SQLite 数据库和 Markdown 知识库。

运行入口是 [answer.py](/F:/Programs/project_6/.claude/skills/enterprise-qa/scripts/answer.py)。它会把员工、项目、考勤、绩效、制度、报销、FAQ 和会议纪要等问题路由到正确的数据源，再返回带来源标注的答案。

默认运行配置在 [config.yaml](/F:/Programs/project_6/.claude/skills/enterprise-qa/config.yaml)。如果需要，也可以通过 `ENTERPRISE_QA_DB_PATH` 和 `ENTERPRISE_QA_KB_PATH` 覆盖数据库和知识库路径。

如果数据库还没准备好，可以先执行下面的命令初始化数据：

```powershell
$env:PYTHONPATH="F:\Programs\project_6\.claude\skills\enterprise-qa\scripts"
python .claude\skills\enterprise-qa\scripts\prepare_data.py
```

如果要从命令行直接提问，可以执行：

```powershell
$env:PYTHONPATH="F:\Programs\project_6\.claude\skills\enterprise-qa\scripts"
python .claude\skills\enterprise-qa\scripts\answer.py "张三的部门是什么？"
```

在 Claude Code 中，可以使用 `enterprise-qa` 这个 Skill。常见触发方式包括 `/enterprise-qa "年假怎么算？"` 或 `@enterprise "王五符合晋升条件吗？"`。

如果要运行回归测试，执行：

```powershell
python -m unittest discover -s .claude\skills\enterprise-qa\tests -v
```

如果要检查核心包的代码覆盖率，执行：

```powershell
python .claude\skills\enterprise-qa\tests\run_coverage.py --min 80
```

覆盖率脚本只依赖 Python 标准库 `trace`，当 `scripts/enterprise_qa/` 的总体覆盖率低于指定阈值时会直接返回失败。
