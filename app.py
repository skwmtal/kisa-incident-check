"""사고별 공식 안내 확인 시제품 화면 (Streamlit). 실행: streamlit run app.py"""
import html

import pandas as pd
import streamlit as st

from core import INCIDENTS, actions_for, alert_text, check_message

st.set_page_config(page_title="진짜 안내 확인", layout="wide")

COLORS = {"공식 채널 일치": "#e2efda", "사칭 의심": "#f8d7da", "주의": "#fff3c4", "판단 어려움": "#eef2f7"}
by_id = {i.id: i for i in INCIDENTS}

st.title("개인정보 유출 사고별 진짜 안내 확인")
st.caption("모두의 KISA 국민참여예산 아이디어 제안용 시연 시제품 · KISA 공식 서비스가 아닙니다")
st.info("사고와 기업은 모두 **가상**이고, 주소는 예시용 예약 도메인(.example)입니다. "
        "실제 운영 시에는 유출 신고 때 기업이 공식 안내 주소와 번호를 등록하고, 보호나라가 사고별 안내 페이지를 엽니다.")

tab_page, tab_check, tab_admin = st.tabs(["사고별 안내 페이지", "받은 문자 확인", "담당자: 등록·알림"])

with tab_page:
    rows = [{"기업": i.company, "업종": i.sector, "신고일": i.reported, "유출 항목": ", ".join(i.leaked),
             "상태": i.status, "최근 갱신": i.updated} for i in INCIDENTS]
    st.table(pd.DataFrame(rows).style.hide(axis="index"))
    pick = st.selectbox("사고 선택", [i.id for i in INCIDENTS], format_func=lambda x: f"{by_id[x].company} ({by_id[x].reported})")
    inc = by_id[pick]
    left, right = st.columns([1, 1])
    with left:
        st.subheader(f"{inc.company} 공식 안내 채널")
        st.markdown("**공식 주소:** " + ", ".join(f"`{d}`" for d in inc.official_domains))
        st.markdown("**공식 번호:** " + ", ".join(inc.official_numbers))
        st.markdown("**기업 공식 통지 문구**")
        st.success(inc.official_notice)
        st.markdown("**지금 돌고 있는 사칭 문자 예시**")
        for s in inc.fake_samples:
            st.error(s)
    with right:
        st.subheader("지금 할 일")
        for a in actions_for(inc):
            st.checkbox(a, key=f"{inc.id}-{a}")
        st.caption("유출 항목에 맞춰 할 일이 자동으로 정해집니다.")

with tab_check:
    st.write("받은 문자를 붙여 넣으면 사고별 공식 주소·번호와 대조합니다. 최종 판별은 KISA 스미싱 확인 서비스로 연결합니다.")
    samples = {"직접 입력": ""}
    for i in INCIDENTS:
        samples[f"{i.company} 공식 통지"] = i.official_notice
        for n, s in enumerate(i.fake_samples, 1):
            samples[f"{i.company} 사칭 예시 {n}"] = s
    choice = st.selectbox("예시 문자 불러오기", list(samples))
    text = st.text_area("받은 문자", value=samples[choice], height=110)
    if text.strip():
        r = check_message(text)
        st.html(f"<div style='background:{COLORS[r.verdict]};border-radius:8px;padding:14px 18px;font-size:20px;font-weight:700'>"
                f"{html.escape(r.verdict)}</div>")
        for reason in r.reasons:
            st.write("- " + reason)
        if r.incident:
            st.caption(f"관련 사고: {by_id[r.incident].company} 안내 페이지에서 공식 채널과 할 일을 확인하세요.")
        st.caption("이 점검은 공식 목록과의 대조 결과이며, 안전을 보장하지 않습니다.")

with tab_admin:
    st.write("기업이 유출 신고 때 공식 채널을 등록하면, 담당자가 확인한 뒤 안내 페이지와 알림을 엽니다.")
    with st.form("register"):
        c1, c2 = st.columns(2)
        company = c1.text_input("기업명", "가상카드")
        domain = c2.text_input("공식 주소", "gasang-card.example")
        number = c1.text_input("공식 번호", "1500-0404")
        leaked = c2.multiselect("유출 항목", ["이름", "휴대전화번호", "이메일", "아이디·비밀번호", "계좌번호", "주민등록번호", "배송지 주소"],
                                default=["이름", "휴대전화번호", "계좌번호"])
        submitted = st.form_submit_button("안내 페이지 미리보기")
    if submitted:
        from core import Incident
        new = Incident(id="NEW", company=company, sector="-", reported="-", leaked=leaked, official_domains=[domain],
                       official_numbers=[number], official_notice="", fake_samples=[], status="등록 대기", updated="-")
        st.markdown("**카카오톡 보호나라 채널 알림 미리보기**")
        st.code(alert_text(new), language=None)
        st.markdown("**자동으로 정해진 할 일**")
        for a in actions_for(new):
            st.write("- " + a)
