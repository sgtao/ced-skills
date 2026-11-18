"""字幕トラックの選択（select_caption_track）の回帰テスト。

英語の動画は language が en-US などの地域付きになり、字幕のキー（en）と一致しなかった。
地域を外した形も候補にして、字幕が取れるようにしたことを確かめる。
実行: python3 tests/test_caption_track.py
"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/ced-url-to-md/scripts"
sys.path.insert(0, str(SCRIPTS))

import youtube_to_md  # noqa: E402

J = [{"ext": "json3", "url": "https://x/j"}]


class CaptionTrackTest(unittest.TestCase):
    def test_region_tag_matches_base_auto_orig(self):
        info = {"language": "en-US", "automatic_captions": {"en": J, "en-orig": J}}
        self.assertEqual(youtube_to_md.select_caption_track(info), ("en", "https://x/j", "auto"))

    def test_region_tag_matches_base_auto_only(self):
        info = {"language": "en-US", "automatic_captions": {"en": J}}
        self.assertEqual(youtube_to_md.select_caption_track(info), ("en", "https://x/j", "auto"))

    def test_plain_ja_auto_orig(self):
        info = {"language": "ja", "automatic_captions": {"ja-orig": J}}
        self.assertEqual(youtube_to_md.select_caption_track(info), ("ja", "https://x/j", "auto"))

    def test_manual_preferred_over_auto(self):
        info = {"language": "ja", "subtitles": {"ja": J}, "automatic_captions": {"ja-orig": J}}
        self.assertEqual(youtube_to_md.select_caption_track(info), ("ja", "https://x/j", "manual"))

    def test_no_matching_track_returns_none(self):
        info = {"language": "en-US", "automatic_captions": {"fr": J}}
        self.assertIsNone(youtube_to_md.select_caption_track(info))


if __name__ == "__main__":
    unittest.main()
