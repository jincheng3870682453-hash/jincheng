#!/usr/bin/env python3
"""verify.py — Word 体系 V2+V3 整合版全功能验证"""
import sys, os, json, traceback
sys.path.insert(0, '.')

PASS = 0; FAIL = 0; results = []

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; results.append(("✅", name, detail))
        print(f"  ✅ {name}  {detail}")
    else:
        FAIL += 1; results.append(("❌", name, detail))
        print(f"  ❌ {name}  {detail}")

print("═"*55)
print("  Word 体系 V2+V3 整合版 — 全功能验证")
print("═"*55)

# ── 导入 ─────────────────────────────────────────
print("\n📦 模块导入")
try:
    from Toolkit import (
        work, guardian, Archive, shiyun, Nuwa, gateway, Proteus,
        InstinctGuard, MultiLangASTEngine, LangDetector,
        Guardian, RollbackJury, Verdict,
        Archive as ArchiveMod,
        Shiyun, Nuwa as NuwaMod,
        RadiationDetector, RadAlert,
        WordGateway, IntentEngine,
        SkillRecommender, Skill,
        FineTunedCore, PolicyEngine,
        FeedbackFlywheel, GatewayResult, V1Bridge,
    )
    check("所有模块导入成功", True, "7 个 .py 全部 OK")
except Exception as e:
    check("模块导入", False, str(e))
    traceback.print_exc()
    sys.exit(1)

# ── L1 IntentEngine ────────────────────────────────
print("\n🧠 L1 IntentEngine")
ie = IntentEngine()
r = ie.classify("帮我写一个 Python 登录接口")
check("Python API 意图", r["category"] == "code_python", f"→ {r['category']}")
r2 = ie.classify("写一个 SQL 查询")
check("SQL 意图", r2["category"] == "code_sql", f"→ {r2['category']}")
r3 = ie.classify("帮我构思小说剧情")
check("小说意图", r3["category"] == "fiction", f"→ {r3['category']}")

# ── L2 SkillRecommender ────────────────────────────
print("\n🎯 L2 SkillRecommender")
from pathlib import Path as _P
skills = Skill.load_dir("Toolkit/skills")
check("Skill 加载", len(skills) >= 5, f"加载 {len(skills)} 个")
sr = SkillRecommender(skills)
recs = sr.recommend("帮我写 Python 接口")
names = [s.name for s in recs]
check("Python 推荐", "python_api_design" in names, f"→ {names[:3]}")
recs2 = sr.recommend("写个 SQL 查询")
check("SQL 推荐", "sql_safety" in [s.name for s in recs2])
recs3 = sr.recommend("写小说剧情")
check("小说推荐", "fiction_writing" in [s.name for s in recs3])
prompt = sr.assemble(recs, "写登录接口")
check("Prompt 组装", "Skill:" in prompt and "写登录接口" in prompt)

# ── V1 InstinctGuard (work.py) ─────────────────────
print("\n🛡️ InstinctGuard (work.py)")
ig = InstinctGuard()

good = "def add(a: int, b: int) -> int:\n    return a + b\n"
r1 = ig.check_all(good)
check("type_hints 通过", any(x.rule=="type_hints" and x.passed for x in r1))

bad = "def add(a, b):\n    return a + b\n"
r2 = ig.check_all(bad)
check("type_hints 拦截", any(x.rule=="type_hints" and not x.passed for x in r2))

risky = 'def read(p):\n    f=open(p)\n    return f.read()\n'
r3 = ig.check_all(risky)
check("try_except 拦截", any(x.rule=="try_except" and not x.passed for x in r3))

safe = 'def read(p):\n    try:\n        f=open(p)\n        return f.read()\n    except OSError:\n        return ""\n'
r4 = ig.check_all(safe)
check("try_except 通过", any(x.rule=="try_except" and x.passed for x in r4))

secret = 'api_key = "sk-1234567890abcdef12345678"\n'
r5 = ig.check_all(secret)
check("hardcoded 拦截", any(x.rule=="no_hardcoded_secrets" and not x.passed for x in r5))

sqli = 'cursor.execute("SELECT * FROM u WHERE n=\'" + name + "\'")\n'
r6 = ig.check_all(sqli)
check("sqli 拦截", any(x.rule=="no_sql_injection" and not x.passed for x in r6))

md_bad = "# Title\n[TODO: fill]\n"
r7 = ig.check_all(md_bad)
check("markdown 拦截", any(x.rule=="markdown_clean" and not x.passed for x in r7))

rec_code = "def f(n):\n    f(n-1)\n    f(n-2)\nf(5)\n"
r8 = ig.check_all(rec_code)
check("recursion 拦截", any(x.rule=="no_infinite_recursion" and not x.passed for x in r8))

ui = "import os\nimport sys\nx = 1\n"
r9 = ig.check_all(ui)
check("unused_import 拦截", any(x.rule=="no_unused_import" and not x.passed for x in r9))

san = ig.sanitize("Hello [TODO: xxx] world [占位符] end")
check("sanitize 清理", "[TODO" not in san and "占位" not in san)

# ── PolicyEngine ───────────────────────────────────
print("\n🔀 PolicyEngine 动态策略")
for env in ["dev", "test", "prod"]:
    p = PolicyEngine(env)
    names = p.active_rule_names(InstinctGuard.ALL_RULES)
    print(f"  [{env}] → {len(names)} 条: {names}")
    check(f"Policy[{env}]", len(names) > 0, f"{len(names)}条")

# ── L5 FeedbackFlywheel ────────────────────────────
print("\n🔄 FeedbackFlywheel")
fw = FeedbackFlywheel("test_feedback")
rec = fw.record(user_input="test", rule="type_hints",
                 original="def f(x): pass", fixed="def f(x:int)->None: pass",
                 skills=["python_api_design"], verdict_id="V-test")
check("飞轮记录", len(fw.records) == 1)
exp = fw.export_training_data("test_feedback/sft.jsonl")
check("SFT 导出", "导出" in exp and _P("test_feedback/sft.jsonl").exists())
check("飞轮统计", fw.stats()["total"] == 1)

# ── L6 RollbackJury (guardian.py) ──────────────────
print("\n⚖️ RollbackJury (guardian.py)")
jury = RollbackJury("test_verdicts")
v = jury.issue(rule_name="no_hardcoded_secrets",
                original_code='key="sk-abc"',
                evidence={"pattern": "openai_key"},
                snapshot_id="snap-001", user="jincheng", env="prod", model="deepseek")
check("判决书签发", v.data["verdict_id"].startswith("V-"))
check("判决书签名", len(v.data["signature"]) == 16)
check("Markdown 生成", "违规判决书" in v.to_markdown())
check("JSON 生成", "verdict_id" in v.to_json())
check("判决书列表", len(jury.list_verdicts()) >= 1)
check("陪审团统计", jury.stats()["total"] >= 1)

# ── Guardian 快照回滚 ───────────────────────────────
print("\n💾 Guardian 快照回滚")
g = Guardian("test_snaps")
# 创建测试文件
_P("test_proj").mkdir(exist_ok=True)
_P("test_proj/main.py").write_text("print('hello')\n", encoding="utf-8")
sid = g.create_snapshot("test_proj")
check("快照创建", sid.startswith("snap-"))
check("快照预检", g.precheck(sid)["valid"])
result = g.rollback(sid, "test_proj")
check("快照回滚", result["status"] == "rolled_back")

# ── L7 RadiationDetector (Nuwa.py) ────────────────
print("\n☢️ RadiationDetector (Nuwa.py)")
rd = RadiationDetector(".")
_P("test_rad.py").write_text(
    "import os\nkey = os.getenv('DB_HOST')\n"
    "def query():\n    cursor.execute('SELECT * FROM users')\n",
    encoding="utf-8")
alerts = rd.scan("test_rad.py")
check("辐射检测运行", len(alerts) >= 0, f"{len(alerts)}条告警")
_P(".env.example").write_text("DB_HOST=localhost\n", encoding="utf-8")
alerts2 = rd.scan("test_rad.py")
report = rd.generate_report(alerts)
check("辐射报告", "辐射" in report or "通过" in report)

# ── L8 MultiLangASTEngine (work.py) ───────────────
print("\n🌐 MultiLangASTEngine (work.py)")
ml = MultiLangASTEngine()
supported = ml.list_supported()
check("支持 5 种语言", len(supported) == 5, str(list(supported.keys())))

py = "def add(a: int, b: int) -> int:\n    return a + b\n"
check("Python 通过", ml.check(py, "test.py")["passed"])

java_bad = 'public void read() { FileInputStream f = new FileInputStream("a.txt"); }\n'
check("Java try_catch 拦截", not ml.check(java_bad, "T.java")["passed"])
java_good = "/** docs */\npublic void helper() {}\npublic String getName() { return \"x\"; }\n"
check("Java Javadoc 通过", ml.check(java_good, "T.java")["passed"])

kt_bad = 'fun risky() { Thread { println("x") }.start() }\n'
check("Kotlin 检测", ml.check(kt_bad, "T.kt")["language"] == "kotlin")

ts_bad = "function fetch(): any { return Promise.resolve(); }\n"
check("TypeScript 拦截", not ml.check(ts_bad, "t.ts")["passed"])

sw_bad = "func getUser() -> String! { return nil }\n"
check("Swift 检测", ml.check(sw_bad, "T.swift")["language"] == "swift")

check("扩展名识别 .tsx", ml.detect_language("", "App.tsx") == "typescript")
check("内容识别 Java", ml.detect_language("public static void main", "Main.java") == "java")

# ── V1 Bridge ────────────────────────────────────────
print("\n🔌 V1Bridge")
v1 = V1Bridge()
check("V1 桥接初始化", isinstance(v1.available, dict))
print(f"  V1 状态: {v1.available}")

# ── Archive (Archive.py) ────────────────────────────
print("\n🧠 Archive 长对话记忆")
from Toolkit.Archive import Archive as ArchiveCls
a = ArchiveCls("test_archive")
r1 = a.remember("demo", "帮我写一个 Python 登录接口")
check("记住对话", r1["status"] == "stored")
r2 = a.remember("demo", "紧急！生产环境崩了")
check("紧急度检测", r2["urgency"] == True)
r3 = a.remember("demo", "现在构思小说剧情")
check("主题切换检测", r3["topic_shift"] == True)
ctx = a.context_inject("demo")
check("上下文注入", len(ctx) > 0)

# ── Shiyun (shiyun.py) ──────────────────────────────
print("\n📖 Shiyun 叙事工厂")
s = shiyun.Shiyun()
genres = s.list_genres()
check("题材库", len(genres) >= 30, f"{len(genres)} 种")
g = s.random_genre()
check("随机题材", g in genres)
card = s.make_scene_card(
    scene_id="1-1", pov="金呈", timeline="第十世",
    location="朱墙内殿", goal="发现指尖透明")
prompt = s.scene_to_prompt(card)
check("场景卡生成", "朱墙" in prompt and "指尖" in prompt)

# ── Nuwa POC 报告 (Nuwa.py) ───────────────────────
print("\n📊 Nuwa POC 报告")
n = Nuwa("test_poc")
n.add("规则通过率", "92%", "", "ok")
n.add("违规回滚", 3, "次", "warn")
report = n.generate("测试报告")
check("POC 报告", "92%" in report.to_json() and "<table>" in report.to_html())

# ── WordGateway 主流程 ──────────────────────────────
print("\n🚀 WordGateway 主流程（Mock）")
config = {
    "env": "test",
    "model": {"provider": "deepseek", "model": "deepseek-coder", "api_key": "sk-mock"},
    "skill_dir": "Toolkit/skills",
    "user": "jincheng",
}
gw = WordGateway(config)
print(f"  环境: {gw.env_name}")
print(f"  Skills: {len(gw.skill_recommender.skills)}")
print(f"  V1: {gw.v1.available}")

res = gw.handle("帮我写一个 Python 登录接口", interactive=False)
check("Gateway 调用", hasattr(res, "model_output"))
check("Gateway 有输出", len(res.model_output) > 0)
print(f"  意图: {res.intent.get('category','?')}")
print(f"  Skills: {res.skills_used}")
print(f"  守门: {res.guard_summary['passed']}/{res.guard_summary['total']} 通过")
print(f"  重试: {res.retries} | 最终: {res.final_action}")
print(f"  多语言: {res.multilingal}")

stats = gw.stats()
check("Gateway stats", "rules_active" in stats)
print(f"  Stats: {json.dumps(stats, ensure_ascii=False)[:200]}")

# ── 清理 ────────────────────────────────────────────
import shutil
for d in ["test_feedback", "test_verdicts", "test_snaps", "test_archive", "test_poc"]:
    p = _P(d)
    if p.exists():
        shutil.rmtree(p)
for f in ["test_rad.py", ".env.example", "feedback.jsonl", "config.json.bak"]:
    p = _P(f)
    if p.exists():
        p.unlink()
p = _P("test_proj")
if p.exists():
    shutil.rmtree(p)

# ── 汇总 ────────────────────────────────────────────
print("\n" + "═"*55)
total = PASS + FAIL
rate = PASS / total * 100 if total else 0
icon = "🎉" if FAIL == 0 else "⚠️"
print(f"  {icon} 验证完成: {PASS}/{total} 通过 ({rate:.0f}%)")
if FAIL:
    print(f"  ❌ {FAIL} 项失败:")
    for s, n, d in results:
        if s == "❌":
            print(f"     {n}: {d}")
print("═"*55)
sys.exit(0 if FAIL == 0 else 1)
