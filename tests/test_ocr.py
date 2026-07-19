import unittest

from autofire.ocr import OCRLine, parse_contact_candidates, parse_contact_candidates_from_lines


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

    def test_extracts_only_douyin_chat_name_rows(self) -> None:
        width = 930
        height = 2016
        lines = [
            OCRLine("18:28", 55, 38, 120, 40, width, height),
            OCRLine("消息", 423, 120, 100, 46, width, height),
            OCRLine("LNL 火 62", 205, 232, 160, 45, width, height),
            OCRLine("在线", 205, 298, 80, 32, width, height),
            OCRLine("40分钟前", 777, 240, 100, 30, width, height),
            OCRLine("aaa 洛 圣 都 富 兰 克 林 0 96", 205, 404, 440, 45, width, height),
            OCRLine("向你打了个招呼", 205, 469, 260, 31, width, height),
            OCRLine("Freya 火 5", 205, 576, 210, 45, width, height),
            OCRLine("和你一起续火花", 205, 636, 250, 31, width, height),
            OCRLine("迷彦.", 205, 1255, 110, 45, width, height),
            OCRLine("[分享图文]", 205, 1320, 170, 31, width, height),
            OCRLine("3", 370, 1655, 30, 26, width, height),
            OCRLine("首页", 51, 1840, 100, 45, width, height),
        ]

        self.assertEqual(
            parse_contact_candidates_from_lines(lines),
            ["LNL", "aaa洛圣都富兰克林", "Freya", "迷彦."],
        )


if __name__ == "__main__":
    unittest.main()
