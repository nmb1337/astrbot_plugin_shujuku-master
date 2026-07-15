"""Focused regression checks for template-editor data and rendering helpers."""

from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_plugin_module():
    """Load the plugin without requiring a running AstrBot installation."""
    if "astrbot" not in sys.modules:
        astrbot = types.ModuleType("astrbot")
        api = types.ModuleType("astrbot.api")
        event = types.ModuleType("astrbot.api.event")
        star = types.ModuleType("astrbot.api.star")
        quart = types.ModuleType("quart")

        class Filter:
            class EventMessageType:
                ALL = "all"

            def __getattr__(self, _name):
                return lambda *_args, **_kwargs: lambda func: func

        class Star:
            def __init__(self, _context=None):
                pass

        api.logger = logging.getLogger("template-management-tests")
        event.AstrMessageEvent = object
        event.filter = Filter()
        star.Context = object
        star.Star = Star
        star.register = lambda *_args, **_kwargs: lambda cls: cls
        quart.jsonify = lambda value: value
        quart.request = object()

        async def send_file(*_args, **_kwargs):
            return None

        quart.send_file = send_file
        sys.modules.update(
            {
                "astrbot": astrbot,
                "astrbot.api": api,
                "astrbot.api.event": event,
                "astrbot.api.star": star,
                "quart": quart,
            }
        )

    spec = importlib.util.spec_from_file_location("shujuku_plugin_for_tests", REPO_ROOT / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLUGIN = load_plugin_module()


def plugin_instance():
    instance = PLUGIN.JubenNpcPlugin.__new__(PLUGIN.JubenNpcPlugin)
    instance.characters = [
        {"id": "linger", "kind": PLUGIN.COMPANION_KIND},
        {"id": "linger_skin", "kind": PLUGIN.SKIN_KIND, "parent_id": "linger"},
    ]
    instance._font_cache = {}
    instance._warned_missing_font = False
    return instance


class TemplateManagementTests(unittest.TestCase):
    def test_rows_can_be_deleted_and_keep_font_inheritance(self):
        instance = plugin_instance()
        template = instance._normalize_checkin_template(
            {
                "id": "my_checkin",
                "name": "我的打卡",
                "font_family": "msyh",
                "texts": {
                    "custom": {
                        "text": "{message}",
                        "x": 0.31,
                        "y": 0.42,
                        "size": 0.035,
                        "font_family": "inherit",
                        "bold": "false",
                    }
                },
            }
        )

        self.assertEqual(set(template["texts"]), {"custom"})
        self.assertEqual(template["texts"]["custom"]["font_family"], "inherit")
        self.assertFalse(template["texts"]["custom"]["bold"])

    def test_message_limit_and_boolean_normalization(self):
        instance = plugin_instance()
        self.assertEqual(len(instance._normalize_checkin_messages(["a", "b", "c", "d", "e", "f"])), 5)
        self.assertTrue(instance._template_bool("true"))
        self.assertFalse(instance._template_bool("false"))
        self.assertEqual(instance._normalize_text_font_family("not-a-font"), "inherit")

    def test_background_file_list_uses_only_supported_images(self):
        instance = plugin_instance()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            Image.new("RGB", (20, 10), "red").save(directory / "B.JPG")
            Image.new("RGB", (20, 10), "blue").save(directory / "a.png")
            (directory / "ignore.gif").write_bytes(b"not an image")
            (directory / "notes.txt").write_text("ignore", encoding="utf-8")

            assets = instance._list_visual_assets(directory)

        self.assertEqual([asset["filename"] for asset in assets], ["a.png", "B.JPG"])
        self.assertTrue(all(asset["preview"].startswith("data:image/jpeg;base64,") for asset in assets))

    def test_text_position_and_bold_affect_the_rendered_card(self):
        instance = plugin_instance()
        with tempfile.TemporaryDirectory() as temporary:
            instance.font_dir = Path(temporary)
            template = {
                "font_family": "default",
                "texts": {
                    "line": {
                        "text": "Bold",
                        "x": 0.50,
                        "y": 0.25,
                        "size": 0.08,
                        "color": "#123456",
                        "font_family": "inherit",
                        "bold": False,
                    }
                },
            }
            plain = Image.new("RGBA", (400, 200), "white")
            instance._draw_template_texts(ImageDraw.Draw(plain), template, {}, plain.size)
            template["texts"]["line"]["bold"] = True
            bold = Image.new("RGBA", (400, 200), "white")
            instance._draw_template_texts(ImageDraw.Draw(bold), template, {}, bold.size)

        self.assertNotEqual(plain.tobytes(), bold.tobytes())
        difference = ImageChops.difference(plain, Image.new("RGBA", plain.size, "white"))
        bbox = difference.getbbox()
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(bbox[0], 200)
        self.assertGreaterEqual(bbox[1], 50)

    def test_template_selection_prefers_equipped_skin_then_companion_then_general(self):
        instance = plugin_instance()
        player = {"current_skin": "linger_skin", "skins": {"linger_skin": {}}}
        templates = [
            {"id": "general", "bound_entry_id": "", "enabled": True, "priority": 99},
            {"id": "companion", "bound_entry_id": "linger", "enabled": True, "priority": 1},
            {"id": "skin", "bound_entry_id": "linger_skin", "enabled": True, "priority": 0},
        ]

        selected = instance._select_role_template(templates, player, "linger", {"id": "fallback"})
        self.assertEqual(selected["id"], "skin")

        player["current_skin"] = ""
        selected = instance._select_role_template(templates, player, "linger", {"id": "fallback"})
        self.assertEqual(selected["id"], "companion")

        selected = instance._select_role_template(templates, player, "unknown", {"id": "fallback"})
        self.assertEqual(selected["id"], "general")

    def test_equipped_skin_overrides_status_text_values(self):
        instance = plugin_instance()
        companion = {
            "id": "linger",
            "kind": PLUGIN.COMPANION_KIND,
            "name": "同伴资料",
            "english_name": "Companion Profile",
            "quality": "SR",
            "bonus": "同伴经验 +5%",
            "skills": [["同伴二星", "同伴二星描述"], ["同伴三星", "同伴三星描述"], ["同伴五星", "同伴五星描述"]],
            "colors": ["#123456", "#abcdef", "#0f172a"],
        }
        skin = {
            "id": "linger_skin",
            "kind": PLUGIN.SKIN_KIND,
            "parent_id": "linger",
            "name": "皮肤资料",
            "english_name": "Skin Profile",
            "quality": "SSR",
            "bonus": "皮肤经验 +12%",
            "skills": [["皮肤二星", "皮肤二星描述"], ["皮肤三星", "皮肤三星描述"], ["皮肤五星", "皮肤五星描述"]],
        }
        instance.characters = [companion, skin]
        captured = {}
        instance._draw_template_texts = lambda _draw, _template, values, _size: captured.update(values)
        player = {
            "user_id": "10001",
            "name": "示例玩家",
            "npcs": {"linger": {"exp": 2600}},
            "skins": {"linger_skin": {}},
            "current_skin": "linger_skin",
        }

        with tempfile.TemporaryDirectory() as temporary:
            instance.status_assets_dir = Path(temporary)
            instance._compose_status_image({"texts": {}}, player, companion)

        self.assertEqual(captured["subtitle_name"], "Skin Profile")
        self.assertEqual(captured["quality"], "SSR")
        self.assertEqual(captured["bonus"], "皮肤经验 +12%")
        self.assertEqual(captured["skill_2_name"], "皮肤二星")
        self.assertEqual(captured["skill_5_desc"], "皮肤五星描述")


if __name__ == "__main__":
    unittest.main()
