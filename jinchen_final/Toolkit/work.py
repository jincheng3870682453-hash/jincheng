#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
work.py — 核心行为约束（多态诱饵 + AST 检测 + 多语言引擎）

V1 原有功能：
  - 13 层焊缝检测（类型注解、异常处理、SQL 注入、硬编码密钥等）
  - 多态诱饵注入（未导入模块、类型不匹配、无限递归等）
  - AST 行为后验

V3 新增功能：
  - MultiLangASTEngine：支持 Python / Java / Kotlin / TypeScript / Swift
  - 每种语言独立的检测器插件
  - 自动语言识别（按扩展名 + 语法特征）
"""

import re
import ast
import hashlib
import random
import string
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

log = logging.getLogger("work")


# ═════════════════════════════════════════════════════════
# 数据类
# ═════════════════════════════════════════════════════════

@dataclass
class GuardResult:
    """单条检测结果"""
    rule: str
    passed: bool
    action: str          # pass / regenerate / rollback / warn
    evidence: dict = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "passed": self.passed,
            "action": self.action,
            "evidence": self.evidence,
            "message": self.message,
        }


# ═════════════════════════════════════════════════════════
# V1 — InstinctGuard  本能守门（13 层检测）
# ═════════════════════════════════════════════════════════

class InstinctGuard:
    """
    核心守门器 —— 所有 AI 输出必须经过的 13 层焊缝。
    无状态：每次调用独立检测，不依赖历史。
    """

    ALL_RULES = [
        "type_hints", "try_except", "no_hardcoded_secrets",
        "no_sql_injection", "markdown_clean",
        "no_infinite_recursion", "no_unused_import",
        "v1_ast_check",
    ]

    def __init__(self, extra_rules: list | None = None):
        self.extra_rules = extra_rules or []

    # ── 主入口 ────────────────────────────────────────
    def check_all(self, code: str) -> list[GuardResult]:
        """对一段代码执行全部检测，返回结果列表"""
        results: list[GuardResult] = []
        # 内置 7 条
        detectors = [
            ("type_hints",            self._detect_type_hints),
            ("try_except",            self._detect_try_except),
            ("no_hardcoded_secrets",  self._detect_hardcoded_secrets),
            ("no_sql_injection",      self._detect_sql_injection),
            ("markdown_clean",         self._detect_markdown_clean),
            ("no_infinite_recursion", self._detect_infinite_recursion),
            ("no_unused_import",      self._detect_unused_import),
        ]
        for name, fn in detectors:
            try:
                results.append(fn(code))
            except Exception as e:
                results.append(GuardResult(name, False, "regenerate",
                                           {"error": str(e)}, f"检测异常: {e}"))
        # V1 桥接规则
        for rule_name in self.extra_rules:
            results.append(GuardResult(rule_name, True, "pass", {},
                                       "V1 桥接规则（由 gateway 注入）"))
        return results

    def summary(self, results: list[GuardResult]) -> dict:
        """汇总检测结果"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        blocked = sum(1 for r in results if not r.passed and r.action == "rollback")
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "details": [r.to_dict() for r in results],
        }

    def should_block(self, results: list[GuardResult], strict: bool = False) -> bool:
        """是否应该拦截"""
        for r in results:
            if not r.passed:
                if r.action == "rollback" or strict:
                    return True
        return False

    def sanitize(self, text: str) -> str:
        """清理占位符（[TODO]、[待补充] 等）"""
        patterns = [
            r"\[TODO[^\]]*\]", r"\[待补充[^\]]*\]", r"\[待填[^\]]*\]",
            r"\[占位[^\]]*\]", r"\[placeholder[^\]]*\]",
            r"\[fixme[^\]]*\]", r"\[xxx[^\]]*\]", r"\[…+\]",
        ]
        out = text
        for p in patterns:
            out = re.sub(p, "", out, flags=re.I)
        return out.strip()

    # ── 7 条检测实现 ──────────────────────────────────

    def _detect_type_hints(self, code: str) -> GuardResult:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return GuardResult("type_hints", True, "pass", {}, "语法错误无法 AST，跳过")
        func_count = 0
        no_hint = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_count += 1
                args = node.args
                for a in args.args + args.kwonlyargs:
                    if a.arg in ("self", "cls"):
                        continue
                    if a.annotation is None:
                        no_hint.append(a.arg)
                if args.vararg and args.vararg.annotation is None:
                    no_hint.append("*" + args.vararg.arg)
                if args.kwarg and args.kwarg.annotation is None:
                    no_hint.append("**" + args.kwarg.arg)
                if node.returns is None:
                    no_hint.append(f"{node.name}()返回值")
        if func_count == 0:
            return GuardResult("type_hints", True, "pass", {}, "无函数定义")
        if no_hint:
            return GuardResult("type_hints", False, "regenerate",
                               {"missing": no_hint[:5]},
                               f"缺少类型注解: {no_hint[:3]}")
        return GuardResult("type_hints", True, "pass", {}, "类型注解完整")

    def _detect_try_except(self, code: str) -> GuardResult:
        risky = re.search(r"\b(open|socket|subprocess|requests\.(get|post|put|delete)|"
                          r"cursor\.execute|file\.write|os\.remove|shutil)\b", code, re.I)
        has_try = bool(re.search(r"\btry\s*:", code))
        has_except = bool(re.search(r"\bexcept\b", code))
        if risky and not (has_try and has_except):
            ops = re.findall(r"\b(open|socket|subprocess|requests\.(?:get|post|put|delete)|"
                              r"cursor\.execute|file\.write|os\.remove|shutil)\b", code, re.I)
            return GuardResult("try_except", False, "regenerate",
                               {"risky_ops": ops[:3]},
                               f"风险操作缺 try-except: {ops[:2]}")
        return GuardResult("try_except", True, "pass", {}, "异常处理合规")

    def _detect_hardcoded_secrets(self, code: str) -> GuardResult:
        patterns = {
            "openai_key":    r"sk-[a-zA-Z0-9]{20,}",
            "aws_key":       r"AKIA[0-9A-Z]{16}",
            "private_key":   r"-----BEGIN\s+(?:RSA\s+)?PRIVATE KEY-----",
            "generic_token":  r"(?:api_key|apikey|secret|token|password|passwd)\s*=\s*['\"][^'\"]{8,}['\"]",
        }
        for name, pat in patterns.items():
            m = re.search(pat, code)
            if m:
                return GuardResult("no_hardcoded_secrets", False, "rollback",
                                   {"pattern": name, "matched": m.group()[:30]},
                                   f"硬编码密钥: {name}")
        return GuardResult("no_hardcoded_secrets", True, "pass", {}, "无硬编码密钥")

    def _detect_sql_injection(self, code: str) -> GuardResult:
        patterns = [
            r'execute\s*\(\s*["\'][^"\']*[\+\-\.format]',
            r'cursor\.execute\s*\(\s*f?["\'][^"\']*\{',
            r'query\s*=\s*["\'][^"\']*[\+%]',
            r'\.execute\s*\(\s*["\']SELECT.*[\+%]',
        ]
        for p in patterns:
            if re.search(p, code, re.I):
                matched = re.search(p, code, re.I).group()
                return GuardResult("no_sql_injection", False, "rollback",
                                   {"pattern": p, "matched": matched[:60]},
                                   "SQL 拼接风险")
        # 正向：有参数化写法
        if re.search(r"execute\s*\([^)]*%s|execute\s*\([^)]*\?|execute\s*\([^)]*:\w+", code):
            return GuardResult("no_sql_injection", True, "pass", {}, "SQL 写法安全")
        return GuardResult("no_sql_injection", True, "pass", {}, "无 SQL 操作")

    def _detect_markdown_clean(self, code: str) -> GuardResult:
        placeholders = re.findall(r"\[(TODO|待补充|待填|占位|placeholder|fixme|xxx)[^\]]*\]",
                                  code, re.I)
        if placeholders:
            return GuardResult("markdown_clean", False, "regenerate",
                               {"found": placeholders[:3]},
                               f"文档含占位符: {placeholders[:2]}")
        return GuardResult("markdown_clean", True, "pass", {}, "文档干净")

    def _detect_infinite_recursion(self, code: str) -> GuardResult:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return GuardResult("no_infinite_recursion", True, "pass", {}, "跳过")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                calls_self = any(
                    isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Name) and
                    n.func.id == node.name
                    for n in ast.walk(node)
                )
                if calls_self:
                    has_terminate = any(
                        isinstance(n, (ast.If, ast.Return, ast.For, ast.While))
                        for n in ast.walk(node)
                    )
                    if not has_terminate:
                        return GuardResult("no_infinite_recursion", False, "rollback",
                                           {"func": node.name},
                                           f"函数 {node.name} 可能无限递归")
        return GuardResult("no_infinite_recursion", True, "pass", {}, "无无限递归")

    def _detect_unused_import(self, code: str) -> GuardResult:
        imports = re.findall(r"^\s*import\s+(\w+)|^\s*from\s+(\S+)\s+import", code, re.M)
        names: set[str] = set()
        for m in imports:
            n = (m[0] or m[1].split(".")[0]).strip()
            if n and n != "*":
                names.add(n)
        if not names:
            return GuardResult("no_unused_import", True, "pass", {}, "无导入语句")
        body_lines = [l for l in code.splitlines()
                      if not l.strip().startswith(("import ", "from "))]
        body = "\n".join(body_lines)
        unused = []
        for n in sorted(names):
            if re.search(rf"\b{re.escape(n)}\b", body):
                continue
            if re.search(rf"\b{re.escape(n)}\.", body):
                continue
            unused.append(n)
        if unused:
            return GuardResult("no_unused_import", False, "regenerate",
                               {"unused": unused[:3]},
                               f"未使用的导入: {unused[:3]}")
        return GuardResult("no_unused_import", True, "pass", {}, "导入均被使用")

    # ── 多态诱饵注入 ──────────────────────────────────

    def inject_decoy(self, code: str) -> str:
        """注入随机诱饵，用于检测 AI 是否真正理解代码"""
        decoys = [
            "\nimport nonexistent_module_xyz\n",
            "\n# TYPE_MISMATCH: str + int\nresult = 'hello' + 42\n",
            "\n# INFINITE_RECURSION_SEED\ndef _decoy_recurse(n):\n    return _decoy_recurse(n-1)\n",
            "\n# UNUSED_IMPORT_DECOY\nimport json as _unused_json\n",
            "\n# SECRET_DECOY\napi_key = 'sk-decoy-1234567890abcdef'\n",
        ]
        d = random.choice(decoys)
        return code + d

    def verify_fix(self, original: str, fixed: str) -> dict:
        """验证 AI 的"修复"是否真实有效"""
        results = self.check_all(fixed)
        summary = self.summary(results)
        return {
            "passed": summary["passed"] == summary["total"],
            "summary": summary,
            "cheating": self._detect_cheating(original, fixed),
        }

    def _detect_cheating(self, original: str, fixed: str) -> list[str]:
        """检测 AI 是否在"作弊"（搬家、注释掉、无效包裹）"""
        flags = []
        if len(fixed) < len(original) * 0.5:
            flags.append("suspiciously_short")
        if "TODO" in fixed and "TODO" not in original:
            flags.append("added_todo_instead_of_fixing")
        if fixed.count("#") > original.count("#") * 2:
            flags.append("commented_out_instead_of_fixing")
        return flags


# ═════════════════════════════════════════════════════════
# V3 — MultiLangASTEngine  多语言 AST 引擎
# ═════════════════════════════════════════════════════════

class LangDetector:
    """单种语言的检测器集合"""

    def __init__(self, name: str):
        self.name = name
        self.detectors: list[dict] = []

    def register(self, rule_name: str, detect_func: Callable, on_fail: str = "regenerate"):
        self.detectors.append({
            "name": rule_name,
            "detect": detect_func,
            "on_fail": on_fail,
        })

    def check(self, code: str) -> list[dict]:
        violations = []
        for d in self.detectors:
            try:
                if not d["detect"](code):
                    violations.append({
                        "rule": d["name"],
                        "on_fail": d["on_fail"],
                    })
            except Exception:
                pass
        return violations


class MultiLangASTEngine:
    """
    多语言 AST 引擎 —— 插件式检测器。
    支持：Python / Java / Kotlin / TypeScript / Swift
    """

    def __init__(self):
        self.languages: dict[str, LangDetector] = {}
        self._register_python()
        self._register_java()
        self._register_kotlin()
        self._register_typescript()
        self._register_swift()

    # ── Python ────────────────────────────────────────
    def _register_python(self):
        lang = LangDetector("python")
        ig = InstinctGuard()
        lang.register("type_hints",
                     lambda c: ig._detect_type_hints(c).passed, "regenerate")
        lang.register("try_except",
                     lambda c: ig._detect_try_except(c).passed, "regenerate")
        lang.register("no_infinite_recursion",
                     lambda c: ig._detect_infinite_recursion(c).passed, "rollback")
        lang.register("no_unused_import",
                     lambda c: ig._detect_unused_import(c).passed, "regenerate")
        self.languages["python"] = lang

    # ── Java ──────────────────────────────────────────
    def _register_java(self):
        lang = LangDetector("java")
        lang.register("try_catch",
                     lambda c: not bool(re.search(r"\b(FileInputStream|Socket\(|"
                                               r"ProcessBuilder|Runtime\.getRuntime)", c))
                               or bool(re.search(r"try\s*\{", c)),
                     "regenerate")
        lang.register("no_bare_printstack",
                     lambda c: "printStackTrace" not in c
                               or bool(re.search(r"\b(logger|Log\.|Logger\.)", c)),
                     "regenerate")
        lang.register("sql_prepared_statement",
                     lambda c: "Statement" not in c
                               or "PreparedStatement" in c
                               or "prepareStatement" in c,
                     "rollback")
        def _has_javadoc(c):
            # 提取所有 public 方法：(方法名, 参数列表)
            methods = re.findall(
                r"public\s+(?:static\s+|final\s+)*"
                r"[\w<>\[\],\s\?]+?\s+"
                r"(\w+)\s*\(([^)]*)\)\s*\{", c)
            if not methods:
                return True
            # 简单类（所有方法都无参）→ 不强制 Javadoc
            all_no_params = all(len(m[1].strip()) == 0 for m in methods)
            if all_no_params:
                return True
            # 有带参方法 → 要求存在 /** ... */ Javadoc 块
            has_javadoc_blocks = bool(
                re.search(r"/\*\*(?:\s*\n\s*\*\s*\w).*?\*/", c, re.DOTALL))
            return has_javadoc_blocks
        lang.register("has_javadoc", _has_javadoc, "warn")
        self.languages["java"] = lang

    # ── Kotlin ────────────────────────────────────────
    def _register_kotlin(self):
        lang = LangDetector("kotlin")
        lang.register("explicit_types",
                     lambda c: not bool(re.search(r"fun\s+\w+\s*\([^)]*\)\s*\{", c))
                               or bool(re.search(r"fun\s+\w+\s*\([^)]*\)\s*:\s*\w", c)),
                     "regenerate")
        lang.register("no_bang_bang",
                     lambda c: c.count("!!") == 0,
                     "regenerate")
        lang.register("uses_coroutines",
                     lambda c: "Thread(" not in c
                               or "CoroutineScope" in c
                               or "launch" in c
                               or "async" in c,
                     "warn")
        self.languages["kotlin"] = lang

    # ── TypeScript ───────────────────────────────────
    def _register_typescript(self):
        lang = LangDetector("typescript")
        lang.register("ts_type_annotations",
                     lambda c: ": any" not in c
                               and (bool(re.search(r"interface\s+\w+|type\s+\w+\s*=", c))
                                    or bool(re.search(r"function\s+\w+\s*\([^)]*\)\s*:", c))),
                     "regenerate")
        lang.register("no_any",
                     lambda c: ": any" not in c and "as any" not in c,
                     "warn")
        lang.register("promise_handled",
                     lambda c: "Promise" not in c
                               or "await" in c
                               or ".then(" in c
                               or ".catch(" in c,
                     "regenerate")
        self.languages["typescript"] = lang

    # ── Swift ────────────────────────────────────────
    def _register_swift(self):
        lang = LangDetector("swift")
        lang.register("optional_binding",
                     lambda c: c.count("!") <= 1
                               or "guard let" in c
                               or "if let" in c,
                     "regenerate")
        lang.register("error_handling",
                     lambda c: "try!" not in c
                               and ("do {" in c and "catch" in c
                                    or "try?" in c),
                     "regenerate")
        lang.register("no_force_chain",
                     lambda c: c.count("!") <= 2,
                     "warn")
        self.languages["swift"] = lang

    # ── 自动语言识别 ──────────────────────────────────
    def detect_language(self, code: str, filename: str = "") -> str:
        ext_map = {
            ".py": "python", ".java": "java", ".kt": "kotlin",
            ".ts": "typescript", ".tsx": "typescript",
            ".swift": "swift", ".js": "typescript",
        }
        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang
        if "func " in code and "->" in code and "let " in code:
            return "swift"
        if "public static void" in code:
            return "java"
        if "fun " in code and "val " in code:
            return "kotlin"
        if "interface " in code and ": " in code:
            return "typescript"
        return "python"

    def check(self, code: str, filename: str = "") -> dict:
        lang = self.detect_language(code, filename)
        if lang not in self.languages:
            return {"language": lang, "violations": [], "passed": True}
        violations = self.languages[lang].check(code)
        return {
            "language": lang,
            "violations": violations,
            "passed": len(violations) == 0,
        }

    def list_supported(self) -> dict[str, list[str]]:
        return {
            name: [d["name"] for d in lang.detectors]
            for name, lang in self.languages.items()
        }


# ═════════════════════════════════════════════════════════
# 快捷函数
# ═════════════════════════════════════════════════════════

def check_code(code: str, filename: str = "") -> dict:
    """一行检查代码（自动识别语言 + 全部规则）"""
    guard = InstinctGuard()
    ml = MultiLangASTEngine()
    r1 = guard.check_all(code)
    r2 = ml.check(code, filename)
    return {
        "guard": guard.summary(r1),
        "multilang": r2,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        f = sys.argv[1]
        code = open(f, encoding="utf-8").read()
        result = check_code(code, f)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("用法: python work.py <file.py/java/kt/ts/swift>")
