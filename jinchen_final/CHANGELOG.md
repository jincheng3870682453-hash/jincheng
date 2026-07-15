# 📜 CHANGELOG — Word 体系

> 版本号规则：主版本.次版本.修订
> 主版本 = 不兼容变更，次版本 = 新功能，修订 = bug 修复

---

## [V3.1] — 2026-07-15 · 诚实版（当前版本）

**代号：不骗自己**

"承认不完美，比假装完美更重要。"

### 🔴 重大变更（Breaking）

- **移除 Mock 兜底**：模型调用失败现在直接抛 `ModelCallError`，不再返回 `[MOCK-xxx]` 假数据
- **配置文件不再存明文 Key**：`config.json` 改为存 `api_key_env` 引用环境变量
- **签名机制降级**：`RollbackJury` 的"防篡改签名"改为"本地完整性哈希"，明确标注无密码学防篡改能力

### 🆕 新增

- **反馈式重试**：违规时把原因注入 prompt，让模型知道哪里错了再生成（不再同一个问题问 3 遍）
- **无状态网关**：`FeedbackFlywheel` 改为 `FeedbackStore`，仅文件持久化，不维护内存全局状态
- **语义意图识别**（可选）：安装 `sentence-transformers` 后自动启用，否则降级为关键词
- **`.gitignore` 自动生成**：`guardian.ensure_gitignore()` 自动创建/更新忽略规则
- **`requirements.txt`**：明确声明依赖

### 🔧 改进

- `_detect_unused_import`：从正则改为 AST 遍历，解决变量名碰撞（如 `json_data` 误判 `json` 模块）
- `sanitize()`：仅检查 docstring 和注释中的占位符，不再误删字符串字面量
- `RadiationDetector`：修复 `os.getenv()` 变量提取正则 bug
- `gateway.py`：所有 `except Exception: pass` 改为捕获具体异常 + 日志记录
- `V1Bridge.ast_check()`：检测模块异常时返回 `action=warn` 而非静默空列表

### 🐛 修复

- `guardian.py`：快照复制权限不足时不再静默失败
- `Nuwa.py`：`test_files` 拼接类型错误（`list + generator`）
- `gateway.py`：`config.json` 解析失败时有明确报错
- `RollbackJury`：哈希截断从 16 位改为 32 位（仍非签名，仅完整性校验）

### 📊 当前验证状态

| 项目 | 状态 |
|------|------|
| 单元验证 | ✅ 通过（使用 toy code 自测） |
| 真实项目测试 | ❌ 尚未做（无真实项目样本） |
| 性能测试 | ❌ 尚未做（无 1000 文件扫描基准） |
| 准确率测试 | ❌ 尚未做（无标注数据集） |

> ⚠️ **诚实标注**：当前测试覆盖率数字（如"57/57 通过"）是在手写用例上的自测结果，
> 不代表真实场景的准确率。请勿将此数字用于生产决策。

### 📦 模块状态一览

| 模块 | 方法 | 准确率 | 生产可用 |
|------|------|--------|---------|
| work.py (Python) | AST | 高 | ✅ 是 |
| work.py (Java) | 正则 | 低 | ❌ 仅筛查 |
| work.py (Kotlin) | 正则 | 低 | ❌ 仅筛查 |
| work.py (TS) | 正则 | 低 | ❌ 仅筛查 |
| work.py (Swift) | 正则 | 低 | ❌ 仅筛查 |
| guardian.py | shutil | 高 | ✅ 是 |
| Archive.py | SimHash | 中 | 🟡 可用 |
| Nuwa.py | 正则 | 中 | 🟡 可用 |
| gateway.py | Python | 高 | ✅ 是 |

---

## [V3.0] — 2026-07-14 · 企业级治理平台（已废弃）

**代号：交通规则**

> ⚠️ **此版本存在已知严重问题，请勿使用。**

### 🔴 已知问题

1. **Mock 欺骗**：模型失败时返回 `[MOCK-xxx]` 假数据，用户不知情
2. **多语言夸大**：README 写"AST 引擎"，实际 4/5 语言是正则
3. **签名虚假**：64 位哈希冒充防篡改签名
4. **重试无效**：同一 prompt 重复 3 次，指望答案自己变对
5. **全局状态**：`FeedbackFlywheel` 维护内存列表，多线程不安全
6. **密钥明文**：`config.json` 直接存 API Key
7. **静默吞错**：`except: pass` 遍布，检测失败用户不知

### 📦 变更

- 新增 `PolicyEngine`：dev/test/prod 三级策略
- 新增 `RollbackJury`：违规判决书生成
- 新增 `RadiationDetector`：全栈辐射检测
- 新增 `MultiLangASTEngine`：5 语言检测（实际只有 Python 是 AST）
- 新增 `Skill` 交互推荐

---

## [V2.0] — 2026-07-13 · 无状态网关

**代号：守门人**

### 🆕 新增

- `gateway.py`：统一网关（意图 → Skill → 模型 → 守门）
- `IntentEngine`：轻量关键词意图识别
- `SkillRecommender`：交互式 Skill 推荐
- `FineTunedCore`：10+ AI 平台适配
- `FeedbackFlywheel`：违规数据积累 → SFT 导出
- `V1Bridge`：V1 模块自动桥接

### 🔧 改进

- 守门规则从 5 条扩展到 7 条
- 快照预检：杜绝空快照
- 回滚前自动备份当前状态

### 🐛 修复

- 快照恢复时忽略项不生效
- `config.json` 不存在时崩溃

---

## [V1.0] — 2026-07-10 · 原型诞生

**代号：闲的没事干**

### 🎉 初始功能

- `work.py`：13 层焊缝检测（Python AST）
- `guardian.py`：基础快照 + 回滚
- `Archive.py`：SimHash 长对话记忆
- `shiyun.py`：硬核叙事工厂（30+ 题材库）
- `Nuwa.py`：基础 POC 报告（HTML + JSON）
- `Proteus.py`：交互式启动菜单

### 📦 首发平台

GitHub：`jincheng3870682453-hash/jinchen`

---

## 🗺️ 未来计划（Roadmap）

| 功能 | 优先级 | 预计版本 | 状态 |
|------|--------|---------|------|
| `tree-sitter` 真 AST（Java/Kotlin/TS/Swift） | 🔴 高 | V3.2 | 调研中 |
| 真实项目准确率测试（100+ 样本） | 🔴 高 | V3.2 | 待收集 |
| 性能基准测试（1000 文件扫描） | 🟡 中 | V3.2 | 待做 |
| Sigstore 集成（真签名） | 🟡 中 | V3.3 | 调研中 |
| Web UI 仪表盘 | 🟢 低 | V4.0 | 构思中 |
| 插件系统（第三方 Skill 市场） | 🟢 低 | V4.0 | 构思中 |

---

**让 AI 守规矩，从承认不完美开始。 🛡️**
