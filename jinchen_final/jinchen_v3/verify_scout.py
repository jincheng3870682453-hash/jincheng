"""
verify_scout.py —— 验证 github_scout.py 的所有功能
"""
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "Toolkit"))

from github_scout import (
    GithubScout, quick_scan, build_context_for_ai,
    parse_tree_to_paths, FileNode, RepoInfo
)

PASS = 0
FAIL = 0
results = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        results.append(f"  ✅ {name}")
    else:
        FAIL += 1
        results.append(f"  ❌ {name} — {detail}")

# ═══════════════════════════════════════
# 1. URL 解析
# ═══════════════════════════════════════
print("\n1️⃣  URL 解析")
scout = GithubScout("https://github.com/jincheng3870682453-hash/jinchen")
check("user 解析正确", scout.repo.user == "jincheng3870682453-hash")
check("repo 解析正确", scout.repo.repo == "jinchen")
check("branch 默认 main", scout.repo.branch == "main")
check("raw_base 拼接正确",
      "raw.githubusercontent.com" in scout.repo.raw_base)

scout2 = GithubScout("https://github.com/user/repo/tree/dev")
check("自定义 branch", scout2.repo.branch == "dev")

try:
    GithubScout("https://google.com")
    check("非法 URL 抛异常", False)
except ValueError:
    check("非法 URL 抛 ValueError", True)

# ═══════════════════════════════════════
# 2. parse_tree_to_paths 独立测试
# ═══════════════════════════════════════
print("\n2️⃣  parse_tree_to_paths")

tree = """├── Toolkit/
│   ├── __init__.py
│   ├── gateway.py
│   ├── work.py
│   ├── guardian.py
│   ├── Archive.py
│   ├── shiyun.py
│   ├── Nuwa.py
│   ├── Proteus.py
│   └── skills/
│       ├── python_api_design.skill
│       └── error_handling.skill
├── config/
│   └── config_template.json
├── README.md
└── LICENSE"""

paths = parse_tree_to_paths(tree)
check("解析出 >= 10 个文件", len(paths) >= 10, f"got {len(paths)}")

# 关键：路径必须带目录前缀
check("Toolkit/gateway.py 路径正确", "Toolkit/gateway.py" in paths)
check("Toolkit/work.py 路径正确", "Toolkit/work.py" in paths)
check("Toolkit/skills/python_api_design.skill", 
      "Toolkit/skills/python_api_design.skill" in paths)
check("config/config_template.json", "config/config_template.json" in paths)
check("README.md 在根目录", "README.md" in paths)
check("LICENSE 在根目录", "LICENSE" in paths)

# ═══════════════════════════════════════
# 3. parse_structure 集成测试
# ═══════════════════════════════════════
print("\n3️⃣  parse_structure 集成")

scout3 = GithubScout("https://github.com/user/repo")
scout3.parse_structure(tree, source="test")

check("文件数 >= 10", len(scout3.files) >= 10, f"got {len(scout3.files)}")
check("gateway.py 在 files 中", "Toolkit/gateway.py" in scout3.files)
check("每个文件都有 URL", 
      all(n.url.startswith("https://") for n in scout3.files.values()))

# ═══════════════════════════════════════
# 4. 内联路径提取
# ═══════════════════════════════════════
print("\n4️⃣  内联路径提取")

inline = "帮我看下 Toolkit/gateway.py 和 config/config_template.json"
scout4 = GithubScout("https://github.com/user/repo")
scout4.parse_structure(inline, source="inline")
check("提取 Toolkit/gateway.py", "Toolkit/gateway.py" in scout4.files)
check("提取 config/config_template.json", 
      "config/config_template.json" in scout4.files)

# ═══════════════════════════════════════
# 5. build_system_context
# ═══════════════════════════════════════
print("\n5️⃣  build_system_context")
ctx = scout3.build_system_context()
check("包含仓库名", "user/repo" in ctx)
check("包含文件列表", "Toolkit/gateway.py" in ctx)
check("包含规则提示", "不要编造" in ctx or "不在列表" in ctx)

# ═══════════════════════════════════════
# 6. build_followup_question
# ═══════════════════════════════════════
print("\n6️⃣  build_followup_question")
scout_empty = GithubScout("https://github.com/user/repo")
q = scout_empty.build_followup_question()
check("包含反问内容", "文件夹" in q or "目录" in q)
check("包含仓库地址", "github.com" in q)

# ═══════════════════════════════════════
# 7. find 搜索
# ═══════════════════════════════════════
print("\n7️⃣  find 搜索")
results_gw = scout3.find("gateway")
check("find('gateway')", "Toolkit/gateway.py" in results_gw)

results_skill = scout3.find("skill")
check("find('skill')", any("skill" in r for r in results_skill))

# ═══════════════════════════════════════
# 8. get_related
# ═══════════════════════════════════════
print("\n8️⃣  get_related")
# 手动设置内容
for p, c in [
    ("Toolkit/gateway.py", "import os\nfrom .work import check\n"),
    ("Toolkit/work.py", "import ast\nimport re\n"),
]:
    scout3.files[p].content = c
    scout3.files[p].fetched = True

related = scout3.get_related("Toolkit/gateway.py")
check("gateway 关联到 work", "Toolkit/work.py" in related)

# ═══════════════════════════════════════
# 9. get_imports
# ═══════════════════════════════════════
print("\n9️⃣  get_imports")
imports = scout3.get_imports("Toolkit/gateway.py")
check("解析到 os", "os" in imports)
check("解析到 work", "work" in imports)

# ═══════════════════════════════════════
# 10. 序列化 / 反序列化
# ═══════════════════════════════════════
print("\n🔟  序列化 / 反序列化")
with tempfile.TemporaryDirectory() as tmpdir:
    sp = os.path.join(tmpdir, "state.json")
    scout3.save_state(sp)
    check("状态文件存在", os.path.exists(sp))
    
    scout5 = GithubScout("https://github.com/user/repo")
    loaded = scout5.load_state(sp)
    check("加载成功", loaded)
    check("文件数恢复", len(scout5.files) >= 10)
    check("gateway.py 在恢复列表中", "Toolkit/gateway.py" in scout5.files)

# ═══════════════════════════════════════
# 11. quick_scan
# ═══════════════════════════════════════
print("\n1️⃣1️⃣  quick_scan")
prompt_result = quick_scan(
    "https://github.com/user/repo",
    conversation=[{"role": "user", "content": "看下 Toolkit/gateway.py"}],
)
check("quick_scan 返回字符串", isinstance(prompt_result, str))
check("包含文件信息", "gateway" in prompt_result)

empty_result = quick_scan("https://github.com/user/repo", conversation=[])
check("无文件时返回反问", "文件夹" in empty_result or "目录" in empty_result)

# ═══════════════════════════════════════
# 12. build_context_for_ai
# ═══════════════════════════════════════
print("\n1️⃣2️⃣  build_context_for_ai")
ctx_ai = build_context_for_ai(
    "https://github.com/user/repo",
    conversation=[{"role": "user", "content": "看下 Toolkit/work.py"}],
)
check("返回字符串", isinstance(ctx_ai, str))
check("包含仓库信息", "user/repo" in ctx_ai)

# ═══════════════════════════════════════
# 13. 模拟 jinchen README
# ═══════════════════════════════════════
print("\n1️⃣3️⃣  模拟 jinchen 仓库 README")
jinchen_readme = """
├── tool/
│   ├── work.py
│   ├── guardian.py
│   ├── Archive.py
│   ├── shiyun.py
│   ├── Nuwa.py
│   ├── gateway.py
│   └── Proteus.py
├── config/
│   └── config_template.json
├── README.md
└── LICENSE
"""

scout_jc = GithubScout("https://github.com/jincheng3870682453-hash/jinchen")
scout_jc.parse_structure(jinchen_readme, source="jinchen_readme")

check("jinchen work.py", "tool/work.py" in scout_jc.files)
check("jinchen gateway.py", "tool/gateway.py" in scout_jc.files)
check("jinchen README.md", "README.md" in scout_jc.files)
check("jinchen LICENSE", "LICENSE" in scout_jc.files)
check("jinchen raw URL 正确", 
      "raw.githubusercontent.com/jincheng3870682453-hash/jinchen/main" 
      in list(scout_jc.files.values())[0].url)

# ═══════════════════════════════════════
# 汇总
# ═══════════════════════════════════════
print("\n" + "=" * 50)
print(f"📊 Scout 验证: {PASS} 通过 / {FAIL} 失败")
print("=" * 50)
for r in results:
    print(r)

if FAIL == 0:
    print("\n🎉 Scout 全部通过！")
    sys.exit(0)
else:
    print(f"\n⚠️  {FAIL} 项失败")
    sys.exit(1)
