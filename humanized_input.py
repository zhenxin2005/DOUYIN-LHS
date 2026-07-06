"""
M3 拟人输入：jieba 分词 + 节奏化输入。
替换 douyin_interact.py 中固定 time.sleep(0.01)/字 的机械节拍。
"""

import random
import time

import jieba

# 未指定 typing_style 的角色用此常量
DEFAULT_TYPING_STYLE = "normal"

# 词块间短停顿区间（毫秒），按 typing_style 选
INTERVAL_BY_STYLE_MS = {
    "slow":   (120, 280),
    "normal": (50, 200),    # PLAN.md 默认值
    "fast":   (20, 80),
}

# 长停顿区间（秒）
LONG_PAUSE_RANGE_S = (0.5, 1.5)

# 标点后长停顿概率
LONG_PAUSE_PROB = 0.30

# 触发长停顿的标点（中英常见）
LONG_PAUSE_PUNCTS = frozenset("，。？！（）~…\n. ,?!")

# 同一词块内字符间隔（毫秒）—— 不为 0，避免字间过紧被识别
INTRA_TOKEN_DELAY_MS = 5


def chunk_by_words(text: str) -> list[str]:
    """jieba 分词。标点作为独立 token 保留以便触发长停顿。"""
    return list(jieba.cut(text))


def get_interval_ms(typing_style: str) -> int:
    """根据 typing_style 取一个短停顿毫秒数（闭区间 [lo, hi]）。"""
    rng = INTERVAL_BY_STYLE_MS.get(typing_style) or INTERVAL_BY_STYLE_MS[DEFAULT_TYPING_STYLE]
    return random.randint(rng[0], rng[1])


def get_long_pause_s() -> float:
    return random.uniform(*LONG_PAUSE_RANGE_S)


def _inject_char(input_el, ch: str) -> None:
    """单字符 InputEvent 注入（与原 douyin_interact.py 相同 JS）。"""
    input_el.evaluate(
        """(el2, ch) => {
            const sel = window.getSelection();
            const range = sel.getRangeAt(0);
            range.deleteContents();
            const tn = document.createTextNode(ch);
            range.insertNode(tn);
            range.setStartAfter(tn);
            sel.removeAllRanges();
            sel.addRange(range);
            el2.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:ch}));
        }""",
        ch,
    )


def type_humanized(input_el, text: str, typing_style: str = DEFAULT_TYPING_STYLE) -> None:
    """
    拟人输入主函数：
      1) jieba 分词成 token 列表（标点也是 token）
      2) 逐 token 处理：
         - token 内逐字注入（保持与 v2 一致的 React 事件流），INTRA_TOKEN_DELAY_MS 间隔
         - token 间随机短停（INTERVAL_BY_STYLE_MS）
         - token 是标点时 LONG_PAUSE_PROB 概率插入 LONG_PAUSE_RANGE_S 长停
    整段为同步阻塞。空字符串直接返回。
    """
    if not text:
        return
    intra_s = INTRA_TOKEN_DELAY_MS / 1000.0
    for token in chunk_by_words(text):
        for ch in token:
            _inject_char(input_el, ch)
            time.sleep(intra_s)
        # token 间短停
        time.sleep(get_interval_ms(typing_style) / 1000.0)
        # 标点后长停
        if token in LONG_PAUSE_PUNCTS and random.random() < LONG_PAUSE_PROB:
            time.sleep(get_long_pause_s())