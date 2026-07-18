"""Focused regression checks for template-editor data and rendering helpers."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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
    def test_rows_can_be_deleted_and_are_forced_to_the_cute_font(self):
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
                        "weight": "heavy",
                        "shadow": "false",
                    }
                },
            }
        )

        self.assertEqual(set(template["texts"]), {"custom"})
        self.assertEqual(template["font_family"], "cute")
        self.assertEqual(template["texts"]["custom"]["font_family"], "cute")
        self.assertEqual(template["texts"]["custom"]["weight"], "heavy")
        self.assertTrue(template["texts"]["custom"]["bold"])
        self.assertFalse(template["texts"]["custom"]["shadow"])

    def test_message_limit_and_boolean_normalization(self):
        instance = plugin_instance()
        self.assertEqual(len(instance._normalize_checkin_messages(["a", "b", "c", "d", "e", "f"])), 5)
        self.assertTrue(instance._template_bool("true"))
        self.assertFalse(instance._template_bool("false"))
        self.assertEqual(instance._normalize_text_font_family("not-a-font"), "inherit")
        self.assertEqual(instance._normalize_text_font_family("youyuan"), "inherit")

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
            requested_families = []
            original_font = instance._font

            def capture_font(size, bold=False, family="default"):
                requested_families.append(family)
                return original_font(size, bold, family)

            instance._font = capture_font
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
        self.assertEqual(set(requested_families), {"cute"})

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

    def test_status_progress_is_template_bound_and_positioned(self):
        instance = plugin_instance()
        companion = {
            "id": "linger", "kind": PLUGIN.COMPANION_KIND, "name": "灵儿",
            "english_name": "Linger", "quality": "SR", "bonus": "", "skills": [],
            "colors": ["#123456", "#abcdef", "#0f172a"],
        }
        instance.characters = [companion]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            instance.status_assets_dir = directory
            instance.font_dir = directory
            Image.new("RGB", (1280, 840), "white").save(directory / "status.png")
            template = instance._normalize_status_template({
                "id": "status", "name": "状态", "background_image": "status.png", "texts": {},
                "progress": {
                    "enabled": True, "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.04,
                    "background_color": "#112233", "color": "#cc0000",
                },
            })
            image = instance._compose_status_image(
                template,
                {"user_id": "1", "name": "测试", "npcs": {"linger": {"exp": 500}}, "skins": {}, "current_skin": ""},
                companion,
            )

        self.assertEqual(template["progress"]["x"], 0.1)
        self.assertEqual(template["progress"]["height"], 0.04)
        self.assertEqual(image.getpixel((300, 100))[:3], (204, 0, 0))
        self.assertEqual(image.getpixel((600, 100))[:3], (17, 34, 51))

    def test_page_shortcuts_and_bare_switch_command_are_accepted(self):
        instance = plugin_instance()

        class Event:
            def __init__(self, message):
                self.message_str = message
                self.stopped = False

            def stop_event(self):
                self.stopped = True

        async def fake_inventory(_event):
            yield "inventory"

        async def fake_switch(_event):
            yield "switch"

        instance.inventory_cmd = fake_inventory
        instance.switch_cmd = fake_switch
        page_event = Event("同伴栏第二页")
        switch_event = Event("切换同伴灵儿")

        async def collect(event):
            return [result async for result in instance.direct_command_cmd(event)]

        self.assertEqual(instance._parse_page(page_event), 2)
        self.assertEqual(instance._parse_page(Event("同伴栏2")), 2)
        self.assertEqual(asyncio.run(collect(page_event)), ["inventory"])
        self.assertTrue(page_event.stopped)
        self.assertEqual(asyncio.run(collect(switch_event)), ["switch"])
        self.assertTrue(switch_event.stopped)

    def test_all_items_use_one_weighted_draw_pool(self):
        instance = plugin_instance()
        instance.characters = [
            {"id": "normal", "kind": PLUGIN.ITEM_KIND, "name": "普通", "in_pool": True, "draw_weight": 1},
            {"id": "rare", "kind": PLUGIN.ITEM_KIND, "name": "自定义品质", "in_pool": True, "draw_weight": 9},
        ]
        captured = {}

        def choose(entries, weights, k):
            captured["weights"] = weights
            return [entries[-1]]

        instance._grant_draw_entry = lambda _player, entry, label: {"id": entry["id"], "label": label}
        player = {"current_npc": "linger", "draw_state": {"pity_count": 0, "next_pity_kind": "random"}}
        with patch.object(PLUGIN.random, "random", return_value=0.90), patch.object(PLUGIN.random, "choices", side_effect=choose):
            result = instance._roll_draw(player)

        self.assertEqual(captured["weights"], [1, 9])
        self.assertEqual(result, {"id": "rare", "label": "道具"})

    def test_pool_checkbox_strings_survive_character_normalization(self):
        instance = plugin_instance()
        enabled = instance._normalize_character({
            "id": "enabled_item", "kind": "item", "name": "可抽道具", "in_pool": "true",
        })
        disabled = instance._normalize_character({
            "id": "disabled_item", "kind": "item", "name": "未抽道具", "in_pool": "false",
        })

        self.assertTrue(enabled["in_pool"])
        self.assertFalse(disabled["in_pool"])
        instance.characters = [enabled]
        self.assertEqual(instance._draw_pool(PLUGIN.ITEM_KIND), [enabled])

    def test_new_players_start_without_a_companion(self):
        instance = plugin_instance()
        player = instance._new_player("10001", "新玩家")

        self.assertEqual(player["npcs"], {})
        self.assertEqual(player["current_npc"], "")
        self.assertTrue(player["allow_empty_npcs"])

    def test_draw_opening_guide_only_applies_before_the_first_companion(self):
        instance = plugin_instance()
        companion = {"id": "companion", "kind": PLUGIN.COMPANION_KIND, "name": "同伴", "in_pool": True, "colors": ["#123456"]}
        skin = {"id": "skin", "kind": PLUGIN.SKIN_KIND, "name": "皮肤", "parent_id": "companion", "in_pool": True, "colors": ["#123456"]}
        item = {"id": "item", "kind": PLUGIN.ITEM_KIND, "name": "道具", "in_pool": True, "draw_weight": 1, "colors": ["#123456"]}
        ball = {"id": "ball", "kind": PLUGIN.EXPERIENCE_BALL_KIND, "name": "经验球", "in_pool": True, "draw_weight": 1, "exp_amount": 10, "colors": ["#123456"]}
        instance.characters = [companion, skin, item, ball]
        player = {
            "npcs": {}, "skins": {}, "items": {}, "current_npc": "",
            "draw_state": {"pity_count": 0, "next_pity_kind": "random", "starter_pending": True},
        }

        first = instance._roll_draw(player)
        second = instance._roll_draw(player)
        with patch.object(PLUGIN.random, "random", return_value=0.999):
            third = instance._roll_draw(player)

        self.assertEqual(first["entry_kind"], PLUGIN.COMPANION_KIND)
        self.assertEqual(second["entry_kind"], PLUGIN.SKIN_KIND)
        self.assertEqual(third["entry_kind"], PLUGIN.SKIN_KIND)
        self.assertNotEqual(third["kind"], "未命中")

        established = {
            "npcs": {"companion": {"exp": 0}}, "skins": {}, "items": {}, "current_npc": "companion",
            "draw_state": {"pity_count": 0, "next_pity_kind": "random"},
        }
        with patch.object(PLUGIN.random, "random", return_value=0.01):
            result = instance._roll_draw(established)
        self.assertEqual(result["entry_kind"], PLUGIN.EXPERIENCE_BALL_KIND)

    def test_pity_draw_uses_the_current_pool_and_resets_progress(self):
        instance = plugin_instance()
        companion = {"id": "new_companion", "kind": PLUGIN.COMPANION_KIND, "name": "新同伴", "in_pool": True, "colors": ["#123456"]}
        skin = {"id": "new_skin", "kind": PLUGIN.SKIN_KIND, "name": "新皮肤", "parent_id": "new_companion", "in_pool": True, "colors": ["#123456"]}
        item = {"id": "item", "kind": PLUGIN.ITEM_KIND, "name": "道具", "in_pool": True, "draw_weight": 1, "colors": ["#123456"]}
        instance.characters = [companion, skin, item]
        player = {
            "npcs": {"new_companion": {"exp": 0}}, "skins": {}, "items": {}, "current_npc": "new_companion",
            "draw_state": {"pity_count": PLUGIN.DRAW_PITY_TARGET - 1, "next_pity_kind": PLUGIN.SKIN_KIND},
        }

        result = instance._roll_draw(player)

        self.assertEqual(result["entry_id"], "new_skin")
        self.assertEqual(result["kind"], "保底皮肤")
        self.assertEqual(player["draw_state"]["pity_count"], 0)
        self.assertEqual(player["draw_state"]["next_pity_kind"], PLUGIN.COMPANION_KIND)

    def test_legacy_opening_state_is_removed_for_players_with_companions(self):
        instance = plugin_instance()
        player = {
            "npcs": {"linger": {"exp": 0}}, "skins": {}, "items": {}, "exclusive_items": {},
            "draw_state": {"pity_count": 7, "next_pity_kind": "random", "guarantee_stage": PLUGIN.COMPANION_KIND},
        }

        instance._migrate_player_npcs(player)

        self.assertNotIn("guarantee_stage", player["draw_state"])
        self.assertFalse(player["draw_state"]["starter_pending"])
        self.assertFalse(player["draw_state"]["starter_skin_pending"])

    def test_experience_ball_entries_are_weighted_inside_the_experience_slot(self):
        instance = plugin_instance()
        instance.characters = [
            {"id": "linger", "kind": PLUGIN.COMPANION_KIND},
            {"id": "small", "kind": PLUGIN.EXPERIENCE_BALL_KIND, "name": "小球", "in_pool": True, "draw_weight": 2, "exp_amount": 10},
            {"id": "large", "kind": PLUGIN.EXPERIENCE_BALL_KIND, "name": "大球", "in_pool": True, "draw_weight": 8, "exp_amount": 20},
        ]
        player = {"npcs": {"linger": {"exp": 0}}, "items": {}, "current_npc": "linger"}
        captured = {}

        def choose(entries, weights, k):
            captured["weights"] = weights
            return [entries[-1]]

        with patch.object(PLUGIN.random, "choices", side_effect=choose):
            result = instance._roll_experience_ball(player, "linger")

        self.assertEqual(captured["weights"], [2, 8])
        self.assertEqual(result["name"], "大球")
        self.assertEqual(result["exp"], 20)

    def test_mining_template_pool_and_render_are_role_bound(self):
        instance = plugin_instance()
        companion = {"id": "linger", "kind": PLUGIN.COMPANION_KIND, "name": "灵儿", "colors": ["#325b86", "#dcecff", "#18243c"]}
        item = instance._normalize_character({"id": "ore", "kind": "item", "name": "矿石", "mining_pool": True, "mining_weight": 7})
        instance.characters = [companion, item]
        template = instance._normalize_mining_template({
            "id": "linger_mining", "name": "灵儿矿点", "bound_entry_id": "linger",
            "background_images": ["one.png", "two.png", "three.png", "four.png", "five.png", "six.png", "seven.png"],
        })
        instance.mining_templates = [template]
        player = {"current_npc": "linger", "current_skin": "", "npcs": {"linger": {"exp": 0}}, "items": {}, "user_id": "1", "name": "测试"}

        self.assertEqual(instance._mining_pool(), [item])
        self.assertEqual(template["background_images"], ["one.png", "two.png", "three.png", "four.png", "five.png", "six.png"])
        self.assertEqual(instance._mining_template_for(player, "linger")["id"], "linger_mining")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            instance.assets_dir = directory / "assets"; instance.assets_dir.mkdir()
            instance.mining_assets_dir = directory / "mining"; instance.mining_assets_dir.mkdir()
            instance.render_dir = directory / "rendered"; instance.render_dir.mkdir()
            instance.font_dir = directory / "fonts"; instance.font_dir.mkdir()
            result = instance._render_mining(player, companion, item, template)
            with Image.open(result) as image:
                self.assertEqual(image.size, (1280, 720))

    def test_draw_design_and_compact_coin_receipt_render(self):
        instance = plugin_instance()
        design = instance._normalize_draw_design({"background_image": "../draw.png", "result_card_color": "#123456", "pity_card_color": "invalid"})

        self.assertEqual(design["background_image"], "draw.png")
        self.assertEqual(design["result_card_color"], "#123456")
        self.assertEqual(design["pity_card_color"], "#ffffff")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            instance.render_dir = directory
            instance.font_dir = directory
            result = instance._render_compact_notice_card("星币已发放", ["对象：测试", "发放 +10 星币"])
            with Image.open(result) as image:
                self.assertEqual(image.size, (620, 270))

    def test_draw_and_mining_keep_background_composition_space_clear(self):
        instance = plugin_instance()
        companion = {"id": "linger", "kind": PLUGIN.COMPANION_KIND, "name": "灵儿", "colors": ["#325b86", "#dcecff", "#18243c"]}
        item = {"id": "ore", "kind": PLUGIN.ITEM_KIND, "name": "矿石", "effect": "测试效果", "image": ""}
        instance.characters = [companion, item]
        player = {
            "user_id": "1", "name": "测试", "coins": 10, "current_npc": "linger", "npcs": {"linger": {"exp": 0}},
            "items": {}, "skins": {}, "draw_state": {"pity_count": 0, "next_pity_kind": "random"},
        }
        result = {"name": "矿石", "kind": "道具", "exp": 0, "character_id": "linger", "image": ""}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            instance.assets_dir = directory / "assets"; instance.assets_dir.mkdir()
            instance.draw_assets_dir = directory / "draw"; instance.draw_assets_dir.mkdir()
            instance.mining_assets_dir = directory / "mining"; instance.mining_assets_dir.mkdir()
            instance.render_dir = directory / "rendered"; instance.render_dir.mkdir()
            instance.font_dir = directory / "fonts"; instance.font_dir.mkdir()
            Image.new("RGB", (1180, 760), "#123456").save(instance.draw_assets_dir / "draw.png")
            Image.new("RGB", (1280, 720), "#456789").save(instance.mining_assets_dir / "mining.png")
            instance.draw_design = {"background_image": "draw.png", "result_card_color": "#ffffff", "pity_card_color": "#ffffff"}
            draw_path = instance._render_draw(player, [result] * 5, 10, 0)
            mining_path = instance._render_mining(player, companion, item, {"background_images": ["mining.png"]})
            with Image.open(draw_path) as image:
                self.assertEqual(image.getpixel((850, 220))[:3], image.getpixel((850, 260))[:3])
            with Image.open(mining_path) as image:
                self.assertEqual(image.getpixel((60, 54))[:3], (69, 103, 137))

    def test_cute_template_font_has_a_real_font_file(self):
        instance = plugin_instance()
        instance.font_dir = Path(tempfile.gettempdir()) / "missing-plugin-fonts"

        self.assertIsNotNone(instance._find_font_file(False, "cute"))

    def test_inventory_can_keep_six_companion_groups_on_one_page(self):
        instance = plugin_instance()
        companions = [
            {
                "id": f"companion_{index}", "kind": PLUGIN.COMPANION_KIND, "name": f"同伴{index}",
                "english_name": "Companion", "quality": "SR", "bonus": "", "skills": [],
                "exclusive_items": ["物品甲", "物品乙", "物品丙"], "colors": ["#123456", "#abcdef", "#0f172a"],
                "image": f"companion_{index}.png", "focal_x": 0.5, "focal_y": 0.5,
            }
            for index in range(6)
        ]
        instance.characters = companions
        instance.settings = {
            "companion_name_color": "#172033", "companion_meta_color": "#526071", "companion_border_color": "#d0d6e2",
            "exclusive_item_color": "#2563eb", "exclusive_item_border_color": "#94b6e9",
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            instance.assets_dir = directory / "assets"; instance.assets_dir.mkdir()
            instance.render_dir = directory / "rendered"; instance.render_dir.mkdir()
            instance.font_dir = directory / "fonts"; instance.font_dir.mkdir()
            player = {
                "user_id": "1", "name": "测试", "npcs": {entry["id"]: {"exp": 300} for entry in companions},
                "skins": {}, "items": {}, "exclusive_items": {}, "current_npc": "companion_0", "current_skin": "",
            }
            path = instance._render_inventory(player, page=1)
            with Image.open(path) as image:
                size = image.size
                chip_fill = image.getpixel((530, 264))[:3]
                below_chip = image.getpixel((530, 286))[:3]

        self.assertTrue(path.name.endswith("_1.png"))
        self.assertGreaterEqual(size[1], 900)
        self.assertEqual(chip_fill, (247, 249, 252))
        self.assertNotEqual(below_chip, chip_fill)


if __name__ == "__main__":
    unittest.main()
