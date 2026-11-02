"""
리콜 대상 범위 확인

같은 인증번호·모델이라도 리콜은 '특정 제조사·특정 생산 기간'에만 해당되는 경우가 많습니다.
예) "리콜 대상은 ... 제조자가 Dongguan Ganna ... 로 표기된 2025년 7월~2025년 12월 생산분에 한합니다.
     Huizhou Ligao Cheng ... 표기 제품은 리콜 대상이 아닙니다."

리콜 공고 문구에서 대상/제외 제조사와 생산 기간을 읽고, 사진 라벨의 제조사·제조일과 비교합니다.

결과 scope:
  - "in_scope"     : 리콜 대상 (조건이 없거나, 제조사·기간이 모두 맞음)
  - "out_of_scope" : 리콜 대상 아님 (제외 제조사이거나, 다른 제조사이거나, 생산 기간 밖)
  - "check"        : 직접 확인 필요 (라벨 정보가 부족해서 판단할 수 없음)
"""
import re
from typing import Any, Dict, List, Optional, Tuple

_TEXT_FIELDS = ("publishActionDscr", "harmDscr", "accidentCaseDscr", "recallDscr", "etcDscr", "remark")

_COMPANY_RE = re.compile(
    r"[A-Z][A-Za-z0-9&\-]*(?:\s+[A-Za-z0-9&\-]+){0,8}?\s*"
    r"(?:Co\.,?\s*Ltd\.?|Co\.?\s*,?\s*Limited|Ltd\.?|Limited|Inc\.?|Corporation|Corp\.?|LLC|GmbH)"
)
_SUFFIX_WORDS = {"co", "ltd", "limited", "inc", "corporation", "corp", "llc", "gmbh", "company"}
_EXCLUDE_WORDS = ("아닙니다", "아님", "제외", "해당되지 않", "해당하지 않", "해당 없", "무관")
_CONDITION_WORDS = ("리콜 대상은", "에 한합니다", "에 한함", "대상이 아닙니다", "생산분", "제조분", "제조자가", "제조사가")

_RANGE_RE = re.compile(
    r"(20\d\d)\s*[년.\-/]\s*(\d{1,2})\s*월?\s*[~\-–～부터]+\s*(?:(20\d\d)\s*[년.\-/]\s*)?(\d{1,2})\s*월?"
)
_DATE_RE = re.compile(r"(20\d\d)\s*[년.\-/]\s*(\d{1,2})")


def _words(name: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in _SUFFIX_WORDS]


def _core(name: str) -> str:
    """회사 이름의 앞 두 단어(예: 'dongguan ganna')를 붙여서 비교용 핵심 이름으로 만듭니다."""
    return "".join(_words(name)[:2])


def _same_company(company: str, label_maker: str) -> bool:
    core = _core(company)
    label = "".join(_words(label_maker))
    return bool(core) and len(core) >= 6 and core in label


def _recall_text(item: Dict[str, Any]) -> str:
    parts = [str(item.get(k) or "") for k in _TEXT_FIELDS]
    return "\n".join(p for p in parts if p and p.lower() != "none")


def _find_companies(text: str) -> Tuple[List[str], List[str]]:
    """공고 문구에서 리콜 대상 제조사와 제외 제조사를 나눕니다."""
    matches = list(_COMPANY_RE.finditer(text))
    included, excluded = [], []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        window = text[m.end():min(end, m.end() + 80)]
        name = m.group(0).strip()
        (excluded if any(w in window for w in _EXCLUDE_WORDS) else included).append(name)
    return included, excluded


def _parse_range(text: str) -> Optional[Tuple[int, int]]:
    m = _RANGE_RE.search(text)
    if not m:
        return None
    y1, m1, y2, m2 = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(1)), int(m.group(4))
    if not (1 <= m1 <= 12 and 1 <= m2 <= 12):
        return None
    return y1 * 12 + m1, y2 * 12 + m2


def _parse_label_date(label_date: Any) -> Optional[int]:
    if not label_date:
        return None
    m = _DATE_RE.search(str(label_date))
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return y * 12 + mo if 1 <= mo <= 12 else None


def _fmt(ym: int) -> str:
    y, m = divmod(ym - 1, 12)
    return f"{y}년 {m + 1}월"


def scope_sentence(item: Dict[str, Any]) -> str:
    """공고 문구 중 '리콜 대상은 ~' 처럼 대상 범위를 설명하는 부분만 뽑습니다."""
    text = _recall_text(item)
    idx = text.find("리콜 대상은")
    if idx < 0:
        for w in ("생산분", "제조분", "에 한합니다"):
            idx = text.find(w)
            if idx >= 0:
                idx = max(text.rfind("\n", 0, idx) + 1, 0)
                break
    return text[idx:].strip() if idx >= 0 else ""


def check_recall_scope(item: Dict[str, Any], label_maker: str = "", label_date: Any = None) -> Dict[str, str]:
    text = _recall_text(item)
    has_condition = any(w in text for w in _CONDITION_WORDS)
    if not has_condition:
        return {"scope": "in_scope", "reason": "리콜 공고에 제조사·생산 기간 조건이 없어 같은 모델 전체가 대상이에요."}

    included, excluded = _find_companies(text)
    period = _parse_range(text)
    period_txt = f"{_fmt(period[0])}~{_fmt(period[1])}" if period else ""
    label_ym = _parse_label_date(label_date)
    label_maker = (label_maker or "").strip()

    if not label_maker or label_maker.lower() in ("null", "none", "-"):
        need = "제조사와 제조일을" if period else "제조사를"
        return {"scope": "check",
                "reason": f"이 리콜은 특정 제품만 대상이에요. 사진에서 {need} 읽지 못해 대상인지 판단할 수 없어요. 아래 '리콜 대상 범위'와 제품 라벨을 비교해 주세요."}

    for c in excluded:
        if _same_company(c, label_maker):
            return {"scope": "out_of_scope",
                    "reason": f"라벨의 제조사({c})는 리콜 공고에서 '대상이 아니다'라고 밝힌 제조사예요."}

    maker_match = next((c for c in included if _same_company(c, label_maker)), None)
    if included and not maker_match:
        return {"scope": "out_of_scope",
                "reason": f"리콜 대상 제조사는 {', '.join(included)}인데, 라벨의 제조사는 {label_maker}로 달라요."}

    if period:
        if label_ym is None:
            who = f"제조사({maker_match})는 리콜 대상과 같아요" if maker_match else "같은 모델이에요"
            return {"scope": "check",
                    "reason": f"{who}. 생산 시기가 {period_txt}이면 리콜 대상이에요. 제품 본체 라벨의 제조일을 확인해 주세요."}
        if not (period[0] <= label_ym <= period[1]):
            return {"scope": "out_of_scope",
                    "reason": f"라벨의 제조일({_fmt(label_ym)})이 리콜 대상 생산 기간({period_txt}) 밖이에요."}
        return {"scope": "in_scope",
                "reason": f"제조사와 제조일({_fmt(label_ym)})이 리콜 대상 조건({period_txt} 생산분)에 해당해요."}

    if maker_match:
        return {"scope": "in_scope", "reason": f"라벨의 제조사({maker_match})가 리콜 대상 제조사와 같아요."}
    return {"scope": "check", "reason": "리콜 대상 조건이 있지만 라벨 정보만으로는 판단하기 어려워요. 아래 '리콜 대상 범위'를 확인해 주세요."}
