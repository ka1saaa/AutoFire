import unittest

from autofire.ocr import parse_contact_candidates


class OCRParsingTests(unittest.TestCase):
    def test_filters_common_message_panel_noise(self) -> None:
        text = """
        消息
        搜索
        小王
        12:30
        3分钟前
        小李
        在线
        小王
        """

        self.assertEqual(parse_contact_candidates(text), ["小王", "小李"])

    def test_keeps_editable_contact_lines(self) -> None:
        text = """
        阿明|同学
        Lemon
        今天
        """

        self.assertEqual(parse_contact_candidates(text), ["阿明|同学", "Lemon"])


if __name__ == "__main__":
    unittest.main()
