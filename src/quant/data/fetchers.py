"""行情拉取器：统一返回 storage.REQUIRED_COLS schema 的 DataFrame。

- A股个股：akshare stock_zh_a_hist（东财，前复权）
- A股指数：akshare index_zh_a_hist（基准用，如 000300）
- 美股：yfinance 优先（auto_adjust 复权）；失败时退回 akshare stock_us_daily（新浪）
"""

from __future__ import annotations

import os

import pandas as pd

# 本机若挂代理（如 Clash 127.0.0.1:7890），国内数据源走代理会被掐断，必须直连。
_DOMESTIC_NO_PROXY = "eastmoney.com,sina.com.cn,sinajs.cn"
for _var in ("NO_PROXY", "no_proxy"):
    _cur = os.environ.get(_var, "")
    if "eastmoney.com" not in _cur:
        os.environ[_var] = f"{_cur},{_DOMESTIC_NO_PROXY}".strip(",")

# yfinance（Yahoo）在国内网络经常不可用；同一进程内失败一次后直接走新浪源
_yf_broken = False
# 东财接口同理（可能被反爬掐断），失败一次后 A股走新浪源
_em_broken = False


def _sina_cn_code(symbol: str) -> str:
    """6 位代码 → 新浪带交易所前缀代码：600519→sh600519, 000858→sz000858"""
    if symbol.startswith(("6", "9", "5")):
        return f"sh{symbol}"
    if symbol.startswith(("4", "8")):
        return f"bj{symbol}"
    return f"sz{symbol}"


def _sina_cn_index_code(symbol: str) -> str:
    """指数前缀规则与个股不同：000300/000001 等为沪市，399xxx 为深市。"""
    return f"sz{symbol}" if symbol.startswith("39") else f"sh{symbol}"


def _ymd(d: str | pd.Timestamp) -> str:
    return pd.Timestamp(d).strftime("%Y%m%d")


def _fetch_cn_eastmoney(symbol: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_zh_a_hist(
        symbol=symbol, period="daily",
        start_date=_ymd(start), end_date=_ymd(end), adjust="qfq",
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.rename(columns={
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount",
    })
    return df[["date", "open", "high", "low", "close", "volume", "amount"]]


def _fetch_cn_sina(symbol: str, start: str, end: str) -> pd.DataFrame:
    """新浪源备援。注意：成交量单位为股（东财为手），跨源混用时勿直接比较 volume。"""
    import akshare as ak

    raw = ak.stock_zh_a_daily(symbol=_sina_cn_code(symbol), adjust="qfq")
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.rename(columns=str.lower)
    df["date"] = pd.to_datetime(df["date"])
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    cols = ["date", "open", "high", "low", "close", "volume"]
    if "amount" in df.columns:
        cols.append("amount")
    return df.loc[mask, cols]


def fetch_cn_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    global _em_broken
    if not _em_broken:
        try:
            return _fetch_cn_eastmoney(symbol, start, end)
        except Exception as e:
            print(f"  [warn] 东财源不可用({type(e).__name__})，本轮改用新浪源")
            _em_broken = True
    return _fetch_cn_sina(symbol, start, end)


def fetch_cn_index_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    global _em_broken
    if not _em_broken:
        try:
            raw = ak.index_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=_ymd(start), end_date=_ymd(end),
            )
            if raw is None or raw.empty:
                return pd.DataFrame()
            df = raw.rename(columns={
                "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
                "收盘": "close", "成交量": "volume", "成交额": "amount",
            })
            return df[["date", "open", "high", "low", "close", "volume", "amount"]]
        except Exception as e:
            print(f"  [warn] 东财指数源不可用({type(e).__name__})，本轮改用新浪源")
            _em_broken = True

    # 新浪指数源：代码需带交易所前缀（000300 → sh000300）
    raw = ak.stock_zh_index_daily(symbol=_sina_cn_index_code(symbol))
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.rename(columns=str.lower)
    df["date"] = pd.to_datetime(df["date"])
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df.loc[mask, ["date", "open", "high", "low", "close", "volume"]]


def _fetch_us_yfinance(symbol: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.Ticker(symbol).history(
        start=start, end=pd.Timestamp(end) + pd.Timedelta(days=1),
        auto_adjust=True,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.reset_index().rename(columns={
        "Date": "date", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    })
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df[["date", "open", "high", "low", "close", "volume"]]


def _fetch_us_akshare(symbol: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_us_daily(symbol=symbol, adjust="qfq")
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.rename(columns=str.lower)
    df["date"] = pd.to_datetime(df["date"])
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df.loc[mask, ["date", "open", "high", "low", "close", "volume"]]


def fetch_us_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    global _yf_broken
    if not _yf_broken:
        try:
            df = _fetch_us_yfinance(symbol, start, end)
            if not df.empty:
                return df
            _yf_broken = True
        except Exception as e:  # 国内网络可能无法访问 Yahoo
            print(f"  [warn] yfinance 不可用({type(e).__name__})，本轮改用新浪源")
            _yf_broken = True
    return _fetch_us_akshare(symbol, start, end)
