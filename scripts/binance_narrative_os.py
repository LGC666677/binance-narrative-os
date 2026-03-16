from __future__ import annotations

import argparse
import json
import math
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests.exceptions import SSLError


TOPIC_RUSH_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/social-rush/rank/list"
SOCIAL_HYPE_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/social/hype/rank/leaderboard"
UNIFIED_RANK_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/unified/rank/list"
SMART_MONEY_INFLOW_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/tracker/wallet/token/inflow/rank/query"
SMART_SIGNAL_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/web/signal/smart-money"
CMS_ARTICLE_LIST_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
CMS_ARTICLE_DETAIL_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query"
TOKEN_AUDIT_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit"

DEFAULT_CONFIG: Dict[str, Any] = {
    "chains": ["56", "CT_501", "8453"],
    "topic_rank_types": [30, 20],
    "topic_limit_per_chain": 8,
    "social_limit_per_chain": 16,
    "smart_money_period": "24h",
    "signal_limit_per_chain": 12,
    "market_rank_size": 10,
    "rotation_limit": 8,
    "playbook_limit": 6,
    "calendar_limit": 8,
    "false_narrative_limit": 6,
    "history_dir": "output/history",
    "history_keep_files": 96,
    "history_window_hours": 48,
    "announcement_catalog_ids": [48, 49, 93],
    "announcement_limit_per_catalog": 3,
    "request_timeout_seconds": 20,
    "request_interval_seconds": 0.08,
}

CHAIN_NAMES = {"56": "BSC", "CT_501": "Solana", "8453": "Base", "1": "Ethereum"}
STATUS_LABELS = {
    "Confirmed": "已确认",
    "Accelerating": "加速中",
    "Igniting": "点火期",
    "Cooling": "降温中",
}
MEMORY_STATE_LABELS = {
    "New": "新出现",
    "Continuing": "延续",
    "Strengthening": "强化",
    "Weakening": "转弱",
    "Returning": "回归",
}
RISK_BAND_LABELS = {
    "High": "高",
    "Medium": "中",
    "Low": "低",
    "Unknown": "未知",
}
DIRECTION_LABELS = {
    "buy": "看多",
    "sell": "看空",
    "unknown": "未知",
}
SIGNAL_STATUS_LABELS = {
    "timeout": "超时",
    "exitRate": "退出率触发",
    "active": "激活中",
    "unknown": "未知",
}
CATALOG_NAME_LABELS = {
    "Latest Activities": "最新活动",
    "Latest Binance News": "币安最新公告",
    "New Cryptocurrency Listing": "新币上新",
}


def ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ts_to_iso(timestamp_ms: Any) -> Optional[str]:
    value = to_int(timestamp_ms)
    if value is None or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def safe_first(items: Iterable[Any]) -> Any:
    for item in items:
        return item
    return None


def dedupe_list(items: Iterable[Any]) -> List[Any]:
    seen = set()
    output: List[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
    if not raw.strip():
        return default
    return json.loads(raw)


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_json(path: Path, payload: Any) -> None:
    save_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def average(values: Iterable[Optional[float]]) -> Optional[float]:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def median_value(values: Iterable[Optional[float]]) -> Optional[float]:
    numbers = sorted(value for value in values if value is not None)
    if not numbers:
        return None
    middle = len(numbers) // 2
    if len(numbers) % 2 == 1:
        return numbers[middle]
    return (numbers[middle - 1] + numbers[middle]) / 2.0


def safe_log10(value: Any) -> float:
    number = to_float(value) or 0.0
    return math.log10(max(number, 1.0))


def clip_text(text: Any, max_chars: int = 180) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    compact = " ".join(value.split())
    return compact if len(compact) <= max_chars else f"{compact[: max_chars - 1].rstrip()}…"


def normalize_text_key(text: Any) -> str:
    value = str(text or "").strip().lower()
    output = []
    for char in value:
        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            output.append(char)
    return "".join(output)


def topic_identity(chain_id: str, topic_id: Any, topic_name: Any) -> str:
    topic_id_text = str(topic_id or "").strip()
    if topic_id_text:
        return f"{chain_id}:{topic_id_text}"
    return f"{chain_id}:{normalize_text_key(topic_name)}"


def load_report_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = load_json(path, None)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def iso_to_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def hours_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    if not start or not end:
        return None
    return abs((end - start).total_seconds()) / 3600.0


def score_to_band(score: Optional[float]) -> str:
    number = to_float(score) or 0.0
    if number >= 72:
        return "High"
    if number >= 45:
        return "Medium"
    return "Low"


def status_label(status: Any) -> str:
    return STATUS_LABELS.get(str(status or ""), str(status or "-"))


def memory_state_label(state: Any) -> str:
    return MEMORY_STATE_LABELS.get(str(state or ""), str(state or "-"))


def risk_band_label(band: Any) -> str:
    return RISK_BAND_LABELS.get(str(band or ""), str(band or "-"))


def direction_label(direction: Any) -> str:
    return DIRECTION_LABELS.get(str(direction or "").lower(), str(direction or "-"))


def signal_status_label(status: Any) -> str:
    raw = str(status or "")
    return SIGNAL_STATUS_LABELS.get(raw, SIGNAL_STATUS_LABELS.get(raw.lower(), raw or "-"))


def catalog_name_label(name: Any) -> str:
    return CATALOG_NAME_LABELS.get(str(name or ""), str(name or "-"))


def extract_text_segments(node: Any) -> List[str]:
    if isinstance(node, dict):
        if node.get("node") == "text":
            text = str(node.get("text") or "").strip()
            return [text] if text else []
        output: List[str] = []
        for child in node.get("child") or []:
            output.extend(extract_text_segments(child))
        return output
    if isinstance(node, list):
        output: List[str] = []
        for child in node:
            output.extend(extract_text_segments(child))
        return output
    return []


def body_json_to_summary(raw_body: Any, max_chars: int = 180) -> str:
    if not raw_body:
        return ""
    try:
        payload = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except json.JSONDecodeError:
        return str(raw_body)[:max_chars].strip()
    text = " ".join(segment for segment in extract_text_segments(payload) if segment)
    text = " ".join(text.split())
    return text if len(text) <= max_chars else f"{text[: max_chars - 1].rstrip()}…"


def pct_delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    baseline = abs(previous) if abs(previous) >= 1e-9 else 1.0
    return ((current - previous) / baseline) * 100.0


def flatten_tag_names(tag_map: Any) -> List[str]:
    if not isinstance(tag_map, dict):
        return []
    tags: List[str] = []
    for values in tag_map.values():
        if not isinstance(values, list):
            continue
        for item in values:
            tag_name = str((item or {}).get("tagName") or "").strip()
            if tag_name:
                tags.append(tag_name)
    return dedupe_list(tags)


class BinanceNarrativeClient:
    def __init__(self, timeout_seconds: int, interval_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
        self.session = requests.Session()
        self.session.headers.update({"Accept-Encoding": "identity"})
        self._tls_warning_disabled = False

    def _sleep(self) -> None:
        if self.interval_seconds > 0:
            time.sleep(self.interval_seconds)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Dict[str, Any] | None = None,
        body: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
    ) -> Any:
        request_kwargs = {
            "method": method,
            "url": url,
            "params": params,
            "json": body,
            "headers": headers,
            "timeout": self.timeout_seconds,
        }
        try:
            response = self.session.request(**request_kwargs)
        except SSLError:
            if not self._tls_warning_disabled:
                requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
                self._tls_warning_disabled = True
            response = self.session.request(**request_kwargs, verify=False)
        response.raise_for_status()
        self._sleep()
        try:
            payload = json.loads(response.content.decode("utf-8"))
        except Exception:
            payload = response.json()
        if isinstance(payload, dict):
            code = str(payload.get("code", ""))
            if code and code != "000000":
                raise RuntimeError(f"request failed code={code} url={url}")
            if payload.get("success") is False:
                raise RuntimeError(f"request failed success=false url={url}")
        return payload

    def get_topic_rush(self, chain_id: str, rank_type: int, sort: int) -> List[Dict[str, Any]]:
        payload = self._request_json(
            "GET",
            TOPIC_RUSH_URL,
            params={"chainId": chain_id, "rankType": rank_type, "sort": sort, "asc": "false"},
            headers={"User-Agent": "binance-web3/1.0 (Skill)"},
        )
        return payload.get("data") or []

    def get_social_hype(self, chain_id: str) -> List[Dict[str, Any]]:
        payload = self._request_json(
            "GET",
            SOCIAL_HYPE_URL,
            params={"chainId": chain_id, "sentiment": "All", "socialLanguage": "ALL", "targetLanguage": "en", "timeRange": 1},
            headers={"User-Agent": "binance-web3/2.0 (Skill)"},
        )
        return (payload.get("data") or {}).get("leaderBoardList") or []

    def get_unified_rank(self, chain_id: str, rank_type: int, size: int) -> List[Dict[str, Any]]:
        payload = self._request_json(
            "POST",
            UNIFIED_RANK_URL,
            body={"rankType": rank_type, "chainId": chain_id, "period": 50, "sortBy": 0, "orderAsc": False, "page": 1, "size": size},
            headers={"Content-Type": "application/json", "User-Agent": "binance-web3/2.0 (Skill)"},
        )
        return (payload.get("data") or {}).get("tokens") or []

    def get_smart_money_inflow(self, chain_id: str, period: str) -> List[Dict[str, Any]]:
        payload = self._request_json(
            "POST",
            SMART_MONEY_INFLOW_URL,
            body={"chainId": chain_id, "period": period, "tagType": 2},
            headers={"Content-Type": "application/json", "User-Agent": "binance-web3/2.0 (Skill)"},
        )
        return payload.get("data") or []

    def get_smart_signals(self, chain_id: str, page_size: int) -> List[Dict[str, Any]]:
        payload = self._request_json(
            "POST",
            SMART_SIGNAL_URL,
            body={"smartSignalType": "", "page": 1, "pageSize": page_size, "chainId": chain_id},
            headers={"Content-Type": "application/json", "User-Agent": "binance-web3/1.0 (Skill)"},
        )
        return payload.get("data") or []

    def get_announcement_catalogs(self, page_size: int = 50) -> List[Dict[str, Any]]:
        payload = self._request_json(
            "GET",
            CMS_ARTICLE_LIST_URL,
            params={"type": 1, "pageNo": 1, "pageSize": page_size},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return (payload.get("data") or {}).get("catalogs") or []

    def get_announcement_detail(self, article_code: str) -> Dict[str, Any]:
        payload = self._request_json(
            "GET",
            CMS_ARTICLE_DETAIL_URL,
            params={"articleCode": article_code},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return payload.get("data") or {}

    def audit_token(self, chain_id: str, contract_address: str) -> Dict[str, Any]:
        payload = self._request_json(
            "POST",
            TOKEN_AUDIT_URL,
            body={"binanceChainId": chain_id, "contractAddress": contract_address, "requestId": str(uuid.uuid4())},
            headers={"Content-Type": "application/json", "User-Agent": "binance-web3/1.4 (Skill)", "source": "agent"},
        )
        return payload.get("data") or {}


class NarrativeBuilder:
    def __init__(
        self,
        config: Dict[str, Any],
        *,
        previous_report: Optional[Dict[str, Any]] = None,
        history_reports: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.config = config
        self.client = BinanceNarrativeClient(
            timeout_seconds=to_int(config.get("request_timeout_seconds")) or 20,
            interval_seconds=to_float(config.get("request_interval_seconds")) or 0.0,
        )
        self.generated_at_dt = datetime.now(timezone.utc)
        self.generated_at = self.generated_at_dt.isoformat()
        self.previous_report = previous_report or {}
        self.history_reports = [item for item in (history_reports or []) if isinstance(item, dict)]
        self.previous_radar_index = self.index_radar(self.previous_report.get("narrative_radar") or [])
        self.history_radar_indexes = [self.index_radar(item.get("narrative_radar") or []) for item in self.history_reports]
        self.warnings: List[str] = []
        self.audit_cache: Dict[tuple[str, str], Dict[str, Any]] = {}

    def safe_call(self, label: str, func: Any, *args: Any, fallback: Any = None, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            self.warnings.append(f"{label}: {exc}")
            return fallback

    def topic_key(self, chain_id: str, topic_id: Any, topic_name: Any) -> str:
        return topic_identity(chain_id, topic_id, topic_name)

    def index_radar(self, radar: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        indexed: Dict[str, Dict[str, Any]] = {}
        for item in radar:
            key = self.topic_key(item.get("chain_id") or "", item.get("topic_id"), item.get("topic_name"))
            indexed[key] = item
        return indexed

    def find_previous_entry(self, chain_id: str, topic_id: Any, topic_name: Any) -> Optional[Dict[str, Any]]:
        return self.previous_radar_index.get(self.topic_key(chain_id, topic_id, topic_name))

    def find_24h_entry(self, chain_id: str, topic_id: Any, topic_name: Any) -> Optional[Dict[str, Any]]:
        key = self.topic_key(chain_id, topic_id, topic_name)
        best_match: Optional[Dict[str, Any]] = None
        best_gap: Optional[float] = None
        for report, index in zip(self.history_reports, self.history_radar_indexes):
            candidate = index.get(key)
            if not candidate:
                continue
            snapshot_time = iso_to_datetime(report.get("generated_at"))
            gap = hours_between(snapshot_time, self.generated_at_dt)
            if gap is None:
                continue
            distance = abs(gap - 24.0)
            if best_gap is None or distance < best_gap:
                best_gap = distance
                best_match = candidate
        return best_match

    def safe_audit_lead_token(self, chain_id: str, contract_address: str) -> Dict[str, Any]:
        key = (chain_id, contract_address.lower())
        if key not in self.audit_cache:
            self.audit_cache[key] = self.safe_call(
                f"token_audit:{chain_id}:{contract_address}",
                self.client.audit_token,
                chain_id,
                contract_address,
                fallback={},
            ) or {}
        return self.audit_cache[key]

    def topic_name_from_raw(self, topic: Dict[str, Any]) -> str:
        name = topic.get("name") or {}
        return str(name.get("topicNameEn") or name.get("topicNameCn") or "Untitled Narrative").strip()
    def build_topic_terms(self, topic: Dict[str, Any]) -> List[str]:
        terms: List[str] = []
        topic_name = str(topic.get("topic_name") or "").strip()
        lead = topic.get("lead_token") or {}
        if topic_name:
            terms.append(topic_name)
            normalized_name = normalize_text_key(topic_name)
            if normalized_name and normalized_name != topic_name.lower():
                terms.append(normalized_name)
        lead_symbol = str(lead.get("symbol") or "").strip()
        if len(lead_symbol) >= 3:
            terms.append(lead_symbol)
        for token in (topic.get("satellite_tokens") or [])[:4]:
            symbol = str(token.get("symbol") or "").strip()
            if len(symbol) >= 3:
                terms.append(symbol)
        return dedupe_list(term for term in terms if term)

    def article_match_score(self, article: Dict[str, Any], topic: Dict[str, Any]) -> float:
        haystack_raw = " ".join(
            [
                str(article.get("title") or ""),
                str(article.get("summary") or ""),
                str(article.get("catalog_name") or ""),
            ]
        )
        haystack = haystack_raw.lower()
        if not haystack.strip():
            return 0.0
        normalized_haystack = normalize_text_key(haystack_raw)
        score = 0.0
        for term in self.build_topic_terms(topic):
            raw_term = str(term).strip()
            normalized = normalize_text_key(raw_term)
            if raw_term and raw_term.lower() in haystack:
                score += 30.0 if raw_term == topic.get("topic_name") else 16.0
            if normalized and normalized in normalized_haystack:
                score += 10.0
        return score

    def summarize_audit(self, chain_id: str, contract_address: str) -> Dict[str, Any]:
        if not contract_address:
            return {
                "has_result": False,
                "risk_level": None,
                "risk_band": "Unknown",
                "verified": None,
                "buy_tax": None,
                "sell_tax": None,
                "hit_risks": [],
            }
        audit = self.safe_audit_lead_token(chain_id, contract_address)
        extra_info = audit.get("extraInfo") or {}
        hit_risks: List[str] = []
        for item in audit.get("riskItems") or []:
            for detail in item.get("details") or []:
                if detail.get("isHit"):
                    title = str(detail.get("title") or "").strip()
                    if title:
                        hit_risks.append(title)
        risk_level_enum = str(audit.get("riskLevelEnum") or "").upper()
        risk_band = "Low"
        if risk_level_enum in {"MEDIUM", "HIGH"}:
            risk_band = "Medium" if risk_level_enum == "MEDIUM" else "High"
        return {
            "has_result": bool(audit.get("hasResult")),
            "risk_level": audit.get("riskLevel"),
            "risk_level_enum": risk_level_enum or None,
            "risk_band": risk_band,
            "verified": extra_info.get("isVerified"),
            "reported": extra_info.get("isReported"),
            "buy_tax": to_float(extra_info.get("buyTax")),
            "sell_tax": to_float(extra_info.get("sellTax")),
            "hit_risks": dedupe_list(hit_risks),
        }

    def build_topic_token_snapshot(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        normalized_tokens: List[Dict[str, Any]] = []
        for raw in topic.get("tokenList") or []:
            normalized_tokens.append(
                {
                    "chain_id": str(raw.get("chainId") or topic.get("chainId") or ""),
                    "symbol": str(raw.get("symbol") or "").strip() or "Unknown",
                    "contract_address": str(raw.get("contractAddress") or "").strip(),
                    "create_time": ts_to_iso(raw.get("createTime")),
                    "net_inflow": to_float(raw.get("netInflow")),
                    "net_inflow_1h": to_float(raw.get("netInflow1h")),
                    "market_cap": to_float(raw.get("marketCap")),
                    "price_change_24h": to_float(raw.get("priceChange24h")),
                    "liquidity": to_float(raw.get("liquidity")),
                    "holders": to_int(raw.get("holders")),
                    "unique_trader_24h": to_int(raw.get("uniqueTrader24h")),
                    "unique_trader_4h": to_int(raw.get("uniqueTrader4h")),
                    "unique_trader_1h": to_int(raw.get("uniqueTrader1h")),
                    "smart_money_holders": to_int(raw.get("smartMoneyHolders")),
                    "smart_money_holding_percent": to_float(raw.get("smartMoneyHoldingPercent")),
                    "dev_holding_percent": to_float(raw.get("devHoldingPercent")),
                    "sniper_holding_percent": to_float(raw.get("sniperHoldingPercent")),
                    "insider_holding_percent": to_float(raw.get("insiderHoldingPercent")),
                    "tags": flatten_tag_names(raw.get("tokenTag") or {}),
                }
            )
        normalized_tokens.sort(
            key=lambda item: (
                item.get("net_inflow") or 0.0,
                item.get("unique_trader_24h") or 0,
                item.get("liquidity") or 0.0,
            ),
            reverse=True,
        )
        lead = safe_first(normalized_tokens) or {}
        holder_concentration = (
            (lead.get("dev_holding_percent") or 0.0)
            + (lead.get("insider_holding_percent") or 0.0)
            + (lead.get("sniper_holding_percent") or 0.0)
        )
        return {
            "lead_token": lead,
            "satellite_tokens": normalized_tokens[1:5],
            "token_count": len(normalized_tokens),
            "median_liquidity": median_value(token.get("liquidity") for token in normalized_tokens),
            "median_holders": median_value(token.get("holders") for token in normalized_tokens),
            "average_price_change_24h": average(token.get("price_change_24h") for token in normalized_tokens),
            "total_unique_trader_24h": sum(token.get("unique_trader_24h") or 0 for token in normalized_tokens),
            "smart_money_token_count": sum(1 for token in normalized_tokens if (token.get("smart_money_holders") or 0) > 0),
            "holder_concentration_pct": round(holder_concentration, 4),
            "token_symbols": [token.get("symbol") for token in normalized_tokens if token.get("symbol")],
        }

    def build_topic_flags(self, item: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        lead = item.get("lead_token") or {}
        audit = item.get("audit") or {}
        if item.get("deep_analysis"):
            flags.append("有深度主题分析")
        if (item.get("net_inflow_1h") or 0.0) > 0:
            flags.append("近 1 小时资金继续流入")
        if (lead.get("smart_money_holders") or 0) > 0:
            flags.append("龙头币已有聪明钱持仓")
        if (item.get("median_liquidity") or 0.0) < 50000:
            flags.append("整体流动性偏薄")
        if (item.get("holder_concentration_pct") or 0.0) >= 15:
            flags.append("龙头筹码集中度偏高")
        lead_create_time = iso_to_datetime(lead.get("create_time")) if lead.get("create_time") else None
        if lead_create_time is not None and (hours_between(lead_create_time, self.generated_at_dt) or 9999) <= 12:
            flags.append("龙头币较新")
        if audit.get("risk_band") == "High":
            flags.append("审计风险偏高")
        elif audit.get("risk_band") == "Medium":
            flags.append("审计风险中等")
        if audit.get("verified") is True:
            flags.append("合约已验证")
        if audit.get("buy_tax") and audit.get("buy_tax") >= 0.08:
            flags.append("买入税较高")
        if audit.get("sell_tax") and audit.get("sell_tax") >= 0.08:
            flags.append("卖出税较高")
        for tag in lead.get("tags") or []:
            if "Wash Trading" in tag and "疑似对刷标签" not in flags:
                flags.append("疑似对刷标签")
            if "High Tax" in tag and "高税标签" not in flags:
                flags.append("高税标签")
        return dedupe_list(flags)

    def build_status_reason(self, item: Dict[str, Any]) -> str:
        status = item.get("status")
        if status == "Confirmed":
            if item.get("catalyst_matches"):
                return "官方催化与资金确认同时存在，叙事已经从讨论走向被市场认可。"
            return "资金、广度和可交易性同时过线，属于当前被市场确认的主线。"
        if status == "Accelerating":
            return "注意力正在扩散，资金也在跟上，属于强化阶段。"
        if status == "Igniting":
            return "热度已经点起来，但深度确认还不够，适合继续跟踪。"
        return "确认层偏薄，或者资金、流动性已经开始走弱。"

    def build_next_watch_condition(self, item: Dict[str, Any]) -> str:
        if item.get("status") == "Confirmed":
            return "继续观察近 1 小时净流入是否维持为正，以及是否还有新增催化。"
        if item.get("status") == "Accelerating":
            return "继续观察龙头币流动性和聪明钱参与度是否同步上升。"
        if item.get("status") == "Igniting":
            return "继续观察社交热度能否真正转化为持续净流入。"
        return "继续观察该主题能否重新回到正净流入，或出现新的催化。"

    def finalize_topic_scores(self, item: Dict[str, Any]) -> Dict[str, Any]:
        attention_score = clamp(to_float(item.get("attention_score")) or 0.0, 0.0, 100.0)
        money_score = clamp(to_float(item.get("money_score")) or 0.0, 0.0, 100.0)
        breadth_score = clamp(to_float(item.get("breadth_score")) or 0.0, 0.0, 100.0)
        tradability_score = clamp(to_float(item.get("tradability_score")) or 0.0, 0.0, 100.0)
        momentum_score = clamp(to_float(item.get("momentum_score")) or 0.0, 0.0, 100.0)
        catalyst_score = clamp(to_float(item.get("catalyst_score")) or 0.0, 0.0, 100.0)
        confirmation_base = clamp(to_float(item.get("confirmation_base_score")) or 0.0, 0.0, 100.0)
        confirmation_score = clamp(confirmation_base * 0.72 + catalyst_score * 0.28, 0.0, 100.0)
        fragility_score = clamp(to_float(item.get("fragility_score")) or 0.0, 0.0, 100.0)
        quality_score = clamp(
            breadth_score * 0.30 + tradability_score * 0.30 + confirmation_score * 0.22 + momentum_score * 0.18,
            0.0,
            100.0,
        )
        strength = clamp(
            attention_score * 0.18
            + money_score * 0.22
            + breadth_score * 0.15
            + tradability_score * 0.14
            + confirmation_score * 0.14
            + momentum_score * 0.10
            + quality_score * 0.12
            - fragility_score * 0.12,
            0.0,
            100.0,
        )
        status = "Cooling"
        if strength >= 78 and confirmation_score >= 28 and fragility_score < 55:
            status = "Confirmed"
        elif strength >= 60 and confirmation_score >= 18:
            status = "Accelerating"
        elif attention_score >= 46 and (item.get("progress_pct") or 0.0) < 52:
            status = "Igniting"
        item["attention_score"] = round(attention_score, 2)
        item["money_score"] = round(money_score, 2)
        item["breadth_score"] = round(breadth_score, 2)
        item["tradability_score"] = round(tradability_score, 2)
        item["momentum_score"] = round(momentum_score, 2)
        item["confirmation_score"] = round(confirmation_score, 2)
        item["fragility_score"] = round(fragility_score, 2)
        item["quality_score"] = round(quality_score, 2)
        item["narrative_strength_score"] = round(strength, 2)
        item["status"] = status
        item["status_label"] = status_label(status)
        item["status_reason"] = self.build_status_reason(item)
        item["next_watch"] = self.build_next_watch_condition(item)
        item["score_band"] = score_to_band(strength)
        item["score_band_label"] = risk_band_label(item["score_band"])
        return item

    def build(self) -> Dict[str, Any]:
        chains = [str(item) for item in (self.config.get("chains") or ["56", "CT_501"])]
        bundle: Dict[str, Dict[str, Any]] = {}
        for chain_id in chains:
            bundle[chain_id] = self.collect_chain_bundle(chain_id)
        crossovers = self.build_crossovers(bundle)
        market_pulse = self.build_market_pulse(bundle)
        catalysts = self.build_official_catalysts()
        radar = self.build_narrative_radar(bundle, crossovers)
        catalysts = self.attach_catalyst_matches(radar, catalysts)
        radar.sort(key=lambda item: item["narrative_strength_score"], reverse=True)
        memory = self.build_narrative_memory(radar)
        rotation_map = self.build_rotation_map(radar, memory)
        false_narratives = self.build_false_narratives(radar)
        quality_board = self.build_quality_board(radar)
        playbooks = self.build_narrative_playbooks(radar, false_narratives)
        editorial_calendar = self.build_editorial_calendar(radar, catalysts, memory)
        signals = self.build_signal_watch(bundle, radar)
        overview = self.build_overview(radar, crossovers, catalysts, market_pulse, memory, rotation_map, false_narratives, quality_board)
        daily_brief = self.build_daily_brief(overview, radar, crossovers, catalysts, memory, rotation_map, false_narratives)
        square_draft = self.build_square_draft(radar, crossovers, catalysts, memory)
        return {
            "skill": "binance-narrative-os",
            "generated_at": self.generated_at,
            "chains": [{"chain_id": chain_id, "chain_name": CHAIN_NAMES.get(chain_id, chain_id)} for chain_id in chains],
            "overview": overview,
            "market_pulse": market_pulse,
            "narrative_radar": radar,
            "narrative_memory": memory,
            "narrative_rotation_map": rotation_map,
            "narrative_quality_board": quality_board,
            "risk_of_false_narratives": false_narratives,
            "attention_capital_crossovers": crossovers,
            "signal_watch": signals,
            "official_catalysts": catalysts,
            "narrative_playbooks": playbooks,
            "editorial_calendar": editorial_calendar,
            "daily_brief": daily_brief,
            "square_draft": square_draft,
            "warnings": self.warnings,
        }

    def collect_chain_bundle(self, chain_id: str) -> Dict[str, Any]:
        topic_rank_types = [to_int(item) or 30 for item in (self.config.get("topic_rank_types") or [30, 20])]
        topic_lists: List[Dict[str, Any]] = []
        for rank_type in topic_rank_types:
            sort = 30 if rank_type == 30 else 10
            topic_lists.extend(
                self.safe_call(f"topic_rush:{chain_id}:{rank_type}", self.client.get_topic_rush, chain_id, rank_type, sort, fallback=[])
            )
        market_rank_size = to_int(self.config.get("market_rank_size")) or 10
        return {
            "chain_id": chain_id,
            "chain_name": CHAIN_NAMES.get(chain_id, chain_id),
            "topics": topic_lists,
            "social_hype": self.safe_call(f"social_hype:{chain_id}", self.client.get_social_hype, chain_id, fallback=[]),
            "trending": self.safe_call(f"unified_rank:trending:{chain_id}", self.client.get_unified_rank, chain_id, 10, market_rank_size, fallback=[]),
            "top_search": self.safe_call(f"unified_rank:topsearch:{chain_id}", self.client.get_unified_rank, chain_id, 11, market_rank_size, fallback=[]),
            "smart_money_inflow": self.safe_call(
                f"smart_money_inflow:{chain_id}",
                self.client.get_smart_money_inflow,
                chain_id,
                str(self.config.get("smart_money_period") or "24h"),
                fallback=[],
            ),
            "smart_signals": self.safe_call(
                f"smart_signals:{chain_id}",
                self.client.get_smart_signals,
                chain_id,
                to_int(self.config.get("signal_limit_per_chain")) or 10,
                fallback=[],
            ),
        }

    def build_crossovers(self, bundle: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        crossovers: List[Dict[str, Any]] = []
        limit = to_int(self.config.get("social_limit_per_chain")) or 16
        for chain_id, chain_bundle in bundle.items():
            social_map: Dict[str, Dict[str, Any]] = {}
            for index, item in enumerate((chain_bundle.get("social_hype") or [])[:limit], start=1):
                meta = item.get("metaInfo") or {}
                contract_address = str(meta.get("contractAddress") or "").lower()
                if not contract_address:
                    continue
                series = (item.get("socialHypeInfo") or {}).get("socialHypeSerialChart") or []
                first_point = safe_first(series) or {}
                last_point = series[-1] if series else {}
                first_social = to_float(first_point.get("socialHype")) or 0.0
                last_social = to_float(last_point.get("socialHype")) or 0.0
                attention_velocity = pct_delta(last_social, first_social) or 0.0
                social_map[contract_address] = {
                    "social_rank": index,
                    "social_hype": to_float((item.get("socialHypeInfo") or {}).get("socialHype")) or 0.0,
                    "sentiment": (item.get("socialHypeInfo") or {}).get("sentiment") or "Unknown",
                    "summary": clip_text(
                        (item.get("socialHypeInfo") or {}).get("socialSummaryBriefTranslated")
                        or (item.get("socialHypeInfo") or {}).get("socialSummaryBrief")
                    ),
                    "symbol": meta.get("symbol"),
                    "kol_count": to_int((item.get("socialHypeInfo") or {}).get("kolCount")) or 0,
                    "attention_velocity_pct": round(attention_velocity, 2),
                }
            inflow_map: Dict[str, Dict[str, Any]] = {}
            for index, item in enumerate(chain_bundle.get("smart_money_inflow") or [], start=1):
                contract_address = str(item.get("ca") or "").lower()
                if not contract_address:
                    continue
                inflow_map[contract_address] = {
                    "inflow_rank": index,
                    "inflow": to_float(item.get("inflow")) or 0.0,
                    "traders": to_int(item.get("traders")) or 0,
                    "symbol": item.get("tokenName"),
                    "price_change": to_float(item.get("priceChangeRate")),
                    "liquidity": to_float(item.get("liquidity")),
                    "holders": to_int(item.get("holders")),
                    "token_risk_level": to_int(item.get("tokenRiskLevel")),
                    "market_cap": to_float(item.get("marketCap")),
                }
            for contract_address in sorted(set(social_map).intersection(inflow_map)):
                social = social_map[contract_address]
                inflow = inflow_map[contract_address]
                inflow_value = inflow["inflow"]
                social_value = social["social_hype"]
                resonance = clamp(
                    safe_log10(social_value) * 13.0
                    + safe_log10(abs(inflow_value) + 1.0) * 18.0
                    + max(0.0, 14.0 - social["social_rank"]) * 1.8
                    + min(inflow["traders"], 12) * 2.0
                    + max(0.0, social["attention_velocity_pct"]) * 0.22
                    - (10.0 if inflow_value < 0 else 0.0),
                    0.0,
                    100.0,
                )
                crossovers.append(
                    {
                        "chain_id": chain_id,
                        "chain_name": CHAIN_NAMES.get(chain_id, chain_id),
                        "contract_address": contract_address,
                        "symbol": social.get("symbol") or inflow.get("symbol") or "未知",
                        "social_rank": social["social_rank"],
                        "social_hype": round(social["social_hype"], 2),
                        "sentiment": social["sentiment"],
                        "smart_money_inflow": inflow["inflow"],
                        "smart_money_traders": inflow["traders"],
                        "price_change_24h": inflow["price_change"],
                        "liquidity": inflow["liquidity"],
                        "holders": inflow["holders"],
                        "market_cap": inflow["market_cap"],
                        "attention_velocity_pct": social["attention_velocity_pct"],
                        "resonance_score": round(resonance, 2),
                        "why": social["summary"] or "社交热度与聪明钱流入在同一代币上形成共振。",
                    }
                )
        crossovers.sort(key=lambda item: item["resonance_score"], reverse=True)
        return crossovers[:12]

    def build_narrative_radar(self, bundle: Dict[str, Dict[str, Any]], crossovers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        crossover_index: Dict[tuple[str, str], Dict[str, Any]] = {
            (item["chain_id"], item["contract_address"]): item for item in crossovers
        }
        radar: List[Dict[str, Any]] = []
        per_chain_limit = to_int(self.config.get("topic_limit_per_chain")) or 8
        for chain_id, chain_bundle in bundle.items():
            normalized: List[Dict[str, Any]] = []
            for topic in chain_bundle.get("topics") or []:
                snapshot = self.build_topic_token_snapshot(topic)
                lead = snapshot.get("lead_token") or {}
                topic_name = self.topic_name_from_raw(topic)
                progress = to_float(topic.get("progress")) or 0.0
                net_inflow = to_float(topic.get("topicNetInflow")) or 0.0
                net_inflow_1h = to_float(topic.get("topicNetInflow1h"))
                token_size = to_int(topic.get("tokenSize")) or snapshot.get("token_count") or 0
                overlap_items = [
                    crossover_index[(chain_id, str(token.get("contractAddress") or "").lower())]
                    for token in topic.get("tokenList") or []
                    if (chain_id, str(token.get("contractAddress") or "").lower()) in crossover_index
                ]
                overlap_symbols = dedupe_list(item.get("symbol") for item in overlap_items if item.get("symbol"))
                overlap_count = len(overlap_items)
                median_liquidity = snapshot.get("median_liquidity") or 0.0
                median_holders = snapshot.get("median_holders") or 0.0
                total_unique_trader_24h = snapshot.get("total_unique_trader_24h") or 0
                smart_money_token_count = snapshot.get("smart_money_token_count") or 0
                holder_concentration_pct = snapshot.get("holder_concentration_pct") or 0.0
                audit = self.summarize_audit(chain_id, str(lead.get("contract_address") or ""))
                attention_score = clamp(
                    progress * 0.55
                    + overlap_count * 7.0
                    + safe_log10(total_unique_trader_24h + 1) * 11.0
                    + (6.0 if to_int(topic.get("deepAnalysisFlag")) == 1 else 0.0),
                    0.0,
                    100.0,
                )
                money_score = clamp(
                    safe_log10(abs(net_inflow) + 1.0) * 18.0
                    + safe_log10(abs(lead.get("net_inflow") or 0.0) + 1.0) * 8.0
                    + (9.0 if net_inflow > 0 else -9.0)
                    + (7.0 if (net_inflow_1h or 0.0) > 0 else -5.0),
                    0.0,
                    100.0,
                )
                breadth_score = clamp(
                    min(token_size, 12) * 5.5
                    + safe_log10(total_unique_trader_24h + 1) * 12.0
                    + safe_log10(median_holders + 1) * 8.5,
                    0.0,
                    100.0,
                )
                tradability_score = clamp(
                    safe_log10(median_liquidity + 1) * 18.0
                    + safe_log10((lead.get("market_cap") or 0.0) + 1.0) * 7.5
                    + min((lead.get("holders") or 0) / 60.0, 12.0)
                    - max(0.0, holder_concentration_pct - 10.0) * 1.2
                    - max(0.0, ((audit.get("buy_tax") or 0.0) + (audit.get("sell_tax") or 0.0)) * 100.0 - 8.0) * 1.1,
                    0.0,
                    100.0,
                )
                momentum_score = clamp(
                    progress * 0.32
                    + safe_log10(abs(net_inflow_1h or 0.0) + 1.0) * 16.0
                    + max(0.0, average([lead.get("price_change_24h"), snapshot.get("average_price_change_24h")]) or 0.0) * 0.12,
                    0.0,
                    100.0,
                )
                confirmation_base_score = clamp(
                    overlap_count * 9.0
                    + smart_money_token_count * 5.0
                    + (6.0 if audit.get("verified") else 0.0)
                    + (7.0 if to_int(topic.get("deepAnalysisFlag")) == 1 else 0.0)
                    + min((lead.get("smart_money_holders") or 0) * 5.0, 16.0),
                    0.0,
                    100.0,
                )
                fragility_score = clamp(
                    (14.0 if median_liquidity < 50000 else 0.0)
                    + (10.0 if (net_inflow_1h or 0.0) < 0 else 0.0)
                    + max(0.0, holder_concentration_pct - 12.0) * 1.4
                    + (12.0 if audit.get("risk_band") == "High" else 6.0 if audit.get("risk_band") == "Medium" else 0.0)
                    + min(len(audit.get("hit_risks") or []) * 4.0, 18.0),
                    0.0,
                    100.0,
                )
                thesis = clip_text(
                    ((topic.get("aiSummary") or {}).get("aiSummaryEn"))
                    or ((topic.get("aiSummary") or {}).get("aiSummaryCn"))
                    or f"{topic_name} 正在形成同时具备注意力与资金确认的叙事聚集。"
                )
                item = {
                    "chain_id": chain_id,
                    "chain_name": CHAIN_NAMES.get(chain_id, chain_id),
                    "topic_id": topic.get("topicId"),
                    "topic_name": topic_name,
                    "topic_type": topic.get("type") or "General",
                    "progress_pct": round(progress, 2),
                    "net_inflow": net_inflow,
                    "net_inflow_1h": net_inflow_1h,
                    "token_count": token_size,
                    "deep_analysis": to_int(topic.get("deepAnalysisFlag")) == 1,
                    "topic_link": topic.get("topicLink"),
                    "thesis": thesis,
                    "create_time": ts_to_iso(topic.get("createTime")),
                    "viral_time": ts_to_iso(topic.get("viralTime")),
                    "rising_time": ts_to_iso(topic.get("risingTime")),
                    "lead_token": lead,
                    "satellite_tokens": snapshot.get("satellite_tokens") or [],
                    "token_symbols": snapshot.get("token_symbols") or [],
                    "median_liquidity": snapshot.get("median_liquidity"),
                    "median_holders": snapshot.get("median_holders"),
                    "total_unique_trader_24h": total_unique_trader_24h,
                    "smart_money_token_count": smart_money_token_count,
                    "holder_concentration_pct": holder_concentration_pct,
                    "attention_overlap_count": overlap_count,
                    "attention_overlap_symbols": overlap_symbols,
                    "attention_score": attention_score,
                    "money_score": money_score,
                    "breadth_score": breadth_score,
                    "tradability_score": tradability_score,
                    "momentum_score": momentum_score,
                    "confirmation_base_score": confirmation_base_score,
                    "catalyst_score": 0.0,
                    "fragility_score": fragility_score,
                    "audit": audit,
                    "catalyst_matches": [],
                }
                item["flags"] = self.build_topic_flags(item)
                self.finalize_topic_scores(item)
                normalized.append(item)
            normalized.sort(key=lambda item: item["narrative_strength_score"], reverse=True)
            radar.extend(normalized[:per_chain_limit])
        radar.sort(key=lambda item: item["narrative_strength_score"], reverse=True)
        return radar[:14]

    def build_signal_watch(self, bundle: Dict[str, Dict[str, Any]], radar: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contract_map: Dict[tuple[str, str], List[str]] = {}
        for topic in radar:
            lead_key = (topic.get("chain_id") or "", str((topic.get("lead_token") or {}).get("contract_address") or "").lower())
            if lead_key[1]:
                names = contract_map.setdefault(lead_key, [])
                if topic.get("topic_name"):
                    names.append(topic["topic_name"])
            for satellite in topic.get("satellite_tokens") or []:
                key = (topic.get("chain_id") or "", str(satellite.get("contract_address") or "").lower())
                if not key[1]:
                    continue
                existing = contract_map.setdefault(key, [])
                if topic.get("topic_name"):
                    existing.append(topic["topic_name"])
        alerts: List[Dict[str, Any]] = []
        for chain_id, chain_bundle in bundle.items():
            for item in chain_bundle.get("smart_signals") or []:
                direction = str(item.get("direction") or "").lower()
                smart_money_count = to_int(item.get("smartMoneyCount")) or 0
                exit_rate = to_float(item.get("exitRate")) or 0.0
                max_gain = to_float(item.get("maxGain")) or 0.0
                linked_narratives = dedupe_list(contract_map.get((chain_id, str(item.get("contractAddress") or "").lower()), []))
                linked_score = 12.0 if linked_narratives else 0.0
                freshness = clamp(
                    smart_money_count * 8.0
                    + (10.0 if direction == "buy" else 0.0)
                    + max(0.0, 35.0 - exit_rate) * 0.6
                    + max_gain * 35.0
                    + linked_score,
                    0.0,
                    100.0,
                )
                if freshness < 38 and not linked_narratives:
                    continue
                reason = "聪明钱信号"
                if linked_narratives:
                    reason = f"与叙事 {linked_narratives[0]} 直接关联"
                alerts.append(
                    {
                        "chain_id": chain_id,
                        "chain_name": CHAIN_NAMES.get(chain_id, chain_id),
                        "symbol": item.get("ticker"),
                        "contract_address": item.get("contractAddress"),
                        "direction": direction or "unknown",
                        "direction_label": direction_label(direction or "unknown"),
                        "smart_money_count": smart_money_count,
                        "alert_price": to_float(item.get("alertPrice")),
                        "current_price": to_float(item.get("currentPrice")),
                        "max_gain_pct": (to_float(item.get("maxGain")) or 0.0) * 100.0,
                        "exit_rate_pct": exit_rate,
                        "status": item.get("status") or "unknown",
                        "signal_status_label": signal_status_label(item.get("status") or "unknown"),
                        "signal_trigger_time": ts_to_iso(item.get("signalTriggerTime")),
                        "freshness_score": round(freshness, 2),
                        "linked_narratives": linked_narratives,
                        "reason": reason,
                    }
                )
        alerts.sort(key=lambda item: item["freshness_score"], reverse=True)
        return alerts[:10]

    def build_market_pulse(self, bundle: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        output = []
        for chain_id, chain_bundle in bundle.items():
            trending = [
                {
                    "symbol": item.get("symbol"),
                    "price_change_24h": to_float(item.get("percentChange24h")),
                    "volume_24h": to_float(item.get("volume24h")),
                    "market_cap": to_float(item.get("marketCap")),
                }
                for item in (chain_bundle.get("trending") or [])[:5]
            ]
            top_search = [
                {
                    "symbol": item.get("symbol"),
                    "price_change_24h": to_float(item.get("percentChange24h")),
                    "volume_24h": to_float(item.get("volume24h")),
                    "market_cap": to_float(item.get("marketCap")),
                }
                for item in (chain_bundle.get("top_search") or [])[:5]
            ]
            output.append(
                {
                    "chain_id": chain_id,
                    "chain_name": CHAIN_NAMES.get(chain_id, chain_id),
                    "trending": trending,
                    "top_search": top_search,
                    "pulse_score": round(
                        clamp(
                            safe_log10(sum(token.get("volume_24h") or 0.0 for token in trending) + 1.0) * 14.0
                            + len([token for token in trending if (token.get("price_change_24h") or 0.0) > 0]) * 7.0,
                            0.0,
                            100.0,
                        ),
                        2,
                    ),
                }
            )
        output.sort(key=lambda item: item["pulse_score"], reverse=True)
        return output

    def build_official_catalysts(self) -> List[Dict[str, Any]]:
        catalogs = self.safe_call("cms_article_list", self.client.get_announcement_catalogs, fallback=[])
        catalog_map = {to_int(catalog.get("catalogId")): catalog for catalog in catalogs}
        output: List[Dict[str, Any]] = []
        limit = to_int(self.config.get("announcement_limit_per_catalog")) or 3
        for catalog_id in self.config.get("announcement_catalog_ids") or []:
            catalog = catalog_map.get(to_int(catalog_id))
            if not catalog:
                continue
            for article in (catalog.get("articles") or [])[:limit]:
                code = str(article.get("code") or "")
                detail = self.safe_call(f"cms_article_detail:{code}", self.client.get_announcement_detail, code, fallback={})
                output.append(
                    {
                        "catalog_id": to_int(catalog.get("catalogId")),
                        "catalog_name": catalog.get("catalogName"),
                        "catalog_name_label": catalog_name_label(catalog.get("catalogName")),
                        "title": article.get("title"),
                        "article_code": code,
                        "publish_time": ts_to_iso(detail.get("publishDate") or article.get("releaseDate")),
                        "support_url": f"https://www.binance.com/zh-CN/support/announcement/detail/{code}",
                        "summary": body_json_to_summary(detail.get("body"), max_chars=220),
                    }
                )
        output.sort(key=lambda item: item.get("publish_time") or "", reverse=True)
        return output[:9]

    def attach_catalyst_matches(self, radar: List[Dict[str, Any]], catalysts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for topic in radar:
            matches: List[Dict[str, Any]] = []
            for article in catalysts:
                match_score = self.article_match_score(article, topic)
                if match_score < 26.0:
                    continue
                matches.append(
                    {
                        "title": article.get("title"),
                        "catalog_name": article.get("catalog_name"),
                        "catalog_name_label": article.get("catalog_name_label"),
                        "publish_time": article.get("publish_time"),
                        "support_url": article.get("support_url"),
                        "score": round(match_score, 2),
                    }
                )
            matches.sort(key=lambda item: item["score"], reverse=True)
            topic["catalyst_matches"] = matches[:3]
            topic["catalyst_score"] = clamp(sum(item["score"] for item in topic["catalyst_matches"]) / 2.0, 0.0, 100.0)
            if topic["catalyst_matches"]:
                topic["flags"] = dedupe_list([*topic.get("flags", []), "存在官方内容映射"])
            self.finalize_topic_scores(topic)
        return catalysts

    def build_narrative_memory(self, radar: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        memory: List[Dict[str, Any]] = []
        rank_lookup = {
            self.topic_key(item.get("chain_id") or "", item.get("topic_id"), item.get("topic_name")): index
            for index, item in enumerate(radar, start=1)
        }
        prev_rank_lookup = {
            self.topic_key(item.get("chain_id") or "", item.get("topic_id"), item.get("topic_name")): index
            for index, item in enumerate(self.previous_report.get("narrative_radar") or [], start=1)
        }
        for item in radar:
            key = self.topic_key(item.get("chain_id") or "", item.get("topic_id"), item.get("topic_name"))
            current_rank = rank_lookup.get(key)
            previous = self.find_previous_entry(item.get("chain_id") or "", item.get("topic_id"), item.get("topic_name"))
            previous_rank = prev_rank_lookup.get(key)
            previous_score = to_float((previous or {}).get("narrative_strength_score"))
            previous_inflow = to_float((previous or {}).get("net_inflow"))
            score_delta = None if previous_score is None else round((item["narrative_strength_score"] - previous_score), 2)
            inflow_delta = None if previous_inflow is None else round((item["net_inflow"] - previous_inflow), 2)
            rank_delta = None
            if current_rank is not None and previous_rank is not None:
                rank_delta = previous_rank - current_rank
            day_entry = self.find_24h_entry(item.get("chain_id") or "", item.get("topic_id"), item.get("topic_name"))
            day_score = to_float((day_entry or {}).get("narrative_strength_score"))
            day_delta = None if day_score is None else round((item["narrative_strength_score"] - day_score), 2)
            state = "New"
            if previous and previous_score is not None:
                state = "Continuing"
                if score_delta is not None and score_delta >= 8:
                    state = "Strengthening"
                elif score_delta is not None and score_delta <= -8:
                    state = "Weakening"
            elif day_entry and day_score is not None and day_score >= 40:
                state = "Returning"
            summary = f"{memory_state_label(state)}，当前分数 {item['narrative_strength_score']:.2f}"
            if score_delta is not None:
                summary += f"，较上次 {score_delta:+.2f}"
            if day_delta is not None:
                summary += f"，较 24h 参考 {day_delta:+.2f}"
            record = {
                "chain_name": item.get("chain_name"),
                "topic_name": item.get("topic_name"),
                "status": item.get("status"),
                "status_label": status_label(item.get("status")),
                "memory_state": state,
                "memory_state_label": memory_state_label(state),
                "current_rank": current_rank,
                "rank_delta": rank_delta,
                "score_delta": score_delta,
                "day_delta": day_delta,
                "inflow_delta": inflow_delta,
                "summary": summary,
            }
            item["memory_state"] = state
            item["memory_state_label"] = memory_state_label(state)
            item["rank_delta"] = rank_delta
            item["score_delta"] = score_delta
            item["day_delta"] = day_delta
            memory.append(record)
        priority = {"Strengthening": 0, "Returning": 1, "New": 2, "Continuing": 3, "Weakening": 4}
        memory.sort(key=lambda item: (priority.get(item["memory_state"], 9), -(item.get("score_delta") or -999)))
        return memory[:12]

    def build_rotation_map(self, radar: List[Dict[str, Any]], memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        chain_scores: Dict[str, Dict[str, Any]] = {}
        for item in radar:
            chain_name = str(item.get("chain_name") or "")
            stats = chain_scores.setdefault(
                chain_name,
                {"chain_name": chain_name, "narrative_count": 0, "score_sum": 0.0, "net_inflow_sum": 0.0, "confirmed_count": 0},
            )
            stats["narrative_count"] += 1
            stats["score_sum"] += item.get("narrative_strength_score") or 0.0
            stats["net_inflow_sum"] += item.get("net_inflow") or 0.0
            if item.get("status") == "Confirmed":
                stats["confirmed_count"] += 1
        chain_rotation = []
        for stats in chain_scores.values():
            avg_score = stats["score_sum"] / max(stats["narrative_count"], 1)
            chain_rotation.append(
                {
                    **stats,
                    "average_strength": round(avg_score, 2),
                    "rotation_heat": round(clamp(avg_score * 0.6 + safe_log10(abs(stats["net_inflow_sum"]) + 1.0) * 12.0, 0.0, 100.0), 2),
                }
            )
        chain_rotation.sort(key=lambda item: item["rotation_heat"], reverse=True)
        emerging = [
            {
                "topic_name": item.get("topic_name"),
                "chain_name": item.get("chain_name"),
                "memory_state": item.get("memory_state"),
                "narrative_strength_score": item.get("narrative_strength_score"),
                "why": item.get("status_reason"),
            }
            for item in radar
            if item.get("memory_state") in {"New", "Strengthening", "Returning"} and item.get("status") in {"Igniting", "Accelerating", "Confirmed"}
        ][: to_int(self.config.get("rotation_limit")) or 8]
        fading = [
            {
                "topic_name": item.get("topic_name"),
                "chain_name": item.get("chain_name"),
                "memory_state": item.get("memory_state"),
                "narrative_strength_score": item.get("narrative_strength_score"),
                "why": item.get("status_reason"),
            }
            for item in radar
            if item.get("memory_state") == "Weakening" or item.get("status") == "Cooling"
        ][: to_int(self.config.get("rotation_limit")) or 8]
        attention_leads = [
            {
                "topic_name": item.get("topic_name"),
                "chain_name": item.get("chain_name"),
                "attention_gap": round((item.get("attention_score") or 0.0) - (item.get("money_score") or 0.0), 2),
                "watch": "继续观察注意力能否转化为持续净流入。",
            }
            for item in radar
            if (item.get("attention_score") or 0.0) - (item.get("money_score") or 0.0) >= 15.0
        ][:6]
        capital_leads = [
            {
                "topic_name": item.get("topic_name"),
                "chain_name": item.get("chain_name"),
                "money_gap": round((item.get("money_score") or 0.0) - (item.get("attention_score") or 0.0), 2),
                "watch": "资金先于热度启动，继续观察能否扩散成真正主线。",
            }
            for item in radar
            if (item.get("money_score") or 0.0) - (item.get("attention_score") or 0.0) >= 12.0
        ][:6]
        hypotheses: List[Dict[str, Any]] = []
        top_chain = safe_first(chain_rotation) or {}
        top_emerging = safe_first(emerging) or {}
        top_fading = safe_first(fading) or {}
        if top_chain:
            hypotheses.append(
                {
                    "title": f"{top_chain['chain_name']} 正在承接最密集的叙事集合",
                    "summary": f"当前平均叙事强度为 {top_chain['average_strength']}，其中已确认叙事 {top_chain['confirmed_count']} 个。",
                }
            )
        if top_emerging:
            hypotheses.append(
                {
                    "title": f"{top_emerging['topic_name']} 正在向主线升级",
                    "summary": f"{top_emerging['chain_name']} 上该叙事处于“{memory_state_label(top_emerging['memory_state'])}”状态，值得持续跟踪。",
                }
            )
        if top_fading:
            hypotheses.append(
                {
                    "title": f"{top_fading['topic_name']} 需要防止叙事惯性误判",
                    "summary": f"{top_fading['chain_name']} 上该叙事已经边际转弱，不能再只看过去热度。",
                }
            )
        return {
            "chain_rotation": chain_rotation,
            "emerging": emerging,
            "fading": fading,
            "attention_leads": attention_leads,
            "capital_leads": capital_leads,
            "hypotheses": hypotheses[:6],
        }

    def build_false_narratives(self, radar: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for item in radar:
            attention = item.get("attention_score") or 0.0
            money = item.get("money_score") or 0.0
            confirmation = item.get("confirmation_score") or 0.0
            fragility = item.get("fragility_score") or 0.0
            risk = clamp(
                fragility * 0.52
                + max(0.0, attention - money) * 0.9
                + max(0.0, 45.0 - confirmation) * 0.8
                + (12.0 if item.get("status") == "Igniting" else 0.0),
                0.0,
                100.0,
            )
            reasons: List[str] = []
            if (item.get("median_liquidity") or 0.0) < 50000:
                reasons.append("流动性偏薄")
            if (item.get("net_inflow_1h") or 0.0) < 0:
                reasons.append("近 1 小时净流入转负")
            if (item.get("holder_concentration_pct") or 0.0) >= 15:
                reasons.append("龙头筹码集中度偏高")
            if (item.get("audit") or {}).get("risk_band") in {"Medium", "High"}:
                reasons.append(f"审计风险{risk_band_label((item.get('audit') or {}).get('risk_band'))}")
            if attention - money >= 15:
                reasons.append("热度领先于资金")
            if not reasons:
                reasons.append("确认层仍然偏薄")
            action_bias = "降权观察"
            if risk < 60:
                action_bias = "保守跟踪"
            record = {
                "topic_name": item.get("topic_name"),
                "chain_name": item.get("chain_name"),
                "status": item.get("status"),
                "false_narrative_risk_score": round(risk, 2),
                "reasons": reasons,
                "action_bias": action_bias,
                "lead_symbol": (item.get("lead_token") or {}).get("symbol"),
                "next_watch": item.get("next_watch"),
            }
            item["false_narrative_risk_score"] = record["false_narrative_risk_score"]
            records.append(record)
        records.sort(key=lambda item: item["false_narrative_risk_score"], reverse=True)
        limit = to_int(self.config.get("false_narrative_limit")) or 6
        return [item for item in records if item["false_narrative_risk_score"] >= 40][:limit]

    def build_quality_board(self, radar: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        board = [
            {
                "topic_name": item.get("topic_name"),
                "chain_name": item.get("chain_name"),
                "quality_score": item.get("quality_score"),
                "narrative_strength_score": item.get("narrative_strength_score"),
                "breadth_score": item.get("breadth_score"),
                "tradability_score": item.get("tradability_score"),
                "confirmation_score": item.get("confirmation_score"),
                "fragility_score": item.get("fragility_score"),
                "risk_band": (item.get("audit") or {}).get("risk_band"),
                "status": item.get("status"),
            }
            for item in radar
        ]
        board.sort(key=lambda item: (item["quality_score"] or 0.0, item["narrative_strength_score"] or 0.0), reverse=True)
        return board[:10]

    def build_narrative_playbooks(self, radar: List[Dict[str, Any]], false_narratives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        confirmed = [item for item in radar if item.get("status") == "Confirmed"]
        igniting = [item for item in radar if item.get("status") == "Igniting"]
        accelerating = [item for item in radar if item.get("status") == "Accelerating"]
        playbooks: List[Dict[str, Any]] = []
        top_confirmed = safe_first(confirmed) or {}
        if top_confirmed:
            playbooks.append(
                {
                    "title": f"主线跟踪：{top_confirmed.get('topic_name')}",
                    "persona": "研究 / 直播讲解",
                    "why_now": "这是当前确认度最高的主线，适合持续讲解和拆解。",
                    "actions": [
                        f"重点盯住龙头币 {((top_confirmed.get('lead_token') or {}).get('symbol') or '-')}",
                        "复核近 1 小时净流入是否继续为正",
                        "跟踪是否还有新增官方催化",
                    ],
                }
            )
        top_accelerating = safe_first(accelerating) or {}
        if top_accelerating:
            playbooks.append(
                {
                    "title": f"升级观察：{top_accelerating.get('topic_name')}",
                    "persona": "广场作者",
                    "why_now": "热度和资金正在同步强化，适合做“热点升级为主线”的内容。",
                    "actions": [
                        "对比本次和上一份报告的分数变化",
                        "关注是否出现新的官方映射",
                        "把“为什么现在强”拆成 3 个证据点",
                    ],
                }
            )
        top_igniting = safe_first(igniting) or {}
        if top_igniting:
            playbooks.append(
                {
                    "title": f"早期预警：{top_igniting.get('topic_name')}",
                    "persona": "选题编辑",
                    "why_now": "这类叙事往往最先带来注意力，但误判率也最高。",
                    "actions": [
                        "不要只写热度，也要写资金有没有确认",
                        "重点看龙头币流动性和集中度",
                        "如果 1h 净流入连续转负，就立刻降权",
                    ],
                }
            )
        top_false = safe_first(false_narratives) or {}
        if top_false:
            playbooks.append(
                {
                    "title": f"伪叙事风控：{top_false.get('topic_name')}",
                    "persona": "风控 / 审核",
                    "why_now": "这类叙事最容易因为惯性和单点热搜被放大。",
                    "actions": [
                        "优先复核流动性和集中度",
                        "复查审计和税率信息",
                        "避免把单点热搜包装成全市场主线",
                    ],
                }
            )
        if top_confirmed and top_igniting:
            playbooks.append(
                {
                    "title": "轮动对照稿",
                    "persona": "内容运营",
                    "why_now": "把成熟主线和早期火种放在一起，更能体现市场结构变化。",
                    "actions": [
                        f"把 {top_confirmed.get('topic_name')} 写成“已确认主线”",
                        f"把 {top_igniting.get('topic_name')} 写成“早期火种”",
                        "用同一套指标解释二者差异",
                    ],
                }
            )
        return playbooks[: to_int(self.config.get("playbook_limit")) or 6]

    def build_editorial_calendar(self, radar: List[Dict[str, Any]], catalysts: List[Dict[str, Any]], memory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        agenda: List[Dict[str, Any]] = []
        now = self.generated_at_dt
        for index, item in enumerate(radar[:4]):
            publish_time = (now + timedelta(hours=index * 2)).isoformat()
            agenda.append(
                {
                    "publish_time": publish_time,
                    "priority": "高" if index < 2 else "中",
                    "title": f"{item.get('topic_name')}：为什么它已经不只是一个热词",
                    "angle": item.get("status_reason"),
                    "evidence": [
                        f"叙事强度 {item.get('narrative_strength_score')}",
                        f"确认度 {item.get('confirmation_score')}",
                        f"龙头币 {((item.get('lead_token') or {}).get('symbol') or '-')}",
                    ],
                }
            )
        for article in catalysts[:3]:
            agenda.append(
                {
                    "publish_time": article.get("publish_time"),
                    "priority": "高",
                    "title": article.get("title"),
                    "angle": f"官方催化来自 {article.get('catalog_name_label') or article.get('catalog_name')}，适合继续做事件追踪。",
                    "evidence": [clip_text(article.get("summary"), 120) or "查看原文", article.get("support_url")],
                }
            )
        for item in memory[:3]:
            if item.get("memory_state") == "Weakening":
                agenda.append(
                    {
                        "publish_time": (now + timedelta(hours=6)).isoformat(),
                        "priority": "中",
                        "title": f"{item.get('topic_name')}：为什么现在应该降权",
                        "angle": item.get("summary"),
                        "evidence": ["避免叙事惯性", "说明降权逻辑", "保留下次观察条件"],
                    }
                )
        agenda.sort(key=lambda item: item.get("publish_time") or "")
        return agenda[: to_int(self.config.get("calendar_limit")) or 8]

    def build_overview(
        self,
        radar: List[Dict[str, Any]],
        crossovers: List[Dict[str, Any]],
        catalysts: List[Dict[str, Any]],
        market_pulse: List[Dict[str, Any]],
        memory: List[Dict[str, Any]],
        rotation_map: Dict[str, Any],
        false_narratives: List[Dict[str, Any]],
        quality_board: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        strongest = safe_first(radar) or {}
        hottest_chain = safe_first(market_pulse) or {}
        best_quality = safe_first(quality_board) or {}
        top_rotation = safe_first(rotation_map.get("hypotheses") or []) or {}
        memory_states = {"New": 0, "Strengthening": 0, "Returning": 0, "Continuing": 0, "Weakening": 0}
        for item in memory:
            state = item.get("memory_state") or "Continuing"
            memory_states[state] = memory_states.get(state, 0) + 1
        return {
            "tracked_narratives": len(radar),
            "resonance_tokens": len(crossovers),
            "official_catalysts": len(catalysts),
            "confirmed_narratives": sum(1 for item in radar if item.get("status") == "Confirmed"),
            "high_false_risk_count": sum(1 for item in false_narratives if (item.get("false_narrative_risk_score") or 0.0) >= 50),
            "strongest_narrative": strongest.get("topic_name"),
            "strongest_score": strongest.get("narrative_strength_score"),
            "strongest_chain": strongest.get("chain_name"),
            "hottest_chain_by_trending_volume": hottest_chain.get("chain_name"),
            "best_quality_narrative": best_quality.get("topic_name"),
            "best_quality_score": best_quality.get("quality_score"),
            "top_rotation_hypothesis": top_rotation.get("title"),
            "top_rotation_summary": top_rotation.get("summary"),
            "memory_states": memory_states,
        }

    def build_daily_brief(
        self,
        overview: Dict[str, Any],
        radar: List[Dict[str, Any]],
        crossovers: List[Dict[str, Any]],
        catalysts: List[Dict[str, Any]],
        memory: List[Dict[str, Any]],
        rotation_map: Dict[str, Any],
        false_narratives: List[Dict[str, Any]],
    ) -> List[str]:
        lines: List[str] = []
        strongest = safe_first(radar) or {}
        if strongest:
            lines.append(
                f"当前最强叙事是 {strongest.get('topic_name')}，所在链为 {strongest.get('chain_name')}，叙事强度 {strongest.get('narrative_strength_score')}。"
            )
        top_rotation = safe_first(rotation_map.get("hypotheses") or []) or {}
        if top_rotation:
            lines.append(top_rotation.get("summary") or top_rotation.get("title") or "")
        top_crossover = safe_first(crossovers) or {}
        if top_crossover:
            lines.append(
                f"注意力与资金共振最强的代币是 {top_crossover.get('symbol')}，来自 {top_crossover.get('chain_name')}，共振分数 {top_crossover.get('resonance_score')}。"
            )
        top_memory = safe_first(memory) or {}
        if top_memory:
            lines.append(f"记忆层显示 {top_memory.get('topic_name')} 当前处于“{top_memory.get('memory_state_label')}”状态。")
        if false_narratives:
            top_false = safe_first(false_narratives) or {}
            lines.append(
                f"当前最需要防止误判的叙事是 {top_false.get('topic_name')}，伪叙事风险 {top_false.get('false_narrative_risk_score')}。"
            )
        if catalysts:
            newest = safe_first(catalysts) or {}
            lines.append(f"最新官方催化来自 {newest.get('catalog_name_label') or newest.get('catalog_name')}：{newest.get('title')}。")
        return [line for line in lines if line]

    def build_square_draft(
        self,
        radar: List[Dict[str, Any]],
        crossovers: List[Dict[str, Any]],
        catalysts: List[Dict[str, Any]],
        memory: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        strongest = safe_first(radar) or {}
        crossover = safe_first(crossovers) or {}
        catalyst = safe_first(catalysts) or {}
        memory_item = safe_first(memory) or {}
        body_lines = [
            "今日币安叙事中枢观察：",
            f"1. 当前最强叙事：{strongest.get('topic_name') or '待确认'}（{strongest.get('chain_name') or '-'}，分数 {strongest.get('narrative_strength_score') or '-'}）",
            f"2. 共振最强代币：{crossover.get('symbol') or '待确认'}（{crossover.get('chain_name') or '-'}，共振 {crossover.get('resonance_score') or '-'}）",
            f"3. 记忆层变化：{memory_item.get('topic_name') or '待确认'} 当前为“{memory_item.get('memory_state_label') or '待确认'}”",
            f"4. 最新官方催化：{catalyst.get('title') or '暂无'}",
            "#Binance #NarrativeOS #OpenClaw",
        ]
        return {"title": "币安叙事中枢今日简报", "body": "\n".join(body_lines)}


def render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# 币安叙事中枢 2.0",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 跟踪叙事：{report['overview']['tracked_narratives']}",
        f"- 已确认叙事：{report['overview']['confirmed_narratives']}",
        f"- 高风险伪叙事：{report['overview']['high_false_risk_count']}",
        "",
        "## 今日摘要",
        "",
    ]
    for item in report["daily_brief"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 叙事雷达", ""])
    for item in report["narrative_radar"]:
        lines.append(
            f"- {item['topic_name']} | {item['chain_name']} | {item['status_label']} | 强度 {item['narrative_strength_score']:.2f} | 质量 {item['quality_score']:.2f}"
        )
        lines.append(f"  - 主题摘要：{item['thesis']}")
        lines.append(
            f"  - 资金 {item['money_score']:.2f} / 广度 {item['breadth_score']:.2f} / 确认 {item['confirmation_score']:.2f} / 脆弱性 {item['fragility_score']:.2f}"
        )
        lines.append(f"  - 下一个观察条件：{item['next_watch']}")
    lines.extend(["", "## 轮动地图", ""])
    for item in report["narrative_rotation_map"]["hypotheses"]:
        lines.append(f"- {item['title']}: {item['summary']}")
    lines.extend(["", "## 质量榜", ""])
    for item in report["narrative_quality_board"]:
        lines.append(
            f"- {item['topic_name']} | 质量 {item['quality_score']:.2f} | 可交易性 {item['tradability_score']:.2f} | 风险 {risk_band_label(item['risk_band'])}"
        )
    lines.extend(["", "## 伪叙事风险", ""])
    for item in report["risk_of_false_narratives"]:
        lines.append(
            f"- {item['topic_name']} | 风险 {item['false_narrative_risk_score']:.2f} | 原因：{'、'.join(item['reasons'])}"
        )
    lines.extend(["", "## 信号台", ""])
    for item in report["signal_watch"]:
        linked = " / ".join(item.get("linked_narratives") or []) or "暂无直接叙事映射"
        lines.append(
            f"- {item['symbol']} | {item['chain_name']} | {item.get('direction_label') or direction_label(item['direction'])} | 新鲜度 {item['freshness_score']:.2f} | {linked}"
        )
    lines.extend(["", "## 官方催化", ""])
    for item in report["official_catalysts"]:
        lines.append(f"- [{item['title']}]({item['support_url']})")
        if item.get("summary"):
            lines.append(f"  - {item['summary']}")
    lines.extend(["", "## Square 草稿", "", report["square_draft"]["body"], ""])
    if report["warnings"]:
        lines.extend(["## 警告", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def render_html(report: Dict[str, Any], template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8").replace("__REPORT_JSON__", json.dumps(report, ensure_ascii=False))


def resolve_history_dir(base_dir: Path, config: Dict[str, Any], explicit_history_dir: Optional[str]) -> Path:
    raw = explicit_history_dir or str(config.get("history_dir") or "output/history")
    path = Path(raw)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def load_history_reports(history_dir: Path, window_hours: int, now: datetime) -> List[Dict[str, Any]]:
    if not history_dir.exists():
        return []
    reports: List[Dict[str, Any]] = []
    for path in sorted(history_dir.glob("*.json"), reverse=True):
        report = load_report_if_exists(path)
        if not report:
            continue
        generated_at = iso_to_datetime(report.get("generated_at"))
        if not generated_at:
            continue
        if generated_at < now - timedelta(hours=window_hours):
            continue
        reports.append(report)
    reports.sort(key=lambda item: item.get("generated_at") or "", reverse=True)
    return reports


def save_history_snapshot(history_dir: Path, report: Dict[str, Any]) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = history_dir / f"report_{timestamp}.json"
    save_json(path, report)
    return path


def prune_history_snapshots(history_dir: Path, keep_files: int) -> None:
    if not history_dir.exists():
        return
    snapshots = sorted(history_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in snapshots[keep_files:]:
        try:
            path.unlink()
        except OSError:
            continue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Binance narrative report.")
    parser.add_argument("--config", default="config.example.json", help="Path to config JSON file")
    parser.add_argument("--json-output", default="output/latest_report.json", help="JSON output path")
    parser.add_argument("--markdown-output", default="output/latest_report.md", help="Markdown output path")
    parser.add_argument("--html-output", default="output/latest_report.html", help="HTML output path")
    parser.add_argument("--history-dir", default="", help="Directory used to store and read historical report snapshots")
    return parser.parse_args()


def main() -> int:
    ensure_utf8_stdout()
    args = parse_args()
    base_dir = Path(__file__).resolve().parent.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (base_dir / config_path).resolve()
    config = merge_dicts(DEFAULT_CONFIG, load_json(config_path, {})) if config_path.exists() else dict(DEFAULT_CONFIG)

    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    html_output = Path(args.html_output)
    if not json_output.is_absolute():
        json_output = (base_dir / json_output).resolve()
    if not markdown_output.is_absolute():
        markdown_output = (base_dir / markdown_output).resolve()
    if not html_output.is_absolute():
        html_output = (base_dir / html_output).resolve()

    previous_report = load_report_if_exists(json_output)
    history_dir = resolve_history_dir(base_dir, config, args.history_dir or None)
    history_reports = load_history_reports(
        history_dir,
        to_int(config.get("history_window_hours")) or 48,
        datetime.now(timezone.utc),
    )
    report = NarrativeBuilder(config, previous_report=previous_report, history_reports=history_reports).build()

    save_json(json_output, report)
    save_text(markdown_output, render_markdown(report))
    save_text(html_output, render_html(report, base_dir / "assets" / "report_template.html"))
    save_history_snapshot(history_dir, report)
    prune_history_snapshots(history_dir, to_int(config.get("history_keep_files")) or 96)

    print(f"JSON  : {json_output}")
    print(f"MD    : {markdown_output}")
    print(f"HTML  : {html_output}")
    print(
        "摘要：跟踪叙事 {0} 个，已确认叙事 {1} 个，高风险伪叙事 {2} 个。".format(
            report["overview"]["tracked_narratives"],
            report["overview"]["confirmed_narratives"],
            report["overview"]["high_false_risk_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
