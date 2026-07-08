"""
M1 人格化 LLM 决策引擎。

- 加载 rules.json（13 字段 schema：4 旧 + 9 新）
- 拼接 system prompt + user prompt
- 调 OpenAI 兼容协议 LLM（DeepSeek / 豆包 / KIMI / MINIMAX / MIMO 均兼容）
- 返回 {respond, content, emotion} 决策结果
- 失败 → fallback_pick 从 messages 随机取

向后兼容：
- 保留 PERSONAS 常量（list[dict] 格式）
- 保留 load_personas() 函数签名
- 保留 _default_personas() 兜底
"""

import json
import random
import re
import sys
from pathlib import Path
from typing import Optional

# ──── 模块常量 ────

# PyInstaller 打包后优先读运行目录（用户可编辑）的 rules.json，
# 缺失时回退到 bundle 内置默认；开发时用脚本目录。
if getattr(sys, 'frozen', False):
    _run = Path(sys.executable).parent
    ROOT = _run if (_run / "rules.json").exists() else Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parent
RULES_FILE = ROOT / "rules.json"

# LLM 默认配置（可在 config.json 覆盖）
DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TEMPERATURE = 0.8
DEFAULT_MAX_TOKENS = 512  # 推理模型(MiniMax-M3 / deepseek-reasoner 等)需要更大预算:思考+JSON
DEFAULT_TIMEOUT_S = 8
DEFAULT_MODE = "pick"  # "pick" | "generate"

# 弹幕长度控制（B 任务：可在 config.json["length_control"] 覆盖）
# 四个上限，按概率分布生效；hard_cap 是程序兜底的硬截断
DEFAULT_LENGTH_CONTROL = {
    "min_chars": 1,         # 最短不低于（防止空字符串 / 单标点）
    "max_common": 5,        # 约 70% 时间用这个上限
    "max_occasional": 9,    # 约 25% 时间
    "max_rare": 11,         # 约 5% 时间
    "hard_cap": 12,         # 后处理强制截断到这个值
}


def _normalize_length_control(cfg: dict | None) -> dict:
    """合并用户配置 + 默认值，返回完整 length_control 字典。"""
    out = dict(DEFAULT_LENGTH_CONTROL)
    if isinstance(cfg, dict):
        for k in out.keys():
            if k in cfg:
                try:
                    out[k] = int(cfg[k])
                except (TypeError, ValueError):
                    pass
    # 校验顺序：min ≤ max_common ≤ max_occasional ≤ max_rare ≤ hard_cap
    out["min_chars"] = max(1, out["min_chars"])
    out["max_common"] = max(out["min_chars"], out["max_common"])
    out["max_occasional"] = max(out["max_common"], out["max_occasional"])
    out["max_rare"] = max(out["max_occasional"], out["max_rare"])
    out["hard_cap"] = max(out["max_rare"], out["hard_cap"])
    return out


def _length_rules_text(lc: dict) -> str:
    """生成 prompt 里描述长度分布的文本段。"""
    return (
        f"【弹幕长度（严格遵循）】\n"
        f"- 常见（~70%）：{lc['min_chars']}~{lc['max_common']} 个字（如「透气？」「贵了点」）\n"
        f"- 偶尔（~25%）：{lc['max_common']+1}~{lc['max_occasional']} 个字\n"
        f"- 极少（~5%）：{lc['max_occasional']+1}~{lc['max_rare']} 个字\n"
        f"- 绝不超过 {lc['hard_cap']} 字 · 多个短句比一个长句自然"
    )


# ──── 向后兼容：旧 API ────

def _default_personas() -> list[dict]:
    """内置 2 个兜底角色（rules.json 缺失或损坏时用）。"""
    return [
        {
            "name": "做生意的老板",
            "tone": "务实直接，关心能不能带来生意和财运",
            "trait": "做生意多年，信这个，身边朋友也在用",
            "style": "会问招不招财、谈客户顺不顺、放哪里效果好，说话干脆",
            "messages": ["拍了一单，希望明天谈客户顺利", "招财吗？"],
            "crowd": "都市中产", "device": "3000-5000", "vehicle": "无车",
            "purchase_freq": "中", "region": "广东", "marriage": "已婚有娃",
            "customer_type": "潜客", "typing_style": "中", "response_tendency": 0.45,
        },
        {
            "name": "运势不顺想转运的",
            "tone": "焦虑、急切",
            "trait": "最近不顺，听朋友说来试试",
            "style": "问得多、怕被骗、想要保证",
            "messages": ["真的有用吗", "多少钱"],
            "crowd": "都市蓝领", "device": "1000-3000", "vehicle": "无车",
            "purchase_freq": "低", "region": "河南", "marriage": "已婚有娃",
            "customer_type": "新客", "typing_style": "慢", "response_tendency": 0.30,
        },
    ]


def _normalize(name: str, raw: dict) -> dict:
    """把 rules.json 里某个角色的 dict 补齐所有字段，返回 14 字段 dict。"""
    return {
        # 4 个旧字段
        "tone": raw.get("tone", ""),
        "trait": raw.get("trait", ""),
        "style": raw.get("style", ""),
        "messages": list(raw.get("messages", [])),
        # 9 个新字段（M1 schema）
        "crowd": raw.get("crowd", "都市中产"),
        "device": raw.get("device", "3000-5000"),
        "vehicle": raw.get("vehicle", "无车"),
        "purchase_freq": raw.get("purchase_freq", "中"),
        "region": raw.get("region", "广东"),
        "marriage": raw.get("marriage", "已婚有娃"),
        "customer_type": raw.get("customer_type", "潜客"),
        "typing_style": raw.get("typing_style", "中"),
        "response_tendency": float(raw.get("response_tendency", 0.45)),
        # 角色名（key）
        "name": name,
    }


def load_personas() -> list[dict]:
    """读 rules.json，返回 list[dict]（每个 dict 14 字段）。"""
    if not RULES_FILE.exists():
        return _default_personas()
    try:
        data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_personas()
    if not isinstance(data, dict):
        return _default_personas()
    out: list[dict] = []
    for name, raw in data.items():
        if not isinstance(raw, dict):
            continue
        out.append(_normalize(name, raw))
    return out


# 模块级常量（向后兼容）
PERSONAS = load_personas()


# ──── LLM 客户端 ────

def get_llm_client(api_key: str, base_url: str, timeout: float = DEFAULT_TIMEOUT_S):
    """
    返回 OpenAI 兼容客户端。
    api_key / base_url 为空时抛 RuntimeError（让 think() 走降级）。
    """
    if not api_key or not base_url:
        raise RuntimeError("LLM 未配置（缺少 api_key 或 base_url）")
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


# ──── Prompt 拼装 ────

def compose_system_prompt(persona: dict, length_control: dict | None = None) -> str:
    """
    从 persona 14 字段拼出 system prompt。
    persona.md 自定义段（如存在）会追加到末尾。
    length_control：弹幕长度约束（B 任务），None 时用默认。
    """
    name = persona.get("name", "顾客")
    crowd = persona.get("crowd", "都市中产")
    region = persona.get("region", "广东")
    marriage = persona.get("marriage", "已婚有娃")
    device = persona.get("device", "3000-5000")
    vehicle = persona.get("vehicle", "无车")
    purchase_freq = persona.get("purchase_freq", "中")
    tone = persona.get("tone", "") or "自然"
    typing_style = persona.get("typing_style", "中")
    response_tendency = float(persona.get("response_tendency", 0.45))
    customer_type = persona.get("customer_type", "潜客")

    lc = _normalize_length_control(length_control)
    typing_zh = {"慢": "慢慢的", "中": "正常速度", "快": "快一些"}.get(typing_style, "正常速度")

    parts = [
        f"你是「{name}」，一名来自 {region} 的{customer_type}顾客。",
        "",
        "【人群画像】",
        f"- 八大人群：{crowd}",
        f"- 婚姻：{marriage}",
        "",
        "【消费力】",
        f"- 手机：{device} 元档",
        f"- 车：{vehicle}",
        f"- 购物频次：{purchase_freq}",
        "",
        "【表达风格】",
        f"- 语气：{tone}",
        f"- 打字速度：{typing_zh}",
        f"- 回应率：{int(response_tendency * 100)}%（多数时候保持沉默）",
        "",
        "【行为约束】",
        _length_rules_text(lc),
        f"- 用「{customer_type}」的视角看主播：新客（好奇基础）、潜客（比价犹豫）、老客（复购反馈）",
        "- 只用中文，不用英文",
        "- 像真人那样打字，不要工整",
    ]

    base = "\n".join(parts)

    # persona.md 追加（如存在）
    md_path = ROOT / "personas" / f"{name}.md"
    if md_path.exists():
        try:
            custom = md_path.read_text(encoding="utf-8").strip()
            if custom:
                base += "\n\n【自定义补充】\n" + custom
        except OSError:
            pass

    return base


def compose_user_prompt(persona: dict, mode: str = DEFAULT_MODE) -> str:
    """
    拼 user prompt。两种模式：
      - "pick": 让 LLM 从 messages 池里挑一条
      - "generate": 让 LLM 自己生成
    """
    messages = persona.get("messages", []) or ["这个怎么用"]
    msgs_text = "\n".join(f"  - {m}" for m in messages)

    if mode == "generate":
        return (
            "用你的人格说一句短弹幕（5~15 字）。\n\n"
            "只输出 JSON（一行，不要其他文字）：\n"
            '{"respond": true, "content": "<你说的>", "emotion": "<1~2 字>"}'
        )

    # 默认 pick 模式
    return (
        "从下面的话术池里挑一条最像你刚才心情的（或挑一条最不讨厌的也行）：\n\n"
        f"{msgs_text}\n\n"
        "只输出 JSON（一行，不要其他文字）：\n"
        '{"respond": true, "content": "<挑的那条原文>", "emotion": "<1~2 字，如：好奇/怀疑/期待/满意/犹豫>"}'
    )


# ──── 思考（核心入口） ────

def _enforce_length(content: str, lc: dict) -> str:
    """B 任务：超长截断 + 最低保底。返回新字符串。"""
    if not content:
        return content
    cap = lc.get("hard_cap", 12)
    # 中文字符数计算（含中文标点，不算空白）
    visible = content.strip()
    if len(visible) > cap:
        return visible[:cap]
    return visible


def think(persona: dict, config: dict) -> dict:
    """
    调 LLM，返回 {respond, content, emotion}。
    失败（任意异常）→ 返回 fallback_pick 的结果（兜底）。

    config 应包含：
      - llm_api_key: str
      - llm_base_url: str
      - llm_model: str
      - llm_temperature: float (可选)
      - llm_mode: "pick" | "generate" (可选)
      - llm_timeout: float (可选)
      - length_control: dict (可选,见 DEFAULT_LENGTH_CONTROL)
    """
    lc = _normalize_length_control(config.get("length_control"))

    fallback = {
        "respond": True,
        "content": _enforce_length(fallback_pick(persona), lc),
        "emotion": "neutral",
    }

    api_key = config.get("llm_api_key", "")
    base_url = config.get("llm_base_url", DEFAULT_API_BASE)
    model = config.get("llm_model", DEFAULT_MODEL)
    temperature = float(config.get("llm_temperature", DEFAULT_TEMPERATURE))
    mode = config.get("llm_mode", DEFAULT_MODE)
    timeout = float(config.get("llm_timeout", DEFAULT_TIMEOUT_S))

    if not api_key:
        return fallback

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": compose_system_prompt(persona, lc)},
                {"role": "user", "content": compose_user_prompt(persona, mode)},
            ],
            temperature=temperature,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        text = (resp.choices[0].message.content or "").strip()
        parsed = _parse_json_response(text, debug_log=print)
        if parsed is None:
            # 解析失败,原文打到 stderr,便于诊断
            print(f"  [LLM] JSON 解析失败,原文: {text[:200]!r}", file=sys.stderr)
            return fallback
        # B 任务：超长截断 + 日志
        raw = parsed.get("content", "")
        new = _enforce_length(raw, lc)
        if new != raw:
            print(f"  [LLM] ⚠ 超长截断 ({len(raw)}→{len(new)} 字): {raw!r} → {new!r}")
        parsed["content"] = new
        # 成功路径:打一行简明日志,确认 LLM 真的在工作
        print(f"  [LLM] ✓ respond={parsed.get('respond')} content={parsed.get('content')!r}")
        return parsed
    except Exception as e:
        # 把异常类型 + 消息打到 stderr,而不是静默吞掉
        print(f"  [LLM] ✗ 调用失败: {type(e).__name__}: {e}", file=sys.stderr)
        return fallback


# ──── 降级 ────

def fallback_pick(persona: dict) -> str:
    """从 persona.messages 随机取一条（兜底用）。"""
    messages = persona.get("messages") or []
    if not messages:
        return ""
    return random.choice(messages)


def _parse_json_response(text: str, debug_log=None) -> Optional[dict]:
    """从 LLM 输出里抓 JSON。失败返回 None。可选 debug_log(可调用)输出诊断。
    自动剥离 reasoning models 的 <think>...</think> 标签和 markdown 代码块。
    """
    if not text:
        if debug_log:
            debug_log(f"  [LLM] _parse_json: 文本为空")
        return None
    # 1) 去掉 reasoning models 的思考块(MiniMax-M3 / deepseek-reasoner 等)
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    # 2) 去掉 markdown 代码块围栏 ```json ... ```
    text = re.sub(r"```\w*\n.*?\n```\s*", "", text, flags=re.DOTALL)
    text = text.strip()
    if not text:
        if debug_log:
            debug_log(f"  [LLM] _parse_json: 剥离 think/代码块后文本为空")
        return None
    # 3) 抓第一个 {...} 块
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        if debug_log:
            debug_log(f"  [LLM] _parse_json: 未找到 {{...}} 块,原文={text[:200]!r}")
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        if debug_log:
            debug_log(f"  [LLM] _parse_json: JSON 语法错误 {e},原文={m.group(0)[:200]!r}")
        return None
    if not isinstance(data, dict):
        if debug_log:
            debug_log(f"  [LLM] _parse_json: 解析结果非 dict: {type(data).__name__}")
        return None
    if "content" not in data:
        if debug_log:
            debug_log(f"  [LLM] _parse_json: 缺少 content 字段, keys={list(data.keys())}")
        return None
    return {
        "respond": bool(data.get("respond", True)),
        "content": str(data.get("content", "")),
        "emotion": str(data.get("emotion", "neutral")),
    }