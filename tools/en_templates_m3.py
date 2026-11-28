# -*- coding: utf-8 -*-
"""M3 补充的带插值文案模板：zh 正则（命名组）→ en 模板（{组名}）。

用途：页面里很多「说明 · 范围 a – b · 默认 c」「20 种鱼」「吃 A 等 6 种」这类
由 JS 拼起来的整句，单一中文原文对不上，只能按形状匹配。整句匹配才替换，
所以不会碰到玩家名、日志正文这类数据。
"""

TEMPLATES_M3 = [
    # 参数提示的元信息段（页面里以 " · " 拼在说明后面）
    (r"^范围 (?P<a>\S+) – (?P<b>.+)$", "range {a} – {b}"),
    (r"^默认 (?P<v>.+)$", "default {v}"),
    (r"^(?P<v>[\d.]+) 倍$", "{v}×"),
    (r"^最长 (?P<v>.+)$", "max {v}"),
    (r"^固定 (?P<v>.+)$", "fixed {v}"),
    (r"^先显示 (?P<n>.+)$", "showing first {n}"),
    (r"^本地 (?P<v>.+)$", "local {v}"),
    (r"^(?P<n>[\d.]+) (?P<u>秒|分钟|小时|米|克|件|条|项|封|个)$", "{n} {u}"),
    (r"^(?P<v>[\d.]+) %/秒$", "{v} %/s"),
    (r"^本次查询显示 (?P<a>[\d.]+) / (?P<b>[\d.]+) 件$", "Showing {a} of {b} items"),
    (r"^(?P<a>[\d.]+) 银 / (?P<b>[\d.]+) 金 / (?P<c>[\d.]+) 件$", "{a} silver / {b} gold / {c} pcs"),
    (r"^(?P<a>[\d.]+) 银 / (?P<b>[\d.]+) 金$", "{a} silver / {b} gold"),

    # 数值 + 量词
    (r"^(?P<n>[\d.]+) (?P<u>秒|轮|件|个|种|条|项|封|米|克|小时|分钟)$", "{n} {u}"),
    (r"^(?P<n>[\d.]+) 种鱼$", "{n} species"),
    (r"^(?P<n>[\d.]+) 个格子$", "{n} cells"),
    (r"^(?P<n>[\d.]+) 个型号$", "{n} models"),
    (r"^(?P<n>[\d.]+) 种鱼 · 仅影响此水域$", "{n} species · this water only"),
    (r"^启用全部 (?P<n>[\d.]+) 种$", "Enable all {n}"),
    (r"^停用全部 (?P<n>[\d.]+) 种$", "Disable all {n}"),
    (r"^共 (?P<n>[\d.]+) 条$", "{n} rows"),
    (r"^第 (?P<n>[\d.]+) 组$", "Group {n}"),
    (r"^已填入 (?P<n>[\d.]+) 个空白阶段。$", "Filled in {n} blank stages."),
    (r"^店铺列表（(?P<n>[\d.]+) 家）$", "Shop list ({n})"),
    (r"^找到 (?P<n>[\d.]+) 个$", "Found {n}"),
    (r"^间隔 (?P<n>[\d.]+) 秒$", "Every {n} s"),
    (r"^阶段 (?P<n>[\d.]+)$", "Stage {n}"),
    (r"^（(?P<n>[\d.]+) 项，一般不用改）$", "({n} items, usually left alone)"),

    # 拼在标题后面的括号计数
    (r"^(?P<h>.+) （(?P<n>[\d.]+) 项，一般不用改）$", "{h} ({n} items, usually left alone)"),
    (r"^(?P<h>.+)（(?P<n>[\d.]+) 项，一般不用改）$", "{h} ({n} items, usually left alone)"),

    # 鱼饵偏好的摘要句
    (r"^吃 (?P<a>.+?) 等 (?P<n>[\d.]+) 种$", "Eats {a} and others ({n} in total)"),
    (r"^吃 (?P<a>.+)$", "Eats {a}"),
    (r"^不吃 (?P<a>.+)$", "Does not eat {a}"),
    (r"^（现在：(?P<v>.+)）$", "(now {v})"),
    (r"^（现在：(?P<v>.+)）", "(now {v})"),

    # 邮箱收件人
    (r"^收件人：\s*(?P<v>.+)$", "Recipient: {v}"),

    # 玩法预设摘要
    (r"^当前预设：(?P<v>.+?)。预设覆盖前六项；欢乐时光独立。$",
     "Current preset: {v}. A preset covers the first six rules; happy hour is separate."),

    # 区域/地图摘要
    (r"^圆形，半径 (?P<r>[\d.]+) 米$", "Circle, radius {r} m"),
    (r"^圆形，半径 (?P<r>[\d.]+) 米，圆心在 (?P<c>.+)$", "Circle, radius {r} m, centre at {c}"),
    (r"^(?P<a>[\d.]+)×(?P<b>[\d.]+) 米$", "{a}×{b} m"),
    (r"^(?P<a>[\d.]+)×(?P<b>[\d.]+) 米，游戏坐标 (?P<c>.+) · 松开完成$",
     "{a}×{b} m, game coords {c} · release to finish"),
    (r"^已划鱼群区域：(?P<n>[\d.]+) 个。$", "Shoal zones drawn: {n}."),
    (r"^(?P<span>.+?) g 以下$", "under {span} g"),

    # 邮件/活动
    (r"^已切换到「(?P<t>.+)」，最多 30 秒生效$", "Switched to \"{t}\"; takes effect within 30 seconds"),
    (r"^已切换到「(?P<t>.+)」，约 30 秒内生效$", "Switched to \"{t}\"; takes effect within about 30 seconds"),
    (r"^已保存「(?P<s>.+)」，在线玩家立即收到刷新$", "Saved \"{s}\"; online players refresh immediately"),
    (r"^已加入「(?P<s>.+)」，记得保存$", "Added \"{s}\" — remember to save"),
    (r"^封禁「(?P<p>.+)」？$", "Ban \"{p}\"?"),
    (r"^恢复「(?P<i>.+)」的整件覆盖？$", "Restore the whole-item override for \"{i}\"?"),
    (r"^找不到店铺：(?P<id>.+)$", "Shop not found: {id}"),
    (r"^(?P<id>.+)（当前编辑，不在所选水.+$", "{id} (currently editing, not in the selected water list)"),
    (r"^已确认保存：(?P<a>.+?)；待重试：(?P<b>.+?)。(?P<e>.*)$",
     "Saved: {a}; retrying: {b}. {e}"),
    (r"^预设读取失败，草稿未变：(?P<e>.+)$", "Could not read the preset; the draft is unchanged: {e}"),
    (r"^(?P<n>[\d.]+) 封$", "{n} mails"),

    # 报错串
    (r"^请求失败（HTTP (?P<code>[\d.]+)）$", "Request failed (HTTP {code})"),
]