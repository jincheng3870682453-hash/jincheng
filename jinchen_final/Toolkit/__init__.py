"""Toolkit — Word 体系（整合版）

V2 功能：Skill 交互推荐、飞轮训练、V1 模块桥接
V3 功能：动态策略引擎、回滚陪审团、全栈辐射检测、多语言 AST

模块分工：
  work.py          → 行为约束（13 层检测 + 多语言 AST 引擎）
  guardian.py      → 快照回滚 + 回滚陪审团（违规判决书）
  Archive.py       → 长对话记忆（SimHash）
  shiyun.py       → 硬核叙事工厂
  Nuwa.py         → POC 报告 + 辐射检测
  gateway.py       → 统一网关（含意图理解 + Skill 推荐 + 飞轮）
  Proteus.py      → 交互启动入口
"""
from . import work, guardian, Archive, shiyun, Nuwa as NuwaModule, gateway, Proteus
from .work import (
    InstinctGuard, GuardResult,
    MultiLangASTEngine, LangDetector,
)
from .guardian import Guardian, RollbackJury, Verdict
from .Archive import Archive
from .shiyun import Shiyun
from .Nuwa import Nuwa, RadiationDetector, RadAlert
from .gateway import (
    WordGateway, IntentEngine,
    SkillRecommender, Skill,
    FineTunedCore, PolicyEngine,
    FeedbackFlywheel, GatewayResult,
)
from .gateway import V1Bridge

__all__ = [
    "work", "guardian", "Archive", "shiyun", "NuwaModule", "gateway", "Proteus",
    "InstinctGuard", "GuardResult",
    "MultiLangASTEngine", "LangDetector",
    "Guardian", "RollbackJury", "Verdict",
    "Archive", "Shiyun", "Nuwa",
    "RadiationDetector", "RadAlert",
    "WordGateway", "IntentEngine",
    "SkillRecommender", "Skill",
    "FineTunedCore", "PolicyEngine",
    "FeedbackFlywheel", "GatewayResult",
    "V1Bridge",
]
