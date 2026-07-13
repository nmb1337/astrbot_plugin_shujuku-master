"""Focused regressions for the customer-reported command and shelf issues."""

import importlib.util
import logging
import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image


def _load_plugin_module():
    """Import the plugin without requiring a running AstrBot installation."""
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    event = types.ModuleType("astrbot.api.event")
    star = types.ModuleType("astrbot.api.star")

    class Filter:
        class EventMessageType:
            ALL = "all"

        @staticmethod
        def command(*_args, **_kwargs):
            return lambda function: function

        @staticmethod
        def event_message_type(*_args, **_kwargs):
            return lambda function: function

    class Star:
        def __init__(self, *_args, **_kwargs):
            pass

    api.logger = logging.getLogger("plugin-test")
    event.AstrMessageEvent = object
    event.filter = Filter
    star.Context = object
    star.Star = Star
    star.register = lambda *_args, **_kwargs: lambda cls: cls

    quart = types.ModuleType("quart")
    quart.jsonify = lambda value: value
    quart.request = types.SimpleNamespace()

    async def send_file(*_args, **_kwargs):
        return None

    quart.send_file = send_file
    sys.modules.update({
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
        "quart": quart,
    })
    source = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("plugin_under_test", source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PLUGIN = _load_plugin_module()


class Event:
    def __init__(self, message_str):
        self.message_str = message_str
        self.stopped = False

    def stop_event(self):
        self.stopped = True


class CommandAndLayoutRegressionTests(unittest.TestCase):
    def setUp(self):
        self.plugin = object.__new__(PLUGIN.JubenNpcPlugin)

    def test_parsed_command_arguments_are_not_erased(self):
        self.assertEqual(self.plugin._arg_text(Event("2")), "2")
        self.assertEqual(self.plugin._parse_page(Event("2")), 2)
        self.assertEqual(self.plugin._parse_page(Event("同伴栏第6页")), 6)
        self.assertEqual(self.plugin._arg_text(Event("灵儿")), "灵儿")
        self.assertEqual(self.plugin._arg_text(Event("/切换同伴 灵儿")), "灵儿")

    def test_direct_paging_and_switch_commands_are_dispatched(self):
        calls = []

        async def inventory(event):
            calls.append(("inventory", event.message_str))
            yield "inventory-result"

        async def switch(event):
            calls.append(("switch", event.message_str))
            yield "switch-result"

        self.plugin.inventory_cmd = inventory
        self.plugin.switch_cmd = switch

        async def collect(message):
            event = Event(message)
            results = [result async for result in self.plugin.direct_command_cmd(event)]
            return results, event.stopped

        page_results, page_stopped = asyncio.run(collect("同伴栏第2页"))
        switch_results, switch_stopped = asyncio.run(collect("切换同伴 灵儿"))
        self.assertEqual(page_results, ["inventory-result"])
        self.assertEqual(switch_results, ["switch-result"])
        self.assertTrue(page_stopped)
        self.assertTrue(switch_stopped)
        self.assertEqual(calls, [("inventory", "同伴栏第2页"), ("switch", "切换同伴 灵儿")])

    def test_legacy_item_tiers_migrate_to_one_weighted_item_pool(self):
        item = self.plugin._normalize_character({
            "id": "legacy_high", "name": "旧高级道具", "kind": "advanced_item",
            "draw_weight": 37, "in_pool": True,
        })
        self.assertEqual(item["kind"], PLUGIN.ITEM_KIND)
        self.assertEqual(item["quality"], "道具")
        self.assertEqual(item["draw_weight"], 37)
        self.assertTrue(item["in_pool"])

    def test_six_companions_stay_on_first_page_and_seventh_is_next_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.plugin.assets_dir = root / "assets"
            self.plugin.render_dir = root / "rendered"
            self.plugin.assets_dir.mkdir()
            self.plugin.render_dir.mkdir()
            self.plugin.font_dir = Path("C:/Windows/Fonts")
            self.plugin._font_cache = {}
            self.plugin._warned_missing_font = False
            self.plugin.settings = dict(PLUGIN.DEFAULT_VISUAL_SETTINGS)
            self.plugin.characters = [
                {
                    "id": f"companion_{index}", "kind": PLUGIN.COMPANION_KIND,
                    "name": f"同伴{index}", "english_name": f"Companion {index}",
                    "quality": "SR", "bonus": "经验 +5%", "colors": ["#6c8cff", "#f4d35e", "#10172a"],
                    "image": f"companion_{index}.png", "exclusive_items": ["徽章", "信物", "邀请函"],
                }
                for index in range(1, 8)
            ]
            player = {
                "user_id": "10001", "current_npc": "companion_1", "current_skin": "",
                "npcs": {f"companion_{index}": {"exp": 0, "owned_at": "2026-07-13"} for index in range(1, 8)},
                "skins": {}, "exclusive_items": {},
            }

            first = self.plugin._render_inventory(player, 1)
            second = self.plugin._render_inventory(player, 2)

            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            self.assertTrue(first.name.endswith("_1.png"))
            self.assertTrue(second.name.endswith("_2.png"))
            with Image.open(first) as image:
                self.assertEqual(image.width, 1280)
                self.assertLessEqual(image.height, 900)


if __name__ == "__main__":
    unittest.main()
