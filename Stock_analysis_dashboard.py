import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate
import plotly.graph_objects as go
import plotly.express as px
import math
import numpy as np
import io
import os

# 小工具：將 Hex 轉為 RGBA（用於雷達圖填色）
def hex_to_rgba(hex_color: str, alpha: float) -> str:
    try:
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    except Exception:
        return "rgba(31,119,180,0.25)"


# 產生「漂亮」刻度：回傳 (tick_min, tick_max, ticks_list)
def nice_ticks(vmin: float, vmax: float, nticks: int = 6):
    try:
        if not (isinstance(vmin, (int, float)) and isinstance(vmax, (int, float))):
            raise ValueError("vmin/vmax must be numbers")
        if not math.isfinite(vmin) or not math.isfinite(vmax):
            vmin, vmax = 0.0, 1.0
        if vmin == vmax:
            eps = 1.0 if vmin == 0 else abs(vmin) * 0.05
            vmin, vmax = vmin - eps, vmax + eps

        span = abs(vmax - vmin)
        N = max(nticks - 1, 1)
        raw = span / N
        magnitude = 10 ** math.floor(math.log10(raw))
        nice_steps = [1, 2, 2.5, 5, 10]
        step = nice_steps[-1] * magnitude
        for nice in nice_steps:
            cand = nice * magnitude
            if raw <= cand:
                step = cand
                break

        tick_min = math.floor(vmin / step) * step
        tick_max = tick_min + N * step
        if tick_max < vmax:
            shift = math.ceil((vmax - tick_max) / step)
            tick_min += shift * step
            tick_max = tick_min + N * step

        ticks = [tick_min + i * step for i in range(nticks)]

        def _round(v):
            if step == 0:
                return v
            dec = max(0, -int(math.floor(math.log10(abs(step)))) + 2)
            return round(v, dec)

        tick_min = _round(tick_min)
        tick_max = _round(tick_max)
        ticks = [_round(t) for t in ticks]
        return tick_min, tick_max, ticks
    except Exception:
        a, b = float(vmin), float(vmax)
        if a == b:
            a, b = a - 1.0, b + 1.0
        step = (b - a) / (nticks - 1)
        ticks = [a + i * step for i in range(nticks)]
        return a, b, ticks

# 嘗試註冊可顯示中文字體（Windows 常見字體）
def build_pdf_report(all_details: dict, summary_df: pd.DataFrame) -> bytes:
    # 將 reportlab 的 import 放在函數內，避免環境未安裝時造成全域匯入錯誤
    try:
        import importlib
        A4 = importlib.import_module('reportlab.lib.pagesizes').A4
        colors = importlib.import_module('reportlab.lib.colors')
        styles_mod = importlib.import_module('reportlab.lib.styles')
        getSampleStyleSheet = styles_mod.getSampleStyleSheet
        ParagraphStyle = styles_mod.ParagraphStyle
        pdfmetrics = importlib.import_module('reportlab.pdfbase.pdfmetrics')
        TTFont = importlib.import_module('reportlab.pdfbase.ttfonts').TTFont
        platypus = importlib.import_module('reportlab.platypus')
        SimpleDocTemplate = platypus.SimpleDocTemplate
        Paragraph = platypus.Paragraph
        Spacer = platypus.Spacer
        Table = platypus.Table
        TableStyle = platypus.TableStyle
    except Exception as e:
        raise RuntimeError("reportlab 未安裝，無法生成 PDF") from e

    def _register_cjk_font() -> str:
        candidates = [
            ("MSJH", r"C:\\Windows\\Fonts\\msjh.ttc"),  # 微軟正黑體
            ("MSYH", r"C:\\Windows\\Fonts\\msyh.ttc"),  # 微軵雅黑體
            ("MINGLIU", r"C:\\Windows\\Fonts\\mingliu.ttc"),  # 細明體
            ("SIMSUN", r"C:\\Windows\\Fonts\\simsun.ttc"),  # 宋體
        ]
        for name, path in candidates:
            try:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont(name, path))
                    return name
            except Exception:
                continue
        return "Helvetica"
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    font_name = _register_cjk_font()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCJK", parent=styles["Title"], fontName=font_name))
    styles.add(ParagraphStyle(name="BodyCJK", parent=styles["BodyText"], fontName=font_name, leading=14))
    styles.add(ParagraphStyle(name="HeadingCJK", parent=styles["Heading2"], fontName=font_name))

    story = []
    story.append(Paragraph("股票分析報告", styles["TitleCJK"]))
    story.append(Paragraph(pd.Timestamp.now().strftime("分析日期：%Y-%m-%d"), styles["BodyCJK"]))
    story.append(Paragraph("分析標的：" + ", ".join(all_details.keys()), styles["BodyCJK"]))
    story.append(Spacer(1, 12))

    # 綜合評分表
    story.append(Paragraph("綜合評分比較", styles["HeadingCJK"]))
    if not summary_df.empty:
        table_data = [list(summary_df.columns)] + summary_df.astype(str).values.tolist()
        tbl = Table(table_data, hAlign='LEFT')
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.gray),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey])
        ]))
        story.append(tbl)
    story.append(Spacer(1, 12))

    # 個股詳情
    story.append(Paragraph("個股詳細分析", styles["HeadingCJK"]))
    for symbol, data in all_details.items():
        story.append(Spacer(1, 6))
        story.append(Paragraph(symbol, styles["HeadingCJK"]))
        story.append(Paragraph(f"總分：{data['total_score']} / 20", styles["BodyCJK"]))
        story.append(Paragraph(f"投資建議：{data['suggestion']}", styles["BodyCJK"]))
        story.append(Paragraph(f"股組類型：{data['mode']}", styles["BodyCJK"]))
        # details now includes basis column
        df = pd.DataFrame(data["details"], columns=["指標", "口徑", "數值", "評級", "解釋"])
        table_data = [list(df.columns)] + df.astype(str).values.tolist()
        tbl = Table(table_data, hAlign='LEFT', colWidths=[60, 40, 60, 40, None])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.gray),
        ]))
        story.append(tbl)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ====== 股票分析函數 ======
def analyze_stock(ticker):
    stock = yf.Ticker(ticker)

    # 抓年度財報與資產負債表
    fin = stock.financials  # annual income statement
    bs = stock.balance_sheet  # annual balance sheet

    def _get_last_close() -> float | None:
        try:
            h = stock.history(period="5d", interval="1d", auto_adjust=True)
            if not h.empty:
                return float(h["Close"].dropna().iloc[-1])
        except Exception:
            pass
        return None

    def _pick(df: pd.DataFrame, candidates: list[str]):
        if df is None or df.empty:
            return None, None
        col = df.columns.max() if len(df.columns) else None
        if col is None:
            return None, None
        for name in candidates:
            if name in df.index:
                try:
                    return float(df.loc[name, col]), col
                except Exception:
                    continue
        return None, col

    # 取最近年度數據
    net_income, fin_col = _pick(fin, [
        "Net Income",
        "Net Income Common Stockholders",
    ])
    total_revenue, _ = _pick(fin, [
        "Total Revenue",
        "Revenue",
    ])
    equity_curr, bs_col = _pick(bs, [
        "Total Stockholder Equity",
        "Total Stockholders Equity",
        "Total Equity Gross Minority Interest",
    ])
    # 前一年股東權益（用來計算平均權益）
    equity_prev = None
    try:
        if bs is not None and not bs.empty and bs_col in bs.columns:
            prev_idx = list(bs.columns).index(bs_col) - 1
            if prev_idx >= 0:
                for name in [
                    "Total Stockholder Equity",
                    "Total Stockholders Equity",
                    "Total Equity Gross Minority Interest",
                ]:
                    if name in bs.index:
                        equity_prev = float(bs.iloc[bs.index.get_loc(name), prev_idx])
                        break
    except Exception:
        equity_prev = None

    # 股數與基本資訊（優先用 info，若無再嘗試財報中的 Shares）
    shares_outstanding = None
    info = {}
    try:
        info = stock.info or {}
        shares_outstanding = info.get("sharesOutstanding")
    except Exception:
        shares_outstanding = None
    if not shares_outstanding and fin is not None and not fin.empty:
        for cand in [
            "Basic Average Shares",
            "Diluted Average Shares",
            "Weighted Average Shares",
        ]:
            v, _ = _pick(fin, [cand])
            if v:
                shares_outstanding = v
                break

    price = _get_last_close()
    price_currency = (info or {}).get("currency")
    financial_currency = (info or {}).get("financialCurrency")

    # 統一年度化計算
    # EPS 優先使用 Yahoo 提供之 trailingEps（與價格同幣別，避免 ADR/幣別不一致）
    eps = None
    eps_source = None  # 'TTM' (trailingEps), 'NTM' (forwardEps), or 'FY' (derived annual)
    try:
        teps = info.get("trailingEps")
        if isinstance(teps, (int, float)) and math.isfinite(teps):
            eps = float(teps)
            eps_source = "TTM"
        else:
            feps = info.get("forwardEps")
            if isinstance(feps, (int, float)) and math.isfinite(feps):
                eps = float(feps)
                eps_source = "NTM"
    except Exception:
        pass
    # 後備：用年度淨利/流通股數（幣別=財報幣別；後續計算 P/E 時需注意幣別不一致）
    if eps is None and net_income is not None and shares_outstanding:
        try:
            eps = float(net_income) / float(shares_outstanding)
            eps_source = "FY"
        except Exception:
            eps = None

    # 平均權益（若缺前一年，退回當年）
    avg_equity = None
    try:
        if equity_curr is not None:
            if equity_prev is not None:
                avg_equity = (float(equity_curr) + float(equity_prev)) / 2.0
            else:
                avg_equity = float(equity_curr)
    except Exception:
        avg_equity = None

    roe = None
    try:
        if net_income is not None and avg_equity and avg_equity != 0:
            roe = float(net_income) / float(avg_equity)
    except Exception:
        roe = None

    # 每股淨值：優先用最近季 (MRQ) 權益；退回最近年度 (FY)
    bvps = None
    bvps_basis = None  # 'MRQ' or 'FY'
    try:
        equity_mrq = None
        try:
            qbs = stock.quarterly_balance_sheet if hasattr(stock, 'quarterly_balance_sheet') else pd.DataFrame()
        except Exception:
            qbs = pd.DataFrame()
        if qbs is not None and not qbs.empty:
            # 取最近一季的股東權益
            cand_idx = None
            for name in [
                "Total Stockholder Equity",
                "Total Stockholders Equity",
                "Total Equity Gross Minority Interest",
            ]:
                if name in qbs.index:
                    cand_idx = name
                    break
            if cand_idx is not None and len(qbs.columns) > 0:
                try:
                    col = qbs.columns.max()
                except Exception:
                    col = qbs.columns[0]
                try:
                    equity_mrq = float(qbs.loc[cand_idx, col])
                except Exception:
                    equity_mrq = None
        if equity_mrq is not None and shares_outstanding:
            bvps = float(equity_mrq) / float(shares_outstanding)
            bvps_basis = "MRQ"
        elif equity_curr is not None and shares_outstanding:
            bvps = float(equity_curr) / float(shares_outstanding)
            bvps_basis = "FY"
    except Exception:
        bvps = None
        bvps_basis = None

    pb = None
    try:
        if price is not None and bvps and bvps > 0:
            pb = float(price) / float(bvps)
    except Exception:
        pb = None

    pe = None
    pe_basis = None  # 'TTM' | 'NTM' | 'FY'
    try:
        if price is not None and eps and eps != 0:
            # 若 EPS 來自 trailingEps/forwardEps，幣別與價格一致；否則需幣別相同才計算
            if eps_source in {"TTM", "NTM"} or (price_currency and financial_currency and price_currency == financial_currency):
                pe = float(price) / float(eps)
                pe_basis = eps_source if eps_source in {"TTM", "NTM"} else "FY"
            else:
                pe = None
    except Exception:
        pe = None
        pe_basis = None

    profit_margin = None
    try:
        if net_income is not None and total_revenue and total_revenue != 0:
            profit_margin = float(net_income) / float(total_revenue)
    except Exception:
        profit_margin = None

    # 股型分類（簡單啟發式）
    # 來源：以 P/E、P/B、EPS 三項當期年度化指標粗略判斷
    # - VALUE：P/E < 20、P/B < 2、EPS > 3（符合 ≥2 項）
    # - GROWTH：P/E > 40、P/B > 4、EPS < 1（符合 ≥2 項）
    # 其餘視為 MIX。
    # 註：僅供快速篩選，非嚴謹財務定義；可依需求調整閾值。
    value_score = sum([pe is not None and pe < 20, pb is not None and pb < 2, eps is not None and eps > 3])
    growth_score = sum([pe is not None and pe > 40, pb is not None and pb > 4, eps is not None and eps < 1])

    if value_score >= 2:
        mode = "VALUE"
    elif growth_score >= 2:
        mode = "GROWTH"
    else:
        mode = "MIX"

    # 評分函數
    def score_eps(val):
        if val is None: return "N/A", None
        if val < 0: return "F", 0
        if val > 3: return "A", 4
        elif val > 2: return "B", 3
        elif val > 1: return "C", 2
        else: return "D", 1
    def score_roe(val):
        if val is None: return "N/A", None
        if val < 0: return "F", 0
        if val > 0.2: return "A", 4
        elif val > 0.15: return "B", 3
        elif val > 0.1: return "C", 2
        else: return "D", 1
    def score_pe(val):
        if val is None: return "N/A", None
        if val <= 0: return "F", 0
        if mode == "GROWTH":
            if val < 60: return "A", 4
            elif val < 80: return "B", 3
            elif val < 100: return "C", 2
            else: return "D", 1
        else:
            if val < 10: return "A", 4
            elif val < 20: return "B", 3
            elif val < 40: return "C", 2
            elif val < 60: return "D", 1
            else: return "F", 0
    def score_pb(val):
        if val is None: return "N/A", None
        if val <= 0: return "F", 0
        if val < 1: return "A", 4
        elif val < 2: return "B", 3
        elif val < 3: return "C", 2
        elif val < 5: return "D", 1
        else: return "F", 0
    def score_profit_margin(val):
        if val is None: return "N/A", None
        if val < 0: return "F", 0
        if val > 0.2: return "A", 4
        elif val > 0.1: return "B", 3
        elif val > 0.05: return "C", 2
        else: return "D", 1

    # 格式化
    def fmt(val):
        return f"{val:.2f}" if isinstance(val, (int, float)) else str(val)

    def explain(name, val, grade, mode, basis):
        if val is None:
            return ""
        if name == "EPS":
            if basis == "TTM":
                return f"EPS (TTM) ≈ {val:.2f}（來源: Yahoo trailingEps；與股價同幣別）"
            if basis == "NTM":
                return f"EPS (NTM) ≈ {val:.2f}（來源: Yahoo forwardEps；未來12個月預估）"
            # FY
            src = "年度淨利/流通股數"
            if price_currency and financial_currency and price_currency != financial_currency:
                src += "；幣別與股價不同，P/E 為避免誤差可能不計"
            return f"EPS (FY) ≈ {val:.2f}（{src}）"
        if name == "ROE":
            return f"ROE (FY) ≈ {val:.2%}（年度淨利/平均權益）"
        if name == "P/E":
            tag = basis or "—"
            label = {"TTM": "Trailing", "NTM": "Forward", "FY": "FY"}.get(tag, tag)
            return f"{label} P/E ({tag}) ≈ {val:.2f}（股價/對應口徑 EPS）"
        if name == "P/B":
            tag = basis or "—"
            return f"P/B ({tag}) ≈ {val:.2f}（股價/每股淨值）"
        if name == "淨利率":
            return f"淨利率 (FY) ≈ {val:.2%}（年度淨利/年度營收）"
        return ""

    # 評分表
    details = []
    scores = {}
    basis_map = {
        "EPS": eps_source or "FY",
        "ROE": "FY",
        "P/E": pe_basis or (eps_source or "FY"),
        "P/B": bvps_basis or "FY",
        "淨利率": "FY",
    }
    for name, val, func in [
        ("EPS", eps, score_eps),
        ("ROE", roe, score_roe),
        ("P/E", pe, score_pe),
        ("P/B", pb, score_pb),
        ("淨利率", profit_margin, score_profit_margin)
    ]:
        grade, score = func(val)
        scores[name] = score
        explanation = explain(name, val, grade, mode, basis_map.get(name))
        details.append([name, basis_map.get(name), fmt(val), grade, explanation])

    # 總分（0~20）：直接加總五項（每項 0~4）
    valid_scores = [v for v in scores.values() if v is not None]
    total_score = int(sum(valid_scores)) if valid_scores else 0
    if total_score >= 14:
        suggestion = "🟢 強烈買進"
    elif total_score >= 11:
        suggestion = "🟡 買進"
    elif total_score >= 7:
        suggestion = "🟠 待觀察"
    elif total_score >= 4:
        suggestion = "🔴 賣出"
    else:
        suggestion = "🚨 強烈賣出"

    return details, total_score, suggestion, mode, stock, scores

# ====== Streamlit 主介面 ======
st.set_page_config(page_title="股票分析儀表板", layout="wide", page_icon="📊")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.75rem; padding-bottom: 1rem; max-width: 1400px;}
    section.main > div {padding-top: 1rem;}
    /* Reduce main title size a bit to avoid clipping on some displays */
    .stApp h1 {font-size: 1.85rem; line-height: 1.2;}
    .stDataFrame {padding-top: 0 !important;}
    div[data-testid="stSidebar"] button {
        text-align: center;
        justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📊 股票分析儀表板")

# Sidebar 輸入
symbols_str = st.sidebar.text_input("股票代碼（逗號分隔）", value="AAPL, MSFT, NVDA")
time_period = st.sidebar.selectbox("查詢期間", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)

symbols = [s.strip().upper() for s in symbols_str.split(',') if s.strip()]
if not symbols:
    st.info("請在左側輸入至少一個股票代碼，例如：AAPL, MSFT")
else:
    # 逐檔分析
    all_details = {}
    for symbol in symbols:
        try:
            details, total_score, suggestion, mode, stock, scores = analyze_stock(symbol)
            all_details[symbol] = {
                "details": details,
                "total_score": total_score,
                "suggestion": suggestion,
                "mode": mode,
                "stock": stock,
                "scores": scores,
            }
        except Exception as e:
            st.error(f"無法分析股票 {symbol}: {e}")

    if not all_details:
        st.warning("分析失敗，請更換股票代碼重試。")
    else:
        # 顏色對映
        tickers = list(all_details.keys())
        palette = px.colors.qualitative.Plotly
        color_map = {sym: palette[i % len(palette)] for i, sym in enumerate(tickers)}

        # ===== 股價走勢（可切換報酬率/價格） =====
        hdr_left, hdr_right = st.columns([5, 3])
        with hdr_right:
            view_mode = st.radio(
                "切換視圖",
                ["報酬率", "價格"],
                horizontal=True,
                label_visibility="collapsed",
                key="price_returns_mode",
            )
        with hdr_left:
            st.subheader("報酬率走勢" if view_mode == "報酬率" else "股價走勢")
        try:
            data = yf.download(tickers, period=time_period, interval="1d", auto_adjust=True, progress=False, group_by='ticker', threads=True)
            if isinstance(data.columns, pd.MultiIndex):
                close_df = pd.concat({sym: data[sym]['Close'] for sym in tickers if sym in data.columns.get_level_values(0)}, axis=1)
            else:
                first = tickers[0]
                close_df = data['Close'].to_frame(first)
            close_df = close_df.dropna(how='any')
            if not isinstance(close_df.index, pd.DatetimeIndex):
                close_df.index = pd.to_datetime(close_df.index)

            ret_df = (close_df / close_df.iloc[0] - 1.0) * 100.0
            px_df = close_df

            # 以資料的實際最高/最低為基準決定報酬率軸範圍（避免被切掉）
            ret_min, ret_max = float(ret_df.min().min()), float(ret_df.max().max())
            rpad = (ret_max - ret_min) * 0.08 if ret_max > ret_min else 1.0
            r0, r1, ret_ticks = nice_ticks(ret_min - rpad, ret_max + rpad, nticks=6)
            ret_range = [r0, r1]

            # 價格軸同理：使用資料的最高/最低
            px_min, px_max = float(px_df.min().min()), float(px_df.max().max())
            ppad = (px_max - px_min) * 0.05 if px_max > px_min else 1.0
            p0, p1, px_ticks = nice_ticks(px_min - ppad, px_max + ppad, nticks=6)
            px_range = [p0, p1]

            fig = go.Figure()

            def add_set(df, is_returns: bool, visible: bool, show_legend: bool):
                for sym in df.columns:
                    series = df[sym].dropna()
                    if len(series) > 1:
                        ht = (f"{sym} : %{{y:.2f}}%<extra></extra>" if is_returns else f"{sym} : $%{{y:.2f}}<extra></extra>") if show_legend else None
                        hinfo = None if show_legend else 'skip'
                        fig.add_trace(go.Scatter(
                            x=series.index, y=series.values, name=sym,
                            mode='lines', connectgaps=True,
                            line=dict(color=color_map.get(sym)),
                            hovertemplate=ht,
                            visible=visible,
                            showlegend=show_legend,
                            hoverinfo=hinfo,
                        ))

            add_set(ret_df, True, True, True)
            add_set(px_df, False, False, False)

            yaxis_init = dict(
                title="變動 (%)",
                ticksuffix="%",
                tickformat=".2f",
                zeroline=True,
                zerolinecolor="#AAAAAA",
                title_standoff=12,
                automargin=False,
                autorange=False,
                fixedrange=True,
                range=ret_range,
                tickmode='array',
                tickvals=ret_ticks,
            )

            n = len(ret_df.columns)
            sym_list = list(ret_df.columns)
            ret_visible = [True]*n + [False]*n
            px_visible  = [False]*n + [True]*n
            ret_hoverinfo  = [None]*n + ['skip']*n
            px_hoverinfo   = ['skip']*n + [None]*n
            ret_legend     = [True]*n + [False]*n
            px_legend      = [False]*n + [True]*n
            ret_templates = [f"{sym} : %{{y:.2f}}%<extra></extra>" for sym in sym_list]
            px_templates  = [f"{sym} : $%{{y:.2f}}<extra></extra>" for sym in sym_list]
            ret_hovertmpl = ret_templates + [None]*n
            px_hovertmpl  = [None]*n + px_templates

            # Apply external toggle to figure instead of in-figure buttons
            show_returns = (view_mode == "報酬率")
            yaxis_cfg = (
                yaxis_init if show_returns else
                {"title": "股價 (USD)", "ticksuffix": "", "tickformat": ".2f", "zeroline": False, "title_standoff": 12, "automargin": False, "autorange": False, "fixedrange": True, "range": px_range, "tickmode": "array", "tickvals": px_ticks}
            )
            fig.update_layout(
                xaxis_title="日期",
                yaxis_title=yaxis_cfg.get("title"),
                legend_title="股票代碼",
                template="plotly_dark",
                hovermode="x unified",
                xaxis=dict(type='date', fixedrange=True),
                yaxis=yaxis_cfg,
                transition=dict(duration=0),
                uirevision="price_returns",
                margin=dict(l=80, r=20, t=40, b=40),
                dragmode='pan'
            )
            vis = ret_visible if show_returns else px_visible
            hoverinfo = ret_hoverinfo if show_returns else px_hoverinfo
            showlegend = ret_legend if show_returns else px_legend
            hovertmpl = ret_hovertmpl if show_returns else px_hovertmpl
            for i in range(len(fig.data)):
                fig.data[i].visible = vis[i]
                fig.data[i].hoverinfo = hoverinfo[i]
                fig.data[i].showlegend = showlegend[i]
                fig.data[i].hovertemplate = hovertmpl[i]
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
        except Exception as e:
            st.warning(f"股價資料批次下載失敗，改用逐一下載。原因: {e}")
            collected = {}
            for symbol in tickers:
                try:
                    stock_obj = yf.Ticker(symbol)
                    price_df = stock_obj.history(period=time_period, interval="1d", auto_adjust=True)
                    if price_df.empty:
                        price_df = yf.download(symbol, period=time_period, interval="1d", auto_adjust=True, progress=False)
                except Exception:
                    price_df = yf.download(symbol, period=time_period, interval="1d", auto_adjust=True, progress=False)
                if not price_df.empty:
                    if not isinstance(price_df.index, pd.DatetimeIndex):
                        price_df.index = pd.to_datetime(price_df.index)
                    collected[symbol] = price_df['Close'].dropna()

            if collected:
                fallback_df = pd.DataFrame(collected).dropna(how='any')
                ret_df = (fallback_df / fallback_df.iloc[0] - 1.0) * 100.0
                px_df = fallback_df

                ret_min, ret_max = float(ret_df.min().min()), float(ret_df.max().max())
                rpad = (ret_max - ret_min) * 0.08 if ret_max > ret_min else 1.0
                r0, r1, ret_ticks = nice_ticks(ret_min - rpad, ret_max + rpad, nticks=6)
                ret_range = [r0, r1]

                px_min, px_max = float(px_df.min().min()), float(px_df.max().max())
                ppad = (px_max - px_min) * 0.05 if px_max > px_min else 1.0
                p0, p1, px_ticks = nice_ticks(px_min - ppad, px_max + ppad, nticks=6)
                px_range = [p0, p1]

                fig = go.Figure()

                def add_set2(df, is_returns: bool, visible: bool, show_legend: bool):
                    for sym in df.columns:
                        series = df[sym].dropna()
                        if len(series) > 1:
                            ht = (f"{sym} : %{{y:.2f}}%<extra></extra>" if is_returns else f"{sym} : $%{{y:.2f}}<extra></extra>") if show_legend else None
                            hinfo = None if show_legend else 'skip'
                            fig.add_trace(go.Scatter(
                                x=series.index, y=series.values, name=sym,
                                mode='lines', connectgaps=True,
                                line=dict(color=color_map.get(sym)),
                                hovertemplate=ht,
                                visible=visible,
                                showlegend=show_legend,
                                hoverinfo=hinfo,
                            ))

                add_set2(ret_df, True, True, True)
                add_set2(px_df, False, False, False)

                yaxis_init = dict(
                    title="變動 (%)",
                    ticksuffix="%",
                    tickformat=".2f",
                    zeroline=True,
                    zerolinecolor="#AAAAAA",
                    title_standoff=12,
                    automargin=False,
                    autorange=False,
                    fixedrange=True,
                    range=ret_range,
                    tickmode='array',
                    tickvals=ret_ticks,
                )

                n = len(ret_df.columns)
                sym_list = list(ret_df.columns)
                ret_visible = [True]*n + [False]*n
                px_visible  = [False]*n + [True]*n
                ret_hoverinfo  = [None]*n + ['skip']*n
                px_hoverinfo   = ['skip']*n + [None]*n
                ret_legend     = [True]*n + [False]*n
                px_legend      = [False]*n + [True]*n
                ret_templates = [f"{sym} : %{{y:.2f}}%<extra></extra>" for sym in sym_list]
                px_templates  = [f"{sym} : $%{{y:.2f}}<extra></extra>" for sym in sym_list]
                ret_hovertmpl = ret_templates + [None]*n
                px_hovertmpl  = [None]*n + px_templates

                show_returns = (view_mode == "報酬率")
                yaxis_cfg = (
                    yaxis_init if show_returns else
                    {"title": "股價 (USD)", "ticksuffix": "", "tickformat": ".2f", "zeroline": False, "title_standoff": 12, "automargin": False, "autorange": False, "fixedrange": True, "range": px_range, "tickmode": "array", "tickvals": px_ticks}
                )
                fig.update_layout(
                    xaxis_title="日期",
                    yaxis_title=yaxis_cfg.get("title"),
                    legend_title="股票代碼",
                    template="plotly_dark",
                    hovermode="x unified",
                    xaxis=dict(type='date', fixedrange=True),
                    yaxis=yaxis_cfg,
                    transition=dict(duration=0),
                    uirevision="price_returns",
                    margin=dict(l=80, r=20, t=40, b=40),
                    dragmode='pan'
                )
                vis = ret_visible if show_returns else px_visible
                hoverinfo = ret_hoverinfo if show_returns else px_hoverinfo
                showlegend = ret_legend if show_returns else px_legend
                hovertmpl = ret_hovertmpl if show_returns else px_hovertmpl
                for i in range(len(fig.data)):
                    fig.data[i].visible = vis[i]
                    fig.data[i].hoverinfo = hoverinfo[i]
                    fig.data[i].showlegend = showlegend[i]
                    fig.data[i].hovertemplate = hovertmpl[i]
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

        # ===== 綜合評分比較 & 合併雷達比較（雙欄） =====
        left, right = st.columns([1.2, 1])
        with left:
            st.subheader("綜合評分比較")
            summary_data = []
            for symbol, data in all_details.items():
                row = {"股票代碼": symbol, "總分": data["total_score"], "投資建議": data["suggestion"], "股組類型": data["mode"]}
                # details: [指標, 口徑, 數值, 評級, 解釋]
                for detail_item in data["details"]:
                    try:
                        row[detail_item[0]] = detail_item[2]
                    except Exception:
                        pass
                summary_data.append(row)
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True, height=min(400, 60 + 32 * len(summary_df)), hide_index=True)
            
            st.caption("""
            **股組類型分類標準:** (符合以下任兩項)
            - **VALUE (價值股):** P/E < 20, P/B < 2, EPS > 3
            - **GROWTH (成長股):** P/E > 40, P/B > 4, EPS < 1
            - **MIX (混合型):** 不完全符合上述任一標準的股票
            """)

            # 指標口徑說明
            st.caption("""
            **指標口徑說明:**
            - **TTM (Trailing Twelve Months):** 近四季合計，最貼近「近一年」。
            - **NTM (Next Twelve Months):** 未來十二個月預估（分析師預期）。
            - **FY (Fiscal Year):** 最近完整會計年度。
            - **MRQ (Most Recent Quarter):** 最近一季的時點數值（快照）。
            """)

        with right:
            st.subheader("財務雷達比較（多股票疊加）")
            try:
                categories = ["EPS", "ROE", "P/E", "P/B", "淨利率"]
                radar_fig = go.Figure()
                traces_data = []
                for symbol, data in all_details.items():
                    values = [data["scores"].get(cat) or 0 for cat in categories]
                    total = sum(values)
                    traces_data.append((total, symbol, values))
                traces_data.sort(reverse=True)
                for _, symbol, values in traces_data:
                    col = color_map.get(symbol)
                    radar_fig.add_trace(go.Scatterpolar(
                        r=values + [values[0]],
                        theta=categories + [categories[0]],
                        fill='toself',
                        name=symbol,
                        line=dict(color=col, width=2.0),
                        marker=dict(size=2, color=col),
                        fillcolor=hex_to_rgba(col or '#1f77b4', 0.08)
                    ))
                radar_fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0,4], showticklabels=False, ticks=''),
                        angularaxis=dict(ticks='', tickfont=dict(size=11))
                    ),
                    template="plotly_dark",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=10, r=10, t=10, b=0),
                    height=360
                )
                st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})
            except Exception as e:
                st.warning(f"雷達圖比較繪製失敗: {e}")

        # ===== 個股詳細分析 =====
        st.subheader("個股詳細分析")
        for symbol, data in all_details.items():
            with st.expander(f"查看 {symbol} 的詳細資料"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"#### {symbol} 評分指標")
                    df = pd.DataFrame(data["details"], columns=["指標", "口徑", "數值", "評級", "解釋"])
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "評級": st.column_config.TextColumn(
                                "評級",
                                help="""
                                **評級標準:**
                                - **A:** 傑出 (4分)
                                - **B:** 良好 (3分)
                                - **C:** 一般 (2分)
                                - **D:** 尚可 (1分)
                                - **F:** 不佳 (0分)
                                ---
                                **EPS:** A:>3, B:>2, C:>1, D:>0
                                
                                **ROE:** A:>20%, B:>15%, C:>10%, D:>0%
                                
                                **P/E (非成長股):** A:<10, B:<20, C:<40, D:<60
                                
                                **P/E (成長股):** A:<60, B:<80, C:<100
                                
                                **P/B:** A:<1, B:<2, C:<3, D:<5
                                
                                **淨利率:** A:>20%, B:>10%, C:>5%, D:>0%
                                """
                            )
                        }
                    )
                    st.write(f"**✅ 總分: {data['total_score']} / 20**")
                    st.write(f"**📝 投資建議: {data['suggestion']}**")
                    st.write(f"**📈 股組類型: {data['mode']}**")

                with col2:
                    st.write(f"#### {symbol} 財務雷達圖")
                    try:
                        categories = ["EPS", "ROE", "P/E", "P/B", "淨利率"]
                        values = [data["scores"].get(cat) or 0 for cat in categories]
                        fig2 = go.Figure()
                        col = color_map.get(symbol, '#1f77b4')
                        fig2.add_trace(go.Scatterpolar(
                            r=values + [values[0]],
                            theta=categories + [categories[0]],
                            fill='toself',
                            name=symbol,
                            line=dict(width=2.6, color=col),
                            marker=dict(size=4, color=col),
                            fillcolor=hex_to_rgba(col, 0.18),
                        ))
                        fig2.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 4], showticklabels=False, ticks='')),
                            showlegend=False,
                            template="plotly_dark",
                        )
                        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False, "staticPlot": True, "scrollZoom": False})
                    except Exception as e:
                        st.warning(f"無法繪製 {symbol} 的雷達圖: {e}")

                st.write("---")
                st.write(f"#### {symbol} 財務圖表")
                col3, col4 = st.columns(2)
                stock_obj = data["stock"]

                with col3:
                    income_statement = stock_obj.financials
                    if not income_statement.empty:
                        st.write("**營收 vs 淨利**")
                        wanted = ['Total Revenue', 'Net Income']
                        available = [w for w in wanted if w in income_statement.index]
                        if available:
                            df_plot = income_statement.loc[available].transpose()
                            # 顯示：最近三個完整年度 + 當年(YTD)
                            try:
                                if not isinstance(df_plot.index, pd.DatetimeIndex):
                                    df_plot.index = pd.to_datetime(df_plot.index, errors='coerce')
                                df_plot = df_plot[~df_plot.index.isna()]
                                annual_df = df_plot.groupby(df_plot.index.year).first()
                            except Exception:
                                annual_df = df_plot

                            current_year = pd.Timestamp.today().year
                            # 過去三個完整年（小於當年）
                            prev_years = sorted([int(y) for y in annual_df.index if str(y).isdigit() and int(y) < current_year])[-3:]

                            # 當年 YTD（損益：以季度合計）
                            ytd_vals = {m: None for m in available}
                            try:
                                qfin = data_for_stock.quarterly_financials if False else None  # placeholder
                            except Exception:
                                qfin = None
                            # 正確抓取：使用 stock_obj 的季度損益
                            qfin = stock_obj.quarterly_financials if hasattr(stock_obj, 'quarterly_financials') else pd.DataFrame()
                            if qfin is not None and not qfin.empty:
                                qdf = qfin.loc[[m for m in available if m in qfin.index]].transpose()
                                if not isinstance(qdf.index, pd.DatetimeIndex):
                                    qdf.index = pd.to_datetime(qdf.index, errors='coerce')
                                qdf = qdf[~qdf.index.isna()]
                                cur = qdf[qdf.index.year == current_year]
                                if not cur.empty:
                                    for m in available:
                                        if m in cur.columns:
                                            try:
                                                ytd_vals[m] = float(cur[m].dropna().sum())
                                            except Exception:
                                                ytd_vals[m] = None

                            # 組裝資料
                            rows = []
                            for y in prev_years:
                                row = {m: None for m in available}
                                if y in annual_df.index:
                                    for m in available:
                                        try:
                                            row[m] = float(annual_df.loc[y, m])
                                        except Exception:
                                            row[m] = None
                                rows.append((str(y), row))
                            rows.append((f"{current_year} (YTD)", ytd_vals))

                            plot_dict = {label: vals for label, vals in rows}
                            df_plot_b = pd.DataFrame(plot_dict).transpose() / 1e9
                            fig_bar = go.Figure()
                            base_col = color_map.get(symbol, '#1f77b4')
                            if not df_plot_b.empty:
                                x_labels = list(df_plot_b.index)
                                for i, metric in enumerate(available):
                                    alpha = 0.50 if i == 0 else 0.25
                                    fig_bar.add_trace(go.Bar(
                                        x=x_labels,
                                        y=df_plot_b[metric].values,
                                        name=metric,
                                        marker=dict(color=hex_to_rgba(base_col, alpha), line=dict(color=base_col, width=1)),
                                        hovertemplate=f"%{{x}}<br>{metric}: %{{y:.2f}}<extra></extra>",
                                    ))
                            fig_bar.update_layout(
                                barmode='group',
                                template='plotly_dark',
                                legend_title='指標',
                                xaxis_title='期間',
                                yaxis_title='金額 (十億美元)',
                                yaxis=dict(tickformat=',d'),
                                margin=dict(l=10, r=10, t=10, b=10)
                            )
                            if df_plot_b.empty:
                                st.info("2022–2025 無對應的營收/淨利資料")
                            else:
                                st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

                with col4:
                    balance_sheet = stock_obj.balance_sheet
                    if not balance_sheet.empty:
                        st.write("**總資產 vs 總負債**")
                        wanted = ['Total Assets', 'Total Liabilities Net Minority Interest']
                        available = [w for w in wanted if w in balance_sheet.index]
                        if available:
                            df_plot = balance_sheet.loc[available].transpose()
                            # 顯示：最近三個完整年度 + 當年(YTD)（資產負債：取當年最近一季快照）
                            try:
                                if not isinstance(df_plot.index, pd.DatetimeIndex):
                                    df_plot.index = pd.to_datetime(df_plot.index, errors='coerce')
                                df_plot = df_plot[~df_plot.index.isna()]
                                annual_df = df_plot.groupby(df_plot.index.year).first()
                            except Exception:
                                annual_df = df_plot

                            current_year = pd.Timestamp.today().year
                            prev_years = sorted([int(y) for y in annual_df.index if str(y).isdigit() and int(y) < current_year])[-3:]

                            ytd_vals2 = {m: None for m in available}
                            qbs = stock_obj.quarterly_balance_sheet if hasattr(stock_obj, 'quarterly_balance_sheet') else pd.DataFrame()
                            if qbs is not None and not qbs.empty:
                                qdf = qbs.loc[[m for m in available if m in qbs.index]].transpose()
                                if not isinstance(qdf.index, pd.DatetimeIndex):
                                    qdf.index = pd.to_datetime(qdf.index, errors='coerce')
                                qdf = qdf[~qdf.index.isna()]
                                cur = qdf[qdf.index.year == current_year]
                                if not cur.empty:
                                    last_row = cur.sort_index().iloc[-1]
                                    for m in available:
                                        try:
                                            ytd_vals2[m] = float(last_row.get(m, None))
                                        except Exception:
                                            ytd_vals2[m] = None

                            rows2 = []
                            for y in prev_years:
                                row = {m: None for m in available}
                                if y in annual_df.index:
                                    for m in available:
                                        try:
                                            row[m] = float(annual_df.loc[y, m])
                                        except Exception:
                                            row[m] = None
                                rows2.append((str(y), row))
                            rows2.append((f"{current_year} (YTD)", ytd_vals2))

                            plot_dict2 = {label: vals for label, vals in rows2}
                            df_plot_b = pd.DataFrame(plot_dict2).transpose() / 1e9
                            fig_bar2 = go.Figure()
                            base_col = color_map.get(symbol, '#1f77b4')
                            if not df_plot_b.empty:
                                x_labels2 = list(df_plot_b.index)
                                for i, metric in enumerate(available):
                                    alpha = 0.50 if i == 0 else 0.25
                                    fig_bar2.add_trace(go.Bar(
                                        x=x_labels2,
                                        y=df_plot_b[metric].values,
                                        name=metric,
                                        marker=dict(color=hex_to_rgba(base_col, alpha), line=dict(color=base_col, width=1)),
                                        hovertemplate=f"%{{x}}<br>{metric}: %{{y:.2f}}<extra></extra>",
                                    ))
                            fig_bar2.update_layout(
                                barmode='group',
                                template='plotly_dark',
                                legend_title='指標',
                                xaxis_title='期間',
                                yaxis_title='金額 (十億美元)',
                                yaxis=dict(tickformat=',d'),
                                margin=dict(l=10, r=10, t=10, b=10)
                            )
                            if df_plot_b.empty:
                                st.info("2022–2025 無對應的資產/負債資料")
                            else:
                                st.plotly_chart(fig_bar2, use_container_width=True, config={"displayModeBar": False})

        # ===== PDF 報告 =====
        if st.sidebar.button("生成PDF報告"):
            try:
                pdf_bytes = build_pdf_report(all_details, summary_df)
                st.sidebar.download_button(
                    label="下載PDF",
                    data=pdf_bytes,
                    file_name=f"stock_analysis_report_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    key="download_pdf_btn_file",
                )
                st.sidebar.success("PDF 已生成！")
            except RuntimeError:
                st.sidebar.error("需要安裝 reportlab 才能生成 PDF。")
                st.sidebar.info("請在終端安裝: pip install reportlab")
            except Exception as e:
                st.sidebar.error(f"PDF 生成失敗: {e}")

# ===== 參考文獻 =====
with st.sidebar.expander("評分方法論與參考文獻"):
    st.markdown("""
    本儀表板的評分模型與財務指標分析，其方法論主要基於以下經典財務管理、投資學及證券分析文獻的理論框架。這些標準旨在提供一個快速、量化的篩選工具，而非取代深入的個案分析。

    **核心理論依據:**
    - **價值投資 (Value Investing):** 承襲葛拉漢 (Graham) 的概念，強調公司的內在價值，關注如低本益比 (P/E)、低股價淨值比 (P/B) 等指標，尋找價格被市場低估的標的。
    - **成長投資 (Growth Investing):** 關注具有高成長潛力的公司，看重股東權益報酬率 (ROE)、淨利率 (Profit Margin) 等反映公司獲利能力與效率的指標。
    - **財務報表分析 (Financial Statement Analysis):** 透過解析財務報表（損益表、資產負債表）的關鍵數據，評估公司的財務健康狀況與經營績效。

    **參考書目 (References):**
    - Brigham, E. F., & Ehrhardt, M. C. (2016). *Financial Management: Theory & Practice* (15th ed.). Cengage Learning.
    - CFA Institute. (2020). *Equity Asset Valuation* (CFA Program Curriculum, Level II). Wiley.
    - Damodaran, A. (2012). *Investment Valuation: Tools and Techniques for Determining the Value of Any Asset* (3rd ed.). Wiley.
    - Graham, B. (1949). *The Intelligent Investor*. Harper & Brothers.
    - Graham, B., & Dodd, D. L. (1934). *Security Analysis*. McGraw-Hill.
    - Penman, S. H. (2012). *Financial Statement Analysis and Security Valuation* (5th ed.). McGraw-Hill.
    - Subramanyam, K. R. (2014). *Financial Statement Analysis* (11th ed.). McGraw-Hill.
    """)
