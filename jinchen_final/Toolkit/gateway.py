#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gateway.py — 统一网关（意图理解 + Skill 推荐 + 飞轮 + V1 桥接）

V2 功能：
  - IntentEngine：轻量意图识别（关键词映射，零训练）
  - SkillRecommender：交互式 Skill 推荐（用户自选，不猜）
  - FineTunedCore：多平台模型调用（10+ AI 平台）
  - FeedbackFlywheel：反馈飞轮（违规数据回灌训练）
  - PolicyEngine：动态策略（dev/test/prod 分级守门）
  - V1Bridge：V1 模块自动桥接（guardian/Archive/shiyun/Nuwa）

V3 功能：
  - 以上全部 + 多语言 AST 集成 + 回滚陪审团集成 + 辐射检测集成
"""

import os
import re
import sys
import json
import random
import string
import logging
import warnings
import importlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Callable

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("gateway")

# 导入同包模块
from . import work, guardian, Archive, shiyun
import Toolkit.Nuwa as NuwaModule
from .Nuwa import Nuwa as NuwaCls


# ════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════

def _rid(prefix: str = "id", n: int = 8) -> str:
    return prefix + "-" + "".join(random.choices(string.hexdigits.lower(), k=n))

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _read(p: str) -> str:
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""

def _write(p: str, content: str) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(content, encoding="utf-8")


# ════════════════════════════════════════════════════════
# L1 — IntentEngine  意图理解
# ════════════════════════════════════════════════════════

class IntentEngine:
    """轻量意图识别 —— 关键词映射，零训练数据"""

    CATEGORIES = {
        "code_python":  ["python", "函数", "类", "def ", "import ", "pip"],
        "code_api":     ["接口", "api", "路由", "endpoint", "rest"],
        "code_sql":     ["sql", "查询", "数据库", "select", "insert", "表"],
        "code_refactor": ["重构", "优化", "简化", "重命名"],
        "fiction":      ["小说", "故事", "角色", "剧情", "世界观", "章节"],
        "doc":          ["文档", "readme", "说明", "markdown"],
        "config":       ["配置", "环境变量", "config", "settings"],
        "test":         ["测试", "test", "unittest", "pytest"],
    }

    def classify(self, user_input: str) -> dict:
        text = user_input.lower()
        scores: dict[str, float] = {}
        for cat, kws in self.CATEGORIES.items():
            score = 0.0
            for kw in kws:
                if kw.lower() in text:
                    score += 1.0
            if score > 0:
                scores[cat] = score
        if not scores:
            return {"category": "general", "confidence": 0.0, "tags": []}
        best = max(scores, key=scores.get)
        # 提取命中的标签
        tags = []
        for kw in self.CATEGORIES[best]:
            if kw.lower() in text:
                tags.append(kw)
        return {
            "category": best,
            "confidence": scores[best] / len(self.CATEGORIES[best]),
            "tags": tags,
        }


# ════════════════════════════════════════════════════════
# L2 — Skill  技能单元
# ════════════════════════════════════════════════════════

@dataclass
class Skill:
    """单个 Skill 文件"""
    name: str
    content: str
    tags: list[str] = field(default_factory=list)
    desc: str = ""

    @classmethod
    def load(cls, path: str) -> "Skill":
        text = Path(path).read_text(encoding="utf-8")
        tags: list[str] = []
        desc = ""
        for line in text.splitlines():
            if line.startswith("# Tags:"):
                tags = [t.strip() for t in line.replace("# Tags:", "").split(",")]
            elif line.startswith("# Desc:"):
                desc = line.replace("# Desc:", "").strip()
        return cls(name=Path(path).stem, content=text, tags=tags, desc=desc)

    @classmethod
    def load_dir(cls, directory: str) -> list["Skill"]:
        skills = []
        d = Path(directory)
        if not d.exists():
            return skills
        for f in sorted(d.glob("*.skill")):
            try:
                skills.append(cls.load(str(f)))
            except Exception as e:
                log.warning(f"⚠️ 加载 Skill 失败 {f}: {e}")
        return skills


class SkillRecommender:
    """
    交互式 Skill 推荐器。
    核心哲学：不猜用户要什么，直接问。
    """

    def __init__(self, skills: list[Skill]):
        self.skills = skills

    def recommend(self, user_input: str, top_k: int = 5) -> list[Skill]:
        text = user_input.lower()
        scored: list[tuple[int, Skill]] = []
        extra_kw = ["python", "api", "sql", "markdown", "error",
                    "test", "refactor", "fiction", "novel", "narrative",
                    "小说", "故事", "剧情", "接口", "数据库", "文档",
                    "世界观", "角色", "章节"]
        for s in self.skills:
            score = 0
            for tag in s.tags:
                if tag.lower() in text:
                    score += 2
            content_l = s.content.lower()
            for kw in extra_kw:
                if kw in text and kw in content_l:
                    score += 1
            for word in re.split(r"[\s,，。.!?]+", user_input):
                if len(word) >= 2 and word.lower() in content_l:
                    score += 0.5
            if score > 0:
                scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:top_k]]

    def ask_user(self, user_input: str, top_k: int = 5) -> list[Skill]:
        """交互式：弹出推荐 → 用户勾选 → 返回"""
        recs = self.recommend(user_input, top_k)
        if not recs:
            return []
        print(f"\n{'═'*40}")
        print(f"🎯 检测到需求: {user_input}")
        print(f"{'─'*40}")
        print(f"📋 推荐以下 Skill（输入编号选择，逗号分隔）:\n")
        for i, s in enumerate(recs, 1):
            tags = ", ".join(s.tags)
            desc = s.desc or s.content.split('\n')[0][:60]
            print(f"  [{i}] {s.name}  ({tags})")
            print(f"      └─ {desc}")
        print(f"\n  [a] 全选   [s] 跳过   [q] 取消")
        print(f"{'═'*40}")

        try:
            choice = input("👉 你的选择(默认全选): ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = ""

        if choice == "q":
            return []
        if choice == "s":
            return []
        if choice == "a" or not choice:
            return recs

        selected = []
        for idx in choice.split(","):
            idx = idx.strip()
            if idx.isdigit() and 1 <= int(idx) <= len(recs):
                selected.append(recs[int(idx) - 1])
        return selected or recs

    def assemble(self, skills: list[Skill], user_input: str) -> str:
        """将选中的 Skill 组装成 prompt"""
        if not skills:
            return user_input
        parts = ["以下是可用的专业规范（Skill）：\n"]
        for s in skills:
            parts.append(f"--- Skill: {s.name} ---")
            parts.append(s.content[:2000])
            parts.append("")
        parts.append(f"--- 用户需求 ---")
        parts.append(user_input)
        return "\n".join(parts)


# ════════════════════════════════════════════════════════
# L3 — FineTunedCore  多平台模型调用
# ════════════════════════════════════════════════════════

PROVIDERS: dict[str, dict] = {
    "openai":      {"url": "https://api.openai.com/v1/chat/completions",       "model": "gpt-4o-mini"},
    "anthropic":   {"url": "https://api.anthropic.com/v1/messages",         "model": "claude-sonnet-4-20250514"},
    "gemini":      {"url": "https://generativelanguage.googleapis.com/v1beta/models", "model": "gemini-1.5-pro"},
    "ollama":      {"url": "http://localhost:11434/api/generate",           "model": "llama2"},
    "qwen":        {"url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation", "model": "qwen-plus"},
    "zhipu":       {"url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "model": "glm-4"},
    "deepseek":    {"url": "https://api.deepseek.com/v1/chat/completions",  "model": "deepseek-coder"},
    "minimax":     {"url": "https://api.minimax.chat/v1/text/chatcompletion_v2", "model": "abab6-chat"},
    "baichuan":    {"url": "https://api.baichuan-ai.com/v1/chat",          "model": "Baichuan3-Turbo"},
    "hunyuan":     {"url": "https://hunyuan.tencentcloudapi.com/",         "model": "hunyuan-pro"},
}


class FineTunedCore:
    """多平台模型调用核心"""

    def __init__(self, provider: str = "deepseek", model: str = "",
                 api_key: str = "", base_url: str = "", timeout: int = 60):
        self.provider = provider
        self.model = model or PROVIDERS.get(provider, {}).get("model", "default")
        self.api_key = api_key or os.getenv(f"NUWA_AI_API_KEY", "")
        self.base_url = base_url or PROVIDERS.get(provider, {}).get("url", "")
        self.timeout = timeout

    def generate(self, prompt: str, **kwargs) -> str:
        """调用模型生成文本"""
        try:
            import requests
        except ImportError:
            return f"[MOCK] {prompt[:100]}..."

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = self.base_url
        data: dict = {}

        if self.provider == "anthropic":
            url = f"{self.base_url.rstrip('/')}"
            data = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", 2048),
                "messages": [{"role": "user", "content": prompt}],
            }
        elif self.provider == "gemini":
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
            data = {"contents": [{"parts": [{"text": prompt}]}]}
        elif self.provider == "ollama":
            url = f"{self.base_url.rstrip('/')}/api/generate"
            data = {"model": self.model, "prompt": prompt, "stream": False}
        else:
            # OpenAI 兼容格式（DeepSeek/Qwen/Zhipu/MiniMax/Baichuan 等）
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": kwargs.get("max_tokens", 2048),
                "temperature": kwargs.get("temperature", 0.3),
            }

        try:
            resp = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            resp.raise_for_status()
            j = resp.json()

            # 统一提取文本
            if self.provider == "anthropic":
                return j.get("content", [{}])[0].get("text", "")
            elif self.provider == "gemini":
                return j.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            elif self.provider == "ollama":
                return j.get("response", "")
            else:
                return j.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            log.warning(f"⚠️ 模型调用失败 ({self.provider}): {e}")
            return f"[MOCK-{self.provider}] {prompt[:200]}"

    def list_providers(self) -> dict:
        return {k: v["model"] for k, v in PROVIDERS.items()}


# ════════════════════════════════════════════════════════
# L4 — PolicyEngine  动态策略引擎
# ════════════════════════════════════════════════════════

class PolicyEngine:
    """
    动态策略引擎 —— 按环境等级加载不同规则集。
    dev → 只卡红线（安全相关）
    test → 加代码质量
    prod → 全部规则 + 严格模式
    """

    POLICIES = {
        "dev": {
            "description": "开发环境：仅安全红线",
            "rules": ["no_hardcoded_secrets", "no_sql_injection"],
            "max_retries": 1,
            "strict": False,
        },
        "test": {
            "description": "测试环境：加代码质量",
            "rules": [
                "type_hints", "no_hardcoded_secrets",
                "no_sql_injection", "markdown_clean",
                "no_infinite_recursion", "no_unused_import",
            ],
            "max_retries": 2,
            "strict": False,
        },
        "prod": {
            "description": "生产环境：全部规则 + 严格模式",
            "rules": [
                "type_hints", "try_except", "no_hardcoded_secrets",
                "no_sql_injection", "markdown_clean",
                "no_infinite_recursion", "no_unused_import",
                "v1_ast_check",
            ],
            "max_retries": 3,
            "strict": True,
        },
    }

    def __init__(self, env: str = "dev"):
        self.env = env if env in self.POLICIES else "dev"
        self.policy = self.POLICIES[self.env].copy()

    def active_rule_names(self, all_rule_names: list[str]) -> list[str]:
        active = set(self.policy["rules"])
        return [r for r in all_rule_names if r in active]

    def should_block(self, results: list) -> bool:
        if self.policy.get("strict"):
            return any(not r.passed for r in results)
        return any(not r.passed and r.action == "rollback" for r in results)

    def max_retries(self) -> int:
        return self.policy.get("max_retries", 2)


# ════════════════════════════════════════════════════════
# L5 — FeedbackFlywheel  反馈飞轮
# ════════════════════════════════════════════════════════

@dataclass
class FeedbackRecord:
    """单条反馈记录"""
    timestamp: str
    user_input: str
    rule: str
    original: str
    fixed: str
    skills: list[str] = field(default_factory=list)
    verdict_id: str = ""

class FeedbackFlywheel:
    """
    反馈飞轮 —— 违规数据积累 → 回灌训练 → 模型越用越准。
    """

    def __init__(self, store_dir: str = "feedback"):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[FeedbackRecord] = []
        self._load()

    def _load(self):
        f = self.store_dir / "feedback.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(line)
                    self.records.append(FeedbackRecord(**d))
                except Exception:
                    pass

    def record(self, *, user_input: str, rule: str,
               original: str, fixed: str,
               skills: list[str] | None = None,
               verdict_id: str = "") -> FeedbackRecord:
        rec = FeedbackRecord(
            timestamp=_now(),
            user_input=user_input[:200],
            rule=rule,
            original=original[:1000],
            fixed=fixed[:1000],
            skills=skills or [],
            verdict_id=verdict_id,
        )
        self.records.append(rec)
        # 追加写入
        with open(self.store_dir / "feedback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.__dict__, ensure_ascii=False) + "\n")
        return rec

    def export_training_data(self, output_path: str) -> str:
        """导出 SFT 训练数据（JSONL 格式）"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for r in self.records:
                item = {
                    "instruction": r.user_input,
                    "input": r.original,
                    "output": r.fixed,
                    "metadata": {
                        "rule": r.rule,
                        "skills": r.skills,
                        "verdict_id": r.verdict_id,
                    },
                }
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                count += 1
        return f"导出 {count} 条 SFT 训练样本 → {output_path}"

    def stats(self) -> dict:
        by_rule: dict = {}
        for r in self.records:
            by_rule[r.rule] = by_rule.get(r.rule, 0) + 1
        return {
            "total": len(self.records),
            "by_rule": by_rule,
        }


# ════════════════════════════════════════════════════════
# V1Bridge  V1 模块自动桥接
# ════════════════════════════════════════════════════════

class V1Bridge:
    """
    V1 模块自动桥接。
    检测 guardian / Archive / shiyun / Nuwa 是否可用，
    可用即接入，不可用则降级。
    """

    MODULES = ["work", "guardian", "Archive", "shiyun", "Nuwa"]

    def __init__(self):
        self.available: dict[str, bool] = {}
        self.modules: dict[str, object] = {}
        for name in self.MODULES:
            try:
                mod = importlib.import_module(f".{name}", package="Toolkit")
                self.modules[name] = mod
                self.available[name] = True
            except Exception:
                self.available[name] = False

    def get(self, name: str):
        return self.modules.get(name)

    def ast_check(self, code: str) -> list[dict]:
        """调用 V1 work.py 的 AST 检测"""
        work_mod = self.get("work")
        if not work_mod:
            return []
        results = []
        # 尝试调用 work 里的检测函数
        for fn_name in ["check_type_hints", "check_no_recursion",
                        "check_hardcoded", "check_injection"]:
            fn = getattr(work_mod, fn_name, None)
            if fn:
                try:
                    r = fn(code)
                    if isinstance(r, dict):
                        results.append(r)
                except Exception:
                    pass
        return results

    def snapshot(self, root: str = ".") -> Optional[str]:
        g = self.get("guardian")
        if not g:
            return None
        fn = getattr(g, "create_snapshot", None)
        if fn:
            try:
                return fn(root)
            except Exception:
                pass
        return None

    def rollback(self, snap_id: str, root: str = ".") -> Optional[dict]:
        g = self.get("guardian")
        if not g:
            return None
        fn = getattr(g, "rollback", None)
        if fn:
            try:
                return fn(snap_id, root)
            except Exception:
                pass
        return None


# ════════════════════════════════════════════════════════
# GatewayResult  统一返回
# ════════════════════════════════════════════════════════

@dataclass
class GatewayResult:
    """WordGateway 的统一返回"""
    intent: dict = field(default_factory=dict)
    skills_used: list[str] = field(default_factory=list)
    model_output: str = ""
    guard_summary: dict = field(default_factory=dict)
    retries: int = 0
    final_action: str = "pass"  # pass / rollback / warn
    multilingal: dict = field(default_factory=dict)
    verdict_id: str = ""
    errors: list[str] = field(default_factory=list)


# ════════════════════════════════════════════════════════
# WordGateway  主入口
# ════════════════════════════════════════════════════════

class WordGateway:
    """
    Word 体系统一网关 —— 无状态、可审计、可治理。

    每次调用独立、无状态。
    内部串联：意图 → Skill推荐 → 模型调用 → 守门 → 飞轮 → 陪审团
    """

    def __init__(self, config: dict | None = None):
        config = config or {}

        # 环境
        self.env_name = config.get("env", os.getenv("NUWA_ENV", "dev"))
        self.user = config.get("user", os.getenv("NUWA_USER", "anonymous"))

        # 子模块
        self.intent = IntentEngine()
        self.skill_recommender = SkillRecommender(
            Skill.load_dir(config.get("skill_dir", "Toolkit/skills"))
        )
        self.model = FineTunedCore(
            provider=config.get("model", {}).get("provider", "deepseek"),
            model=config.get("model", {}).get("model", ""),
            api_key=config.get("model", {}).get("api_key", ""),
            base_url=config.get("model", {}).get("base_url", ""),
            timeout=config.get("model", {}).get("timeout", 60),
        )
        self.guard = work.InstinctGuard()
        self.policy = PolicyEngine(self.env_name)
        self.flywheel = FeedbackFlywheel(config.get("feedback_dir", "feedback"))
        self.v1 = V1Bridge()

        # 多语言引擎
        self.multilang = work.MultiLangASTEngine()

        # 回滚陪审团
        self.jury = guardian.RollbackJury(config.get("verdict_dir", "verdicts"))

        # 辐射检测
        self.rad = NuwaModule.RadiationDetector(config.get("project_root", "."))

        # 配置守门规则（按策略过滤）
        all_rules = work.InstinctGuard.ALL_RULES
        active = self.policy.active_rule_names(all_rules)
        # 重建 guard 的 extra_rules
        v1_rules = ["v1_ast_check"] if self.v1.available.get("work") else []
        self.guard.extra_rules = [r for r in v1_rules if r in active]

    # ── 主入口 ──────────────────────────────────────
    def handle(self, user_input: str, *, interactive: bool = False,
               filename: str = "") -> GatewayResult:
        """
        处理一次完整的用户请求。
        无状态：每次调用独立，不依赖历史。
        """
        result = GatewayResult(intent=self.intent.classify(user_input))

        # L2: Skill 推荐
        if interactive:
            skills = self.skill_recommender.ask_user(user_input)
        else:
            skills = self.skill_recommender.recommend(user_input)
        result.skills_used = [s.name for s in skills]

        # 组装 prompt
        prompt = self.skill_recommender.assemble(skills, user_input)

        # L3: 模型调用（带重试）
        max_retries = self.policy.max_retries()
        output = ""
        for attempt in range(max_retries + 1):
            output = self.model.generate(prompt)
            result.retries = attempt

            # L4: 守门检测
            guard_results = self.guard.check_all(output)
            result.guard_summary = self.guard.summary(guard_results)

            # 多语言检测
            ml_result = self.multilang.check(output, filename)
            result.multilingal = ml_result

            # 判断是否需要重试
            should_block = self.policy.should_block(guard_results)
            if not should_block and ml_result.get("passed", True):
                result.final_action = "pass"
                break

            # 违规 → 记录 + 签发判决书 + 重试
            for gr in guard_results:
                if not gr.passed:
                    verdict = self.jury.issue(
                        rule_name=gr.rule,
                        original_code=output[:500],
                        evidence=gr.evidence,
                        snapshot_id=f"snap-{attempt}",
                        user=self.user,
                        env=self.env_name,
                        model=self.model.provider,
                    )
                    result.verdict_id = verdict.data["verdict_id"]
                    self.flywheel.record(
                        user_input=user_input,
                        rule=gr.rule,
                        original=output[:500],
                        fixed="[retry]",
                        skills=result.skills_used,
                        verdict_id=result.verdict_id,
                    )
            log.info(f"  ⚠️ 第 {attempt+1} 次尝试违规，准备重试...")

        result.model_output = self.guard.sanitize(output)
        return result

    # ── 统计 ────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "env": self.env_name,
            "policy": self.policy.policy.get("description", ""),
            "rules_active": self.policy.active_rule_names(work.InstinctGuard.ALL_RULES),
            "skills_loaded": len(self.skill_recommender.skills),
            "v1_available": self.v1.available,
            "flywheel": self.flywheel.stats(),
            "jury": self.jury.stats(),
            "multilang": self.multilang.list_supported(),
        }


# ════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════

def main():
    """命令行入口"""
    config_path = "config.json"
    config = {}
    if Path(config_path).exists():
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    else:
        config = {
            "env": os.getenv("NUWA_ENV", "dev"),
            "model": {
                "provider": os.getenv("NUWA_AI_PROVIDER", "deepseek"),
                "api_key": os.getenv("NUWA_AI_API_KEY", "sk-xxx"),
            },
            "skill_dir": "Toolkit/skills",
            "user": "cli_user",
        }

    gw = WordGateway(config)

    print(f"🛡️ Word 体系网关  |  环境: {gw.env_name}  |  模型: {gw.model.provider}")
    print(f"📋 规则: {len(gw.policy.active_rule_names(work.InstinctGuard.ALL_RULES))} 条激活")
    print(f"🎯 Skills: {len(gw.skill_recommender.skills)} 个")
    print(f"🔌 V1: {gw.v1.available}")
    print(f"{'─'*50}")

    # 交互模式
    if sys.stdin.isatty():
        print("💬 输入需求开始对话（输入 'quit' 退出，'stats' 查看统计）:\n")
        while True:
            try:
                user_input = input("👤 > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n👋 再见！")
                break
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 再见！")
                break
            if user_input.lower() == "stats":
                print(json.dumps(gw.stats(), indent=2, ensure_ascii=False))
                continue

            result = gw.handle(user_input, interactive=True)
            print(f"\n{'═'*50}")
            print(f"📊 意图: {result.intent.get('category','?')}")
            print(f"🎯 Skills: {result.skills_used}")
            print(f"🛡️ 守门: {result.guard_summary}")
            print(f"🔄 重试: {result.retries}")
            print(f"✅ 最终: {result.final_action}")
            if result.verdict_id:
                print(f"⚖️ 判决书: {result.verdict_id}")
            print(f"{'─'*50}")
            print(f"📤 输出:\n{result.model_output[:500]}")
            print()
    else:
        # 管道模式
        user_input = sys.stdin.read().strip()
        if user_input:
            result = gw.handle(user_input)
            print(result.model_output)


if __name__ == "__main__":
    main()
