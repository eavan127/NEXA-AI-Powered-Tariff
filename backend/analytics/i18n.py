"""
i18n.py — multilingual support for the NEXA chatbox.

Only the three languages relevant to Jabil's Malaysia operation are
hand-translated: English, Bahasa Malaysia, Mandarin (Simplified). These
are real template strings, not LLM-generated translations — the
deterministic numeric summary (which contains figures) must never be
machine-translated, because a small local model could silently corrupt a
number while "translating" prose around it. Only qwen's framing intro
sentence (which is forbidden from containing digits — see
chat_analytics._qwen_intro) is actually LLM-generated per language.

Known limitation: `langdetect` has no dedicated Bahasa Malaysia language
profile (Malay and Indonesian are extremely close), so Malay text is
classified as Indonesian ("id") and mapped to "ms" here.
"""
from langdetect import detect, LangDetectException

SUPPORTED = ("en", "ms", "zh")

_LANGDETECT_MAP = {
    "id": "ms",     # langdetect lacks a Malay profile; Indonesian is the closest match
    "ms": "ms",
    "zh-cn": "zh",
    "zh-tw": "zh",
}


def detect_language(text: str) -> str:
    try:
        code = detect(text or "")
    except LangDetectException:
        return "en"
    mapped = _LANGDETECT_MAP.get(code, code)
    return mapped if mapped in SUPPORTED else "en"


PERIOD_LABEL = {
    "en": {"today": "today", "week": "the last 7 days", "month": "the last 30 days", "all": "all time"},
    "ms": {"today": "hari ini", "week": "7 hari lepas", "month": "30 hari lepas", "all": "sepanjang masa"},
    "zh": {"today": "今天", "week": "过去7天", "month": "过去30天", "all": "所有时间"},
}

TREND_LABEL = {
    "en": {"increasing": "increasing", "decreasing": "decreasing", "roughly flat": "roughly flat"},
    "ms": {"increasing": "meningkat", "decreasing": "menurun", "roughly flat": "agak mendatar"},
    "zh": {"increasing": "上升", "decreasing": "下降", "roughly flat": "大致平稳"},
}

T = {
    "en": {
        "savings_no_data": (
            "No landed-cost records found for {period}. NEXA tracks duty savings, not "
            "\"profit\" — this is a cost-avoidance tool, not a revenue system."
        ),
        "savings_summary": (
            "NEXA doesn't store \"profit\" — it's a cost-avoidance tool, so the closest metric "
            "is FTA duty savings. For {period}: {total} saved across {count} shipment(s). "
            "Mean {mean} · Median {median} · Mode {mode} per shipment."
        ),
        "cost_no_data": "No landed-cost records found for {period}.",
        "cost_summary": (
            "Total landed cost for {period}: {total} across {count} shipment(s). "
            "Mean {mean} · Median {median} · Mode {mode} per shipment."
        ),
        "forecast_insufficient": (
            "Not enough historical data yet for a forecast (need at least 2 days with "
            "recorded savings). NEXA also doesn't track \"profit\" — the closest metric is "
            "FTA duty savings."
        ),
        "forecast_summary": (
            "NEXA doesn't track \"profit\" — this is a projection of FTA duty savings, not "
            "revenue. Based on a linear trend over the last {count} day(s) of data ({trend}), "
            "projected savings for the next {horizon} days: {predicted}. This is a simple "
            "trendline extrapolation, not a predictive model — treat it as directional, not "
            "a committed forecast."
        ),
        "fallback": (
            "I can answer questions about FTA duty savings, landed cost, or a savings "
            "forecast — try \"what's our savings today\", \"show cost this month\", or "
            "\"predict next week's savings\". NEXA doesn't track \"profit\" directly since "
            "it's a cost-avoidance tool, not a revenue P&L."
        ),
        "citation_internal": "Internal: {count} record(s) from `{table}`, dated {start} to {end} (Supabase, queried live).",
        "citation_external": "External: {fta} rate schedule — {url}{page}",
        "citation_forecast": (
            "Internal: linear regression (numpy.polyfit) over `landed_costs.fta_saving_usd`, "
            "grouped by day, computed live from Supabase."
        ),
        "sources_label": "Sources",
        "chart_savings_title": "FTA Savings by Day (USD)",
        "chart_cost_title": "Landed Cost by Day (USD)",
        "chart_forecast_title": "Savings Forecast (USD)",
        "legend_actual": "Actual",
        "legend_forecast": "Forecast (linear trend)",
    },
    "ms": {
        "savings_no_data": (
            "Tiada rekod kos pendaratan dijumpai untuk {period}. NEXA menjejaki penjimatan "
            "duti, bukan \"keuntungan\" — ini adalah alat pengelakan kos, bukan sistem hasil."
        ),
        "savings_summary": (
            "NEXA tidak menyimpan data \"keuntungan\" — ia adalah alat pengelakan kos, jadi "
            "metrik paling hampir ialah penjimatan duti FTA. Bagi {period}: {total} dijimat "
            "merentasi {count} penghantaran. Min {mean} · Median {median} · Mod {mode} setiap penghantaran."
        ),
        "cost_no_data": "Tiada rekod kos pendaratan dijumpai untuk {period}.",
        "cost_summary": (
            "Jumlah kos pendaratan untuk {period}: {total} merentasi {count} penghantaran. "
            "Min {mean} · Median {median} · Mod {mode} setiap penghantaran."
        ),
        "forecast_insufficient": (
            "Data sejarah tidak mencukupi lagi untuk ramalan (memerlukan sekurang-kurangnya "
            "2 hari data penjimatan direkodkan). NEXA juga tidak menjejaki \"keuntungan\" — "
            "metrik paling hampir ialah penjimatan duti FTA."
        ),
        "forecast_summary": (
            "NEXA tidak menjejaki \"keuntungan\" — ini adalah unjuran penjimatan duti FTA, "
            "bukan hasil. Berdasarkan trend linear sepanjang {count} hari data lepas "
            "({trend}), unjuran penjimatan untuk {horizon} hari akan datang: {predicted}. Ini "
            "adalah ekstrapolasi trend ringkas, bukan model ramalan — anggap sebagai panduan "
            "arah, bukan komitmen muktamad."
        ),
        "fallback": (
            "Saya boleh menjawab soalan tentang penjimatan duti FTA, kos pendaratan, atau "
            "ramalan penjimatan — cuba \"apa penjimatan kita hari ini\", \"tunjukkan kos "
            "bulan ini\", atau \"ramalkan penjimatan minggu depan\". NEXA tidak menjejaki "
            "\"keuntungan\" secara langsung kerana ia adalah alat pengelakan kos, bukan P&L hasil."
        ),
        "citation_internal": "Dalaman: {count} rekod daripada `{table}`, bertarikh {start} hingga {end} (Supabase, disoal secara langsung).",
        "citation_external": "Luaran: jadual kadar {fta} — {url}{page}",
        "citation_forecast": (
            "Dalaman: regresi linear (numpy.polyfit) ke atas `landed_costs.fta_saving_usd`, "
            "dikumpulkan mengikut hari, dikira secara langsung daripada Supabase."
        ),
        "sources_label": "Sumber",
        "chart_savings_title": "Penjimatan Duti FTA Mengikut Hari (USD)",
        "chart_cost_title": "Kos Pendaratan Mengikut Hari (USD)",
        "chart_forecast_title": "Ramalan Penjimatan (USD)",
        "legend_actual": "Sebenar",
        "legend_forecast": "Ramalan (trend linear)",
    },
    "zh": {
        "savings_no_data": (
            "未找到{period}的到岸成本记录。NEXA 追踪的是关税节省，而非\"利润\"——这是一个"
            "成本规避工具，不是营收系统。"
        ),
        "savings_summary": (
            "NEXA 不存储\"利润\"数据——这是一个成本规避工具，因此最接近的指标是 FTA 关税"
            "节省。{period}：共 {count} 笔货运节省 {total}。平均值 {mean} · 中位数 {median} "
            "· 众数 {mode}（每笔货运）。"
        ),
        "cost_no_data": "未找到{period}的到岸成本记录。",
        "cost_summary": (
            "{period}的总到岸成本：{count} 笔货运共计 {total}。平均值 {mean} · 中位数 "
            "{median} · 众数 {mode}（每笔货运）。"
        ),
        "forecast_insufficient": (
            "历史数据尚不足以进行预测（需要至少2天的节省记录）。NEXA 同样不追踪\"利润\""
            "——最接近的指标是 FTA 关税节省。"
        ),
        "forecast_summary": (
            "NEXA 不追踪\"利润\"——这是 FTA 关税节省的预测，而非营收预测。根据过去 {count} "
            "天数据的线性趋势（{trend}），未来 {horizon} 天的预计节省额为 {predicted}。这只"
            "是简单的趋势线外推，并非预测模型——请将其视为方向性参考，而非确定的预测。"
        ),
        "fallback": (
            "我可以回答有关 FTA 关税节省、到岸成本或节省预测的问题——可以试着问\"我们今天"
            "的节省是多少\"、\"显示本月成本\"或\"预测下周的节省\"。NEXA 不直接追踪\"利润\""
            "，因为这是一个成本规避工具，不是营收损益表。"
        ),
        "citation_internal": "内部来源：来自 `{table}` 的 {count} 条记录，日期为 {start} 至 {end}（实时查询自 Supabase）。",
        "citation_external": "外部来源：{fta} 税率表 — {url}{page}",
        "citation_forecast": (
            "内部来源：基于 `landed_costs.fta_saving_usd` 按天分组的线性回归（numpy.polyfit），"
            "实时计算自 Supabase。"
        ),
        "sources_label": "来源",
        "chart_savings_title": "每日FTA节省金额（美元）",
        "chart_cost_title": "每日到岸成本（美元）",
        "chart_forecast_title": "节省预测（美元）",
        "legend_actual": "实际",
        "legend_forecast": "预测（线性趋势）",
    },
}


def t(lang: str, key: str) -> str:
    lang = lang if lang in T else "en"
    return T[lang].get(key, T["en"][key])
