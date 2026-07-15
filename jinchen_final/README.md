# 🛡️ Word 体系 —— AI 行为约束与治理工具集

> 让 AI 按规矩干活，违规就回滚。一套可审计、可对抗、可落地的 AI 治理方案。

**V2 + V3 整合版** —— 无状态网关 + 动态策略 + 回滚陪审团 + 全栈辐射检测 + 多语言 AST + Skill 交互推荐，全部模块化，开箱即用。

---

## ✨ 核心能力一览

| 层级 | 模块 | 能力 |
|------|------|------|
| L1 | `gateway.py` — IntentEngine | 轻量意图识别（关键词映射，零训练） |
| L2 | `gateway.py` — SkillRecommender | 交互式 Skill 推荐（用户自选，不猜） |
| L3 | `gateway.py` — FineTunedCore | 多平台模型调用（10+ AI 平台） |
| L4 | `work.py` — InstinctGuard | 本能守门（7 条内置 + V1 桥接规则） |
| L4a | `gateway.py` — PolicyEngine | 动态策略（dev/test/prod 分级守门） |
| L5 | `gateway.py` — FeedbackFlywheel | 反馈飞轮（违规数据 → SFT 训练集） |
| L6 | `guardian.py` — RollbackJury | 回滚陪审团（每次违规签发《判决书》） |
| L7 | `Nuwa.py` — RadiationDetector | 全栈辐射检测（DB/API/Test/Import/Config） |
| L8 | `work.py` — MultiLangASTEngine | 多语言 AST（Python/Java/Kotlin/TS/Swift） |
| V1 | `work.py` + `guardian.py` + `Archive.py` + `shiyun.py` + `Nuwa.py` | 5 个 V1 模块自动桥接 |

---

## 📁 目录结构

```
.
├── Toolkit/                    # 🚀 所有核心代码集中在此
│   ├── __init__.py           # 包导出（统一入口）
│   ├── gateway.py             # 统一网关（L1-L5 + PolicyEngine + V1Bridge）
│   ├── work.py                # 行为约束（InstinctGuard + MultiLangASTEngine）
│   ├── guardian.py            # 快照回滚 + 回滚陪审团（RollbackJury）
│   ├── Archive.py             # 长对话记忆（SimHash + 主题感知）
│   ├── shiyun.py             # 硬核叙事工厂（30+ 题材库）
│   ├── Nuwa.py               # POC 报告 + 全栈辐射检测
│   ├── Proteus.py            # 交互启动入口（菜单式）
│   └── skills/               # 7 个预置 Skill
│       ├── python_api_design.skill
│       ├── error_handling.skill
│       ├── sql_safety.skill
│       ├── code_refactor.skill
│       ├── markown_format.skill
│       ├── interactive_ux.skill
│       └── fiction_writing.skill
├── config.json                # 你的配置（改 API Key 即可）
├── config/config_template.json # 配置模板
├── verify.py                  # 全功能验证脚本（57 项检测）
├── LICENSE                    # MIT 许可证
└── README.md                 # 本文件
```

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- `pip install requests`（唯一外部依赖）

### 2. 配置 API Key

编辑 `config.json`，填入你的 API Key：

```json
{
  "env": "dev",
  "model": {
    "provider": "deepseek",
    "model": "deepseek-coder",
    "api_key": "sk-你的真实key"
  },
  "skill_dir": "Toolkit/skills",
  "user": "jincheng"
}
```

或通过环境变量（适合 CI/CD）：

```bash
export NUWA_AI_PROVIDER=deepseek
export NUWA_AI_API_KEY=sk-xxxx
```

### 3. 跑验证（确认环境 OK）

```bash
python3 verify.py
```

看到 `🎉 验证完成: 57/57 通过 (100%)` 就说明一切正常。

### 4. 启动交互模式

```bash
python3 Toolkit/gateway.py
```

输入需求 → 弹出 Skill 推荐 → 选编号 → AI 生成 → 守门检测 → 返回结果。

---

## 🔧 三行接入你的项目

```python
import sys
sys.path.insert(0, '.')

from Toolkit.gateway import WordGateway

gw = WordGateway({"env": "prod"})  # prod = 全部规则 + 严格模式
result = gw.handle("帮我写一个 Java 单例模式")
print(result.model_output)
```

---

## 🔀 动态策略：dev / test / prod

| 环境 | 规则数 | 检查内容 | 重试次数 |
|------|--------|---------|---------|
| `dev` | 2 条 | 硬编码密钥、SQL 注入（只卡红线） | 1 |
| `test` | 6 条 | + 类型注解、递归、占位符、未用导入 | 2 |
| `prod` | 8 条 | + try-except、V1 AST 桥接 + 严格模式 | 3 |

切换方式：

```bash
export NUWA_ENV=prod          # 方式1：环境变量
# 或
{"env": "prod", ...}          # 方式2：config.json
# 或
WordGateway(config, env="prod")  # 方式3：代码指定
```

---

## ⚖️ 回滚陪审团（RollbackJury）

每次违规自动生成《违规判决书》：

```markdown
# ⚖️ 违规判决书 `V-20260715-143022-a3f1`

| 字段 | 值 |
|------|---|
| 时间 | 2026-07-15T14:30:22 |
| 用户 | jincheng |
| 环境 | prod |
| AI 模型 | deepseek-coder |
| 违规规则 | `no_hardcoded_secrets` |
| 严重等级 | **CRITICAL** |

## 📋 违规代码
```python
api_key = "sk-1234567890abcdef12345678"
```

## 🔧 修复建议
将硬编码密钥替换为环境变量: `os.getenv('API_KEY')`

---
*本文件由 RollbackJury 自动生成 | 签名: `a3f1b2c4d5e6f7a8`*
```

JSON 版本同步生成，便于机器读取和审计。

---

## ☢️ 全栈辐射检测（RadiationDetector）

代码改动后自动扫描上下游关联：

```bash
$ python3 -c "
from Toolkit.Nuwa import RadiationDetector
rd = RadiationDetector('.')
alerts = rd.scan('my_file.py')
print(rd.generate_report(alerts))
"
```

输出示例：

```markdown
## ⚠️ 全栈辐射检测报告

### 🔴 CRITICAL (1)

- **db_migration** `models.py`
  - SQL 文件已修改，但 migration (002_add_user.py) 更旧
  - 💡 创建新的 migration 文件，包含本次 SQL 变更

### 🟡 WARNING (1)

- **unit_test** `utils.py`
  - 修改了 3 个函数，但未找到对应测试文件
  - 💡 为以下函数添加单元测试: fetch_data, parse_config, validate_input
```

---

## 🌐 多语言 AST 支持

| 语言 | 检测规则 |
|------|---------|
| **Python** | 类型注解、try-except、无限递归、未用导入 |
| **Java** | try-catch、PreparedStatement、Javadoc、无裸 printStackTrace |
| **Kotlin** | 显式类型、无 `!!` 强制解包、使用协程 |
| **TypeScript** | 类型注解、无 `any`、Promise 必须 await |
| **Swift** | Optional Binding、do-try-catch、无链式强制解包 |

自动识别语言（按扩展名 + 语法特征），无需手动指定。

---

## 🎯 Skill 交互推荐

用户说话 → 弹出推荐 → 用户勾选 → 组装 prompt → 模型生成：

```
用户 >>> 帮我写一个 Python 登录接口

════════════════════════════════════════
🎯 检测到需求: 帮我写一个 Python 登录接口
────────────────────────────────────────────
📋 推荐以下 Skill（输入编号选择，逗号分隔）:

  [1] python_api_design    (python, api, security)
      └─ Python API 接口编写规范
  [2] error_handling       (python, error, security)
      └─ Python 异常处理规范
  [3] code_refactor        (python, refactor, test)
      └─ 代码重构规范
  [4] sql_safety          (sql, security)
      └─ SQL 编写安全规范
  [5] interactive_ux      (ux, design)
      └─ 交互设计最佳实践

  [a] 全选   [s] 跳过   [q] 取消
════════════════════════════════════════
👉 你的选择: 1,2
```

---

## 📊 支持的 AI 平台（10+）

| Provider | 默认模型 | 说明 |
|----------|---------|------|
| `openai` | gpt-4o-mini | OpenAI Chat Completions |
| `anthropic` | claude-sonnet-4 | Anthropic Messages API |
| `gemini` | gemini-1.5-pro | Google Generative AI |
| `ollama` | llama2 | 本地部署 |
| `qwen` | qwen-plus | 阿里通义千问 |
| `zhipu` | glm-4 | 智谱 AI |
| `deepseek` | deepseek-coder | 深度求索（默认） |
| `minimax` | abab6-chat | MiniMax |
| `baichuan` | Baichuan3-Turbo | 百川智能 |
| `hunyuan` | hunyuan-pro | 腾讯混元 |

---

## 🤝 客户痛点 → 我们的解法

| 客户原话 | Word 体系解法 |
|----------|---------------|
| "规则太死板，开发不想查注解" | ✅ PolicyEngine：dev/test/prod 一键切换 |
| "回滚了不知道为啥" | ✅ RollbackJury：自动生成《违规判决书》 |
| "AI 不修表结构" | ✅ RadiationDetector：代码改动扫上下游 |
| "我们只写 Java/Swift" | ✅ MultiLangASTEngine：5 语言通用检测 |
| "训练数据从哪来？" | ✅ FeedbackFlywheel：违规数据自动导出 SFT 集 |
| "AI 总写错" | ✅ Skill 交互推荐：用户选规则，不猜 |
| "长对话失忆" | ✅ Archive：SimHash 记忆 + 主题切换检测 |

---

## 📄 许可证

MIT License —— 自由使用、修改、分发，需保留原始版权声明。

---

让 AI 守规矩，从这套工具开始。 🛡️
