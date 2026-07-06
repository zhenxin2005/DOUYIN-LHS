#!/usr/bin/env python3
"""
角色与弹幕数据 — 析命师单账号互动亲朋好友静态语义版消费者角色定义

从 rules.json 动态加载角色；如果文件不存在则使用内置默认值。
每个角色有独立的弹幕列表，切换角色时弹幕内容跟着变化。
"""

import json
from pathlib import Path


def _default_personas() -> list[dict]:
    """内置默认角色（rules.json 不存在时的回退）"""
    return [
        {
            "name": "做生意的老板",
            "tone": "务实直接，关心能不能带来生意和财运",
            "trait": "做生意多年，信这个，身边朋友也在用",
            "style": "会问招不招财、谈客户顺不顺、放哪里效果好，说话干脆",
            "messages": ["拍了一单，希望明天谈客户顺利", "身边做生意的朋友都在用，我也来一个"],
        },
        {
            "name": "运势不顺想转运的",
            "tone": "有点焦虑，最近遇到困难，想找转机",
            "trait": "欠债、股票亏、创业压力大、觉得最近很背",
            "style": "会说来拍一单试试、最近很不顺、希望能上岸，语气带着期盼",
            "messages": ["最近感觉不顺，我来拍一单试试", "希望明天开始能顺一点"],
        },
    ]


def load_personas() -> list[dict]:
    """从 rules.json 加载角色列表，不存在则用默认值"""
    path = Path(__file__).parent / "rules.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            personas = []
            for name, info in data.items():
                personas.append({
                    "name": name,
                    "tone": info.get("tone", ""),
                    "trait": info.get("trait", ""),
                    "style": info.get("style", ""),
                    "messages": list(info.get("messages", [])),
                })
            if personas:
                return personas
        except Exception:
            pass
    return _default_personas()


PERSONAS = load_personas()
