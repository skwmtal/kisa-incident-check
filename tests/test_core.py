import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import INCIDENTS, actions_for, alert_text, check_message


class CheckTest(unittest.TestCase):
    def test_official_notice_matches(self):
        r = check_message(INCIDENTS[0].official_notice)
        self.assertEqual(r.verdict, "공식 채널 일치")

    def test_lookalike_domain_is_flagged(self):
        r = check_message("[가상은행] 피해보상금 신청 gasangbank-refund.example/apply")
        self.assertEqual(r.verdict, "사칭 의심")
        self.assertEqual(r.incident, "I001")

    def test_shortener_is_flagged(self):
        self.assertEqual(check_message("[샘플쇼핑] 주소 수정: me2.kr/a1b2").verdict, "사칭 의심")

    def test_unknown_number_for_named_company(self):
        r = check_message("예시증권 고객센터입니다. 앱을 설치해 주세요 010-1234-5678")
        self.assertEqual(r.verdict, "사칭 의심")

    def test_official_number_matches(self):
        self.assertEqual(check_message("예시증권 고객센터 1500-0202").verdict, "공식 채널 일치")

    def test_all_samples_are_flagged(self):
        for inc in INCIDENTS:
            for s in inc.fake_samples:
                self.assertEqual(check_message(s).verdict, "사칭 의심", s)

    def test_plain_text_is_unclear(self):
        self.assertEqual(check_message("오늘 저녁 7시에 만나요").verdict, "판단 어려움")


class ActionTest(unittest.TestCase):
    def test_actions_follow_leaked_items(self):
        acts = actions_for(INCIDENTS[1])
        self.assertIn("2단계 인증 켜기", acts)
        self.assertEqual(acts[-1], "피해가 생기면 118 상담센터에 신고")

    def test_alert_contains_official_channel(self):
        t = alert_text(INCIDENTS[2])
        self.assertIn("sample-shop.example", t)
        self.assertIn("1500-0303", t)


if __name__ == "__main__":
    unittest.main()
