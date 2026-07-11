import base64
import json
import inspect
import os
import random
import re
import shutil
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from quart import jsonify, request, send_file


LEVEL_REQUIREMENTS = [1000, 2000, 3000, 4000, 5000]
DRAW_COST = 10
DRAW_COUNT = 5
DRAW_PITY_TARGET = 100
WINNING_NUMBER_MIN = 1
WINNING_NUMBER_MAX = 100
CHECKIN_REWARDS = [
    ("星币", 1, 20),
    ("星币", 2, 20),
    ("星币", 3, 20),
    ("星币", 4, 20),
    ("星币", 5, 20),
]
EXPERIENCE_BALLS = [
    (30, "星辰经验球", 10, "starlight_exp_orb.jpg"),
    (25, "月辉经验球", 15, "moonlight_exp_orb.jpg"),
    (20, "光明经验球", 20, "light_exp_orb.jpg"),
]
DOWNLOADABLE_FONTS = [
    (
        "NotoSansCJKsc-Regular.otf",
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    ),
    (
        "NotoSansCJKsc-Bold.otf",
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf",
    ),
]
PLUGIN_NAME = "astrbot_plugin_juben_npc"
COMPANION_KIND = "companion"
SKIN_KIND = "skin"
ITEM_KIND = "item"
ITEM_QUALITIES = ("普通", "中级", "高级")
QUALITY_RANK = {"UR": 5, "SSR": 4, "SR": 3, "R": 2, "N": 1, "普通": 1, "中级": 2, "高级": 3}
DEFAULT_VISUAL_SETTINGS = {
    "companion_name_color": "#172033",
    "companion_meta_color": "#6d9bc6",
    "companion_border_color": "#dbe5f1",
    "exclusive_item_color": "#d49a4a",
    "exclusive_item_border_color": "#e6c58d",
    "status_name_color": "#172033",
    "status_meta_color": "#6d9bc6",
    "status_panel_color": "#ffffff",
    "item_name_color": "#172033",
    "item_quality_color": "#6d9bc6",
    "item_effect_color": "#526071",
}
RETIRED_CHARACTER_IDS = {
    "rin",
    "yue",
    "mika",
    "noa",
    "iori",
    "sora",
    "kuro",
    "hana",
    "akito",
}


DEFAULT_CHARACTERS: List[Dict[str, Any]] = [
    {
        "id": "blue_hour_cafe",
        "name": "蓝时咖啡",
        "base": "蓝时咖啡",
        "skin": "Winter Issue",
        "star": "SSR",
        "route": "运营后台添加 / 月度皮肤池",
        "bonus": "推理经验 +12%",
        "intro": "银发女仆在蓝色午后里守着窗边席位，甜点、红茶和冰冷剑锋都摆放得恰到好处。",
        "skills": [["午后礼仪", "社交与推理经验提升。"], ["蓝调侍奉", "礼物转化经验 +15%。"], ["寒光茶歇", "月度皮肤结算经验 +25%。"]],
        "colors": ["#7d9fc2", "#eaf4ff", "#1c2a3f"],
        "image": "blue_hour_cafe.jpg",
        "featured": True,
    },
    {
        "id": "noble_afternoon",
        "name": "贵族下午茶",
        "base": "贵族下午茶",
        "skin": "Chess Strategy",
        "star": "SSR",
        "route": "运营后台添加 / 月度皮肤池",
        "bonus": "策略经验 +12%",
        "intro": "棋盘上的每一步都像一封无声邀请，她从容地把局势推进到最优雅的将死。",
        "skills": [["棋谱预判", "机关与策略经验提升。"], ["临界一步", "失败结算保底经验提升。"], ["贵族终局", "高星剧本结算经验 +25%。"]],
        "colors": ["#31517f", "#f3d98a", "#2a2430"],
        "image": "noble_afternoon.jpg",
        "featured": True,
    },
    {
        "id": "cafe_lumiere",
        "name": "红馆流明",
        "base": "红馆流明",
        "skin": "Cafe Lumiere",
        "star": "SR",
        "route": "运营后台添加 / 活动兑换",
        "bonus": "社交经验 +10%",
        "intro": "红色咖啡馆里，猫耳女仆以笑容招待来客，也用敏锐观察记录每一次停顿。",
        "skills": [["红茶礼节", "社交经验提升。"], ["双影招待", "组队结算额外获得经验。"], ["灯影谢幕", "活动剧本经验 +20%。"]],
        "colors": ["#8b2531", "#f4dfd8", "#2b0f14"],
        "image": "cafe_lumiere.jpg",
        "featured": False,
    },
    {
        "id": "ash_silver_blade",
        "name": "灰堡银刃",
        "base": "灰堡银刃",
        "skin": "Silver Blade",
        "star": "SSR",
        "route": "运营后台添加 / 月度大奖池",
        "bonus": "战斗经验 +14%",
        "intro": "黑衣少女坐在灰堡废墟里，银刃立于身侧，安静得像一场还未开始的审判。",
        "skills": [["灰堡伏击", "战斗线经验提升。"], ["银刃处决", "大奖重复转化经验提升。"], ["冷焰归鞘", "战斗结算经验 +30%。"]],
        "colors": ["#505866", "#dce6f0", "#111419"],
        "image": "ash_silver_blade.jpg",
        "featured": True,
    },
    {
        "id": "blue_cafe_morning",
        "name": "蓝咖啡晨光",
        "base": "蓝咖啡晨光",
        "skin": "Cafe Morning",
        "star": "SR",
        "route": "运营后台添加 / 皮肤池",
        "bonus": "观察经验 +10%",
        "intro": "晨光落在白瓷杯沿，银发女仆端起咖啡，仿佛连线索也被阳光洗得透明。",
        "skills": [["晨光注视", "观察经验提升。"], ["白瓷回声", "礼物经验小幅提升。"], ["蓝窗独白", "探索结算经验 +20%。"]],
        "colors": ["#a8c6df", "#f7fbff", "#26384c"],
        "image": "blue_cafe_morning.jpg",
        "featured": False,
    },
]

@register("astrbot_plugin_juben_npc", "Codex", "剧本杀同伴、皮肤、道具、星币、打卡与抽奖插件", "2.0.0")
class JubenNpcPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = Path(__file__).parent
        self.data_dir = self.plugin_dir / "data"
        self.assets_dir = self.data_dir / "npc_assets"
        self.checkin_assets_dir = self.data_dir / "checkin_assets"
        self.font_dir = self.data_dir / "fonts"
        self.render_dir = self.data_dir / "rendered"
        self.db_path = self.data_dir / "players.json"
        self.characters_path = self.data_dir / "characters.json"
        self.checkin_templates_path = self.data_dir / "checkin_templates.json"
        self.settings_path = self.data_dir / "settings.json"
        self.db: Dict[str, Any] = {"scopes": {}}
        self.characters: List[Dict[str, Any]] = []
        self.checkin_templates: List[Dict[str, Any]] = []
        self.settings: Dict[str, str] = dict(DEFAULT_VISUAL_SETTINGS)
        self._font_cache: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}
        self._warned_missing_font = False
        self._register_page_apis(context)

    async def initialize(self):
        self.data_dir.mkdir(exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        self.checkin_assets_dir.mkdir(exist_ok=True)
        self.font_dir.mkdir(exist_ok=True)
        self.render_dir.mkdir(exist_ok=True)
        self._load_db()
        self._load_characters()
        self._load_checkin_templates()
        self._load_settings()
        self._ensure_fonts()
        self._ensure_assets()
        logger.info("剧本杀同伴与皮肤数据库插件已加载。")

    async def terminate(self):
        self._save_db()
        self._save_characters()
        self._save_checkin_templates()
        self._save_settings()

    async def help_cmd(self, event: AstrMessageEvent):
        path = self._render_text_card(
            "剧本杀同伴数据库",
            [
                "/打卡 - 每天随机领取 1-5 星币",
                "/赠送星币 @群友 数量 - 管理员发放星币",
                "/赠送同伴 @群友 名称 - 管理员赠送同伴或皮肤",
                "/赠送专属 @群友 同伴名 - 管理员赠送同伴专属物品",
                "/状态栏 - 查看当前同伴状态",
                "/切换同伴 名称 - 更换当前同伴或装备皮肤（/切换角色 仍兼容）",
                "/抽奖 - 消耗 10 星币进行 5 抽",
                "/中奖号码 - 机器人在固定范围内随机生成中奖号",
                "/同伴栏 [页码] - 查看已获得同伴与皮肤",
                "/道具栏 [页码] - 查看已获得道具",
            ],
            subtitle="后台 Plugin Page 可维护同伴、皮肤、道具、奖池、色板与打卡图片。",
        )
        yield event.image_result(str(path))

    @filter.event_message_type(filter.EventMessageType.ALL, priority=8)
    async def direct_command_cmd(self, event: AstrMessageEvent):
        text = (event.message_str or "").strip().lstrip("/!！")
        no_space_handlers = {
            "切换同伴": self.switch_cmd,
            "切换角色": self.switch_cmd,
            "更换角色": self.switch_cmd,
            "选择角色": self.switch_cmd,
            "抽奖": self.draw_cmd,
            "npc抽奖": self.draw_cmd,
            "NPC抽奖": self.draw_cmd,
            "中奖号码": self.winning_number_cmd,
            "开奖": self.winning_number_cmd,
        }
        for prefix, handler in no_space_handlers.items():
            if text.startswith(prefix) and text != prefix and not text[len(prefix): len(prefix) + 1].isspace():
                async for result in handler(event):
                    yield result
                event.stop_event()
                return

    async def wallet_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_notice_card(
            "星币余额",
            f"当前持有 {player['coins']} 星币，可在 /打卡 或 /抽奖 页面查看。",
        )
        yield event.image_result(str(path))

    @filter.command("赠送星币", alias={"发放星币", "给星币", "加星币"})
    async def transfer_cmd(self, event: AstrMessageEvent):
        denial = await self._operator_denial(event, "发放星币")
        if denial:
            yield event.image_result(str(denial))
            return

        target_id, target_label, amount = self._parse_transfer(event)
        if not target_id or amount <= 0:
            path = self._render_text_card("发放失败", ["格式：/赠送星币 @群友 数量", "例如：/赠送星币 @小明 20"])
            yield event.image_result(str(path))
            return

        target = self._get_player_by_id(event, target_id, target_label)
        target["coins"] += amount
        self._save_db()
        logger.info(
            "剧本杀星币发放：operator=%s scope=%s target=%s amount=%s balance=%s",
            self._sender_id(event),
            self._scope_id(event),
            target_id,
            amount,
            target["coins"],
        )

        path = self._render_text_card(
            "星币已发放",
            [f"对象：{target_label}", f"发放数量：{amount}", f"对方余额：{target['coins']}"],
            subtitle="可用此命令给群员补发活动星币。",
        )
        yield event.image_result(str(path))

    @filter.command("赠送同伴", alias={"赠送角色", "赠送NPC", "赠送皮肤", "给角色"})
    async def grant_character_cmd(self, event: AstrMessageEvent):
        denial = await self._operator_denial(event, "赠送同伴")
        if denial:
            yield event.image_result(str(denial))
            return

        target_id, target_label = self._parse_target_user(event)
        character_name = self._parse_character_after_target(event)
        character = self._find_character(character_name)
        if not target_id or not character:
            path = self._render_text_card(
                "赠送失败",
                ["格式：/赠送同伴 @群友 名称", "例如：/赠送同伴 @小明 蓝时咖啡"],
                subtitle="也可以在插件后台页面选择已记录的玩家赠送。",
            )
            yield event.image_result(str(path))
            return

        target = self._get_player_by_id(event, target_id, target_label)
        created = self._grant_character(target, character["id"])
        self._save_db()
        logger.info(
            "剧本杀角色赠送：operator=%s scope=%s target=%s character=%s created=%s",
            self._sender_id(event),
            self._scope_id(event),
            target_id,
            character["id"],
            created,
        )
        path = self._render_text_card(
            "同伴已赠送",
            [f"对象：{target_label}", f"内容：{character['name']} / {character.get('english_name', '')}", f"结果：{'新增拥有' if created else '已拥有，未重复添加'}"],
        )
        yield event.image_result(str(path))

    @filter.command("赠送专属", alias={"赠送专属物品", "给专属"})
    async def grant_exclusive_cmd(self, event: AstrMessageEvent):
        denial = await self._operator_denial(event, "赠送专属物品")
        if denial:
            yield event.image_result(str(denial))
            return
        target_id, target_label = self._parse_target_user(event)
        companion_name = self._parse_character_after_target(event)
        companion = self._find_character(companion_name)
        if not target_id or not companion or companion.get("kind") != COMPANION_KIND:
            yield event.image_result(str(self._render_notice_card("赠送失败", "格式：/赠送专属 @群友 同伴名")))
            return
        target = self._get_player_by_id(event, target_id, target_label)
        if not self._grant_exclusive_item(target, companion["id"]):
            yield event.image_result(str(self._render_notice_card("赠送失败", "该同伴没有专属物品，或对方已经拥有。")))
            return
        self._save_db()
        yield event.image_result(str(self._render_notice_card("专属物品已赠送", f"{target_label} 获得了 {companion['exclusive_item']}。")))

    @filter.command("打卡", alias={"每日打卡"})
    async def checkin_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        today = datetime.now().strftime("%Y-%m-%d")
        if player.get("last_checkin") == today:
            path = self._render_checkin_card(player, "今日已打卡", "已领取", today=today)
            yield event.image_result(str(path))
            return

        reward_type, amount = self._roll_checkin()
        player["coins"] += amount
        player["last_checkin"] = today
        self._save_db()

        path = self._render_checkin_card(player, "打卡成功", f"获得：{amount} {reward_type}")
        yield event.image_result(str(path))

    @filter.command("状态栏", alias={"角色状态", "我的角色"})
    async def status_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        character_name = self._arg_text(event)
        character = self._find_character(character_name) if character_name else self._character(player["current_npc"])
        if not character:
            path = self._render_notice_card("没有找到同伴", f"输入：{character_name or '空'}，可用 /同伴栏 查看。")
            yield event.image_result(str(path))
            return
        if character.get("kind") == SKIN_KIND:
            if character["id"] not in player["skins"]:
                path = self._render_notice_card("尚未拥有", f"你还没有获得皮肤：{character['name']}。")
                yield event.image_result(str(path))
                return
            character = self._character(character.get("parent_id", ""))
        if character["id"] not in player["npcs"]:
            path = self._render_notice_card("尚未拥有", f"{character['name']} 还没有加入你的同伴栏。")
            yield event.image_result(str(path))
            return

        path = self._render_status(player, character)
        yield event.image_result(str(path))

    @filter.command("切换同伴", alias={"切换角色", "更换角色", "选择角色"})
    async def switch_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        character_name = self._arg_text(event)
        character = self._find_character(character_name)
        if not character:
            path = self._render_notice_card("切换失败", f"没有找到：{character_name or '空'}。")
            yield event.image_result(str(path))
            return
        if character.get("kind") == SKIN_KIND:
            if character["id"] not in player["skins"]:
                yield event.image_result(str(self._render_notice_card("切换失败", f"你尚未拥有皮肤：{character['name']}。")))
                return
            parent = self._character(character.get("parent_id", ""))
            if parent["id"] not in player["npcs"]:
                yield event.image_result(str(self._render_notice_card("切换失败", "请先获得对应同伴后再装备皮肤。")))
                return
            player["current_npc"] = parent["id"]
            player["current_skin"] = character["id"]
            shown = parent
            banner = "已装备皮肤"
        elif character["id"] not in player["npcs"]:
            path = self._render_notice_card("切换失败", f"你尚未拥有同伴：{character['name']}。")
            yield event.image_result(str(path))
            return
        else:
            player["current_npc"] = character["id"]
            skin = self._character_or_none(str(player.get("current_skin") or ""))
            if not skin or skin.get("parent_id") != character["id"]:
                player["current_skin"] = ""
            shown = character
            banner = "已切换当前同伴"
        self._save_db()
        path = self._render_status(player, shown, banner=banner)
        yield event.image_result(str(path))

    @filter.command("抽奖", alias={"npc抽奖", "NPC抽奖"})
    async def draw_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        count = DRAW_COUNT
        coin_cost = DRAW_COST
        pool_gaps = self._draw_pool_gaps()
        if pool_gaps:
            path = self._render_notice_card(
                "奖池尚未配置完成",
                "缺少：" + "、".join(pool_gaps) + "。请在后台勾选奖池内容后再抽奖；本次不会扣除星币。",
            )
            yield event.image_result(str(path))
            return
        if player["coins"] < coin_cost:
            path = self._render_notice_card("星币不足", f"本次 5 抽需要 {coin_cost} 星币；当前只有 {player['coins']} 星币。")
            yield event.image_result(str(path))
            return

        player["coins"] -= coin_cost
        results = [self._roll_draw(player) for _ in range(count)]
        self._save_db()

        path = self._render_draw(player, results, coin_cost, 0)
        yield event.image_result(str(path))

    @filter.command("中奖号码", alias={"开奖"})
    async def winning_number_cmd(self, event: AstrMessageEvent):
        number = random.randint(WINNING_NUMBER_MIN, WINNING_NUMBER_MAX)
        path = self._render_text_card(
            "中奖号码",
            [
                f"本次中奖号：{number:02d}",
                f"随机范围：{WINNING_NUMBER_MIN}-{WINNING_NUMBER_MAX}",
                "号码完全由机器人随机生成，用户输入的数字不会参与开奖。",
            ],
            subtitle="可用于群内活动抽签、抽奖或剧本杀入场号。",
        )
        yield event.image_result(str(path))

    @filter.command("同伴栏", alias={"物品栏", "NPC仓库", "npc仓库", "我的NPC"})
    async def inventory_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_inventory(player, self._parse_page(event))
        yield event.image_result(str(path))

    @filter.command("道具栏", alias={"我的道具", "道具仓库"})
    async def item_inventory_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_item_inventory(player, self._parse_page(event))
        yield event.image_result(str(path))

    async def npc_info_cmd(self, event: AstrMessageEvent):
        yield event.image_result(
            str(self._render_notice_card("功能已整合", "NPC 信息已整合到 /状态栏 与 /同伴栏。"))
        )

    def _register_page_apis(self, context: Context):
        if not hasattr(context, "register_web_api"):
            return

        async def list_characters():
            return jsonify(
                {
                    "characters": [
                        {
                            **character,
                            "preview": self._thumbnail_data_url(self.assets_dir / character["image"]),
                        }
                        for character in self.characters
                    ],
                    "players": self._known_players(),
                    "settings": self.settings,
                    "checkin_templates": [
                        {
                            **template,
                            "preview": self._thumbnail_data_url(
                                self.checkin_assets_dir / template.get("image", "")
                            ),
                        }
                        for template in self.checkin_templates
                    ],
                }
            )

        async def save_character():
            data = await request.get_json()
            data = data or {}
            character = self._normalize_character(data)
            if character.get("kind") == SKIN_KIND:
                parent = self._character_or_none(character.get("parent_id", ""))
                if not parent or parent.get("kind") != COMPANION_KIND:
                    return jsonify({"status": "error", "message": "皮肤必须绑定一个已存在的同伴。"}), 400
            exists = False
            for index, item in enumerate(self.characters):
                if item["id"] == character["id"]:
                    self.characters[index] = character
                    exists = True
                    break
            if not exists:
                self.characters.append(character)
            self._enforce_single_featured_pool(character)
            self._save_characters()
            self._ensure_assets()
            return jsonify({"ok": True, "character": character})

        async def delete_character(character_id: str):
            entry = self._character_or_none(character_id)
            if entry and entry.get("kind") == COMPANION_KIND and len(self._companions()) <= 1:
                return jsonify({"status": "error", "message": "至少需要保留一名同伴。"}), 400
            if entry and entry.get("kind") == COMPANION_KIND and self._skins_for(character_id):
                return jsonify({"status": "error", "message": "请先删除或重新绑定该同伴的皮肤。"}), 400
            before = len(self.characters)
            self.characters = [item for item in self.characters if item["id"] != character_id]
            self._save_characters()
            return jsonify({"ok": True, "deleted": before != len(self.characters)})

        async def upload_image():
            file = await self._request_upload_file()
            if file is None:
                return jsonify({"status": "error", "message": "没有收到图片文件。"}), 400
            try:
                saved_name = await self._save_uploaded_image(file)
            except (ValueError, OSError) as exc:
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"assets/{saved_name}"})

        async def list_checkin_templates():
            return jsonify({"checkin_templates": self.checkin_templates})

        async def save_checkin_template():
            data = (await request.get_json()) or {}
            template = self._normalize_checkin_template(data)
            for index, item in enumerate(self.checkin_templates):
                if item["id"] == template["id"]:
                    self.checkin_templates[index] = template
                    break
            else:
                self.checkin_templates.append(template)
            self._save_checkin_templates()
            return jsonify({"ok": True, "template": template})

        async def delete_checkin_template(template_id: str):
            before = len(self.checkin_templates)
            self.checkin_templates = [item for item in self.checkin_templates if item["id"] != template_id]
            if not self.checkin_templates:
                self.checkin_templates = [self._default_checkin_template()]
            self._save_checkin_templates()
            return jsonify({"ok": True, "deleted": before != len(self.checkin_templates)})

        async def upload_checkin_background():
            file = await self._request_upload_file()
            if file is None:
                return jsonify({"status": "error", "message": "没有收到背景图片文件。"}), 400
            try:
                saved_name = await self._save_uploaded_image(file, self.checkin_assets_dir, "checkin")
            except (ValueError, OSError) as exc:
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"checkin-assets/{saved_name}"})

        async def preview_checkin_template():
            data = (await request.get_json()) or {}
            template = self._normalize_checkin_template(data)
            values = {
                "title": "打卡成功",
                "reward": "获得：3 星币",
                "coins": 128,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "message": template.get("message") or "今日也要和同伴一起前进。",
                "_portrait_entry": self._companions()[0] if self._companions() else None,
            }
            img = self._compose_checkin_image(template, values)
            return jsonify({"ok": True, "preview": self._image_data_url(img)})

        async def grant_character():
            data = await request.get_json()
            data = data or {}
            scope_id = str(data.get("scope_id", "")).strip()
            user_id = str(data.get("user_id", "")).strip()
            character_id = str(data.get("character_id", "")).strip()
            name = str(data.get("name", user_id)).strip() or user_id
            if not scope_id or not user_id or not self._character_or_none(character_id):
                return jsonify({"status": "error", "message": "scope_id、user_id 或 character_id 无效。"}), 400
            player = self._get_player_by_scope(scope_id, user_id, name)
            created = self._grant_character(player, character_id)
            self._save_db()
            return jsonify({"ok": True, "created": created, "player": player})

        async def grant_exclusive_item():
            data = (await request.get_json()) or {}
            scope_id = str(data.get("scope_id", "")).strip()
            user_id = str(data.get("user_id", "")).strip()
            companion_id = str(data.get("companion_id", "")).strip()
            name = str(data.get("name", user_id)).strip() or user_id
            if not scope_id or not user_id or not companion_id:
                return jsonify({"status": "error", "message": "scope_id、user_id 或 companion_id 无效。"}), 400
            player = self._get_player_by_scope(scope_id, user_id, name)
            created = self._grant_exclusive_item(player, companion_id)
            if not created:
                return jsonify({"status": "error", "message": "同伴不存在、未设置专属物品，或玩家已拥有该专属物品。"}), 400
            self._save_db()
            return jsonify({"ok": True, "created": True, "player": player})

        async def get_settings():
            return jsonify({"settings": self.settings})

        async def save_settings():
            data = (await request.get_json()) or {}
            return jsonify({"ok": True, "settings": self._save_settings_from_payload(data)})

        async def get_asset(filename: str):
            safe_name = Path(filename).name
            path = self.assets_dir / safe_name
            if not path.exists():
                return jsonify({"status": "error", "message": "图片不存在。"}), 404
            return await send_file(path)

        async def get_checkin_asset(filename: str):
            path = self.checkin_assets_dir / Path(filename).name
            if not path.exists():
                return jsonify({"status": "error", "message": "背景图片不存在。"}), 404
            return await send_file(path)

        context.register_web_api(f"/{PLUGIN_NAME}/characters", list_characters, ["GET"], "List NPC characters")
        context.register_web_api(f"/{PLUGIN_NAME}/characters", save_character, ["POST"], "Save NPC character")
        context.register_web_api(f"/{PLUGIN_NAME}/characters/<character_id>/delete", delete_character, ["POST"], "Delete NPC character")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-image", upload_image, ["POST"], "Upload NPC image")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates", list_checkin_templates, ["GET"], "List check-in templates")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates", save_checkin_template, ["POST"], "Save check-in template")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates/<template_id>/delete", delete_checkin_template, ["POST"], "Delete check-in template")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-checkin-background", upload_checkin_background, ["POST"], "Upload check-in background")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates/preview", preview_checkin_template, ["POST"], "Preview check-in template")
        context.register_web_api(f"/{PLUGIN_NAME}/grant", grant_character, ["POST"], "Grant NPC character")
        context.register_web_api(f"/{PLUGIN_NAME}/grant-exclusive", grant_exclusive_item, ["POST"], "Grant companion exclusive item")
        context.register_web_api(f"/{PLUGIN_NAME}/settings", get_settings, ["GET"], "Get companion visual settings")
        context.register_web_api(f"/{PLUGIN_NAME}/settings", save_settings, ["POST"], "Save companion visual settings")
        context.register_web_api(f"/{PLUGIN_NAME}/assets/<filename>", get_asset, ["GET"], "Get NPC image")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-assets/<filename>", get_checkin_asset, ["GET"], "Get check-in background")

    def _load_db(self):
        if not self.db_path.exists():
            self._save_db()
            return
        try:
            self.db = json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"读取剧本杀 NPC 数据失败，将使用空数据库：{exc}")
            self.db = {"scopes": {}}
        self._migrate_database()

    def _save_db(self):
        self.data_dir.mkdir(exist_ok=True)
        self._write_json_atomic(self.db_path, self.db)

    @staticmethod
    def _write_json_atomic(path: Path, payload: Any) -> None:
        """Persist a JSON document without exposing a half-written data file.

        Player assets and operator configuration are updated while the plugin is
        live. Writing a temporary sibling and replacing it only after JSON
        serialization succeeds means a sudden process exit leaves the previous
        usable document in place.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        # A distinct sibling avoids two command handlers trampling the same
        # ``.tmp`` filename. ``os.replace`` is atomic on the same volume, so
        # readers see either the previous complete JSON or the new one.
        temporary = path.with_name(
            f".{path.name}.{os.getpid()}.{random.randrange(1_000_000_000)}.tmp"
        )
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                if temporary.exists():
                    temporary.unlink()
            except OSError:
                pass

    @staticmethod
    def _backup_once(path: Path, tag: str) -> None:
        """Keep a one-time, local rollback copy before the v2 data migration."""
        if not path.exists():
            return
        backup = path.with_name(f"{path.stem}.{tag}.bak{path.suffix}")
        if not backup.exists():
            shutil.copy2(path, backup)

    def _migrate_database(self):
        if not isinstance(self.db, dict):
            self.db = {"scopes": {}}
        if int(self.db.get("schema_version", 1) or 1) >= 2:
            return
        self._backup_once(self.db_path, "v1")
        scopes = self.db.setdefault("scopes", {})
        if not isinstance(scopes, dict):
            scopes = self.db["scopes"] = {}
        for scope in scopes.values():
            if not isinstance(scope, dict):
                continue
            players = scope.setdefault("players", {})
            if not isinstance(players, dict):
                continue
            for player in players.values():
                if not isinstance(player, dict):
                    continue
                player.setdefault("npcs", {})
                player.setdefault("skins", {})
                player.setdefault("items", {})
                player.setdefault("exclusive_items", {})
                player.setdefault("current_skin", "")
                player.setdefault(
                    "draw_state",
                    {"pity_count": 0, "next_pity_kind": "random"},
                )
                for value in player.get("npcs", {}).values():
                    if isinstance(value, dict):
                        value.setdefault("owned_at", value.get("obtained_at", ""))
                        value.setdefault("full_at", "")
        self.db["schema_version"] = 2
        self._save_db()

    def _load_characters(self):
        if not self.characters_path.exists():
            self.characters = [self._normalize_character(item) for item in DEFAULT_CHARACTERS]
            self._save_characters()
            return
        try:
            loaded = json.loads(self.characters_path.read_text(encoding="utf-8"))
            characters = loaded.get("characters", loaded) if isinstance(loaded, dict) else loaded
            if isinstance(characters, list) and any(
                isinstance(item, dict) and not item.get("kind") and not item.get("type") for item in characters
            ):
                self._backup_once(self.characters_path, "v1")
            normalized = [self._normalize_character(item) for item in characters]
            self.characters = [item for item in normalized if item["id"] not in RETIRED_CHARACTER_IDS]
            retired_count = len(normalized) - len(self.characters)
            if retired_count:
                logger.info(f"已移除 {retired_count} 个停用的旧 NPC 条目。")
        except Exception as exc:
            logger.error(f"读取角色配置失败，将使用默认角色：{exc}")
            self.characters = [self._normalize_character(item) for item in DEFAULT_CHARACTERS]

        # Defaults are a first-install seed only.  Re-adding every missing
        # default here made an operator's deliberate deletion reappear after a
        # reload, which is especially confusing when the customer replaces the
        # initial illustrations with their own companion library.
        self._save_characters()

    def _load_settings(self):
        self.settings = dict(DEFAULT_VISUAL_SETTINGS)
        if not self.settings_path.exists():
            self._save_settings()
            return
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"读取同伴视觉设置失败，将使用默认设置：{exc}")
            raw = {}
        if isinstance(raw, dict):
            for key, default in DEFAULT_VISUAL_SETTINGS.items():
                value = str(raw.get(key) or default)
                self.settings[key] = value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else default
        self._save_settings()

    def _save_settings(self):
        self.data_dir.mkdir(exist_ok=True)
        self._write_json_atomic(self.settings_path, self.settings)

    def _save_settings_from_payload(self, data: Dict[str, Any]) -> Dict[str, str]:
        for key, default in DEFAULT_VISUAL_SETTINGS.items():
            value = str(data.get(key) or self.settings.get(key) or default)
            self.settings[key] = value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else default
        self._save_settings()
        return self.settings

    def _default_checkin_template(self) -> Dict[str, Any]:
        return {
            "id": "default",
            "name": "同伴打卡样式",
            "image": "",
            "enabled": True,
            "show_companion": True,
            "message": "今日也要和同伴一起前进。",
            "panel_color": "#152238",
            "texts": {
                "title": {"text": "{title}", "x": 0.07, "y": 0.14, "size": 0.062, "color": "#ffffff", "bold": True},
                "reward": {"text": "{reward}", "x": 0.08, "y": 0.30, "size": 0.042, "color": "#eaf4ff", "bold": True},
                "coins": {"text": "当前星币：{coins}", "x": 0.08, "y": 0.41, "size": 0.038, "color": "#d7e6f5", "bold": False},
                "message": {"text": "{message}", "x": 0.08, "y": 0.58, "size": 0.030, "color": "#c8d9ea", "bold": False},
            },
        }

    def _load_checkin_templates(self):
        if not self.checkin_templates_path.exists():
            self.checkin_templates = [self._default_checkin_template()]
            self._save_checkin_templates()
            return
        try:
            raw = json.loads(self.checkin_templates_path.read_text(encoding="utf-8"))
            templates = raw.get("templates", raw) if isinstance(raw, dict) else raw
            self.checkin_templates = [self._normalize_checkin_template(item) for item in templates if isinstance(item, dict)]
        except Exception as exc:
            logger.error(f"读取打卡模板失败，将使用默认样式：{exc}")
            self.checkin_templates = []
        if not self.checkin_templates:
            self.checkin_templates = [self._default_checkin_template()]
        self._save_checkin_templates()

    def _save_checkin_templates(self):
        self._write_json_atomic(self.checkin_templates_path, {"templates": self.checkin_templates})

    def _normalize_checkin_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        base = self._default_checkin_template()
        template_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(data.get("id") or "").strip()).strip("_")
        base["id"] = template_id or f"checkin_{int(datetime.now().timestamp())}"
        base["name"] = str(data.get("name") or base["name"]).strip()[:60]
        base["image"] = Path(str(data.get("image") or "")).name
        base["enabled"] = bool(data.get("enabled", True))
        base["show_companion"] = bool(data.get("show_companion", True))
        base["message"] = str(data.get("message") or base["message"]).strip()[:180]
        panel_color = str(data.get("panel_color") or base["panel_color"])
        base["panel_color"] = panel_color if re.fullmatch(r"#[0-9a-fA-F]{6}", panel_color) else base["panel_color"]
        raw_texts = data.get("texts") if isinstance(data.get("texts"), dict) else {}
        for key, defaults in base["texts"].items():
            source = raw_texts.get(key) if isinstance(raw_texts.get(key), dict) else {}
            if "text" in source:
                defaults["text"] = str(source.get("text") or "")[:180]
            defaults["x"] = self._template_number(source.get("x"), defaults["x"], 0, 1)
            defaults["y"] = self._template_number(source.get("y"), defaults["y"], 0, 1)
            defaults["size"] = self._template_number(source.get("size"), defaults["size"], 0.015, 0.15)
            color = str(source.get("color") or defaults["color"])
            defaults["color"] = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else defaults["color"]
            defaults["bold"] = bool(source.get("bold", defaults["bold"]))
        return base

    @staticmethod
    def _template_number(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            return max(minimum, min(maximum, float(value)))
        except (TypeError, ValueError):
            return default

    def _save_characters(self):
        self.data_dir.mkdir(exist_ok=True)
        payload = {"characters": self.characters}
        self._write_json_atomic(self.characters_path, payload)

    def _normalize_character(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize companions, skins and items while retaining legacy character JSON."""
        raw_kind = str(data.get("kind") or data.get("type") or COMPANION_KIND).lower()
        kind = raw_kind if raw_kind in {COMPANION_KIND, SKIN_KIND, ITEM_KIND} else COMPANION_KIND
        name = str(data.get("name") or data.get("id") or "未命名同伴").strip()
        character_id = self._slug(str(data.get("id") or name))
        quality = str(data.get("quality") or data.get("star") or ("普通" if kind == ITEM_KIND else "R")).strip().upper()
        if kind == ITEM_KIND:
            quality = str(data.get("quality") or data.get("star") or "普通").strip()
            if quality not in ITEM_QUALITIES:
                quality = "普通"
        elif quality not in QUALITY_RANK:
            quality = "R"
        colors = data.get("colors") or ["#6c8cff", "#f4d35e", "#10172a"]
        if not isinstance(colors, list) or len(colors) < 3:
            colors = ["#6c8cff", "#f4d35e", "#10172a"]
        image = Path(str(data.get("image") or f"{character_id}.png").strip()).name

        if kind == ITEM_KIND:
            pool_tier = str(data.get("pool_tier") or data.get("tier") or quality).strip()
            if pool_tier not in ITEM_QUALITIES:
                pool_tier = quality
            return {
                "id": character_id,
                "kind": ITEM_KIND,
                "name": name,
                "english_name": str(data.get("english_name") or "").strip(),
                "quality": quality,
                "pool_tier": pool_tier,
                "effect": str(data.get("effect") or "暂未填写效果。").strip(),
                "image": image,
                "in_pool": bool(data.get("in_pool", data.get("featured", False))),
                "focal_x": self._template_number(data.get("focal_x"), 0.5, 0, 1),
                "focal_y": self._template_number(data.get("focal_y"), 0.5, 0, 1),
                "colors": [str(colors[0]), str(colors[1]), str(colors[2])],
            }

        english_name = str(data.get("english_name") or data.get("skin") or "").strip()
        parent_id = self._slug(str(data.get("parent_id") or data.get("parent") or "")) if kind == SKIN_KIND else ""
        if kind == SKIN_KIND:
            return {
                "id": character_id,
                "kind": SKIN_KIND,
                "parent_id": parent_id,
                "name": name,
                "english_name": english_name or name,
                "quality": quality,
                "star": quality,
                "skin": english_name or name,
                "image": image,
                "in_pool": bool(data.get("in_pool", data.get("featured", False))),
                "featured": bool(data.get("in_pool", data.get("featured", False))),
                "focal_x": self._template_number(data.get("focal_x"), 0.5, 0, 1),
                "focal_y": self._template_number(data.get("focal_y"), 0.5, 0, 1),
                "colors": [str(colors[0]), str(colors[1]), str(colors[2])],
            }

        skills = data.get("skills") or [["未命名技能", "待填写。"], ["未命名技能", "待填写。"], ["未命名技能", "待填写。"]]
        normalized_skills = []
        for item in skills[:3]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                normalized_skills.append([str(item[0]), str(item[1])])
            elif isinstance(item, dict):
                normalized_skills.append([str(item.get("name", "未命名技能")), str(item.get("desc", "待填写。"))])
            else:
                normalized_skills.append(["未命名技能", str(item)])
        while len(normalized_skills) < 3:
            normalized_skills.append(["未命名技能", "待填写。"])

        return {
            "id": character_id,
            "kind": COMPANION_KIND,
            "name": name,
            "base": str(data.get("base") or name).strip(),
            "english_name": english_name,
            "skin": english_name,
            "quality": quality,
            "star": quality,
            "route": str(data.get("route") or "运营后台添加").strip(),
            "bonus": str(data.get("bonus") or "通用经验 +5%").strip(),
            "intro": str(data.get("intro") or "这个角色还没有介绍。").strip(),
            "skills": normalized_skills,
            "colors": [str(colors[0]), str(colors[1]), str(colors[2])],
            "image": image,
            "exclusive_item": str(data.get("exclusive_item") or "").strip(),
            "in_pool": bool(data.get("in_pool", data.get("featured", False))),
            "featured": bool(data.get("in_pool", data.get("featured", False))),
            "focal_x": self._template_number(data.get("focal_x"), 0.5, 0, 1),
            "focal_y": self._template_number(data.get("focal_y"), 0.5, 0, 1),
        }

    def _known_players(self) -> List[Dict[str, Any]]:
        players: List[Dict[str, Any]] = []
        for scope_id, scope in self.db.get("scopes", {}).items():
            for user_id, player in scope.get("players", {}).items():
                players.append(
                    {
                        "scope_id": scope_id,
                        "user_id": user_id,
                        "name": player.get("name") or user_id,
                        "current_npc": player.get("current_npc"),
                        "owned_count": len(player.get("npcs", {})) + len(player.get("skins", {})),
                    }
                )
        return players

    def _scope_id(self, event: AstrMessageEvent) -> str:
        for name in ("get_group_id", "get_session_id"):
            func = getattr(event, name, None)
            if callable(func):
                try:
                    value = func()
                    if value:
                        return str(value)
                except Exception:
                    pass
        return str(getattr(event, "unified_msg_origin", "global"))

    def _group_id(self, event: AstrMessageEvent) -> str:
        """Return a real group ID only; never treat a private session as a group."""
        func = getattr(event, "get_group_id", None)
        if not callable(func):
            return ""
        try:
            value = func()
            return str(value) if value else ""
        except Exception:
            return ""

    def _sender_id(self, event: AstrMessageEvent) -> str:
        for name in ("get_sender_id", "get_user_id"):
            func = getattr(event, name, None)
            if callable(func):
                try:
                    value = func()
                    if value:
                        return str(value)
                except Exception:
                    pass
        return event.get_sender_name()

    async def _operator_denial(self, event: AstrMessageEvent, action: str) -> Optional[Path]:
        allowed, message = await self._ensure_operator_permission(event)
        if allowed:
            return None
        return self._render_text_card(
            f"{action}：权限不足",
            [message],
            subtitle="该操作会直接改变玩家资产，仅限本群群主、群管理员或 AstrBot 管理员。",
        )

    async def _ensure_operator_permission(self, event: AstrMessageEvent) -> Tuple[bool, str]:
        """Allow AstrBot admins or real-time verified QQ group owners/admins."""
        is_admin = getattr(event, "is_admin", None)
        if callable(is_admin):
            try:
                if is_admin():
                    return True, "AstrBot 管理员授权。"
            except Exception:
                pass

        group_id = self._group_id(event)
        sender_id = self._sender_id(event)
        if not group_id or not sender_id:
            return False, "私聊中仅 AstrBot 管理员可以执行该操作。"

        try:
            group_number = int(group_id)
            sender_number = int(sender_id)
        except (TypeError, ValueError):
            return False, "无法识别群号或发送者 QQ，已拒绝执行。"

        ok, info = await self._onebot_call_raw(
            event,
            "get_group_member_info",
            group_id=group_number,
            user_id=sender_number,
            no_cache=True,
        )
        if not ok:
            return False, "无法实时验证你的 QQ 群权限，已拒绝执行。"

        if isinstance(info, dict) and isinstance(info.get("data"), dict):
            info = info["data"]
        role = str(info.get("role") or "").lower() if isinstance(info, dict) else ""
        if role in {"owner", "admin"}:
            return True, f"已验证 QQ 群权限：{role}。"
        return False, "仅本群群主、群管理员或 AstrBot 管理员可以执行该操作。"

    @staticmethod
    async def _onebot_call_raw(event: AstrMessageEvent, action: str, **payload: Any) -> Tuple[bool, Any]:
        get_platform_name = getattr(event, "get_platform_name", None)
        try:
            platform_name = get_platform_name() if callable(get_platform_name) else ""
        except Exception:
            platform_name = ""
        bot = getattr(event, "bot", None)
        api = getattr(bot, "api", None)
        call_action = getattr(api, "call_action", None)
        if platform_name != "aiocqhttp" or not callable(call_action):
            return False, "当前平台不支持 OneBot 实时群权限查询。"
        try:
            return True, await call_action(action, **payload)
        except Exception:
            logger.exception("剧本杀插件 OneBot API 调用失败：%s", action)
            return False, "OneBot API 调用失败。"

    def _scope(self, event: AstrMessageEvent) -> Dict[str, Any]:
        return self._db_scope(self._scope_id(event))

    def _db_scope(self, scope_id: str) -> Dict[str, Any]:
        scopes = self.db.setdefault("scopes", {})
        return scopes.setdefault(str(scope_id), {"players": {}})

    def _new_player(self, user_id: str, name: str) -> Dict[str, Any]:
        starter = "rin" if self._character_or_none("rin") else self._companions()[0]["id"]
        return {
            "user_id": user_id,
            "name": name,
            "coins": 20,
            "tickets": 0,
            "last_checkin": "",
            "current_npc": starter,
            "npcs": {starter: {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}},
            "skins": {},
            "items": {},
            "exclusive_items": {},
            "current_skin": "",
            "draw_state": {"pity_count": 0, "next_pity_kind": "random"},
        }

    def _get_player(self, event: AstrMessageEvent) -> Dict[str, Any]:
        return self._get_player_by_id(event, self._sender_id(event), event.get_sender_name())

    def _get_player_by_id(self, event: AstrMessageEvent, user_id: str, name: str) -> Dict[str, Any]:
        return self._get_player_by_scope(self._scope_id(event), user_id, name)

    def _get_player_by_scope(self, scope_id: str, user_id: str, name: str) -> Dict[str, Any]:
        players = self._db_scope(scope_id).setdefault("players", {})
        player = players.setdefault(str(user_id), self._new_player(str(user_id), name))
        player["name"] = name or player.get("name") or str(user_id)
        player.setdefault("coins", 0)
        player.setdefault("tickets", 0)
        player.setdefault("npcs", {})
        player.setdefault("skins", {})
        player.setdefault("items", {})
        player.setdefault("exclusive_items", {})
        player.setdefault("current_skin", "")
        player.setdefault("draw_state", {"pity_count": 0, "next_pity_kind": "random"})
        self._migrate_player_npcs(player)
        if not player["npcs"]:
            starter = "rin" if self._character_or_none("rin") else self._companions()[0]["id"]
            player["npcs"][starter] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
        player.setdefault("current_npc", next(iter(player["npcs"])))
        current = self._character_or_none(str(player.get("current_npc") or ""))
        if player["current_npc"] not in player["npcs"] or not current or current.get("kind") != COMPANION_KIND:
            player["current_npc"] = next(
                (
                    character_id for character_id in player["npcs"]
                    if (entry := self._character_or_none(character_id)) and entry.get("kind") == COMPANION_KIND
                ),
                self._companions()[0]["id"],
            )
        skin = self._character_or_none(str(player.get("current_skin") or ""))
        if not skin or skin.get("kind") != SKIN_KIND or skin["id"] not in player["skins"] or skin.get("parent_id") != player["current_npc"]:
            player["current_skin"] = ""
        return player

    def _migrate_player_npcs(self, player: Dict[str, Any]):
        npcs = player.setdefault("npcs", {})
        for character_id, value in list(npcs.items()):
            if isinstance(value, int):
                npcs[character_id] = {"exp": value, "owned_at": ""}
            elif isinstance(value, dict):
                value.setdefault("exp", 0)
                value.setdefault("owned_at", "")
                value.setdefault("full_at", "")
            else:
                npcs[character_id] = {"exp": 0, "owned_at": ""}

        retired_exp = 0
        for character_id in list(npcs.keys()):
            if character_id not in RETIRED_CHARACTER_IDS:
                continue
            retired = npcs.pop(character_id)
            try:
                retired_exp += max(0, int(retired.get("exp", 0)))
            except (TypeError, ValueError):
                pass

        if retired_exp:
            replacement_id = next(
                (character_id for character_id in npcs if self._character_or_none(character_id)),
                self._companions()[0]["id"],
            )
            replacement = npcs.setdefault(
                replacement_id,
                {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")},
            )
            replacement["exp"] = max(0, int(replacement.get("exp", 0))) + retired_exp

        if player.get("current_npc") in RETIRED_CHARACTER_IDS:
            valid_owned = next(
                (character_id for character_id in npcs if self._character_or_none(character_id)),
                None,
            )
            player["current_npc"] = valid_owned or self._companions()[0]["id"]

        for character_id in list(npcs.keys()):
            if not self._character_or_none(character_id):
                logger.info(f"玩家拥有未知角色 {character_id}，暂时保留数据。")

        skins = player.setdefault("skins", {})
        if not isinstance(skins, dict):
            player["skins"] = skins = {}
        for skin_id, value in list(skins.items()):
            if isinstance(value, str):
                skins[skin_id] = {"owned_at": value}
            elif isinstance(value, dict):
                value.setdefault("owned_at", "")
            else:
                skins[skin_id] = {"owned_at": ""}

        items = player.setdefault("items", {})
        if not isinstance(items, dict):
            player["items"] = items = {}
        for item_id, value in list(items.items()):
            if isinstance(value, int):
                items[item_id] = {"count": max(0, value), "owned_at": ""}
            elif isinstance(value, dict):
                value["count"] = max(0, int(value.get("count", 0) or 0))
                value.setdefault("owned_at", "")
            else:
                items[item_id] = {"count": 0, "owned_at": ""}

        exclusive_items = player.setdefault("exclusive_items", {})
        if not isinstance(exclusive_items, dict):
            player["exclusive_items"] = exclusive_items = {}
        for companion_id, value in list(exclusive_items.items()):
            if isinstance(value, str):
                exclusive_items[companion_id] = {"owned_at": value}
            elif not isinstance(value, dict):
                exclusive_items[companion_id] = {"owned_at": ""}

        draw_state = player.setdefault("draw_state", {})
        if not isinstance(draw_state, dict):
            draw_state = player["draw_state"] = {}
        draw_state["pity_count"] = max(0, min(DRAW_PITY_TARGET, int(draw_state.get("pity_count", 0) or 0)))
        if draw_state.get("next_pity_kind") not in {"random", COMPANION_KIND, SKIN_KIND}:
            draw_state["next_pity_kind"] = "random"

    def _character(self, character_id: str) -> Dict[str, Any]:
        companion = self._character_or_none(character_id)
        if companion and companion.get("kind") == COMPANION_KIND:
            return companion
        return next((item for item in self.characters if item.get("kind") == COMPANION_KIND), self.characters[0])

    def _character_or_none(self, character_id: str) -> Optional[Dict[str, Any]]:
        for character in self.characters:
            if character["id"] == character_id:
                return character
        return None

    def _companions(self) -> List[Dict[str, Any]]:
        return [item for item in self.characters if item.get("kind") == COMPANION_KIND]

    def _skins_for(self, companion_id: str) -> List[Dict[str, Any]]:
        return [
            item for item in self.characters
            if item.get("kind") == SKIN_KIND and item.get("parent_id") == companion_id
        ]

    def _items(self) -> List[Dict[str, Any]]:
        return [item for item in self.characters if item.get("kind") == ITEM_KIND]

    def _owns_entry(self, player: Dict[str, Any], entry: Dict[str, Any]) -> bool:
        kind = entry.get("kind")
        if kind == COMPANION_KIND:
            return entry["id"] in player.get("npcs", {})
        if kind == SKIN_KIND:
            return entry["id"] in player.get("skins", {})
        if kind == ITEM_KIND:
            return int(player.get("items", {}).get(entry["id"], {}).get("count", 0) or 0) > 0
        return False

    def _find_character(self, value: str) -> Optional[Dict[str, Any]]:
        value = (value or "").strip()
        if not value:
            return None
        if self._character_or_none(value):
            return self._character_or_none(value)
        lowered = value.lower()
        for character in self.characters:
            names = [
                character["name"],
                character.get("base", ""),
                character.get("skin", ""),
                f"{character.get('base', '')} {character.get('skin', '')}",
                f"{character.get('name', '')} {character.get('skin', '')}",
            ]
            if any(lowered == str(name).strip().lower() for name in names if name):
                return character
        for character in self.characters:
            if lowered in character["name"].lower() or lowered in character.get("skin", "").lower():
                return character
        return None

    def _grant_character(self, player: Dict[str, Any], character_id: str) -> bool:
        entry = self._character_or_none(character_id)
        if not entry:
            return False
        now = datetime.now().strftime("%Y-%m-%d")
        if entry.get("kind") == SKIN_KIND:
            if entry["id"] in player["skins"]:
                return False
            player["skins"][entry["id"]] = {"owned_at": now}
            return True
        if entry.get("kind") == ITEM_KIND:
            item = player["items"].setdefault(entry["id"], {"count": 0, "owned_at": now})
            item["count"] = int(item.get("count", 0) or 0) + 1
            return True
        if entry["id"] in player["npcs"]:
            return False
        player["npcs"][entry["id"]] = {"exp": 0, "owned_at": now, "full_at": ""}
        return True

    def _grant_exclusive_item(self, player: Dict[str, Any], companion_id: str) -> bool:
        companion = self._character_or_none(companion_id)
        if not companion or companion.get("kind") != COMPANION_KIND or not companion.get("exclusive_item"):
            return False
        if companion_id in player["exclusive_items"]:
            return False
        player["exclusive_items"][companion_id] = {"owned_at": datetime.now().strftime("%Y-%m-%d")}
        return True

    def _has_exclusive_item(self, player: Dict[str, Any], companion_id: str) -> bool:
        return companion_id in player.get("exclusive_items", {})

    def _npc_exp(self, player: Dict[str, Any], character_id: str) -> int:
        return int(player["npcs"].get(character_id, {}).get("exp", 0))

    def _add_exp(self, player: Dict[str, Any], character_id: str, exp: int):
        if character_id not in player["npcs"]:
            self._grant_character(player, character_id)
        record = player["npcs"][character_id]
        before = int(record.get("exp", 0) or 0)
        record["exp"] = before + max(0, int(exp))
        full_exp = sum(LEVEL_REQUIREMENTS)
        if before < full_exp <= record["exp"] and not record.get("full_at"):
            record["full_at"] = datetime.now().isoformat(timespec="seconds")

    def _level_info(self, exp: int) -> Tuple[int, int, int, float]:
        spent = 0
        for index, requirement in enumerate(LEVEL_REQUIREMENTS, start=1):
            if exp < spent + requirement:
                current = exp - spent
                return index, current, requirement, current / requirement
            spent += requirement
        return 5, LEVEL_REQUIREMENTS[-1], LEVEL_REQUIREMENTS[-1], 1.0

    def _arg_text(self, event: AstrMessageEvent) -> str:
        text = event.message_str.strip().lstrip("/!！").strip()
        command_prefixes = [
            "剧本杀帮助", "同伴帮助", "伙伴帮助", "赠送星币", "发放星币", "赠送同伴", "赠送角色", "赠送NPC", "赠送皮肤", "赠送专属", "赠送专属物品",
            "切换同伴", "切换角色", "更换角色", "选择角色", "NPC信息", "npc信息", "查询NPC",
            "角色信息", "每日打卡", "我的星币", "NPC仓库", "npc仓库", "我的NPC",
            "状态栏", "角色状态", "抽奖", "npc抽奖", "NPC抽奖", "星币", "钱包",
            "中奖号码", "开奖", "打卡", "查NPC", "同伴栏", "物品栏", "道具栏", "我的道具", "道具仓库",
        ]
        for prefix in sorted(command_prefixes, key=len, reverse=True):
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        text = re.sub(r"^[\w\u4e00-\u9fff]+", "", text, count=1).strip()
        return text

    def _parse_count(self, event: AstrMessageEvent, default: int, max_count: int) -> int:
        match = re.search(r"\d+", self._arg_text(event))
        if not match:
            return default
        return max(1, min(max_count, int(match.group())))

    def _parse_page(self, event: AstrMessageEvent, max_page: int = 999) -> int:
        match = re.search(r"\d+", self._arg_text(event))
        if not match:
            return 1
        return max(1, min(max_page, int(match.group())))

    def _parse_transfer(self, event: AstrMessageEvent) -> Tuple[Optional[str], str, int]:
        text = event.message_str
        amount_matches = re.findall(r"\d+", text)
        amount = int(amount_matches[-1]) if amount_matches else 0
        target_id, target_label = self._parse_target_user(event)
        if not target_id:
            arg = self._arg_text(event)
            tokens = arg.split()
            if len(tokens) >= 2:
                target_id = tokens[0].strip("@")
                target_label = target_id
        return target_id, target_label, amount

    def _parse_target_user(self, event: AstrMessageEvent) -> Tuple[Optional[str], str]:
        target_id = self._extract_at_id(event)
        if target_id:
            return target_id, f"用户{target_id}"
        arg = self._arg_text(event)
        tokens = arg.split()
        if tokens:
            user_id = tokens[0].strip("@")
            return user_id, user_id
        return None, ""

    def _parse_character_after_target(self, event: AstrMessageEvent) -> str:
        arg = self._arg_text(event)
        tokens = arg.split(maxsplit=1)
        if len(tokens) == 2:
            return tokens[1].strip()
        return ""

    def _extract_at_id(self, event: AstrMessageEvent) -> Optional[str]:
        try:
            messages = event.get_messages()
        except Exception:
            messages = []
        for seg in messages:
            type_name = seg.__class__.__name__.lower()
            if "at" not in type_name:
                continue
            for attr in ("qq", "user_id", "target", "id"):
                value = getattr(seg, attr, None)
                if value:
                    return str(value)
        return None

    def _roll_checkin(self) -> Tuple[str, int]:
        roll = random.randint(1, 100)
        acc = 0
        for reward_type, amount, chance in CHECKIN_REWARDS:
            acc += chance
            if roll <= acc:
                return reward_type, amount
        return "星币", 1

    def _draw_pool(self, kind: str, tier: str = "") -> List[Dict[str, Any]]:
        entries = [
            entry for entry in self.characters
            if entry.get("kind") == kind and entry.get("in_pool", False)
        ]
        if kind == ITEM_KIND and tier:
            entries = [entry for entry in entries if entry.get("pool_tier") == tier]
        # The monthly specification allows exactly one companion and one skin.
        # Legacy JSON may contain multiple historic featured entries, so remain
        # deterministic and safe until the operator next saves the pool in
        # WebUI (which clears old selections).
        if kind in {COMPANION_KIND, SKIN_KIND} and len(entries) > 1:
            logger.warning("%s 奖池包含多个条目，已临时只使用首个条目。", kind)
            entries = entries[:1]
        return entries

    def _draw_pool_gaps(self) -> List[str]:
        """Return every required reward pool that is not ready for a paid draw.

        The published odds include all three item tiers as well as a featured
        companion and skin. Charging before all five pools exist would turn a
        valid probability slot into an empty reward and is hard to repair for
        the operator, so the command blocks before deducting currency.
        """
        gaps: List[str] = []
        if not self._draw_pool(COMPANION_KIND):
            gaps.append("同伴")
        if not self._draw_pool(SKIN_KIND):
            gaps.append("皮肤")
        for tier in ITEM_QUALITIES:
            if not self._draw_pool(ITEM_KIND, tier):
                gaps.append(f"{tier}道具")
        return gaps

    def _enforce_single_featured_pool(self, saved_entry: Dict[str, Any]) -> None:
        """Keep one active companion and one active skin in the current pool.

        Item pools intentionally remain many-to-one: any number of ordinary,
        intermediate and advanced items can be checked, and one is sampled at
        random for a matching roll.
        """
        kind = saved_entry.get("kind")
        if kind not in {COMPANION_KIND, SKIN_KIND} or not saved_entry.get("in_pool"):
            return
        for entry in self.characters:
            if entry.get("id") == saved_entry.get("id") or entry.get("kind") != kind:
                continue
            entry["in_pool"] = False
            entry["featured"] = False

    def _monthly_pool(self) -> List[Dict[str, Any]]:
        """Compatibility name: return only entries explicitly enabled in the current pool."""
        return self._draw_pool(COMPANION_KIND) + self._draw_pool(SKIN_KIND)

    def _grant_draw_entry(self, player: Dict[str, Any], entry: Dict[str, Any], label: str) -> Dict[str, Any]:
        current_id = player.get("current_npc", self._companions()[0]["id"])
        # Items are stackable inventory.  A duplicate draw must grant another
        # copy (and increment the visible quantity), whereas duplicate
        # companions/skins are intentionally converted into progression EXP.
        if entry.get("kind") == ITEM_KIND:
            self._grant_character(player, entry["id"])
            return {
                "kind": label,
                "name": entry["name"],
                "exp": 0,
                "character_id": current_id,
                "entry_id": entry["id"],
                "entry_kind": ITEM_KIND,
                "image": entry.get("image", ""),
            }
        if self._owns_entry(player, entry):
            exp = 20
            self._add_exp(player, current_id, exp)
            return {
                "kind": f"重复{label}转经验",
                "name": entry["name"],
                "exp": exp,
                "character_id": current_id,
                "entry_id": entry["id"],
                "entry_kind": entry.get("kind"),
                "image": entry.get("image", ""),
            }
        self._grant_character(player, entry["id"])
        return {
            "kind": label,
            "name": entry["name"],
            "exp": 0,
            "character_id": current_id,
            "entry_id": entry["id"],
            "entry_kind": entry.get("kind"),
            "image": entry.get("image", ""),
        }

    def _roll_draw(self, player: Dict[str, Any]) -> Dict[str, Any]:
        """Roll one result using the customer's listed rates plus a transparent 10% no-drop slot.

        The listed rates total 90%.  The final 10% intentionally gives no inventory item while still
        advancing the displayed guarantee bar; it is not silently reassigned to another reward type.
        """
        current_id = player.get("current_npc", self._companions()[0]["id"])
        state = player.setdefault("draw_state", {"pity_count": 0, "next_pity_kind": "random"})
        state["pity_count"] = max(0, int(state.get("pity_count", 0) or 0)) + 1

        companion_pool = self._draw_pool(COMPANION_KIND)
        skin_pool = self._draw_pool(SKIN_KIND)
        if state["pity_count"] >= DRAW_PITY_TARGET and (companion_pool or skin_pool):
            requested = state.get("next_pity_kind", "random")
            if requested == "random":
                requested = random.choice([kind for kind, pool in ((COMPANION_KIND, companion_pool), (SKIN_KIND, skin_pool)) if pool])
            pool = companion_pool if requested == COMPANION_KIND else skin_pool
            if not pool:
                requested = SKIN_KIND if requested == COMPANION_KIND else COMPANION_KIND
                pool = skin_pool if requested == SKIN_KIND else companion_pool
            entry = random.choice(pool)
            state["pity_count"] = 0
            state["next_pity_kind"] = SKIN_KIND if requested == COMPANION_KIND else COMPANION_KIND
            return self._grant_draw_entry(player, entry, "保底同伴" if requested == COMPANION_KIND else "保底皮肤")

        roll = random.random() * 100
        cursor = 0.0
        for rate, name, exp, image in EXPERIENCE_BALLS:
            cursor += rate
            if roll < cursor:
                self._add_exp(player, current_id, exp)
                return {"kind": "经验球", "name": name, "exp": exp, "character_id": current_id, "entry_kind": "experience", "image": image}

        for rate, tier in ((6, "普通"), (4, "中级"), (3, "高级")):
            cursor += rate
            if roll < cursor:
                pool = self._draw_pool(ITEM_KIND, tier)
                if not pool:
                    return {"kind": f"{tier}道具池为空", "name": "未配置道具", "exp": 0, "character_id": current_id, "entry_kind": ITEM_KIND}
                return self._grant_draw_entry(player, random.choice(pool), f"{tier}道具")

        cursor += 0.8
        if roll < cursor:
            if companion_pool:
                state["pity_count"] = 0
                return self._grant_draw_entry(player, random.choice(companion_pool), "同伴")
            return {"kind": "同伴池为空", "name": "未配置同伴", "exp": 0, "character_id": current_id, "entry_kind": COMPANION_KIND}

        cursor += 1.2
        if roll < cursor:
            if skin_pool:
                state["pity_count"] = 0
                return self._grant_draw_entry(player, random.choice(skin_pool), "皮肤")
            return {"kind": "皮肤池为空", "name": "未配置皮肤", "exp": 0, "character_id": current_id, "entry_kind": SKIN_KIND}

        return {"kind": "未命中", "name": "保底进度 +1", "exp": 0, "character_id": current_id, "entry_kind": "none"}

    def _slug(self, value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"\s+", "_", value)
        value = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]", "", value)
        return value or f"character_{int(datetime.now().timestamp())}"

    async def _request_upload_file(self) -> Any:
        """Read multipart files across the AstrBot WebUI bridge and direct Quart fetches."""
        try:
            files = request.files
            if inspect.isawaitable(files):
                files = await files
        except Exception:
            files = None
        if hasattr(files, "get"):
            return files.get("file") or files.get("image")
        if isinstance(files, (list, tuple)):
            return files[0] if files else None
        return None

    async def _save_uploaded_image(self, upload: Any, destination: Optional[Path] = None, prefix: str = "custom") -> str:
        raw_name = Path(getattr(upload, "filename", "") or "character.png").name
        suffix = Path(raw_name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("仅支持 PNG、JPG、JPEG 或 WebP 图片。")
        saved_name = f"{prefix}_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}{suffix}"
        dest = (destination or self.assets_dir) / saved_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(upload, "save"):
            result = upload.save(str(dest))
            if inspect.isawaitable(result):
                await result
        else:
            source_path = getattr(upload, "path", None)
            if source_path:
                shutil.copyfile(str(source_path), dest)
            else:
                reader = getattr(upload, "read", None)
                if not callable(reader):
                    raise RuntimeError("当前 AstrBot 上传对象不支持保存。")
                content = reader()
                if inspect.isawaitable(content):
                    content = await content
                dest.write_bytes(content)
        if dest.stat().st_size > 15 * 1024 * 1024:
            dest.unlink(missing_ok=True)
            raise ValueError("图片不能超过 15MB。")
        try:
            with Image.open(dest) as image:
                image.verify()
            with Image.open(dest) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError("图片像素过大，请使用小于 4000 万像素的图片。")
        except ValueError:
            dest.unlink(missing_ok=True)
            raise
        except Exception:
            dest.unlink(missing_ok=True)
            raise ValueError("上传文件不是有效图片或图片已损坏。")
        return saved_name

    @staticmethod
    def _image_data_url(image: Image.Image) -> str:
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=88, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _thumbnail_data_url(self, path: Path, size: Tuple[int, int] = (320, 180)) -> str:
        if not path.is_file():
            return ""
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail(size, Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", size, "#edf2f7")
                left = (size[0] - image.width) // 2
                top = (size[1] - image.height) // 2
                canvas.paste(image, (left, top))
                return self._image_data_url(canvas)
        except Exception as exc:
            logger.warning(f"生成后台图片预览失败：{path.name}，原因：{exc}")
            return ""

    def _ensure_fonts(self):
        if self._find_font_file(False) and self._find_font_file(True):
            return

        self.font_dir.mkdir(exist_ok=True)
        for filename, url in DOWNLOADABLE_FONTS:
            path = self.font_dir / filename
            if path.exists() and path.stat().st_size > 8 * 1024 * 1024:
                continue
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            try:
                logger.info(f"正在下载中文字体：{filename}")
                tmp_path.unlink(missing_ok=True)
                urllib.request.urlretrieve(url, tmp_path)
                if tmp_path.stat().st_size <= 8 * 1024 * 1024:
                    raise RuntimeError("字体文件下载不完整")
                tmp_path.replace(path)
            except Exception as exc:
                tmp_path.unlink(missing_ok=True)
                if path.exists() and path.stat().st_size <= 8 * 1024 * 1024:
                    path.unlink(missing_ok=True)
                logger.error(f"下载中文字体失败：{filename}，原因：{exc}")

    def _find_font_file(self, bold: bool = False) -> Optional[Path]:
        local_bold = [self.font_dir / "NotoSansCJKsc-Bold.otf", self.font_dir / "SourceHanSansSC-Bold.otf"]
        local_regular = [self.font_dir / "NotoSansCJKsc-Regular.otf", self.font_dir / "SourceHanSansSC-Regular.otf"]
        system_bold = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("C:/Windows/Fonts/msyhbd.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
        ]
        system_regular = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simsun.ttc"),
        ]

        candidates = (local_bold + system_bold if bold else local_regular + system_regular)
        if bold:
            candidates += local_regular + system_regular

        for font_path in candidates:
            if not font_path.exists():
                continue
            min_size = 8 * 1024 * 1024 if self.font_dir in font_path.parents else 1024
            if font_path.stat().st_size > min_size:
                return font_path
        return None

    def _font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        cache_key = (size, bold)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_path = self._find_font_file(bold)
        if font_path:
            font = ImageFont.truetype(str(font_path), size)
            self._font_cache[cache_key] = font
            return font

        if not self._warned_missing_font:
            logger.error("未找到中文字体，图片文字可能显示为方块。请将 NotoSansCJKsc-Regular.otf 放入 data/fonts。")
            self._warned_missing_font = True
        font = ImageFont.load_default()
        self._font_cache[cache_key] = font
        return font

    def _wrap(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> List[str]:
        lines: List[str] = []
        current = ""
        for char in text:
            candidate = current + char
            if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines

    def _gradient(self, size: Tuple[int, int], c1: str, c2: str) -> Image.Image:
        img = Image.new("RGB", size, c1)
        draw = ImageDraw.Draw(img)
        r1, g1, b1 = Image.new("RGB", (1, 1), c1).getpixel((0, 0))
        r2, g2, b2 = Image.new("RGB", (1, 1), c2).getpixel((0, 0))
        for y in range(size[1]):
            t = y / max(1, size[1] - 1)
            color = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
            draw.line((0, y, size[0], y), fill=color)
        return img

    def _ensure_assets(self):
        for character in self.characters:
            path = self.assets_dir / character["image"]
            if path.exists():
                continue
            self._draw_placeholder_portrait(character, path)

    def _draw_placeholder_portrait(self, character: Dict[str, Any], path: Path):
        main, accent, dark = character["colors"]
        img = self._gradient((960, 540), dark, main).convert("RGBA")
        draw = ImageDraw.Draw(img)
        rng = random.Random(character["id"])
        for _ in range(80):
            x = rng.randint(0, 960)
            y = rng.randint(0, 540)
            r = rng.randint(1, 3)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(40, 145)))
        draw.rounded_rectangle((70, 70, 890, 470), radius=28, fill=(255, 255, 255, 42), outline=(255, 255, 255, 150), width=3)
        draw.text((110, 145), character["name"], font=self._font(62, True), fill=(255, 255, 255, 245))
        kind = character.get("kind", COMPANION_KIND)
        subtitle = character.get("english_name") or character.get("skin") or "默认"
        prompt = "请在插件后台上传道具图片" if kind == ITEM_KIND else "请在插件后台上传同伴/皮肤图片"
        quality = character.get("quality") or character.get("star") or "R"
        draw.text((112, 220), str(subtitle), font=self._font(34, True), fill=Image.new("RGB", (1, 1), accent).getpixel((0, 0)) + (255,))
        draw.text((112, 285), prompt, font=self._font(28), fill=(255, 255, 255, 215))
        draw.text((112, 335), str(quality), font=self._font(38, True), fill=(255, 240, 170, 255))
        path.parent.mkdir(parents=True, exist_ok=True)
        # JPEG has no alpha channel.  Default companion assets historically
        # use ``.jpg`` names, so generating a missing placeholder must flatten
        # it before saving instead of making an otherwise unrelated WebUI save
        # request fail with ``cannot write mode RGBA as JPEG``.
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            img.convert("RGB").save(path, quality=92)
        else:
            img.save(path)

    def _active_skin(self, player: Dict[str, Any], companion_id: str) -> Optional[Dict[str, Any]]:
        skin = self._character_or_none(str(player.get("current_skin") or ""))
        if not skin or skin.get("kind") != SKIN_KIND:
            return None
        if skin.get("parent_id") != companion_id or skin["id"] not in player.get("skins", {}):
            return None
        return skin

    def _portrait(self, character: Dict[str, Any], size: Tuple[int, int]) -> Image.Image:
        path = self.assets_dir / character["image"]
        if not path.exists():
            self._draw_placeholder_portrait(character, path)
        with Image.open(path) as source:
            img = ImageOps.exif_transpose(source).convert("RGBA")
        focal_x = self._template_number(character.get("focal_x"), 0.5, 0, 1)
        focal_y = self._template_number(character.get("focal_y"), 0.5, 0, 1)
        return ImageOps.fit(
            img,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(focal_x, focal_y),
        )

    def _asset_thumbnail(self, filename: str, size: Tuple[int, int]) -> Optional[Image.Image]:
        path = self.assets_dir / Path(filename or "").name
        if not path.is_file():
            return None
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGBA")
            return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        except Exception as exc:
            logger.warning(f"读取奖品缩略图失败：{path.name}，原因：{exc}")
            return None

    def _render_text_card(self, title: str, lines: List[str], subtitle: str = "") -> Path:
        path = self.render_dir / f"text_{datetime.now().timestamp()}.png"
        img = self._gradient((1100, 700), "#18243c", "#2f6b6d").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((60, 60, 1040, 640), radius=28, fill=(255, 255, 255, 232))
        draw.text((105, 105), title, font=self._font(54, True), fill="#172033")
        y = 200
        for line in lines:
            for wrapped in self._wrap(draw, line, self._font(32), 850):
                draw.text((115, y), wrapped, font=self._font(32), fill="#243044")
                y += 48
            y += 10
        if subtitle:
            draw.line((105, 545, 995, 545), fill="#d0d6e2", width=2)
            for wrapped in self._wrap(draw, subtitle, self._font(24), 850)[:2]:
                draw.text((115, 565), wrapped, font=self._font(24), fill="#657086")
                y += 32
        img.save(path)
        return path

    def _render_notice_card(self, title: str, message: str) -> Path:
        """A compact, stable tip card for errors and short confirmations."""
        path = self.render_dir / f"notice_{datetime.now().timestamp()}.png"
        img = self._gradient((620, 220), "#1b2b45", "#355f68").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((22, 22, 598, 198), radius=20, fill=(255, 255, 255, 238))
        draw.text((55, 54), title, font=self._font(30, True), fill="#1d2b42")
        for index, line in enumerate(self._wrap(draw, message, self._font(21), 500)[:2]):
            draw.text((55, 110 + index * 30), line, font=self._font(21), fill="#526071")
        img.save(path)
        return path

    def _render_checkin_card(self, player: Dict[str, Any], title: str, reward: str, today: str = "") -> Path:
        """Render a full-bleed 16:9 check-in card with an optional large companion portrait."""
        enabled = [item for item in self.checkin_templates if item.get("enabled")]
        template = random.choice(enabled or self.checkin_templates or [self._default_checkin_template()])
        companion = self._character(player.get("current_npc", ""))
        skin = self._active_skin(player, companion["id"])
        values = {
            "title": title,
            "reward": reward,
            "coins": player.get("coins", 0),
            "date": today or datetime.now().strftime("%Y-%m-%d"),
            "message": template.get("message") or "今日也要和同伴一起前进。",
            "_portrait_entry": skin or companion,
        }
        img = self._compose_checkin_image(template, values)
        path = self.render_dir / f"checkin_{player['user_id']}_{datetime.now().timestamp()}.png"
        img.save(path)
        return path

    def _compose_checkin_image(self, template: Dict[str, Any], values: Dict[str, Any]) -> Image.Image:
        """Compose one template so WebUI preview and QQ output share exactly the same renderer."""
        size = (1280, 720)
        image_name = str(template.get("image") or "")
        background_path = self.checkin_assets_dir / Path(image_name).name
        if image_name and background_path.exists():
            img = self._cover_image(background_path, size)
        else:
            img = self._gradient(size, "#18243c", "#2f6b6d").convert("RGBA")

        draw = ImageDraw.Draw(img)
        panel_color = str(template.get("panel_color") or "#152238")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", panel_color):
            panel_color = "#152238"
        rgb = Image.new("RGB", (1, 1), panel_color).getpixel((0, 0))
        draw.rounded_rectangle((48, 56, 710, 664), radius=30, fill=rgb + (205,))
        portrait_entry = values.get("_portrait_entry")
        if template.get("show_companion", True) and isinstance(portrait_entry, dict):
            portrait = self._portrait(portrait_entry, (480, 630))
            mask = Image.new("L", (480, 630), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, 479, 629), radius=28, fill=255)
            portrait.putalpha(mask)
            img.alpha_composite(portrait, (748, 46))
            draw.rounded_rectangle((748, 46, 1228, 676), radius=28, outline=(255, 255, 255, 185), width=3)
        for item in template.get("texts", {}).values():
            text = self._format_template_text(str(item.get("text") or ""), values)
            if not text:
                continue
            font_size = max(14, int(float(item.get("size", 0.04)) * size[0]))
            font = self._font(font_size, bool(item.get("bold")))
            x = int(float(item.get("x", 0)) * size[0])
            y = int(float(item.get("y", 0)) * size[1])
            color = item.get("color", "#ffffff")
            # A small shadow keeps text readable on user-supplied art without adding borders or panels.
            draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 130))
            draw.text((x, y), text, font=font, fill=color)
        return img

    @staticmethod
    def _format_template_text(template: str, values: Dict[str, Any]) -> str:
        class SafeValues(dict):
            def __missing__(self, key: str) -> str:
                return "{" + key + "}"

        try:
            return template.format_map(SafeValues(values))
        except (ValueError, AttributeError):
            return template

    @staticmethod
    def _cover_image(path: Path, size: Tuple[int, int]) -> Image.Image:
        with Image.open(path) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGBA")
        scale = max(size[0] / source.width, size[1] / source.height)
        resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
        left = max(0, (resized.width - size[0]) // 2)
        top = max(0, (resized.height - size[1]) // 2)
        return resized.crop((left, top, left + size[0], top + size[1]))

    def _render_status(self, player: Dict[str, Any], character: Dict[str, Any], banner: str = "") -> Path:
        path = self.render_dir / f"status_{player['user_id']}_{character['id']}.png"
        main, _, dark = character["colors"]
        skin = self._active_skin(player, character["id"])
        visual = skin or character
        name_color = self.settings["status_name_color"]
        meta_color = self.settings["status_meta_color"]
        panel_color = self.settings["status_panel_color"]
        img = self._gradient((1280, 840), dark, panel_color).convert("RGBA")
        draw = ImageDraw.Draw(img)
        img.alpha_composite(self._portrait(visual, (520, 730)), (55, 70))
        panel_rgb = Image.new("RGB", (1, 1), panel_color).getpixel((0, 0))
        draw.rounded_rectangle((530, 70, 1215, 805), radius=24, fill=panel_rgb + (235,))

        if banner:
            draw.rounded_rectangle((565, 95, 845, 142), radius=18, fill=main)
            draw.text((588, 103), banner, font=self._font(24, True), fill="white")

        exp = self._npc_exp(player, character["id"])
        level, current, need, ratio = self._level_info(exp)
        display_name = character["name"]
        subtitle_name = (skin or character).get("english_name") or (skin or character).get("name")
        quality = (skin or character).get("quality") or character.get("star", "R")
        draw.text((565, 160), display_name, font=self._font(54, True), fill=name_color)
        draw.text((565, 222), f"{subtitle_name}  |  {quality}  |  {character['bonus']}", font=self._font(25, True), fill=meta_color)
        stars = "★" * level + "☆" * (5 - level)
        draw.text((565, 272), stars, font=self._font(40, True), fill="#f5b642")
        draw.text((565, 328), f"Lv.{level}  {current}/{need} EXP", font=self._font(26, True), fill=meta_color)
        draw.rounded_rectangle((565, 370, 1148, 406), radius=18, fill="#dbe2ef")
        draw.rounded_rectangle((565, 370, 565 + int(583 * ratio), 406), radius=18, fill=main)

        # Character introductions are intentionally not rendered: group
        # announcements hold the narrative copy, leaving this card focused on
        # portrait, progression and skills.
        y = 445
        for threshold, (skill, desc) in zip([2, 3, 5], character["skills"]):
            unlocked = level >= threshold
            fill = "#172033" if unlocked else "#8a94a6"
            chip = main if unlocked else "#cfd6e4"
            draw.rounded_rectangle((565, y, 1148, y + 36), radius=14, fill=chip)
            draw.text((585, y + 5), f"{threshold}星 {skill}", font=self._font(20, True), fill="white" if unlocked else "#566071")
            draw.text((585, y + 41), desc, font=self._font(18), fill=meta_color if unlocked else fill)
            y += 64
        img.save(path)
        return path

    def _render_inventory(self, player: Dict[str, Any], page: int = 1) -> Path:
        """Render owned companion groups; skins are always visually nested under their parent."""
        all_groups = []
        full_exp = sum(LEVEL_REQUIREMENTS)
        for companion in self._companions():
            own_companion = companion["id"] in player.get("npcs", {})
            owned_skins = [skin for skin in self._skins_for(companion["id"]) if skin["id"] in player.get("skins", {})]
            if not own_companion and not owned_skins:
                continue
            exp = self._npc_exp(player, companion["id"]) if own_companion else 0
            record = player.get("npcs", {}).get(companion["id"], {})
            is_full = exp >= full_exp
            quality_rank = QUALITY_RANK.get(companion.get("quality") or companion.get("star"), 0)
            if is_full:
                sort_key = (0, -quality_rank, str(record.get("full_at") or record.get("owned_at") or ""), companion["id"])
            else:
                # Sort by the actual visible EXP-bar percentage, rather than
                # total accumulated EXP.  Each level has a different
                # requirement (1k/2k/3k/4k/5k), so raw EXP makes a nearly
                # empty higher-level bar incorrectly outrank a nearly full
                # lower-level bar.
                _, _, _, progress_ratio = self._level_info(exp)
                sort_key = (1, -progress_ratio, -quality_rank, str(record.get("owned_at") or ""), companion["id"])
            all_groups.append((sort_key, companion, own_companion, owned_skins, exp))
        all_groups.sort(key=lambda group: group[0])

        # A companion can own many skins.  Split those skins into small visual
        # groups before page slicing so one heavily customized companion cannot
        # make the image unboundedly tall.  Continued segments intentionally
        # repeat the parent row, keeping every skin visibly attached to it.
        skins_per_segment = 2
        segmented_groups = []
        for sort_key, companion, own_companion, owned_skins, exp in all_groups:
            if not owned_skins:
                segmented_groups.append((sort_key, companion, own_companion, [], exp, 0))
                continue
            for skin_offset in range(0, len(owned_skins), skins_per_segment):
                segmented_groups.append(
                    (
                        sort_key,
                        companion,
                        own_companion,
                        owned_skins[skin_offset: skin_offset + skins_per_segment],
                        exp,
                        skin_offset,
                    )
                )

        per_page = 2
        total_pages = max(1, (len(segmented_groups) + per_page - 1) // per_page)
        page = max(1, min(total_pages, page))
        groups = segmented_groups[(page - 1) * per_page: page * per_page]
        height = max(720, 180 + sum(182 + len(skins) * 104 for _, _, _, skins, _, _ in groups) + 45)
        path = self.render_dir / f"companions_{player['user_id']}_{page}.png"
        img = self._gradient((1280, height), "#173044", "#edf3f7").convert("RGBA")
        draw = ImageDraw.Draw(img)
        title_color = self.settings["companion_name_color"]
        meta_color = self.settings["companion_meta_color"]
        border_color = self.settings["companion_border_color"]
        exclusive_color = self.settings["exclusive_item_color"]
        exclusive_border = self.settings["exclusive_item_border_color"]
        draw.text((58, 38), "同伴栏", font=self._font(54, True), fill="white")
        owned_total = len(player.get("npcs", {})) + len(player.get("skins", {}))
        draw.text((60, 105), f"当前同伴：{self._character(player['current_npc'])['name']}    已拥有：{owned_total}    第 {page}/{total_pages} 页", font=self._font(24), fill="#dbe7f0")

        if not groups:
            draw.rounded_rectangle((55, 175, 1225, 565), radius=24, fill=(255, 255, 255, 238))
            draw.text((105, 310), "暂未获得同伴或皮肤", font=self._font(38, True), fill=title_color)
            draw.text((105, 370), "可通过抽奖、活动或管理员赠送获得。", font=self._font(25), fill=meta_color)
            img.save(path)
            return path

        y = 164
        for _, companion, own_companion, owned_skins, exp, skin_offset in groups:
            main = companion["colors"][0]
            row_fill = (255, 255, 255, 238) if own_companion else (229, 234, 240, 232)
            draw.rounded_rectangle((52, y, 1228, y + 164), radius=18, fill=row_fill, outline=border_color, width=3)
            portrait = self._portrait(companion, (214, 148))
            if not own_companion:
                portrait = ImageEnhance.Color(portrait).enhance(0.05).filter(ImageFilter.GaussianBlur(0.45))
            img.alpha_composite(portrait, (68, y + 8))
            name_fill = title_color if own_companion else "#8b94a6"
            sub_fill = meta_color if own_companion else "#9aa4b3"
            draw.text((304, y + 17), companion["name"], font=self._font(31, True), fill=name_fill)
            draw.text((304, y + 57), f"{companion.get('english_name') or '—'}  |  {companion.get('quality', companion.get('star', 'R'))}  |  {companion['bonus']}", font=self._font(21), fill=sub_fill)
            level, current, need, ratio = self._level_info(exp) if own_companion else (0, 0, LEVEL_REQUIREMENTS[0], 0)
            draw.rounded_rectangle((304, y + 93, 803, y + 115), radius=11, fill="#dbe2ef")
            if own_companion:
                draw.rounded_rectangle((304, y + 93, 304 + int(499 * ratio), y + 115), radius=11, fill=main)
            draw.text((825, y + 89), f"{'已拥有' if own_companion else '未获得'}  Lv.{level}  {current}/{need}", font=self._font(20), fill=sub_fill)
            if companion.get("exclusive_item"):
                exclusive_owned = self._has_exclusive_item(player, companion["id"])
                item_color = exclusive_color if exclusive_owned else "#9aa4b3"
                item_border = exclusive_border if exclusive_owned else "#c5ccd6"
                draw.rounded_rectangle((304, y + 126, 635, y + 158), radius=10, outline=item_border, width=2, fill=(255, 255, 255, 35))
                draw.text((321, y + 130), f"专属物品：{companion['exclusive_item']}", font=self._font(17, True), fill=item_color)
            if companion["id"] == player.get("current_npc"):
                draw.rounded_rectangle((1120, y + 16, 1204, y + 49), radius=12, fill=main)
                draw.text((1137, y + 20), "当前", font=self._font(17, True), fill="white")
            if skin_offset:
                draw.rounded_rectangle((995, y + 16, 1098, y + 49), radius=12, fill="#7d8798")
                draw.text((1010, y + 20), "皮肤续页", font=self._font(15, True), fill="white")
            y += 182

            for skin in owned_skins:
                draw.rounded_rectangle((122, y, 1175, y + 82), radius=16, fill=(255, 255, 255, 225), outline=border_color, width=2)
                portrait = self._portrait(skin, (150, 68))
                img.alpha_composite(portrait, (140, y + 7))
                draw.text((316, y + 13), f"皮肤：{skin['name']}", font=self._font(25, True), fill=title_color)
                draw.text((316, y + 46), f"{skin.get('english_name') or skin['name']}  |  {skin.get('quality', skin.get('star', 'R'))}", font=self._font(18), fill=meta_color)
                if skin["id"] == player.get("current_skin"):
                    draw.rounded_rectangle((1060, y + 21, 1144, y + 53), radius=12, fill=companion["colors"][0])
                    draw.text((1076, y + 24), "已装备", font=self._font(15, True), fill="white")
                y += 104
        img.save(path)
        return path

    def _render_item_inventory(self, player: Dict[str, Any], page: int = 1) -> Path:
        owned_items = [
            item for item in self._items()
            if int(player.get("items", {}).get(item["id"], {}).get("count", 0) or 0) > 0
        ]
        owned_items.sort(key=lambda item: (-QUALITY_RANK.get(item.get("quality"), 0), item["name"], item["id"]))
        per_page = 8
        total_pages = max(1, (len(owned_items) + per_page - 1) // per_page)
        page = max(1, min(total_pages, page))
        entries = owned_items[(page - 1) * per_page: page * per_page]
        path = self.render_dir / f"items_{player['user_id']}_{page}.png"
        img = self._gradient((1280, 920), "#173044", "#edf3f7").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.text((58, 38), "道具栏", font=self._font(54, True), fill="white")
        draw.text((60, 105), f"已获得道具：{sum(int(value.get('count', 0) or 0) for value in player.get('items', {}).values())}    第 {page}/{total_pages} 页", font=self._font(24), fill="#dbe7f0")
        if not entries:
            draw.rounded_rectangle((55, 180, 1225, 680), radius=24, fill=(255, 255, 255, 238))
            draw.text((105, 380), "暂未获得道具", font=self._font(38, True), fill=self.settings["item_name_color"])
            img.save(path)
            return path
        for index, item in enumerate(entries):
            col, row = index % 4, index // 4
            x = 55 + col * 294
            y = 170 + row * 352
            draw.rounded_rectangle((x, y, x + 260, y + 315), radius=18, fill=(255, 255, 255, 238), outline=self.settings["companion_border_color"], width=2)
            img.alpha_composite(self._portrait(item, (226, 130)), (x + 17, y + 17))
            draw.text((x + 18, y + 164), item["name"], font=self._font(25, True), fill=self.settings["item_name_color"])
            draw.text((x + 18, y + 202), item.get("quality", "普通"), font=self._font(20, True), fill=self.settings["item_quality_color"])
            effect_lines = self._wrap(draw, item.get("effect", ""), self._font(18), 220)[:3]
            for line_index, line in enumerate(effect_lines):
                draw.text((x + 18, y + 236 + line_index * 24), line, font=self._font(18), fill=self.settings["item_effect_color"])
            count = int(player["items"][item["id"]].get("count", 0) or 0)
            draw.rounded_rectangle((x + 194, y + 270, x + 240, y + 300), radius=12, fill=item["colors"][0])
            draw.text((x + 204, y + 275), f"×{count}", font=self._font(16, True), fill="white")
        img.save(path)
        return path

    def _render_npc_info(self, player: Dict[str, Any], character: Dict[str, Any]) -> Path:
        owned = character["id"] in player["npcs"]
        path = self.render_dir / f"npc_{character['id']}.png"
        main, _, dark = character["colors"]
        img = self._gradient((1180, 760), dark, "#eef3f8").convert("RGBA")
        draw = ImageDraw.Draw(img)
        img.alpha_composite(self._portrait(character, (430, 650)), (45, 70))
        draw.rounded_rectangle((480, 70, 1125, 690), radius=22, fill=(255, 255, 255, 235))
        draw.text((520, 112), character["name"], font=self._font(50, True), fill="#172033")
        draw.text((520, 174), f"{character.get('skin', '默认')}  |  {character['star']}  |  {'已拥有' if owned else '未拥有'}", font=self._font(25, True), fill=main)
        blocks = [("获取途径", character["route"]), ("经验加成", character["bonus"]), ("角色介绍", character["intro"])]
        y = 238
        for title, text in blocks:
            draw.text((520, y), title, font=self._font(25, True), fill=main)
            y += 36
            for wrapped in self._wrap(draw, text, self._font(23), 555)[:3]:
                draw.text((520, y), wrapped, font=self._font(23), fill="#344056")
                y += 32
            y += 12
        draw.text((520, y), "技能", font=self._font(25, True), fill=main)
        y += 38
        for idx, (skill, desc) in enumerate(character["skills"]):
            draw.text((520, y), f"{[2, 3, 5][idx]}星 {skill}", font=self._font(21, True), fill="#172033")
            y += 29
            draw.text((520, y), desc, font=self._font(19), fill="#526071")
            y += 36
        img.save(path)
        return path

    def _render_draw(self, player: Dict[str, Any], results: List[Dict[str, Any]], coin_cost: int, ticket_used: int) -> Path:
        path = self.render_dir / f"draw_{player['user_id']}.png"
        img = self._gradient((1180, 760), "#231942", "#4d908e").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.text((60, 45), "抽奖结果", font=self._font(56, True), fill="white")
        draw.text((62, 112), f"消耗：{coin_cost} 星币 / 固定 {DRAW_COUNT} 抽    余额：{player['coins']} 星币", font=self._font(24), fill="#eaf2ff")

        state = player.get("draw_state", {})
        pity_count = max(0, min(DRAW_PITY_TARGET, int(state.get("pity_count", 0) or 0)))
        percentage = pity_count / DRAW_PITY_TARGET
        draw.rounded_rectangle((795, 42, 1125, 150), radius=18, fill=(255, 255, 255, 230))
        draw.text((824, 61), "抽奖进度条", font=self._font(26, True), fill="#172033")
        draw.rounded_rectangle((824, 102, 1095, 124), radius=11, fill="#dbe2ef")
        if percentage:
            draw.rounded_rectangle((824, 102, 824 + int(271 * percentage), 124), radius=11, fill="#7d9fc2")
        draw.text((1010, 62), f"{percentage * 100:.0f}%", font=self._font(22, True), fill="#567da7")

        companion_pool = self._draw_pool(COMPANION_KIND)
        skin_pool = self._draw_pool(SKIN_KIND)
        drawn_companion = next((self._character_or_none(result.get("entry_id", "")) for result in results if result.get("entry_kind") == COMPANION_KIND), None)
        drawn_skin = next((self._character_or_none(result.get("entry_id", "")) for result in results if result.get("entry_kind") == SKIN_KIND), None)
        display_companion = drawn_companion or (companion_pool[0] if companion_pool else None)
        display_skin = drawn_skin or (skin_pool[0] if skin_pool else None)

        y = 182
        for index, result in enumerate(results, start=1):
            current = self._character(result["character_id"])
            draw.rounded_rectangle((60, y, 700, y + 82), radius=16, fill=(255, 255, 255, 232))
            thumbnail = self._asset_thumbnail(str(result.get("image") or ""), (67, 44))
            if thumbnail:
                img.alpha_composite(thumbnail, (78, y + 18))
                draw.rounded_rectangle((78, y + 18, 145, y + 62), radius=10, outline=current["colors"][0], width=2)
            else:
                draw.rounded_rectangle((78, y + 18, 145, y + 62), radius=14, fill=current["colors"][0])
            draw.text((84, y + 22), str(index), font=self._font(20, True), fill="white")
            draw.text((168, y + 13), result["name"], font=self._font(25, True), fill="#172033")
            detail = result["kind"] if result["exp"] == 0 else f"{result['kind']} → {current['name']} +{result['exp']} EXP"
            draw.text((168, y + 47), detail, font=self._font(18), fill="#526071")
            y += 97

        def draw_pool_preview(entry: Optional[Dict[str, Any]], label: str, y0: int):
            draw.rounded_rectangle((745, y0, 1125, y0 + 252), radius=18, fill=(255, 255, 255, 226))
            draw.text((770, y0 + 16), label, font=self._font(23, True), fill="#172033")
            if not entry:
                draw.text((770, y0 + 110), "后台尚未勾选奖池内容", font=self._font(20), fill="#657086")
                return
            img.alpha_composite(self._portrait(entry, (148, 174)), (958, y0 + 58))
            draw.text((770, y0 + 66), entry["name"], font=self._font(27, True), fill="#172033")
            draw.text((770, y0 + 108), f"{entry.get('english_name') or entry['name']} | {entry.get('quality', entry.get('star', 'R'))}", font=self._font(18), fill="#6d9bc6")
            draw.text((770, y0 + 150), "已加入本期奖池", font=self._font(18), fill="#526071")

        draw_pool_preview(display_companion, "当前同伴奖池", 178)
        draw_pool_preview(display_skin, "当前皮肤奖池", 454)
        img.save(path)
        return path
