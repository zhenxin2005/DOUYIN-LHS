#!/usr/bin/env python3
"""
一次性迁移脚本：给 rules.json 每个角色补 9 个新字段（M1 人格化重构 schema）。
幂等：再次运行不会重复添加。

用法：
  python migrate_rules.py           # 实际迁移
  python migrate_rules.py --dry-run # 只显示变更，不写
"""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
RULES = ROOT / "rules.json"
BACKUP = ROOT / "rules.json.bak"

# 新字段默认值（schema 顺序固定）
DEFAULTS = {
    "crowd": "都市中产",
    "device": "3000-5000",
    "vehicle": "无车",
    "purchase_freq": "中",
    "region": "广东",
    "marriage": "已婚有娃",
    "customer_type": "潜客",
    "typing_style": "中",
    "response_tendency": 0.45,
}


def migrate(dry_run: bool = False) -> int:
    if not RULES.exists():
        print(f"❌ 找不到 {RULES}")
        return 1

    data = json.loads(RULES.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("❌ rules.json 顶层不是 dict")
        return 1

    changes: list[str] = []
    new_data: dict = {}

    for name, persona in data.items():
        if not isinstance(persona, dict):
            new_data[name] = persona
            continue

        # 旧字段（保留顺序与值）
        tone = persona.get("tone", "")
        trait = persona.get("trait", "")
        style = persona.get("style", "")
        messages = persona.get("messages", [])

        # 已迁移：含 crowd 字段则跳过
        if "crowd" in persona:
            new_data[name] = persona
            continue

        # 按 schema 顺序重建（4 旧 + 9 新 = 13 字段）
        new_persona = {
            "tone": tone,
            "trait": trait,
            "style": style,
            "messages": messages,
            **DEFAULTS,
        }
        new_data[name] = new_persona
        changes.append(name)

    print("\n=== 迁移计划 ===")
    print(f"角色总数:   {len(data)}")
    print(f"需要迁移:   {len(changes)}")
    print(f"已是新版:   {len(data) - len(changes)}")
    if changes:
        print(f"\n将补字段 ({len(DEFAULTS)} 个):")
        for k, v in DEFAULTS.items():
            print(f"  {k}: {v!r}")

    if dry_run:
        print("\n[DRY RUN] 不写文件")
        return 0

    if changes:
        if not BACKUP.exists():
            shutil.copy2(RULES, BACKUP)
            print(f"\n✓ 已备份到 {BACKUP.name}")
        RULES.write_text(
            json.dumps(new_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✓ rules.json 已更新（{len(changes)} 个角色）")
    else:
        print("\n✓ 无需变更")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不写文件")
    args = parser.parse_args()
    raise SystemExit(migrate(dry_run=args.dry_run))