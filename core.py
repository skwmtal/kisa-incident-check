"""사고별 공식 안내 확인 시제품의 핵심 로직: 사고 정보, 행동 체크리스트, 받은 문자 점검, 알림 문안."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse

# ---------- 가상 사고 데이터 ----------
# 실존 기업이 아니다. 도메인은 예시용 예약 도메인(.example)만 쓴다.


@dataclass
class Incident:
    id: str
    company: str
    sector: str
    reported: str
    leaked: list[str]
    official_domains: list[str]
    official_numbers: list[str]
    official_notice: str
    fake_samples: list[str]
    status: str
    updated: str


INCIDENTS = [
    Incident(
        id="I001", company="가상은행", sector="은행", reported="2026-10-02",
        leaked=["이름", "휴대전화번호", "계좌번호"],
        official_domains=["gasang-bank.example"], official_numbers=["1500-0101"],
        official_notice="[가상은행] 고객님의 정보 유출 여부는 가상은행 앱 또는 gasang-bank.example 공지에서 확인하실 수 있습니다. "
                        "가상은행은 문자로 앱 설치나 보상금 신청 링크를 보내지 않습니다.",
        fake_samples=["[가상은행] 개인정보 유출 피해보상금 지급 대상입니다. 신청: gasangbank-refund.example/apply",
                      "[긴급] 유출 계좌 보호를 위해 보안앱 설치 바랍니다 bit.ly/3xYz12"],
        status="통지 완료", updated="2026-10-06"),
    Incident(
        id="I002", company="예시증권", sector="증권", reported="2026-10-09",
        leaked=["이름", "휴대전화번호", "이메일", "아이디·비밀번호"],
        official_domains=["yesi-sec.example"], official_numbers=["1500-0202"],
        official_notice="[예시증권] 일부 고객의 로그인 정보 유출이 확인되었습니다. 예시증권 앱에서 비밀번호를 변경해 주십시오. "
                        "유출 여부 조회는 yesi-sec.example 에서만 가능합니다.",
        fake_samples=["[예시증권] 유출 정보 조회 및 환불 신청 yesi-sec-check.example",
                      "예시증권 고객센터입니다. 원격 점검을 위해 안내드린 앱을 설치해 주세요 010-1234-5678"],
        status="조사 중", updated="2026-10-12"),
    Incident(
        id="I003", company="샘플쇼핑", sector="온라인쇼핑", reported="2026-10-20",
        leaked=["이름", "휴대전화번호", "배송지 주소"],
        official_domains=["sample-shop.example"], official_numbers=["1500-0303"],
        official_notice="[샘플쇼핑] 배송지 정보 일부가 유출되었습니다. 결제 정보는 유출되지 않았습니다. 상세 안내: sample-shop.example/notice",
        fake_samples=["[샘플쇼핑] 배송 주소 오류로 반송 예정입니다. 주소 수정: me2.kr/a1b2",
                      "[샘플쇼핑] 유출 피해 확인 후 보상 포인트를 받으세요 sampleshop-event.example"],
        status="통지 완료", updated="2026-10-23"),
]

# ---------- 유출 항목별 할 일 ----------

ACTIONS: dict[str, list[str]] = {
    "휴대전화번호": ["모르는 번호의 문자 속 링크는 누르지 않기",
                    "번호도용문자 차단 서비스 신청",
                    "이동통신사 소액결제 차단 또는 한도 낮추기"],
    "이메일": ["유출 기업을 사칭한 메일의 첨부파일 열지 않기"],
    "아이디·비밀번호": ["해당 서비스 비밀번호 변경",
                      "같은 비밀번호를 쓰는 다른 사이트도 변경",
                      "2단계 인증 켜기"],
    "계좌번호": ["은행 앱의 입출금 알림 켜기"],
    "주민등록번호": ["명의도용 방지 서비스 가입"],
    "배송지 주소": ["택배·반송을 핑계로 한 주소 수정 문자 주의"],
}
COMMON_ACTIONS = ["의심 문자는 KISA 스미싱 확인 서비스로 확인",
                  "피해가 생기면 118 상담센터에 신고"]


def actions_for(incident: Incident) -> list[str]:
    out: list[str] = []
    for item in incident.leaked:
        for a in ACTIONS.get(item, []):
            if a not in out:
                out.append(a)
    return out + COMMON_ACTIONS


# ---------- 받은 문자 점검 ----------

SHORTENERS = {"bit.ly", "han.gl", "me2.kr", "url.kr", "vo.la", "t.ly", "tinyurl.com", "buly.kr", "c11.kr"}
BAIT_WORDS = ["보상금", "피해보상", "환불", "유출 확인", "유출 정보 조회", "보안앱", "앱 설치", "원격", "반송", "주소 수정", "포인트"]
URL_RE = re.compile(r"(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})(/[^\s]*)?", re.I)
PHONE_RE = re.compile(r"(?<!\d)(0\d{1,2}-?\d{3,4}-?\d{4}|1\d{3}-?\d{4})(?!\d)")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _host(url: str) -> str:
    u = url if "://" in url else "http://" + url
    h = (urlparse(u).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _official(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _lookalike(host: str, domains: list[str]) -> str | None:
    """공식 도메인과 비슷하지만 다른 주소."""
    core = lambda d: re.sub(r"[^a-z0-9]", "", d.split(".")[0])
    for d in domains:
        a, b = core(host), core(d)
        if b and (b in a or SequenceMatcher(None, a, b).ratio() >= 0.75):
            return d
    return None


@dataclass
class Check:
    verdict: str  # 공식 채널 일치 / 사칭 의심 / 주의 / 판단 어려움
    reasons: list[str] = field(default_factory=list)
    incident: str | None = None


def check_message(text: str, incidents: list[Incident] = INCIDENTS) -> Check:
    hosts = [_host(m.group(0)) for m in URL_RE.finditer(text)]
    numbers = [_digits(m.group(0)) for m in PHONE_RE.finditer(text)]
    mentioned = [i for i in incidents if i.company in text]
    pool = mentioned or incidents
    reasons: list[str] = []
    suspicious = False
    official_hit = False
    related = mentioned[0].id if mentioned else None

    for h in hosts:
        owner = next((i for i in pool if _official(h, i.official_domains)), None)
        if owner:
            official_hit = True
            related = related or owner.id
            reasons.append(f"주소 {h}는 {owner.company}의 공식 주소 목록과 일치")
            continue
        if h in SHORTENERS:
            suspicious = True
            reasons.append(f"단축 주소({h})는 실제 목적지를 숨길 수 있음")
            continue
        for i in pool:
            d = _lookalike(h, i.official_domains)
            if d:
                suspicious = True
                related = related or i.id
                reasons.append(f"주소 {h}는 {i.company} 공식 주소({d})와 비슷하지만 다름")
                break
        else:
            if mentioned:
                suspicious = True
                reasons.append(f"주소 {h}는 {mentioned[0].company}의 공식 주소 목록에 없음")
    for n in numbers:
        owner = next((i for i in pool if n in {_digits(x) for x in i.official_numbers}), None)
        if owner:
            official_hit = True
            reasons.append(f"번호 {n}는 {owner.company} 공식 번호와 일치")
        elif mentioned:
            suspicious = True
            reasons.append(f"번호 {n}는 {mentioned[0].company}의 공식 번호 목록에 없음")
    bait = [w for w in BAIT_WORDS if w in text]
    if bait:
        reasons.append("사칭 문자에 자주 쓰이는 표현: " + ", ".join(bait))
    if ".apk" in text.lower():
        suspicious = True
        reasons.append("설치 파일(.apk) 링크가 있음")

    if suspicious:
        verdict = "사칭 의심"
    elif official_hit:
        verdict = "공식 채널 일치"
    elif bait:
        verdict = "주의"
    else:
        verdict = "판단 어려움"
    if not reasons:
        reasons.append("공식 주소나 번호, 사칭 표현을 찾지 못함")
    return Check(verdict, reasons, related)


# ---------- 알림 문안 ----------

def alert_text(incident: Incident) -> str:
    steps = actions_for(incident)[:3]
    return "\n".join([
        f"[보호나라 알림] {incident.company} 개인정보 유출 사고 안내",
        f"유출 항목: {', '.join(incident.leaked)}",
        f"공식 안내는 {', '.join(incident.official_domains)} 와 {', '.join(incident.official_numbers)} 에서만 확인하세요.",
        "보상금·환불·앱 설치를 요구하는 문자는 사칭일 수 있습니다.",
        "지금 할 일: " + " / ".join(steps),
    ])
