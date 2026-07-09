#!/usr/bin/env python3
"""
析命师单账号互动亲朋好友静态语义版 — 抖音直播间互动控制台
Tkinter 桌面 GUI — 扫码登录 + 无头发送（无 ASR / 无 LLM）
"""

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from pathlib import Path

# PyInstaller 打包后用运行目录，开发时用脚本目录
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

sys.path.insert(0, str(APP_DIR))

try:
    from llm_engine import PERSONAS
except Exception:
    PERSONAS = []

CONFIG_FILE = APP_DIR / "config.json"
RULES_FILE = APP_DIR / "rules.json"
PERSONAS_DIR = APP_DIR / "personas"
PERSONAS_DIR.mkdir(exist_ok=True)

# M1 角色设定下拉选项常量
CROWD_OPTIONS = ["小镇中老年", "都市银发族", "都市蓝领", "精致妈妈",
                  "都市中产", "Gen Z", "都市白领", "小镇青年"]
DEVICE_OPTIONS = ["8000+", "5000-8000", "3000-5000", "1000-3000", "1000以下"]
VEHICLE_OPTIONS = ["30万+ BBA", "10-30万合资", "5-10万国产", "电动车", "无车"]
PURCHASE_FREQ_OPTIONS = ["高", "中", "低"]
PROVINCE_OPTIONS = ["北京", "上海", "天津", "重庆", "河北", "山西", "内蒙古",
                    "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建",
                    "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
                    "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃",
                    "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
MARRIAGE_OPTIONS = ["已婚有娃", "已婚无娃", "未婚", "离异", "丧偶"]
CUSTOMER_TYPE_OPTIONS = ["新客", "潜客", "老客"]
TYPING_STYLE_OPTIONS = ["慢", "中", "快"]
TONE_OPTIONS = ["直白务实", "朴实信祈", "得体理性", "玩梗好奇", "温和亲切", "怀疑谨慎"]

# M1 旧 schema 字段（保留向后兼容，但 UI 不再显示）
OLD_SCHEMA_FIELDS = ("tone", "trait", "style")

# 首次运行：从 bundle 复制默认配置到运行目录
# 注意：打包版的 config.json 是占位模板(config.template.json),首次启动会复制为 config.json,
#       UI 检测到空 KEY/空账号时弹提示让用户填写,避免隐私泄露(LLM Key / 账号名 / 房间号)
if getattr(sys, 'frozen', False):
    import shutil as _shutil
    _bundle = Path(sys._MEIPASS)
    _copy_map = {
        "config.json": "config.template.json",  # 占位模板 → config.json
        "rules.json":  "rules.json",
    }
    for _dst_name, _src_name in _copy_map.items():
        _dst = APP_DIR / _dst_name
        if not _dst.exists():
            _src = _bundle / _src_name
            if _src.exists():
                _shutil.copy2(_src, _dst)


# ══════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════

def get_persona_names():
    return [p["name"] for p in PERSONAS] if PERSONAS else []


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ══════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("析命师单账号互动亲朋好友静态语义版 · 互动控制台")
        self.root.geometry("960x720")
        self.root.minsize(860, 600)

        self._proc: subprocess.Popen | None = None  # 运行中的子进程
        self._record_proc = None

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self._load_config_to_form()
        # 打包版首次启动占位提示：UI 显示完再弹窗，不阻塞启动
        if getattr(sys, 'frozen', False):
            self.root.after(200, self._check_placeholder_config)

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#8B0000", height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="析命师单账号互动亲朋好友静态语义版 · 互动控制台",
                 fg="white", bg="#8B0000", font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(header, text="v2.0", fg="#FFD700", bg="#8B0000",
                 font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT, padx=16, pady=8)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._tab_main = ttk.Frame(self.notebook)
        self._tab_rules = ttk.Frame(self.notebook)
        self._tab_llm = ttk.Frame(self.notebook)
        self._tab_record = ttk.Frame(self.notebook)

        self.notebook.add(self._tab_main, text="🎥 直播间互动")
        self.notebook.add(self._tab_rules, text="💬 角色弹幕")
        self.notebook.add(self._tab_llm, text="🤖 LLM 配置")
        self.notebook.add(self._tab_record, text="📝 弹幕采集")

        self._build_tab_main()
        self._build_tab_rules()
        self._build_tab_llm()
        self._build_tab_record()

        # 底部状态栏
        self.status_bar = tk.Label(self.root, text="就绪", bd=1, relief=tk.SUNKEN,
                                   anchor=tk.W, bg="#f0f0f0", font=("Microsoft YaHei", 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ════════════════════════════════════════
    #  Tab 1: 账号管理
    # ════════════════════════════════════════


    # ════════════════════════════════════════
    #  Tab 1: 直播间互动
    # ════════════════════════════════════════

    def _build_tab_main(self):
        frame = ttk.Frame(self._tab_main, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # ── 账号 ──
        account_frame = ttk.LabelFrame(frame, text="账号", padding=8)
        account_frame.pack(fill=tk.X, pady=4)

        ar1 = ttk.Frame(account_frame)
        ar1.pack(fill=tk.X)
        ttk.Label(ar1, text="当前账号：").pack(side=tk.LEFT)
        self.account_combo = ttk.Combobox(ar1, state="readonly", width=18)
        self.account_combo.pack(side=tk.LEFT, padx=4)
        self.account_combo.bind("<<ComboboxSelected>>", lambda e: self._save_config_from_form())
        ttk.Button(ar1, text="🔑 登录", command=self._login).pack(side=tk.LEFT, padx=2)
        ttk.Button(ar1, text="➕ 新建", command=self._new_account).pack(side=tk.LEFT, padx=2)
        ttk.Button(ar1, text="🗑 删除", command=self._delete_account).pack(side=tk.LEFT, padx=2)
        ttk.Button(ar1, text="📂 打开目录", command=self._open_account_dir).pack(side=tk.LEFT, padx=2)

        # ── 直播间 ──
        room_frame = ttk.LabelFrame(frame, text="直播间", padding=8)
        room_frame.pack(fill=tk.X, pady=4)

        r1 = ttk.Frame(room_frame)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="地址：").pack(side=tk.LEFT)
        self.room_url = ttk.Entry(r1)
        self.room_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.room_url.bind("<FocusOut>", lambda e: self._save_config_from_form())

        # ── 发送设置 ──
        intv_frame = ttk.LabelFrame(frame, text="发送设置", padding=8)
        intv_frame.pack(fill=tk.X, pady=4)

        r2 = ttk.Frame(intv_frame)
        r2.pack(fill=tk.X)
        ttk.Label(r2, text="弹幕间隔：").pack(side=tk.LEFT)
        self.send_interval = ttk.Entry(r2, width=8)
        self.send_interval.pack(side=tk.LEFT, padx=4)
        self.send_interval.insert(0, "45")
        self.send_interval.bind("<FocusOut>", lambda e: self._save_config_from_form())
        ttk.Label(r2, text="秒", foreground="gray").pack(side=tk.LEFT)

        ttk.Label(r2, text="  弹幕策略：").pack(side=tk.LEFT, padx=(16, 0))
        self.bullet_strategy = ttk.Combobox(r2, state="readonly", width=10,
                                            values=["循环", "随机"])
        self.bullet_strategy.set("随机")
        self.bullet_strategy.pack(side=tk.LEFT, padx=4)
        self.bullet_strategy.bind("<<ComboboxSelected>>", lambda e: self._save_config_from_form())

        # ── 角色选择（单选下拉）──
        role_frame = ttk.LabelFrame(frame, text="当前角色", padding=8)
        role_frame.pack(fill=tk.X, pady=4)

        r3 = ttk.Frame(role_frame)
        r3.pack(fill=tk.X)
        self.persona_combo = ttk.Combobox(r3, state="readonly", width=24)
        self.persona_combo.pack(side=tk.LEFT, padx=4)
        self.persona_combo["values"] = get_persona_names()
        self.persona_combo.bind("<<ComboboxSelected>>", lambda e: self._save_config_from_form())

        # ── 控制 ──
        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill=tk.X, pady=6)

        self.btn_start = ttk.Button(ctrl_frame, text="▶ 启动", command=self._start)
        self.btn_start.pack(side=tk.LEFT, padx=2)
        self.btn_stop = ttk.Button(ctrl_frame, text="⏹ 停止", command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        self.status_label = tk.Label(ctrl_frame, text="⚪ 已停止", fg="gray",
                                      font=("Microsoft YaHei", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=12)

        # ── 实时日志 ──
        ttk.Label(frame, text="运行日志：", font=("Microsoft YaHei", 9, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self.log_area = scrolledtext.ScrolledText(frame, height=10,
                                                   font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
                                                   insertbackground="white")
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.insert(tk.END, "就绪。设置直播间地址 → 扫码登录 → 启动。\n")
        self.log_area.see(tk.END)

    # ── 配置读写 ──

    def _load_config_to_form(self):
        """从 config.json 加载到表单"""
        cfg = load_config()
        self.room_url.delete(0, tk.END)
        self.room_url.insert(0, cfg.get("room_url", ""))
        self.send_interval.delete(0, tk.END)
        self.send_interval.insert(0, str(cfg.get("send_interval", 45)))
        self.bullet_strategy.set(cfg.get("bullet_strategy", "随机"))

        # 单选下拉：取 personas 列表的第一项作为当前角色
        personas = cfg.get("personas", [])
        if personas:
            self.persona_combo.set(personas[0])

        # 加载账号(刷新下拉框后再设置)
        self._refresh_account_combo()
        saved_account = cfg.get("account", "")
        if saved_account and saved_account in self.account_combo["values"]:
            self.account_combo.set(saved_account)

        # LLM 配置（如果 GUI 已构建）
        if hasattr(self, "llm_api_key"):
            self.llm_api_key.delete(0, tk.END)
            self.llm_api_key.insert(0, cfg.get("llm_api_key", ""))
            self.llm_base_url.delete(0, tk.END)
            self.llm_base_url.insert(0, cfg.get("llm_base_url", "https://api.deepseek.com"))
            self.llm_model.delete(0, tk.END)
            self.llm_model.insert(0, cfg.get("llm_model", "deepseek-chat"))
            try:
                self.llm_temperature.set(int(float(cfg.get("llm_temperature", 0.8)) * 100))
                self._on_llm_temp_change(str(self.llm_temperature.get()))
            except Exception:
                pass
            self.llm_mode.set(cfg.get("llm_mode", "pick"))
            try:
                self.llm_timeout.delete(0, tk.END)
                self.llm_timeout.insert(0, str(cfg.get("llm_timeout", 8)))
            except Exception:
                pass
            self.llm_enabled_var.set(bool(cfg.get("llm_enabled", False)))

            # B 任务：弹幕长度控制
            lc = cfg.get("length_control") or {}
            try: self.len_min.set(int(lc.get("min_chars", 1)))
            except Exception: pass
            try: self.len_max_common.set(int(lc.get("max_common", 5)))
            except Exception: pass
            try: self.len_max_occ.set(int(lc.get("max_occasional", 9)))
            except Exception: pass
            try: self.len_max_rare.set(int(lc.get("max_rare", 11)))
            except Exception: pass
            try: self.len_hard_cap.set(int(lc.get("hard_cap", 12)))
            except Exception: pass

    def _check_placeholder_config(self):
        """打包版首次启动检测：account/llm_api_key/room_url 任一为空就提醒"""
        cfg = load_config()
        missing = []
        if not cfg.get("account", "").strip():
            missing.append("账号名 (account)")
        if not cfg.get("room_url", "").strip():
            missing.append("直播间 URL (room_url)")
        if cfg.get("llm_enabled") and not cfg.get("llm_api_key", "").strip():
            missing.append("LLM API Key (已开启 LLM 模式)")
        if missing:
            messagebox.showwarning(
                "首次启动 — 请补全配置",
                "检测到以下必填项为空：\n\n  • " + "\n  • ".join(missing) +
                "\n\n请在「🎥 直播间互动」和「🤖 LLM 配置」两个 Tab 填好后保存。\n"
                "Tab 字段失焦会自动写入运行目录的 config.json。"
            )

    def _save_config_from_form(self):
        """从表单保存到 config.json"""
        selected_persona = self.persona_combo.get().strip()
        if not selected_persona:
            selected_persona = get_persona_names()[0] if get_persona_names() else ""
        try:
            si = int(self.send_interval.get())
        except ValueError:
            si = 45

        cfg = {
            "room_url": self.room_url.get().strip(),
            "personas": [selected_persona] if selected_persona else [],
            "send_interval": si,
            "bullet_strategy": self.bullet_strategy.get() or "随机",
            "account": self.account_combo.get(),
        }

        # LLM 配置（如果 GUI 已构建）
        if hasattr(self, "llm_api_key"):
            try:
                timeout_val = float(self.llm_timeout.get())
            except ValueError:
                timeout_val = 8.0
            cfg["llm_enabled"] = bool(self.llm_enabled_var.get())
            cfg["llm_api_key"] = self.llm_api_key.get().strip()
            cfg["llm_base_url"] = self.llm_base_url.get().strip() or "https://api.deepseek.com"
            cfg["llm_model"] = self.llm_model.get().strip() or "deepseek-chat"
            cfg["llm_temperature"] = round(int(self.llm_temperature.get()) / 100, 2)
            cfg["llm_mode"] = self.llm_mode.get() or "pick"
            cfg["llm_timeout"] = timeout_val

            # B 任务：弹幕长度控制
            try:
                cfg["length_control"] = {
                    "min_chars":      int(self.len_min.get()),
                    "max_common":     int(self.len_max_common.get()),
                    "max_occasional": int(self.len_max_occ.get()),
                    "max_rare":       int(self.len_max_rare.get()),
                    "hard_cap":       int(self.len_hard_cap.get()),
                }
            except (ValueError, tk.TclError):
                pass  # 用户半填数字不存，避免写坏 config.json

        save_config(cfg)

    # ════════════════════════════════════════════════
    #  Tab 3: LLM 配置（M1）
    # ════════════════════════════════════════════════

    # 已测试厂商 / 协议
    LLM_PROVIDERS = [
        "DeepSeek（推荐）",
        "豆包（Doubao）",
        "KIMI（Moonshot）",
        "MINIMAX",
        "MIMO",
        "OpenAI",
        "自定义（OpenAI 协议）",
    ]

    def _build_tab_llm(self):
        """🤖 LLM 配置 子标签：API Key + 模型 + 参数 + 测试连接"""
        frame = ttk.Frame(self._tab_llm, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # ── 启用开关 ──
        enable_row = ttk.Frame(frame)
        enable_row.pack(fill=tk.X, pady=(0, 8))
        self.llm_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(enable_row, text="启用 LLM 决策（关闭时走 v2 静态模式）",
                        variable=self.llm_enabled_var,
                        command=self._save_config_from_form).pack(side=tk.LEFT)

        # ── 服务配置 ──
        svc = ttk.LabelFrame(frame, text="LLM 服务", padding=8)
        svc.pack(fill=tk.X, pady=4)

        r1 = ttk.Frame(svc)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Provider：", width=12).pack(side=tk.LEFT)
        self.llm_provider = ttk.Combobox(r1, values=self.LLM_PROVIDERS,
                                          state="readonly", width=24)
        self.llm_provider.set("DeepSeek（推荐）")
        self.llm_provider.pack(side=tk.LEFT, padx=4)
        ttk.Label(r1, text="模型：", width=8).pack(side=tk.LEFT, padx=(16, 0))
        self.llm_model = ttk.Entry(r1, width=24)
        self.llm_model.insert(0, "deepseek-chat")
        self.llm_model.pack(side=tk.LEFT, padx=4)
        self.llm_model.bind("<FocusOut>", lambda e: self._save_config_from_form())

        r2 = ttk.Frame(svc)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="Base URL：", width=12).pack(side=tk.LEFT)
        self.llm_base_url = ttk.Entry(r2)
        self.llm_base_url.insert(0, "https://api.deepseek.com")
        self.llm_base_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.llm_base_url.bind("<FocusOut>", lambda e: self._save_config_from_form())

        r3 = ttk.Frame(svc)
        r3.pack(fill=tk.X, pady=2)
        ttk.Label(r3, text="API Key：", width=12).pack(side=tk.LEFT)
        self.llm_api_key = ttk.Entry(r3, show="*")
        self.llm_api_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.llm_api_key.bind("<FocusOut>", lambda e: self._save_config_from_form())
        self.llm_show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(r3, text="显示", variable=self.llm_show_key,
                        command=self._toggle_api_key_visibility).pack(side=tk.LEFT, padx=4)

        ttk.Label(svc, text="已测试厂商：DeepSeek / 豆包 / KIMI / MINIMAX / MIMO / OpenAI · 协议：OpenAI 兼容",
                  foreground="gray", font=("Microsoft YaHei", 8)).pack(anchor=tk.W, pady=(4, 0))

        # ── 生成参数 ──
        param = ttk.LabelFrame(frame, text="生成参数", padding=8)
        param.pack(fill=tk.X, pady=4)

        r4 = ttk.Frame(param)
        r4.pack(fill=tk.X, pady=2)
        ttk.Label(r4, text="温度：", width=12).pack(side=tk.LEFT)
        self.llm_temperature = tk.Scale(r4, from_=0, to=200, orient=tk.HORIZONTAL,
                                         showvalue=False, command=self._on_llm_temp_change)
        self.llm_temperature.set(80)
        self.llm_temperature.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.llm_temp_label = ttk.Label(r4, text="0.80", width=5)
        self.llm_temp_label.pack(side=tk.LEFT, padx=(6, 0))

        r5 = ttk.Frame(param)
        r5.pack(fill=tk.X, pady=2)
        ttk.Label(r5, text="超时（秒）：", width=12).pack(side=tk.LEFT)
        self.llm_timeout = ttk.Entry(r5, width=8)
        self.llm_timeout.insert(0, "8")
        self.llm_timeout.pack(side=tk.LEFT, padx=4)
        self.llm_timeout.bind("<FocusOut>", lambda e: self._save_config_from_form())

        r6 = ttk.Frame(param)
        r6.pack(fill=tk.X, pady=2)
        ttk.Label(r6, text="模式：", width=12).pack(side=tk.LEFT)
        self.llm_mode = ttk.Combobox(r6, values=["pick", "generate"], state="readonly", width=10)
        self.llm_mode.set("pick")
        self.llm_mode.pack(side=tk.LEFT, padx=4)
        self.llm_mode.bind("<<ComboboxSelected>>", lambda e: self._save_config_from_form())
        ttk.Label(r6, text="（pick=从 messages 池挑，generate=LLM 自创）",
                  foreground="gray", font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=8)

        # ── 测试连接 ──
        test_row = ttk.Frame(frame)
        test_row.pack(fill=tk.X, pady=8)
        ttk.Button(test_row, text="🔌 测试连接",
                   command=self._test_llm_connection).pack(side=tk.LEFT, padx=2)
        self.llm_test_status = tk.Label(test_row, text="（未测试）",
                                         fg="gray", font=("Microsoft YaHei", 9))
        self.llm_test_status.pack(side=tk.LEFT, padx=12)

        # ── 弹幕长度控制（B 任务：4 个上限 + 硬截断） ──
        lenfrm = ttk.LabelFrame(frame, text="弹幕长度（字数）", padding=8)
        lenfrm.pack(fill=tk.X, pady=4)

        lr1 = ttk.Frame(lenfrm); lr1.pack(fill=tk.X, pady=2)
        ttk.Label(lr1, text="最短：", width=10).pack(side=tk.LEFT)
        self.len_min = ttk.Spinbox(lr1, from_=1, to=20, width=4)
        self.len_min.set(1); self.len_min.pack(side=tk.LEFT, padx=4)
        ttk.Label(lr1, text="·70% 上限：", width=10).pack(side=tk.LEFT, padx=(8, 0))
        self.len_max_common = ttk.Spinbox(lr1, from_=1, to=20, width=4)
        self.len_max_common.set(5); self.len_max_common.pack(side=tk.LEFT, padx=4)
        self.len_max_common.bind("<FocusOut>", lambda e: self._save_config_from_form())

        lr2 = ttk.Frame(lenfrm); lr2.pack(fill=tk.X, pady=2)
        ttk.Label(lr2, text="·25% 上限：", width=10).pack(side=tk.LEFT)
        self.len_max_occ = ttk.Spinbox(lr2, from_=1, to=20, width=4)
        self.len_max_occ.set(9); self.len_max_occ.pack(side=tk.LEFT, padx=4)
        self.len_max_occ.bind("<FocusOut>", lambda e: self._save_config_from_form())
        ttk.Label(lr2, text="·5% 上限：", width=10).pack(side=tk.LEFT, padx=(8, 0))
        self.len_max_rare = ttk.Spinbox(lr2, from_=1, to=20, width=4)
        self.len_max_rare.set(11); self.len_max_rare.pack(side=tk.LEFT, padx=4)
        self.len_max_rare.bind("<FocusOut>", lambda e: self._save_config_from_form())

        lr3 = ttk.Frame(lenfrm); lr3.pack(fill=tk.X, pady=2)
        ttk.Label(lr3, text="硬截断：", width=10).pack(side=tk.LEFT)
        self.len_hard_cap = ttk.Spinbox(lr3, from_=1, to=30, width=4)
        self.len_hard_cap.set(12); self.len_hard_cap.pack(side=tk.LEFT, padx=4)
        self.len_hard_cap.bind("<FocusOut>", lambda e: self._save_config_from_form())
        ttk.Label(lr3, text="（超过则强制截断 + 日志提示）",
                  foreground="gray", font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=8)

        # ── 提示 ──
        ttk.Label(frame, text="💡 提示：测试连接会发起一次真实 LLM 调用，"
                            "会有 1~2 秒延迟。\n关闭启用后，引擎自动走 v2 静态模式，"
                            "无需修改其他配置。",
                  foreground="gray", font=("Microsoft YaHei", 8),
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))

    def _toggle_api_key_visibility(self):
        self.llm_api_key.config(show="" if self.llm_show_key.get() else "*")

    def _on_llm_temp_change(self, val):
        try:
            self.llm_temp_label.config(text=f"{int(val)/100:.2f}")
        except Exception:
            pass

    def _test_llm_connection(self):
        """测试 LLM 连接 + 一次真实调用"""
        api_key = self.llm_api_key.get().strip()
        base_url = self.llm_base_url.get().strip() or "https://api.deepseek.com"
        model = self.llm_model.get().strip() or "deepseek-chat"

        if not api_key:
            self.llm_test_status.config(text="❌ API Key 为空", fg="red")
            return

        self.llm_test_status.config(text="⏳ 测试中...", fg="blue")
        self.root.update_idletasks()

        try:
            from llm_engine import PERSONAS, think
            cfg = {
                "llm_api_key": api_key,
                "llm_base_url": base_url,
                "llm_model": model,
                "llm_temperature": 0.5,
                "llm_timeout": 10,
            }
            p = PERSONAS[0]
            result = think(p, cfg)
            content = result.get("content", "")
            masked_key = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else "***"
            self.llm_test_status.config(
                text=f"✓ {model} | 内容: {content[:20]} | key={masked_key}", fg="green")
            self.log(f"🔌 LLM 测试成功: {model} → {content}")
        except Exception as e:
            self.llm_test_status.config(text=f"❌ 失败: {e}", fg="red")
            self.log(f"❌ LLM 测试失败: {e}")

    # ── 操作按钮 ──

    @staticmethod
    def _get_python_exe() -> str:
        """获取 pythonw.exe 路径（无黑框），不存在则回退到 python.exe"""
        exe = sys.executable
        if sys.platform == "win32":
            pyw_exe = str(Path(exe).with_name("pythonw.exe"))
            if os.path.exists(pyw_exe):
                return pyw_exe
        return exe

    def _get_subprocess_args(self, mode: str, account_dir: Path | None = None) -> list[str]:
        """获取子进程启动参数（兼容 PyInstaller 打包和源码运行）

        account_dir: 账号浏览器数据目录,None 时用旧路径 browser_data/ 兼容老用法
        """
        script = str(APP_DIR / "douyin_interact.py")
        # 把账号目录加到 --user-data-dir 参数(子进程会读)
        udd = account_dir if account_dir is not None else (APP_DIR / "browser_data")
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包：用自身 exe + --mode 参数
            return [sys.executable, "--mode", mode, "--user-data-dir", str(udd)]
        if mode == "login":
            return [self._get_python_exe(), "-u", script, "--login", "--user-data-dir", str(udd)]
        return [self._get_python_exe(), "-u", script, "--user-data-dir", str(udd)]

    def _login(self):
        """打开有头浏览器扫码登录"""
        try:
            self._save_config_from_form()
            account_dir = self._get_account_dir()
            if account_dir is None:
                messagebox.showwarning("提示", "请先选择或新建一个账号")
                return
            account_dir.mkdir(parents=True, exist_ok=True)

            self.log(f"🔑 正在打开有头浏览器，请扫码登录到 [{self.account_combo.get()}]...")
            args = self._get_subprocess_args("login", account_dir)
            self.log(f"  命令: {' '.join(args)}")
            subprocess.Popen(args, cwd=str(APP_DIR))
            self.log("🔑 浏览器窗口已打开，扫码后会自动保存登录态。")
        except Exception as e:
            self.log(f"❌ 登录失败: {e}")
            messagebox.showerror("错误", f"扫码登录失败:\n{e}")

    # ════════════════════════════════════════
    #  多账号管理
    # ════════════════════════════════════════

    def _accounts_root(self) -> Path:
        return APP_DIR / "accounts"

    def _list_accounts(self) -> list:
        """列出 accounts/ 下所有账号目录"""
        root = self._accounts_root()
        root.mkdir(exist_ok=True)
        return sorted([d.name for d in root.iterdir() if d.is_dir()])

    def _get_account_dir(self) -> Path | None:
        """当前选中账号的目录,没选返回 None"""
        name = self.account_combo.get()
        if not name:
            return None
        return self._accounts_root() / name

    def _refresh_account_combo(self):
        """刷新账号下拉框"""
        names = self._list_accounts()
        self.account_combo["values"] = names
        cfg = load_config()
        current = cfg.get("account", "")
        if current in names:
            self.account_combo.set(current)
        elif names:
            self.account_combo.current(0)
        else:
            self.account_combo.set("")

    def _new_account(self):
        """新建账号(创建空目录)"""
        from tkinter import simpledialog
        name = simpledialog.askstring("新建账号", "输入账号名(字母数字下划线):", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name or "/" in name or "\\" in name or name.startswith("."):
            messagebox.showwarning("提示", "账号名不合法")
            return
        new_dir = self._accounts_root() / name
        if new_dir.exists():
            messagebox.showwarning("提示", f"账号 [{name}] 已存在")
            return
        new_dir.mkdir(parents=True, exist_ok=True)
        self._refresh_account_combo()
        self.account_combo.set(name)
        self._save_config_from_form()
        self.log(f"✅ 已新建账号: {name}(请点「🔑 登录」扫码)")

    def _delete_account(self):
        """删除当前选中账号(连同登录态)"""
        name = self.account_combo.get()
        if not name:
            messagebox.showwarning("提示", "请先选择要删除的账号")
            return
        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除账号 [{name}] 吗?\n\n"
            f"该账号的登录态和浏览器数据将被永久删除,无法恢复!",
        ):
            return
        import shutil
        account_dir = self._accounts_root() / name
        try:
            shutil.rmtree(account_dir)
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")
            return
        self._refresh_account_combo()
        self.log(f"🗑 已删除账号: {name}")
        messagebox.showinfo("完成", f"账号 [{name}] 已删除")

    def _open_account_dir(self):
        """在资源管理器里打开当前账号目录"""
        d = self._get_account_dir()
        if d is None:
            messagebox.showwarning("提示", "请先选择账号")
            return
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(d))   # Windows
        except AttributeError:
            subprocess.Popen(["xdg-open", str(d)])   # Linux 兼容
        except Exception as e:
            messagebox.showerror("错误", f"打开目录失败: {e}")

    def _start(self):
        """启动互动"""
        try:
            if self._proc and self._proc.poll() is None:
                self.log("⚠️ 已在运行中")
                return
            self._save_config_from_form()

            # 必须先选账号
            account_dir = self._get_account_dir()
            if account_dir is None:
                messagebox.showwarning("提示", "请先在「账号」栏选择或新建一个账号")
                return
            if not account_dir.exists() or not any(account_dir.iterdir()):
                if not messagebox.askyesno(
                    "账号未登录",
                    f"账号 [{self.account_combo.get()}] 还没有登录态。\n"
                    f"是否现在点「🔑 登录」扫码?\n\n"
                    f"点「否」会取消启动。",
                ):
                    return
                self._login()
                return

            # 清掉残留的停止标记，确保子进程能正常循环
            stop_flag = APP_DIR / ".stop_flag"
            stop_flag.unlink(missing_ok=True)

            self.log(f"▶️ 启动中 (账号:{self.account_combo.get()})...")
            args = self._get_subprocess_args("run", account_dir)
            self.log(f"  命令: {' '.join(args)}")
            kwargs = dict(
                args=args,
                cwd=str(APP_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            self._proc = subprocess.Popen(**kwargs)
        except Exception as e:
            self.log(f"❌ 启动失败: {e}")
            messagebox.showerror("错误", f"启动失败:\n{e}")
            return

        def _read(p, app):
            try:
                for line in p.stdout:
                    app.root.after(0, app.log, line.rstrip())
            except Exception:
                pass
        threading.Thread(target=_read, args=(self._proc, self), daemon=True).start()

        self._update_status(running=True)
        self.log(f"✅ 已启动 (PID={self._proc.pid})")

    def _stop(self):
        """停止互动：写停止标记 → 等子进程优雅退出（触发 finally 关浏览器）→ 超时再强杀"""
        if not self._proc or self._proc.poll() is not None:
            self.log("⚠️ 未在运行")
            self._update_status(running=False)
            return
        proc = self._proc
        self._proc = None

        # 写入停止标记，子进程主循环检测到后会 break 并 ctx.close()
        stop_flag = APP_DIR / ".stop_flag"
        try:
            stop_flag.touch()
        except Exception:
            pass

        # 给子进程最多 10 秒优雅退出（含浏览器关闭时间）
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.log("⚠️ 子进程未响应，强制结束")
            proc.kill()
        stop_flag.unlink(missing_ok=True)

        self._update_status(running=False)
        self.log("⏹ 已停止")

    def _update_status(self, running: bool):
        """更新运行状态 UI"""
        if running:
            self.status_label.config(text="🟢 运行中", fg="green")
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="⚪ 已停止", fg="gray")
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)

    def _build_tab_rules(self):
        """Tab 2: 角色管理（M1 重做：拆三个子标签 ⚙ 设定 / 💬 弹幕 / 📄 提示词）"""
        frame = ttk.Frame(self._tab_rules, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # 顶部:文件导入按钮行
        import_row = ttk.Frame(frame)
        import_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(import_row, text="📂 从 TXT 导入弹幕",
                   command=self._import_from_txt).pack(side=tk.LEFT, padx=2)
        ttk.Button(import_row, text="💾 导出当前角色为 TXT",
                   command=self._export_to_txt).pack(side=tk.LEFT, padx=2)
        ttk.Label(import_row, text="(每行一条弹幕;或 用户名:弹幕)",
                  foreground="gray", font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=8)

        # 角色选择 + 新增/删除按钮
        r1 = ttk.Frame(frame)
        r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="当前角色：").pack(side=tk.LEFT)
        self.persona_combo = ttk.Combobox(r1, values=get_persona_names(), state="readonly", width=24)
        self.persona_combo.pack(side=tk.LEFT, padx=4)
        self.persona_combo.bind("<<ComboboxSelected>>", self._on_persona_select)
        if get_persona_names():
            self.persona_combo.current(0)
        ttk.Button(r1, text="👤 ➕ 新角色", command=self._add_persona).pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="👤 🗑 删角色", command=self._delete_persona).pack(side=tk.LEFT, padx=2)

        # ── 子标签 Notebook ──
        sub_nb = ttk.Notebook(frame)
        sub_nb.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self._tab_sub_settings = ttk.Frame(sub_nb, padding=8)
        self._tab_sub_messages = ttk.Frame(sub_nb, padding=8)
        self._tab_sub_prompt = ttk.Frame(sub_nb, padding=8)

        sub_nb.add(self._tab_sub_settings, text="⚙ 设定")
        sub_nb.add(self._tab_sub_messages, text="💬 弹幕")
        sub_nb.add(self._tab_sub_prompt, text="📄 提示词")

        self._build_subtab_settings()
        self._build_subtab_messages()
        self._build_subtab_prompt()

        self._load_messages_from_code()

    def _build_subtab_settings(self):
        """⚙ 设定 子标签：10 字段选择器 + 滑块 + 保存"""
        f = self._tab_sub_settings

        top = ttk.Frame(f)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="客户类型：").pack(side=tk.LEFT)
        self.set_customer_type = ttk.Combobox(top, values=CUSTOMER_TYPE_OPTIONS,
                                               state="readonly", width=10)
        self.set_customer_type.set("潜客")
        self.set_customer_type.pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(top, text="打字速度：").pack(side=tk.LEFT)
        self.set_typing_style = ttk.Combobox(top, values=TYPING_STYLE_OPTIONS,
                                              state="readonly", width=6)
        self.set_typing_style.set("中")
        self.set_typing_style.pack(side=tk.LEFT, padx=4)
        self.settings_status = tk.Label(top, text="", fg="gray", font=("Microsoft YaHei", 9))
        self.settings_status.pack(side=tk.RIGHT)

        # 三栏字段组
        cols = ttk.Frame(f)
        cols.pack(fill=tk.BOTH, expand=True)

        # 基础画像
        c1 = ttk.LabelFrame(cols, text="基础画像", padding=8)
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        ttk.Label(c1, text="人群").pack(anchor=tk.W)
        self.set_crowd = ttk.Combobox(c1, values=CROWD_OPTIONS, state="readonly")
        self.set_crowd.set("都市中产"); self.set_crowd.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(c1, text="省份").pack(anchor=tk.W)
        self.set_region = ttk.Combobox(c1, values=PROVINCE_OPTIONS, state="readonly")
        self.set_region.set("广东"); self.set_region.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(c1, text="婚姻").pack(anchor=tk.W)
        self.set_marriage = ttk.Combobox(c1, values=MARRIAGE_OPTIONS, state="readonly")
        self.set_marriage.set("已婚有娃"); self.set_marriage.pack(fill=tk.X, pady=(2, 6))

        # 消费力
        c2 = ttk.LabelFrame(cols, text="消费力", padding=8)
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        ttk.Label(c2, text="手机价位").pack(anchor=tk.W)
        self.set_device = ttk.Combobox(c2, values=DEVICE_OPTIONS, state="readonly")
        self.set_device.set("3000-5000"); self.set_device.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(c2, text="车型").pack(anchor=tk.W)
        self.set_vehicle = ttk.Combobox(c2, values=VEHICLE_OPTIONS, state="readonly")
        self.set_vehicle.set("无车"); self.set_vehicle.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(c2, text="购物频次").pack(anchor=tk.W)
        self.set_purchase_freq = ttk.Combobox(c2, values=PURCHASE_FREQ_OPTIONS, state="readonly")
        self.set_purchase_freq.set("中"); self.set_purchase_freq.pack(fill=tk.X, pady=(2, 6))

        # 表达风格
        c3 = ttk.LabelFrame(cols, text="表达风格", padding=8)
        c3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        ttk.Label(c3, text="语气").pack(anchor=tk.W)
        self.set_tone = ttk.Combobox(c3, values=TONE_OPTIONS, state="readonly")
        self.set_tone.set("直白务实"); self.set_tone.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(c3, text="回应率（0=静默，1=必回）").pack(anchor=tk.W)
        slider_row = ttk.Frame(c3)
        slider_row.pack(fill=tk.X, pady=(2, 6))
        self.set_response_tendency = tk.Scale(slider_row, from_=0, to=100, orient=tk.HORIZONTAL,
                                              showvalue=False, command=self._on_slider_change)
        self.set_response_tendency.set(45)
        self.set_response_tendency.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.response_tendency_label = ttk.Label(slider_row, text="0.45", width=5)
        self.response_tendency_label.pack(side=tk.LEFT, padx=(6, 0))

        # 底部按钮
        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="💾 保存到 JSON", command=self._save_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="👁 预览拼接提示词", command=self._preview_system_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🔄 重新加载", command=self._load_settings).pack(side=tk.LEFT, padx=2)

    def _build_subtab_messages(self):
        """💬 弹幕 子标签：原有 messages 编辑"""
        f = self._tab_sub_messages
        ttk.Label(f, text="该角色的弹幕内容：", font=("Microsoft YaHei", 9, "bold")).pack(anchor=tk.W, pady=(0, 2))
        list_frame = ttk.Frame(f)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.msg_listbox = tk.Listbox(list_frame, height=12, font=("Microsoft YaHei", 10),
                                       selectmode=tk.SINGLE, bg="#fafafa")
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.msg_listbox.yview)
        self.msg_listbox.configure(yscrollcommand=scrollbar.set)
        self.msg_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        edit_frame = ttk.LabelFrame(f, text="编辑弹幕", padding=8)
        edit_frame.pack(fill=tk.X, pady=6)
        r2 = ttk.Frame(edit_frame)
        r2.pack(fill=tk.X)
        ttk.Label(r2, text="弹幕内容：").pack(side=tk.LEFT)
        self.msg_entry = ttk.Entry(r2)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        btn_row = ttk.Frame(edit_frame)
        btn_row.pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="➕ 添加弹幕", command=self._add_message).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✏️ 更新", command=self._update_message).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🗑️ 删除", command=self._delete_message).pack(side=tk.LEFT, padx=2)
        self.msg_listbox.bind("<<ListboxSelect>>", self._on_msg_select)

    def _build_subtab_prompt(self):
        """📄 提示词 子标签：personas/<name>.md 编辑"""
        f = self._tab_sub_prompt
        info = ttk.Label(f, text="高级覆盖：直接编辑当前角色的 system prompt 补充段（保存到 personas/<角色名>.md）。\n"
                            "留空则用自动拼接的模板。",
                          foreground="gray", font=("Microsoft YaHei", 8), justify=tk.LEFT)
        info.pack(anchor=tk.W, pady=(0, 6))
        self.prompt_text = scrolledtext.ScrolledText(f, height=14, font=("Microsoft YaHei", 9),
                                                     wrap=tk.WORD)
        self.prompt_text.pack(fill=tk.BOTH, expand=True)
        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btn_row, text="💾 保存提示词", command=self._save_prompt_md).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🔄 重新加载", command=self._load_prompt_md).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🗑 删除 .md（用自动模板）", command=self._delete_prompt_md).pack(side=tk.LEFT, padx=2)

    # ── 设定子标签：保存/加载/预览 ──

    def _on_slider_change(self, val):
        try:
            self.response_tendency_label.config(text=f"{int(val)/100:.2f}")
        except Exception:
            pass

    def _save_settings(self):
        name = self.persona_combo.get()
        if not name:
            messagebox.showwarning("提示", "请先选择角色")
            return
        data = self._load_persona_data()
        if name not in data or not isinstance(data[name], dict):
            data[name] = {}
        old = data[name]
        # 保留旧字段
        old["tone"] = old.get("tone", "")
        old["trait"] = old.get("trait", "")
        old["style"] = old.get("style", "")
        old["messages"] = old.get("messages", [])
        # 写入 9 个新字段
        old["crowd"] = self.set_crowd.get()
        old["device"] = self.set_device.get()
        old["vehicle"] = self.set_vehicle.get()
        old["purchase_freq"] = self.set_purchase_freq.get()
        old["region"] = self.set_region.get()
        old["marriage"] = self.set_marriage.get()
        old["customer_type"] = self.set_customer_type.get()
        old["typing_style"] = self.set_typing_style.get()
        old["response_tendency"] = round(int(self.set_response_tendency.get()) / 100, 2)
        data[name] = old
        self._save_persona_data(data)
        self._refresh_personas_after_edit()
        self.settings_status.config(text=f"✓ 已保存 {name}", fg="green")
        self.log(f"⚙ 已保存设定: [{name}] {old['customer_type']} / {old['crowd']}")

    def _load_settings(self):
        name = self.persona_combo.get()
        if not name:
            return
        data = self._load_persona_data()
        p = data.get(name, {})
        if not isinstance(p, dict):
            return
        self.set_crowd.set(p.get("crowd", "都市中产"))
        self.set_device.set(p.get("device", "3000-5000"))
        self.set_vehicle.set(p.get("vehicle", "无车"))
        self.set_purchase_freq.set(p.get("purchase_freq", "中"))
        self.set_region.set(p.get("region", "广东"))
        self.set_marriage.set(p.get("marriage", "已婚有娃"))
        self.set_customer_type.set(p.get("customer_type", "潜客"))
        self.set_typing_style.set(p.get("typing_style", "中"))
        rt = float(p.get("response_tendency", 0.45))
        self.set_response_tendency.set(int(rt * 100))
        self.response_tendency_label.config(text=f"{rt:.2f}")

    def _refresh_personas_after_edit(self):
        from llm_engine import load_personas
        global PERSONAS
        PERSONAS = load_personas()
        self._refresh_account_personas()

    def _preview_system_prompt(self):
        name = self.persona_combo.get()
        if not name:
            messagebox.showwarning("提示", "请先选择角色")
            return
        persona = {
            "name": name,
            "crowd": self.set_crowd.get(),
            "device": self.set_device.get(),
            "vehicle": self.set_vehicle.get(),
            "purchase_freq": self.set_purchase_freq.get(),
            "region": self.set_region.get(),
            "marriage": self.set_marriage.get(),
            "customer_type": self.set_customer_type.get(),
            "tone": "",
            "typing_style": self.set_typing_style.get(),
            "response_tendency": int(self.set_response_tendency.get()) / 100,
        }
        try:
            from llm_engine import compose_system_prompt
            sp = compose_system_prompt(persona)
        except Exception as e:
            sp = f"❌ 生成失败: {e}"
        win = tk.Toplevel(self.root)
        win.title(f"系统提示词预览 - {name}")
        win.geometry("640x520")
        txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, sp)
        txt.config(state=tk.DISABLED)

    # ── 提示词子标签：保存/加载/删除 ──

    def _prompt_md_path(self) -> Path:
        name = self.persona_combo.get()
        if not name:
            return None
        return PERSONAS_DIR / f"{name}.md"

    def _load_prompt_md(self):
        path = self._prompt_md_path()
        if path is None or not hasattr(self, "prompt_text"):
            return
        self.prompt_text.delete("1.0", tk.END)
        if path and path.exists():
            try:
                self.prompt_text.insert(tk.END, path.read_text(encoding="utf-8"))
            except Exception as e:
                self.log(f"⚠ 读取 .md 失败: {e}")

    def _save_prompt_md(self):
        path = self._prompt_md_path()
        if path is None:
            messagebox.showwarning("提示", "请先选择角色")
            return
        content = self.prompt_text.get("1.0", tk.END).strip()
        try:
            path.write_text(content, encoding="utf-8")
            self.log(f"📄 已保存提示词: {path.name}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _delete_prompt_md(self):
        path = self._prompt_md_path()
        if path is None or not path.exists():
            return
        if not messagebox.askyesno("确认", f"删除 {path.name}？\n将回退到自动模板。"):
            return
        try:
            path.unlink()
            self.prompt_text.delete("1.0", tk.END)
            self.log(f"🗑 已删除 {path.name}")
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    def _load_messages_from_code(self):
        """从 PERSONAS 加载默认角色到 rules.json 和 UI（含子标签）"""
        data = {}
        for p in PERSONAS:
            data[p["name"]] = {
                "tone": p.get("tone", ""),
                "trait": p.get("trait", ""),
                "style": p.get("style", ""),
                "messages": list(p.get("messages", [])),
            }
        self._save_persona_data(data)
        self._refresh_persona_combo()
        self._refresh_account_personas()
        self._refresh_msg_list()
        # M1: 同步加载子标签
        if hasattr(self, "set_crowd"):
            self._load_settings()
        if hasattr(self, "prompt_text"):
            self._load_prompt_md()

    def _refresh_msg_list(self):
        """刷新当前选中角色的弹幕列表"""
        persona = self.persona_combo.get()
        if not persona:
            return
        self.msg_listbox.delete(0, tk.END)
        data = self._load_persona_data()
        for msg in self._get_persona_messages(data.get(persona, [])):
            self.msg_listbox.insert(tk.END, msg)

    def _load_persona_data(self) -> dict:
        """从 rules.json 加载角色数据（含描述和弹幕）"""
        if RULES_FILE.exists():
            try:
                data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _save_persona_data(self, data: dict):
        RULES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _get_persona_messages(persona_data) -> list:
        """兼容新旧格式：返回弹幕列表"""
        if isinstance(persona_data, dict):
            return persona_data.get("messages", [])
        if isinstance(persona_data, list):
            return persona_data
        return []

    def _on_persona_select(self, event=None):
        self._refresh_msg_list()
        # M1: 切换角色时同步刷新子标签
        if hasattr(self, "set_crowd"):
            self._load_settings()
        if hasattr(self, "prompt_text"):
            self._load_prompt_md()

    def _on_msg_select(self, event=None):
        sel = self.msg_listbox.curselection()
        if sel:
            self.msg_entry.delete(0, tk.END)
            self.msg_entry.insert(0, self.msg_listbox.get(sel[0]))

    def _add_message(self):
        msg = self.msg_entry.get().strip()
        if not msg:
            return
        persona = self.persona_combo.get()
        if not persona:
            return
        data = self._load_persona_data()
        if persona not in data:
            data[persona] = {"messages": []}
        if "messages" not in data[persona]:
            data[persona] = {"messages": data[persona]} if isinstance(data[persona], list) else {"messages": [], **data[persona]}
        data[persona]["messages"].append(msg)
        self._save_persona_data(data)
        self._refresh_msg_list()
        self.log(f"💬 [{persona}] 已添加弹幕: {msg}")

    def _update_message(self):
        sel = self.msg_listbox.curselection()
        if not sel:
            return
        msg = self.msg_entry.get().strip()
        if not msg:
            return
        persona = self.persona_combo.get()
        data = self._load_persona_data()
        msgs = self._get_persona_messages(data.get(persona, []))
        old = msgs[sel[0]]
        msgs[sel[0]] = msg
        self._save_persona_data(data)
        self._refresh_msg_list()
        self.log(f"✏️ [{persona}] {old} → {msg}")

    def _delete_message(self):
        sel = self.msg_listbox.curselection()
        if not sel:
            return
        persona = self.persona_combo.get()
        data = self._load_persona_data()
        msgs = data[persona].get("messages", []) if isinstance(data.get(persona), dict) else data[persona]
        msg = msgs.pop(sel[0])
        self._save_persona_data(data)
        self._refresh_msg_list()
        self.log(f"🗑 [{persona}] 已删除: {msg}")

    def _add_persona(self):
        """添加新角色"""
        name = simpledialog.askstring("添加角色", "请输入新角色名称：", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        data = self._load_persona_data()
        if name in data:
            messagebox.showwarning("提示", f"角色 [{name}] 已存在")
            return
        data[name] = {"tone": "", "trait": "", "style": "", "messages": []}
        self._save_persona_data(data)
        self._refresh_persona_combo()
        self.persona_combo.set(name)
        self._refresh_msg_list()
        self._refresh_account_personas()
        self.log(f"👤 已添加角色: {name}")

    def _delete_persona(self):
        """删除当前选中角色"""
        name = self.persona_combo.get()
        if not name:
            return
        data = self._load_persona_data()
        if len(data) <= 1:
            messagebox.showwarning("提示", "至少保留一个角色")
            return
        if not messagebox.askyesno("确认", f"确定删除角色 [{name}] 吗？\n该角色的弹幕数据也将被删除。"):
            return
        del data[name]
        self._save_persona_data(data)
        self._refresh_persona_combo()
        if self.persona_combo.get():
            self._refresh_msg_list()
        self._refresh_account_personas()
        self.log(f"👤 已删除角色: {name}")

    def _refresh_persona_combo(self):
        """刷新角色下拉列表"""
        data = self._load_persona_data()
        names = list(data.keys())
        self.persona_combo["values"] = names
        if names and self.persona_combo.get() not in names:
            self.persona_combo.current(0)

    # ════════════════════════════════════════
    #  TXT 文件导入/导出
    # ════════════════════════════════════════

    @staticmethod
    def _parse_txt_file(path: str) -> dict:
        """解析 TXT 文件为 {用户名: [弹幕列表]}

        自动识别三种格式:
          A) 每行 "用户名:弹幕"      → 多用户,每行一对
          B) 用户名行 + 弹幕行(空行/==== 分隔) → 分组
          C) 每行纯文本(无冒号)     → 单文件当一个角色
        """
        try:
            text = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = Path(path).read_text(encoding="gbk", errors="ignore")

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return {}

        # 统计有多少行含冒号
        colon_lines = [ln for ln in lines if (":" in ln or "：" in ln) and len(ln) > 1]
        ratio = len(colon_lines) / len(lines)

        # 格式 A: 多数行含冒号 → 按 "用户:弹幕" 解析
        if ratio > 0.5:
            result = {}
            for ln in lines:
                for sep in ["：", ":"]:
                    if sep in ln:
                        u, t = ln.split(sep, 1)
                        u, t = u.strip(), t.strip()
                        if u and t and not u.isdigit() and 1 <= len(u) <= 30:
                            result.setdefault(u, []).append(t)
                        break
            if result:
                return result

        # 格式 B: 用空行/==== 分组,组内第一行是用户名
        groups = []
        current = []
        for ln in lines:
            # 分隔符:空行、====、---、***
            if ln in ("====", "----", "***") or ln.startswith("==="):
                if current:
                    groups.append(current)
                current = []
                continue
            # 多个空行 = 段落分隔
            if not ln:
                if current and len(current) > 1:
                    groups.append(current)
                    current = []
                continue
            current.append(ln)
        if current:
            groups.append(current)

        # 每组:第一行=用户名,其余=弹幕
        if all(len(g) >= 1 for g in groups) and len(groups) > 1:
            result = {}
            for g in groups:
                user = g[0]
                msgs = g[1:] if len(g) > 1 else []
                if msgs and not user.isdigit() and 1 <= len(user) <= 30:
                    result[user] = msgs
            if result:
                return result

        # 格式 C: 单文件当一个角色,文件名(去后缀)当用户名
        from os.path import splitext, basename
        default_name = splitext(basename(path))[0] or "导入用户"
        return {default_name: lines}

    def _import_from_txt(self):
        """从 TXT 文件导入弹幕到 rules.json"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="选择弹幕 TXT 文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return

        parsed = self._parse_txt_file(path)
        if not parsed:
            messagebox.showwarning("提示", "TXT 文件解析失败,没有有效内容")
            return

        total_msgs = sum(len(v) for v in parsed.values())
        # 弹窗确认 + 选导入方式
        dlg = _ImportDialog(self.root, parsed, total_msgs, get_persona_names())
        self.root.wait_window(dlg.top)
        if not dlg.result:
            return

        mode, target = dlg.result
        data = self._load_persona_data()
        imported = 0
        skipped = 0

        if mode == "merge":
            # 追加到指定现有角色
            persona = target
            if persona not in data:
                data[persona] = {"tone": "", "trait": "", "style": "", "messages": []}
            if "messages" not in data[persona] or not isinstance(data[persona].get("messages"), list):
                data[persona]["messages"] = []
            existing = set(data[persona]["messages"])
            added = 0
            for user_msgs in parsed.values():
                for m in user_msgs:
                    if m not in existing:
                        data[persona]["messages"].append(m)
                        existing.add(m)
                        added += 1
                    else:
                        skipped += 1
            imported = added

        elif mode == "new_each":
            # 每个用户新建一个角色
            for user, msgs in parsed.items():
                if user in data:
                    existing = set(data[user].get("messages", []) if isinstance(data[user], dict) else data[user])
                    new_msgs = [m for m in msgs if m not in existing]
                    if isinstance(data[user], dict):
                        data[user].setdefault("messages", []).extend(new_msgs)
                    else:
                        data[user] = {"tone": "", "trait": "", "style": "", "messages": list(data[user]) + new_msgs}
                    skipped += len(msgs) - len(new_msgs)
                    imported += len(new_msgs)
                else:
                    data[user] = {"tone": "", "trait": "", "style": "", "messages": list(msgs)}
                    imported += len(msgs)

        elif mode == "new_one":
            # 所有弹幕归到一个新角色
            name = target or f"导入_{Path(path).stem}"
            all_msgs = []
            for user_msgs in parsed.values():
                all_msgs.extend(user_msgs)
            # 去重
            seen = set()
            unique = []
            for m in all_msgs:
                if m not in seen:
                    seen.add(m)
                    unique.append(m)
            data[name] = {"tone": "", "trait": "", "style": "", "messages": unique}
            imported = len(unique)
            skipped = len(all_msgs) - len(unique)

        self._save_persona_data(data)
        self._refresh_persona_combo()
        self._refresh_account_personas()
        self._refresh_msg_list()

        msg = f"✅ 已导入 {imported} 条弹幕"
        if skipped:
            msg += f"(跳过重复 {skipped} 条)"
        self.log(msg)
        messagebox.showinfo("导入完成", msg)

    def _export_to_txt(self):
        """导出当前角色的弹幕到 TXT"""
        from tkinter import filedialog
        persona = self.persona_combo.get()
        if not persona:
            messagebox.showwarning("提示", "请先选择一个角色")
            return
        data = self._load_persona_data()
        msgs = self._get_persona_messages(data.get(persona, []))
        if not msgs:
            messagebox.showwarning("提示", f"角色 [{persona}] 没有弹幕可导出")
            return

        default_name = f"{persona}_弹幕.txt"
        path = filedialog.asksaveasfilename(
            title="保存为 TXT",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("文本文件", "*.txt")],
        )
        if not path:
            return
        Path(path).write_text(
            "\n".join(f"{persona}:{m}" for m in msgs),
            encoding="utf-8",
        )
        self.log(f"💾 已导出 {len(msgs)} 条到: {path}")
        messagebox.showinfo("导出完成", f"已导出 {len(msgs)} 条弹幕到\n{path}")

    def _refresh_account_personas(self):
        """重新加载 PERSONAS（从 rules.json），刷新角色下拉"""
        from llm_engine import load_personas
        global PERSONAS
        PERSONAS = load_personas()
        # 重建单选角色下拉
        names = get_persona_names()
        self.persona_combo["values"] = names
        if names and not self.persona_combo.get():
            self.persona_combo.set(names[0])
        self._load_config_to_form()

    # ════════════════════════════════════════
    #  Tab 4: 弹幕采集（按用户分组 + 一键导入角色）
    # ════════════════════════════════════════

    def _build_tab_record(self):
        frame = ttk.Frame(self._tab_record, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ctrl = ttk.LabelFrame(frame, text="弹幕采集控制", padding=10)
        ctrl.pack(fill=tk.X, pady=4)

        r1 = ttk.Frame(ctrl)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="直播间：", width=8).pack(side=tk.LEFT)
        self.record_url = ttk.Entry(r1)
        self.record_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.record_url.insert(0, "https://live.douyin.com/212858182821")

        r2 = ttk.Frame(ctrl)
        r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="时长(分钟)：", width=8).pack(side=tk.LEFT)
        self.record_duration = tk.IntVar(value=10)
        ttk.Scale(r2, from_=1, to=60, variable=self.record_duration,
                  orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=6)
        self.dur_label = ttk.Label(r2, text="10 分", width=5)
        self.dur_label.pack(side=tk.LEFT)
        self.record_duration.trace_add("write", lambda *_: self.dur_label.config(
            text=f"{self.record_duration.get()} 分"))

        btn_row = ttk.Frame(ctrl)
        btn_row.pack(fill=tk.X, pady=4)
        self.btn_rec_start = ttk.Button(btn_row, text="🎙️ 开始采集", command=self._on_record_start)
        self.btn_rec_start.pack(side=tk.LEFT, padx=2)
        self.btn_rec_stop = ttk.Button(btn_row, text="⏹ 停止采集", command=self._on_record_stop, state=tk.DISABLED)
        self.btn_rec_stop.pack(side=tk.LEFT, padx=2)
        self.btn_import_roles = ttk.Button(btn_row, text="📥 导入为角色", command=self._on_import_roles, state=tk.DISABLED)
        self.btn_import_roles.pack(side=tk.RIGHT, padx=2)

        # ── 双栏显示：用户列表 | 弹幕内容 ──
        paned = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=6)

        # 左：用户列表
        user_frame = ttk.LabelFrame(paned, text="👤 用户", padding=4)
        paned.add(user_frame, weight=1)
        self.record_user_list = tk.Listbox(user_frame, font=("Microsoft YaHei", 9),
                                           selectmode=tk.SINGLE, exportselection=False)
        self.record_user_list.pack(fill=tk.BOTH, expand=True)
        self.record_user_list.bind("<<ListboxSelect>>", self._on_collect_user_select)

        # 右：弹幕内容
        msg_frame = ttk.LabelFrame(paned, text="💬 弹幕", padding=4)
        paned.add(msg_frame, weight=2)
        self.record_msg_text = scrolledtext.ScrolledText(msg_frame, height=18,
                                                          font=("Microsoft YaHei", 9),
                                                          bg="#fafafa", fg="#333")
        self.record_msg_text.pack(fill=tk.BOTH, expand=True)
        self.record_msg_text.insert(tk.END, "点击「开始采集」后弹幕将按用户分组显示。\n采集完成后可一键导入为角色。\n")

        self._collected_users: dict[str, list[str]] = {}  # 采集结果(按用户分组)
        self._raw_items: list[dict] = []                 # 原始弹幕 [{"user","text"}]

    def _on_record_start(self):
        url = self.record_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入直播间链接")
            return
        self._collected_users = {}
        self._raw_items = []
        self.record_user_list.delete(0, tk.END)
        self.record_msg_text.delete("1.0", tk.END)
        self.record_msg_text.insert(tk.END, "采集中，请稍候...\n")
        self.btn_import_roles.config(state=tk.DISABLED)
        duration = self.record_duration.get()
        self.log(f"🎙️ 开始采集弹幕 ({duration}分钟): {url}")
        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--mode", "record", url, str(duration)]
        else:
            args = [self._get_python_exe(), "-u",
                    str(APP_DIR / "record_content.py"), url, str(duration)]
        kwargs = dict(
            args=args, cwd=str(APP_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        self._record_proc = subprocess.Popen(**kwargs)
        threading.Thread(target=self._read_record_output, daemon=True).start()
        self.btn_rec_start.config(state=tk.DISABLED)
        self.btn_rec_stop.config(state=tk.NORMAL)

    def _on_record_stop(self):
        if self._record_proc and self._record_proc.poll() is None:
            self._record_proc.terminate()
        self._record_proc = None
        self.log("⏹ 采集已停止")
        self.btn_rec_start.config(state=tk.NORMAL)
        self.btn_rec_stop.config(state=tk.DISABLED)
        # 启用导入按钮（如果有采集到数据）
        if self._collected_users:
            self.btn_import_roles.config(state=tk.NORMAL)
            self._refresh_collected_users()
            total = sum(len(v) for v in self._collected_users.values())
            self.log(f"✅ 已采集 {len(self._collected_users)} 个用户, {total} 条弹幕")

    def _read_record_output(self):
        if not self._record_proc:
            return
        for line in self._record_proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "danmaku":
                    text = obj.get("text", "")
                    user = obj.get("user", "")
                    # 边收边按 user 分组(结构化数据,不再走冒号拆分)
                    if user and text:
                        self._collected_users.setdefault(user, []).append(text)
                    # 原始列表保留结构化数据
                    self._raw_items.append({"user": user, "text": text})
                    self.root.after(0, self._append_raw_danmaku,
                                    str(len(self._raw_items)), user, text)
                elif obj.get("type") == "status":
                    self.log(obj.get("text", line))
                elif obj.get("type") == "done":
                    info = json.loads(obj.get("text", "{}"))
                    items = info.get("items", [])
                    # 兼容旧 done 数据(纯文本列表)
                    if items and isinstance(items[0], str):
                        # 旧格式:用冒号兜底拆分一次
                        self._raw_items = [{"user": "", "text": t} for t in items]
                        self._parse_by_colon()
                    else:
                        self._raw_items = items
                        self._collected_users = {}
                        for it in items:
                            u = it.get("user", "")
                            t = it.get("text", "")
                            if u and t:
                                self._collected_users.setdefault(u, []).append(t)
                    self.root.after(0, self._on_record_done)
            except json.JSONDecodeError:
                pass

    def _append_raw_danmaku(self, idx: int, user: str, text: str):
        """实时追加弹幕到右侧文本框"""
        prefix = f"{user}: " if user else ""
        self.record_msg_text.insert(tk.END, f"{idx}. {prefix}{text}\n")
        self.record_msg_text.see(tk.END)

    def _on_record_done(self):
        self.btn_rec_start.config(state=tk.NORMAL)
        self.btn_rec_stop.config(state=tk.DISABLED)
        self._record_proc = None
        self.log(f"✅ 采集完成: {len(self._raw_items)} 条弹幕")
        # 结构化数据已在 _read_record_output 里按 user 分好组,这里只刷新显示
        self._refresh_collected_users()
        total = sum(len(v) for v in self._collected_users.values())
        self.log(f"📊 分组结果: {len(self._collected_users)} 个用户, {total} 条")
        self.btn_import_roles.config(state=tk.NORMAL)
        if self.record_user_list.size() > 0:
            self.record_user_list.selection_set(0)
            self._on_collect_user_select()

    def _parse_by_colon(self):
        """兜底拆分:只对 _raw_items 里 user 为空的旧数据生效。
        新数据(record_content.py v2)已经在后端结构化,不再需要这个方法。
        """
        self._collected_users = {}
        for item in self._raw_items:
            if isinstance(item, dict):
                user = item.get("user", "")
                text = item.get("text", "")
                if user and text:
                    self._collected_users.setdefault(user, []).append(text)
                    continue
                # user 缺失 → 走冒号兜底
                text = text or item.get("text", "")
            else:
                text = str(item)
            t = text.strip()
            for sep in ["：", ":"]:
                if sep in t:
                    left, right = t.split(sep, 1)
                    user = left.strip()
                    content = right.strip()
                    if user.isdigit() or len(user) < 2 or len(user) > 30:
                        continue
                    self._collected_users.setdefault(user, []).append(content)
                    break

    def _refresh_collected_users(self):
        """刷新左侧用户列表"""
        current = self.record_user_list.curselection()
        sel_user = self.record_user_list.get(current[0]) if current else None
        self.record_user_list.delete(0, tk.END)
        for user in sorted(self._collected_users.keys(), key=lambda u: -len(self._collected_users[u])):
            count = len(self._collected_users[user])
            self.record_user_list.insert(tk.END, f"{user} ({count}条)")
        # 恢复选中
        if sel_user:
            for i in range(self.record_user_list.size()):
                if self.record_user_list.get(i).startswith(sel_user.split(" (")[0]):
                    self.record_user_list.selection_set(i)
                    break

    def _on_collect_user_select(self, event=None):
        """选中用户 → 右侧显示其弹幕"""
        sel = self.record_user_list.curselection()
        if not sel:
            return
        text = self.record_user_list.get(sel[0])
        user = text.rsplit(" (", 1)[0]
        self.record_msg_text.delete("1.0", tk.END)
        msgs = self._collected_users.get(user, [])
        for i, msg in enumerate(msgs, 1):
            self.record_msg_text.insert(tk.END, f"{i}. {msg}\n")

    def _on_import_roles(self):
        """一键导入：每个用户 → 新建角色 + 弹幕"""
        if not self._collected_users:
            messagebox.showwarning("提示", "没有可导入的弹幕数据，请先采集")
            return

        users_to_import = list(self._collected_users.keys())
        msg = f"将为以下 {len(users_to_import)} 个用户各创建一个新角色：\n\n"
        msg += "\n".join(f"  · {u} ({len(self._collected_users[u])} 条弹幕)" for u in users_to_import[:10])
        if len(users_to_import) > 10:
            msg += f"\n  ... 共 {len(users_to_import)} 个"

        if not messagebox.askyesno("确认导入", msg):
            return

        data = self._load_persona_data()
        imported = 0
        for user, msgs in self._collected_users.items():
            if user in data:
                # 已存在 → 追加弹幕（去重）
                existing = set(data[user].get("messages", []))
                new_msgs = [m for m in msgs if m not in existing]
                if new_msgs:
                    data[user]["messages"].extend(new_msgs)
                    imported += 1
            else:
                data[user] = {"tone": "", "trait": "", "style": "", "messages": list(msgs)}
                imported += 1

        self._save_persona_data(data)
        self._refresh_persona_combo()
        self._refresh_account_personas()
        self.log(f"📥 已导入 {imported} 个角色 → 💬 角色弹幕标签页查看")

    # ════════════════════════════════════════
    #  生命周期
    # ════════════════════════════════════════

    def _on_close(self):
        self._stop()
        if self._record_proc and self._record_proc.poll() is None:
            self._record_proc.terminate()
        self.root.destroy()

    def log(self, msg):
        import time
        ts = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_area.see(tk.END)

    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════
#  导入对话框
# ══════════════════════════════════════════════

class _ImportDialog:
    """TXT 导入确认弹窗:显示解析结果 + 让用户选导入方式"""

    def __init__(self, parent, parsed: dict, total_msgs: int, existing_personas: list):
        self.result = None  # (mode, target)
        self.parsed = parsed
        self.existing_personas = existing_personas

        self.top = tk.Toplevel(parent)
        self.top.title("导入弹幕")
        self.top.geometry("460x420")
        self.top.transient(parent)
        self.top.grab_set()

        # 解析摘要
        ttk.Label(self.top, text=f"📄 解析结果: {len(parsed)} 个用户,共 {total_msgs} 条弹幕",
                  font=("Microsoft YaHei", 10, "bold")).pack(pady=(12, 6))

        # 用户列表
        list_frame = ttk.LabelFrame(self.top, text="解析到的用户", padding=6)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        preview = scrolledtext.ScrolledText(list_frame, height=8, font=("Microsoft YaHei", 9))
        preview.pack(fill=tk.BOTH, expand=True)
        for user, msgs in parsed.items():
            preview.insert(tk.END, f"  · {user}  ({len(msgs)} 条)\n")
        preview.config(state=tk.DISABLED)

        # 导入方式
        mode_frame = ttk.LabelFrame(self.top, text="导入方式", padding=8)
        mode_frame.pack(fill=tk.X, padx=12, pady=4)

        self.mode_var = tk.StringVar(value="new_each")
        ttk.Radiobutton(mode_frame, text="为每个用户新建一个角色",
                        variable=self.mode_var, value="new_each").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="追加到现有角色:",
                        variable=self.mode_var, value="merge").pack(anchor=tk.W)
        self.persona_combo = ttk.Combobox(mode_frame, values=existing_personas,
                                          state="readonly", width=24)
        self.persona_combo.pack(anchor=tk.W, padx=20, pady=2)
        if existing_personas:
            self.persona_combo.current(0)

        ttk.Radiobutton(mode_frame, text="所有弹幕归到一个新角色(自定义名称):",
                        variable=self.mode_var, value="new_one").pack(anchor=tk.W, pady=(6, 0))
        self.new_name_entry = ttk.Entry(mode_frame, width=26)
        self.new_name_entry.pack(anchor=tk.W, padx=20, pady=2)
        self.new_name_entry.insert(0, "导入角色")

        # 按钮
        btn_frame = ttk.Frame(self.top)
        btn_frame.pack(fill=tk.X, padx=12, pady=12)
        ttk.Button(btn_frame, text="✅ 确定导入",
                   command=self._on_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="取消",
                   command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_ok(self):
        mode = self.mode_var.get()
        target = None
        if mode == "merge":
            target = self.persona_combo.get()
            if not target:
                messagebox.showwarning("提示", "请选择一个现有角色", parent=self.top)
                return
        elif mode == "new_one":
            target = self.new_name_entry.get().strip() or "导入角色"
        self.result = (mode, target)
        self.top.destroy()

    def _on_cancel(self):
        self.result = None
        self.top.destroy()


if __name__ == "__main__":
    App().run()
