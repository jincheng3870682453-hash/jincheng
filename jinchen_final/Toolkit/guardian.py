#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guardian.py — 物理快照与安全回滚 + 回滚陪审团（违规判决书）

V1 原有功能：
  - 修改前自动创建项目快照
  - 回滚前预检完整性
  - 杜绝空快照清空目录

V3 新增功能：
  - RollbackJury：每次回滚自动生成《违规判决书》
  - 判决书含：证据链 + 修复建议 + 数字签名
  - 支持 JSON（机器可读）+ Markdown（人可读）
"""

import os
import re
import json
import shutil
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

log = logging.getLogger("guardian")


# ══════════════════════════════════════════════════════════
# V1 — Guardian  快照与回滚
# ══════════════════════════════════════════════════════════

class Guardian:
    """物理层安全 —— 快照 + 回滚"""

    DEFAULT_IGNORE = [
        "__pycache__", ".git", ".venv", "venv", "env",
        "node_modules", ".idea", ".vscode", "*.pyc",
        "snapshots", "verdicts", "feedback", "poc_reports",
    ]

    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, project_root: str = ".") -> str:
        """创建项目快照，返回 snapshot_id"""
        snap_id = f"snap-{datetime.now():%Y%m%d-%H%M%S}-{os.urandom(2).hex()}"
        snap_path = self.snapshot_dir / snap_id
        src = Path(project_root)

        # 预检：源目录不能为空
        files = list(src.rglob("*"))
        if not files:
            raise ValueError(f"项目目录为空，拒绝创建空快照: {project_root}")

        # 复制文件（跳过忽略项）
        snap_path.mkdir(parents=True, exist_ok=True)
        for f in files:
            if not f.is_file():
                continue
            # 检查是否在忽略列表中
            rel = f.relative_to(src)
            if any(rel.match(ig) for ig in self.DEFAULT_IGNORE):
                continue
            dst = snap_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)

        # 写入清单
        manifest = {
            "id": snap_id,
            "created": datetime.now().isoformat(),
            "root": str(src.resolve()),
            "file_count": len(list(snap_path.rglob("*"))),
        }
        (snap_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        log.info(f"📸 快照创建: {snap_id} ({manifest['file_count']} 文件)")
        return snap_id

    def precheck(self, snap_id: str) -> dict:
        """回滚前预检：确保快照完整"""
        snap_path = self.snapshot_dir / snap_id
        if not snap_path.exists():
            return {"valid": False, "reason": "快照不存在"}
        manifest_f = snap_path / "manifest.json"
        if not manifest_f.exists():
            return {"valid": False, "reason": "清单文件缺失"}
        manifest = json.loads(manifest_f.read_text(encoding="utf-8"))
        if manifest.get("file_count", 0) == 0:
            return {"valid": False, "reason": "空快照（零文件）"}
        # 抽样检查
        files = list(snap_path.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        if file_count == 0:
            return {"valid": False, "reason": "快照目录为空"}
        return {
            "valid": True,
            "file_count": file_count,
            "manifest": manifest,
        }

    def rollback(self, snap_id: str, project_root: str = ".") -> dict:
        """回滚到指定快照"""
        check = self.precheck(snap_id)
        if not check["valid"]:
            raise RuntimeError(f"回滚失败: {check['reason']}")

        snap_path = self.snapshot_dir / snap_id
        src = Path(project_root)

        # 先备份当前状态（防二次回滚丢失）
        backup_id = f"pre-rollback-{os.urandom(2).hex()}"
        backup_path = self.snapshot_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)
        for f in Path(project_root).rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src)
            if any(rel.match(ig) for ig in self.DEFAULT_IGNORE):
                continue
            dst = backup_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)

        # 清空目标目录（保留忽略项）
        for f in src.rglob("*"):
            if any(f.match(ig) for ig in self.DEFAULT_IGNORE):
                continue
            if f.is_file():
                f.unlink()
            elif f.is_dir() and f.name not in self.DEFAULT_IGNORE:
                shutil.rmtree(f, ignore_errors=True)

        # 从快照恢复
        for f in snap_path.rglob("*"):
            if not f.is_file() or f.name == "manifest.json":
                continue
            rel = f.relative_to(snap_path)
            dst = src / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)

        log.info(f"💣 回滚完成: {snap_id} → {project_root}")
        return {
            "status": "rolled_back",
            "snapshot": snap_id,
            "backup": backup_id,
            "restored_files": check["file_count"],
        }

    def list_snapshots(self) -> list[dict]:
        """列出所有快照"""
        results = []
        for d in sorted(self.snapshot_dir.iterdir()):
            if d.is_dir():
                mf = d / "manifest.json"
                if mf.exists():
                    results.append(json.loads(mf.read_text(encoding="utf-8")))
        return results


# ══════════════════════════════════════════════════════════
# V3 — RollbackJury  回滚陪审团
# ══════════════════════════════════════════════════════════

class Verdict:
    """一份违规判决书"""

    def __init__(self, *, verdict_id: str, timestamp: str,
                 user: str, env: str, model: str,
                 rule_name: str, severity: str,
                 original_code: str, violation_line: str,
                 evidence: dict, fix_suggestion: str,
                 snapshot_id: str):
        self.data = {
            "verdict_id": verdict_id,
            "timestamp": timestamp,
            "user": user,
            "env": env,
            "model": model,
            "rule_violated": rule_name,
            "severity": severity,
            "original_code": original_code,
            "violation_line": violation_line,
            "evidence": evidence,
            "fix_suggestion": fix_suggestion,
            "snapshot_id": snapshot_id,
            "signature": "",
        }
        self._sign()

    def _sign(self):
        raw = json.dumps(self.data, sort_keys=True, ensure_ascii=False)
        self.data["signature"] = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_markdown(self) -> str:
        d = self.data
        return f"""# ⚖️ 违规判决书 `{d['verdict_id']}`

| 字段 | 值 |
|------|---|
| 时间 | {d['timestamp']} |
| 用户 | {d['user']} |
| 环境 | {d['env']} |
| AI 模型 | {d['model']} |
| 违规规则 | `{d['rule_violated']}` |
| 严重等级 | **{d['severity'].upper()}** |

## 📋 违规代码

```python
{d['violation_line']}
```

## 🔍 证据

```json
{json.dumps(d['evidence'], indent=2, ensure_ascii=False)}
```

## 🔧 修复建议

{d['fix_suggestion']}

## 💾 快照恢复

```
guardian rollback --snapshot {d['snapshot_id']}
```

---
*本文件由 RollbackJury 自动生成 | 签名: `{d['signature']}`*
"""

    def to_json(self) -> str:
        return json.dumps(self.data, indent=2, ensure_ascii=False)


class RollbackJury:
    """
    回滚陪审团 —— 每次回滚生成完整判决书。
    CTO 看了直呼专业。
    """

    SEVERITY_MAP = {
        "no_hardcoded_secrets": "critical",
        "no_sql_injection":   "critical",
        "try_except":          "high",
        "no_infinite_recursion": "high",
        "type_hints":          "medium",
        "no_unused_import":    "low",
        "markdown_clean":      "low",
        "v1_ast_check":       "medium",
        # 多语言规则
        "try_catch":           "high",
        "no_bare_printstack":  "medium",
        "sql_prepared_statement": "critical",
        "has_javadoc":         "low",
        "explicit_types":       "medium",
        "no_bang_bang":        "high",
        "uses_coroutines":     "low",
        "ts_type_annotations": "medium",
        "no_any":              "low",
        "promise_handled":     "high",
        "optional_binding":    "high",
        "error_handling":      "high",
        "no_force_chain":      "low",
    }

    FIX_SUGGESTIONS = {
        "no_hardcoded_secrets":     "将硬编码密钥替换为环境变量: `os.getenv('API_KEY')`",
        "no_sql_injection":         "使用参数化查询: `cursor.execute(sql, params)`",
        "try_except":               "为风险操作添加 try-except 块",
        "no_infinite_recursion":    "添加终止条件（if/return/for/while）",
        "type_hints":               "为函数参数和返回值添加类型注解",
        "no_unused_import":         "删除未使用的 import 语句",
        "markdown_clean":           "移除文档中的占位符（[TODO]等）",
        "try_catch":                "为 IO/网络操作添加 try-catch 块",
        "no_bare_printstack":       "使用日志框架替代 printStackTrace",
        "sql_prepared_statement":   "使用 PreparedStatement 防 SQL 注入",
        "has_javadoc":              "为公开方法添加 Javadoc 注释",
        "explicit_types":           "为函数参数/返回值添加显式类型注解",
        "no_bang_bang":             "用 ?: 替代 !! 避免 NPE",
        "uses_coroutines":          "使用协程（launch/async）替代裸线程",
        "ts_type_annotations":      "避免使用 any，定义明确接口/类型",
        "no_any":                   "用具体类型或 unknown 替代 any",
        "promise_handled":          "Promise 必须 await 或 .then() 处理",
        "optional_binding":         "用 guard let / if let 安全解包",
        "error_handling":            "Swift 错误必须用 do-try-catch 处理",
        "no_force_chain":           "避免链式强制解包（!）",
    }

    def __init__(self, verdict_dir: str = "verdicts"):
        self.verdict_dir = Path(verdict_dir)
        self.verdict_dir.mkdir(parents=True, exist_ok=True)

    def issue(self, *, rule_name: str, original_code: str,
              evidence: dict, snapshot_id: str,
              user: str = "anonymous", env: str = "dev",
              model: str = "unknown") -> Verdict:
        """签发一份判决书"""
        verdict_id = f"V-{datetime.now():%Y%m%d-%H%M%S}-{os.urandom(2).hex()}"
        severity = self.SEVERITY_MAP.get(rule_name, "medium")
        suggestion = self.FIX_SUGGESTIONS.get(
            rule_name, "请根据规则说明修复代码")

        # 提取违规行
        violation_lines = evidence.get("matched_lines", [])
        violation_text = "\n".join(violation_lines) if violation_lines else original_code[:200]

        v = Verdict(
            verdict_id=verdict_id,
            timestamp=datetime.now().isoformat(),
            user=user, env=env, model=model,
            rule_name=rule_name, severity=severity,
            original_code=original_code,
            violation_line=violation_text,
            evidence=evidence,
            fix_suggestion=suggestion,
            snapshot_id=snapshot_id,
        )

        # 保存双格式
        (self.verdict_dir / f"{verdict_id}.json").write_text(
            v.to_json(), encoding="utf-8")
        (self.verdict_dir / f"{verdict_id}.md").write_text(
            v.to_markdown(), encoding="utf-8")

        log.info(f"⚖️ 判决书签发: {verdict_id} [{severity.upper()}] {rule_name}")
        return v

    def list_verdicts(self) -> list[dict]:
        """列出所有判决书（审计用）"""
        files = sorted(self.verdict_dir.glob("V-*.json"))
        return [json.loads(f.read_text(encoding="utf-8")) for f in files]

    def stats(self) -> dict:
        """统计：用于 POC 报告"""
        verdicts = self.list_verdicts()
        by_severity: dict = {}
        by_rule: dict = {}
        for v in verdicts:
            s = v.get("severity", "unknown")
            by_severity[s] = by_severity.get(s, 0) + 1
            r = v.get("rule_violated", "unknown")
            by_rule[r] = by_rule.get(r, 0) + 1
        return {
            "total": len(verdicts),
            "by_severity": by_severity,
            "by_rule": by_rule,
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        g = Guardian()
        j = RollbackJury()
        sid = g.create_snapshot(".")
        v = j.issue(rule_name="no_hardcoded_secrets",
                     original_code='key="sk-abc"',
                     evidence={"pattern": "openai_key"},
                     snapshot_id=sid, user="demo", env="prod", model="deepseek")
        print(f"Snapshot: {sid}")
        print(f"Verdict:  {v.data['verdict_id']}")
        print(f"Severity: {v.data['severity']}")
        print("---")
        print(v.to_markdown()[:500])
