



\## 项目基本信息

\- 项目语言：python3.11

\- 项目类型：桌面GUI应用

\- 框架：

&#x20;   - GUI:Tkinter(ttk) —— 4 个 Tab

&#x20;   - 浏览器自动化:Playwright 1.60+(同步 API,Chromium 持久化上下文)

&#x20;   - LLM 客户端:OpenAI 兼容协议 SDK(openai>=1.0.0)

&#x20;   - 分词:jieba(拟人输入节奏)

\- 依赖管理：pip + requirements.txt(Python 3.11+)

\- 数据库：无(用 JSON 文件 + 浏览器用户目录持久化)

&#x20;   - config.json —— 运行时配置

&#x20;   - rules.json —— 角色弹幕知识库(22 个角色)

&#x20;   - personas/<name>.md —— 角色高级提示词覆盖

&#x20;   - browser\_data/ —— Playwright 登录态(sessionid cookie)

&#x20;   - screenshots/ —— 异常截图存档

&#x20;   - .stop\_flag —— 运行时停止标记文件

\## 编码规范

&#x20; - 缩进:4 空格(PEP 8)

&#x20; - 命名:

&#x20;   - 函数/变量:snake\_case(如 extract\_room\_id、\_get\_next\_msg)

&#x20;   - 类:PascalCase(如 App 已在 ui.py)

&#x20;   - 常量:UPPER\_SNAKE\_CASE(如 DEFAULT\_TYPING\_STYLE、RULES\_FILE)

&#x20;   - 模块:全小写(llm\_engine.py、humanized\_input.py)

&#x20;   - 私有函数/变量:下划线前缀(\_parse\_json\_response、\_inject\_char)

&#x20; - 注释:

&#x20;   - 关键逻辑加中文注释(简明,不冗余)

&#x20;   - 分区用「══════════════════════════════════════════════」分隔符(如 douyin\_interact.py)

&#x20;   - 模块顶部 docstring 说明用途 / 用法 / 版本里程碑(M1/M2/M3/M4/M5)

&#x20; - 接口:函数式 + 模块化分层,跨模块用显式 import + 简单 dict 配置(llm\_config / config)

&#x20; - 提交:git commit 信息简短(feat/chore/sync/init 前缀),无强制 Co-Authored-By 标签;当前 main 分支



\## 项目规则

&#x20; 1. 单账号模式:固定使用 personas\[0],无角色轮换(v2.0 重构后)

&#x20; 2. 运行模式分层:

&#x20;   - llm\_enabled=false → 完全走 v2 静态路径(\_get\_next\_msg)

&#x20;   - llm\_enabled=true → 掷骰子 response\_tendency → think() → 失败降级 fallback\_pick

&#x20; 3. 三层降级链:LLM 异常 → fallback\_pick 随机 → messages 池为空 → 静默

&#x20; 4. 弹幕策略:

&#x20;   - 循环:顺序消费 + 防连续重复

&#x20;   - 随机:shuffle 后顺序消费,耗尽再 shuffle

&#x20; 5. 拟人输入(M3):jieba 分词 → 词间 50\~200ms → 标点 30% 概率 0.5\~1.5s 长停;slow / normal / fast 三档 typing\_style

&#x20; 6. React 输入框兼容:不直接 fill(),逐字 createTextNode + range.insertNode + InputEvent('input') 注入;Enter 派发到

&#x20; document(事件委托)

&#x20; 7. 定时发送抖动:send\_interval \* uniform(-0.3, 0.3),最小 5s,分段睡眠(0.5s/段)响应 .stop\_flag

&#x20; 8. PyInstaller 打包兼容:

&#x20;   - sys.frozen 检测打包环境

&#x20;   - sys.stdout.reconfigure 必须加 and sys.stdout 保护(--windowed 模式下 stdout 为 None)

&#x20;   - PROJECT\_DIR 打包后用 Path(sys.executable).parent,首次运行从 \_MEIPASS 复制默认配置

&#x20;   - PLAYWRIGHT\_BROWSERS\_PATH 指向 sys.\_MEIPASS/playwright\_browsers

&#x20; 9. 路径优先级:运行目录(PROJECT\_DIR,可编辑) > \_MEIPASS(内置只读) > 脚本目录(开发)

&#x20; 10. GUI 子进程:subprocess.Popen(ui.py → douyin\_interact.py),必须加 -u 禁用 stdout 缓冲,否则 UI 日志不刷新

&#x20; 11. 登录态检测:检查 cookies 是否有 sessionid,无则提示扫码登录

&#x20; 12. 停止机制:GUI 写 .stop\_flag → 主循环检测 → ctx.close() + 删除标记文件





\## 沟通要求

&#x20; - 全程中文,先给方案再解释

&#x20; - 代码示例完整可运行,避免残缺片段

&#x20; - 修改文件时给出绝对完整路径(如 C:\\Users\\zhenx\\Desktop\\DOUYIN-LHS\\llm\_engine.py)

&#x20; - 解释技术概念通俗,避免不必要术语

&#x20; - 回答结构清晰、分点说明、重点突出

&#x20; - 不编造信息,不确定的内容明确说明

&#x20; - 不使用多余格式,保持干净易读

