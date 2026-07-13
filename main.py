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
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
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
# Every font is fetched into ``data/fonts`` on first startup.  This is important
# for AstrBot deployments that run on Linux: Windows-only font names otherwise
# silently fall back to Noto and make the WebUI font selector look broken.
# The small display fonts are deliberately included for the requested cute /
# hand-written styles.  ``minimum_bytes`` prevents an HTML error response from
# being mistaken for a valid font file without requiring every font to be huge.
DOWNLOADABLE_FONTS = [
    (
        "NotoSansCJKsc-Regular.otf",
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
        8 * 1024 * 1024,
    ),
    (
        "NotoSansCJKsc-Bold.otf",
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf",
        8 * 1024 * 1024,
    ),
    (
        "ZCOOLKuaiLe-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf",
        128 * 1024,
    ),
    (
        "MaShanZheng-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/mashanzheng/MaShanZheng-Regular.ttf",
        128 * 1024,
    ),
    (
        "ZCOOLQingKeHuangYou-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/zcoolqingkehuangyou/ZCOOLQingKeHuangYou-Regular.ttf",
        128 * 1024,
    ),
    (
        "LongCang-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/longcang/LongCang-Regular.ttf",
        128 * 1024,
    ),
    (
        "LiuJianMaoCao-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/liujianmaocao/LiuJianMaoCao-Regular.ttf",
        128 * 1024,
    ),
]
PLUGIN_NAME = "astrbot_plugin_juben_npc"
COMPANION_KIND = "companion"
SKIN_KIND = "skin"
ITEM_KIND = "item"
EXPERIENCE_BALL_KIND = "experience_ball"
QUALITY_RANK = {"UR": 5, "SSR": 4, "SR": 3, "R": 2, "N": 1}
# All of these names have a Windows system-font mapping below.  On Linux or
# another host the renderer falls back to the bundled Noto Sans CJK font, so a
# saved template always remains usable even if a particular font is absent.
FONT_FAMILIES = (
    "default", "msyh", "simhei", "simsun", "kaiti", "fangsong",
    "dengxian", "lisu", "youyuan", "stxingkai", "stfangsong",
    "stsong", "stxihei", "zcool_kuaile", "mashanzheng",
    "zcool_qingke", "longcang", "liujianmaocao",
)
FONT_ASSET_FILES = {
    "zcool_kuaile": "ZCOOLKuaiLe-Regular.ttf",
    "mashanzheng": "MaShanZheng-Regular.ttf",
    "zcool_qingke": "ZCOOLQingKeHuangYou-Regular.ttf",
    "longcang": "LongCang-Regular.ttf",
    "liujianmaocao": "LiuJianMaoCao-Regular.ttf",
}
DEFAULT_TEXT_SHADOW = {
    "shadow_color": "#1c2a40",
    "shadow_offset_x": 0,
    "shadow_offset_y": 2,
    "shadow_blur": 2.5,
    "shadow_opacity": 64,
}
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

@register("astrbot_plugin_juben_npc", "Codex", "剧本杀同伴、皮肤、道具、经验球、模板、星币、打卡与抽奖插件", "2.3.0")
class JubenNpcPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = Path(__file__).parent
        self.data_dir = self.plugin_dir / "data"
        self.assets_dir = self.data_dir / "npc_assets"
        self.checkin_assets_dir = self.data_dir / "checkin_assets"
        self.status_assets_dir = self.data_dir / "status_assets"
        self.font_dir = self.data_dir / "fonts"
        self.render_dir = self.data_dir / "rendered"
        self.db_path = self.data_dir / "players.json"
        self.characters_path = self.data_dir / "characters.json"
        self.checkin_templates_path = self.data_dir / "checkin_templates.json"
        self.status_templates_path = self.data_dir / "status_templates.json"
        self.settings_path = self.data_dir / "settings.json"
        self.db: Dict[str, Any] = {"scopes": {}}
        self.characters: List[Dict[str, Any]] = []
        self.checkin_templates: List[Dict[str, Any]] = []
        self.status_templates: List[Dict[str, Any]] = []
        self.settings: Dict[str, str] = dict(DEFAULT_VISUAL_SETTINGS)
        self._font_cache: Dict[Tuple[int, bool, str], ImageFont.FreeTypeFont] = {}
        self._warned_missing_font = False
        self._register_page_apis(context)

    async def initialize(self):
        self.data_dir.mkdir(exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        self.checkin_assets_dir.mkdir(exist_ok=True)
        self.status_assets_dir.mkdir(exist_ok=True)
        self.font_dir.mkdir(exist_ok=True)
        self.render_dir.mkdir(exist_ok=True)
        self._load_db()
        self._load_characters()
        self._load_checkin_templates()
        self._load_status_templates()
        self._load_settings()
        self._ensure_fonts()
        self._ensure_assets()
        logger.info("剧本杀同伴与皮肤数据库插件已加载。")

    async def terminate(self):
        self._save_db()
        self._save_characters()
        self._save_checkin_templates()
        self._save_status_templates()
        self._save_settings()

    async def help_cmd(self, event: AstrMessageEvent):
        path = self._render_text_card(
            "剧本杀同伴数据库",
            [
                "打卡 - 直接触发，每天随机领取 1-5 星币",
                "/赠送星币 @群友 数量 - 管理员发放星币",
                "/赠送同伴 @群友 名称 - 管理员赠送同伴或皮肤",
                "/赠送专属 @群友 同伴名 - 管理员赠送同伴专属物品",
                "状态栏 - 直接触发，查看当前同伴状态",
                "/切换同伴 名称 - 更换当前同伴或装备皮肤（/切换角色 仍兼容）",
                "抽奖 - 直接触发，消耗 10 星币进行 5 抽",
                "/中奖号码 - 机器人在固定范围内随机生成中奖号",
                "同伴栏 [页码] - 直接触发，查看已获得同伴与皮肤",
                "道具栏 [页码] - 直接触发，查看已获得道具",
                "使用道具名 - 消耗一个道具",
            ],
            subtitle="后台 Plugin Page 可维护同伴、皮肤、道具、经验球、奖池、模板、色板和玩家资产。",
        )
        yield event.image_result(str(path))

    @filter.event_message_type(filter.EventMessageType.ALL, priority=8)
    async def direct_command_cmd(self, event: AstrMessageEvent):
        """Handle the player's public commands before the message reaches the AI.

        AstrBot's normal ``@filter.command`` path deliberately honours wake words.
        This game instead promises five short commands that work as plain group
        messages, so match *only* complete commands here.  Anchoring the match
        prevents normal chat such as "今天打卡了" from being consumed.
        """
        text = (event.message_str or "").strip().lstrip("/!！").strip()
        direct_handlers = {
            "打卡": self.checkin_cmd,
            "抽奖": self.draw_cmd,
            "状态栏": self.status_cmd,
            "同伴栏": self.inventory_cmd,
            "道具栏": self.item_inventory_cmd,
            "切换同伴": self.switch_cmd,
        }
        # Do not consume ordinary conversation such as ``今天打卡了``.  At the
        # same time accept both documented page styles (``同伴栏 2`` and
        # ``同伴栏第2页``) without a wake word, and let players switch with the
        # equally natural ``切换同伴 灵儿`` spelling.
        direct_match = re.fullmatch(
            r"(打卡|抽奖)(?:\s*)|"
            r"(状态栏)(?:\s+.+)?|"
            r"(同伴栏|道具栏)(?:\s*(?:第?\d+\s*页?)?)|"
            r"(切换同伴)(?:\s+.+)",
            text,
        )
        if direct_match:
            command = next((part for part in direct_match.groups() if part), "")
            handler = direct_handlers[command]
            async for result in handler(event):
                yield result
            event.stop_event()
            return

        # ``使用XXX`` is intentionally the one extra player action requested by
        # the customer: it consumes one item and does not ask the AI to
        # interpret a game effect.
        if re.fullmatch(r"使用(?:道具)?\s*\S.*", text):
            async for result in self.use_item_cmd(event):
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
        before_owned = set(self._owned_exclusive_item_names(target, companion["id"]))
        if not self._grant_exclusive_item(target, companion["id"]):
            yield event.image_result(str(self._render_notice_card("赠送失败", "该同伴没有可赠送的专属物品，或对方已经全部拥有。")))
            return
        self._save_db()
        granted = next((name for name in self._owned_exclusive_item_names(target, companion["id"]) if name not in before_owned), "专属物品")
        yield event.image_result(str(self._render_notice_card("专属物品已赠送", f"{target_label} 获得了 {granted}。")))

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
        if not player.get("current_npc") or not player.get("npcs"):
            yield event.image_result(
                str(self._render_notice_card("无法抽奖", "你当前没有可获得经验的同伴，请先由管理员发放或通过活动获得同伴。"))
            )
            return
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

    @filter.command("使用", alias={"使用道具"})
    async def use_item_cmd(self, event: AstrMessageEvent):
        """Consume one item held by the sender.

        Item effects are deliberately display copy, not arbitrary executable
        scripts.  This makes the requested `使用XXX` flow safe while still
        keeping the inventory count accurate for the game master.
        """
        player = self._get_player(event)
        item_name = self._arg_text(event)
        item = self._find_item(item_name)
        if not item:
            yield event.image_result(str(self._render_notice_card("使用失败", f"没有找到道具：{item_name or '空'}。")))
            return
        result = self._consume_item(player, item["id"], 1)
        if not result["removed"]:
            yield event.image_result(str(self._render_notice_card("使用失败", f"你没有 {item['name']}，或数量不足。")))
            return
        self._save_db()
        yield event.image_result(
            str(
                self._render_text_card(
                    "道具已使用",
                    [
                        f"道具：{item['name']}",
                        f"已消耗：1 个　剩余：{result['remaining']} 个",
                        f"效果说明：{item.get('effect') or '暂未填写效果。'}",
                    ],
                    subtitle="道具已从你的道具栏扣除；具体游戏效果由剧本主持人按说明结算。",
                )
            )
        )

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
                                self.checkin_assets_dir / template.get("background_image", template.get("image", ""))
                            ),
                        }
                        for template in self.checkin_templates
                    ],
                    "status_templates": [
                        {
                            **template,
                            "preview": self._thumbnail_data_url(
                                self.status_assets_dir / template.get("background_image", template.get("image", ""))
                            ),
                        }
                        for template in self.status_templates
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
            except Exception as exc:
                logger.warning(f"同伴图片上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"assets/{saved_name}"})

        async def upload_image_data_url():
            try:
                saved_name = await self._save_data_url_image((await request.get_json()) or {})
            except Exception as exc:
                logger.warning(f"同伴图片备用上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"assets/{saved_name}"})

        async def list_checkin_templates():
            return jsonify({"checkin_templates": self.checkin_templates})

        async def list_status_templates():
            return jsonify({"status_templates": self.status_templates})

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

        async def save_status_template():
            data = (await request.get_json()) or {}
            template = self._normalize_status_template(data)
            for index, item in enumerate(self.status_templates):
                if item["id"] == template["id"]:
                    self.status_templates[index] = template
                    break
            else:
                self.status_templates.append(template)
            self._save_status_templates()
            return jsonify({"ok": True, "template": template})

        async def delete_status_template(template_id: str):
            before = len(self.status_templates)
            self.status_templates = [item for item in self.status_templates if item["id"] != template_id]
            if not self.status_templates:
                self.status_templates = [self._default_status_template()]
            self._save_status_templates()
            return jsonify({"ok": True, "deleted": before != len(self.status_templates)})

        async def upload_checkin_background():
            file = await self._request_upload_file()
            if file is None:
                return jsonify({"status": "error", "message": "没有收到背景图片文件。"}), 400
            try:
                saved_name = await self._save_uploaded_image(file, self.checkin_assets_dir, "checkin")
            except Exception as exc:
                logger.warning(f"打卡背景上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"checkin-assets/{saved_name}"})

        async def upload_checkin_background_data_url():
            try:
                saved_name = await self._save_data_url_image(
                    (await request.get_json()) or {}, self.checkin_assets_dir, "checkin"
                )
            except Exception as exc:
                logger.warning(f"打卡背景备用上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"checkin-assets/{saved_name}"})

        async def upload_checkin_image():
            file = await self._request_upload_file()
            if file is None:
                return jsonify({"status": "error", "message": "没有收到模板图片文件。"}), 400
            try:
                saved_name = await self._save_uploaded_image(file, self.checkin_assets_dir, "checkin_layer")
            except Exception as exc:
                logger.warning(f"打卡模板图片上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"checkin-assets/{saved_name}"})

        async def upload_checkin_image_data_url():
            try:
                saved_name = await self._save_data_url_image(
                    (await request.get_json()) or {}, self.checkin_assets_dir, "checkin_layer"
                )
            except Exception as exc:
                logger.warning(f"打卡模板备用上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"checkin-assets/{saved_name}"})

        async def upload_status_image():
            file = await self._request_upload_file()
            if file is None:
                return jsonify({"status": "error", "message": "没有收到状态栏模板图片文件。"}), 400
            try:
                saved_name = await self._save_uploaded_image(file, self.status_assets_dir, "status_layer")
            except Exception as exc:
                logger.warning(f"状态栏模板图片上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"status-assets/{saved_name}"})

        async def upload_status_image_data_url():
            try:
                saved_name = await self._save_data_url_image(
                    (await request.get_json()) or {}, self.status_assets_dir, "status_layer"
                )
            except Exception as exc:
                logger.warning(f"状态栏模板备用上传失败：{exc}")
                return jsonify({"status": "error", "message": str(exc)}), 400
            return jsonify({"ok": True, "image": saved_name, "url": f"status-assets/{saved_name}"})

        async def preview_checkin_template():
            data = (await request.get_json()) or {}
            template = self._normalize_checkin_template(data)
            values = {
                "title": "打卡成功",
                "reward": "获得：3 星币",
                "coins": 128,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "message": template.get("message") or "今日也要和同伴一起前进。",
                "user_name": "示例玩家",
                "user_id": "10001",
                "_portrait_entry": self._companions()[0] if self._companions() else None,
            }
            img = self._compose_checkin_image(template, values)
            return jsonify({"ok": True, "preview": self._image_data_url(img)})

        async def preview_status_template():
            data = (await request.get_json()) or {}
            template = self._normalize_status_template(data)
            character = self._companions()[0] if self._companions() else None
            if not character:
                return jsonify({"status": "error", "message": "请先至少保存一名同伴。"}), 400
            player = {
                "user_id": "10001",
                "name": "示例玩家",
                "coins": 128,
                "npcs": {character["id"]: {"exp": 2600}},
                "skins": {},
                "items": {},
                "current_npc": character["id"],
                "current_skin": "",
            }
            img = self._compose_status_image(template, player, character, "效果预览")
            return jsonify({"ok": True, "preview": self._image_data_url(img)})

        async def grant_character():
            data = await request.get_json()
            data = data or {}
            scope_id = str(data.get("scope_id", "")).strip()
            user_id = str(data.get("user_id", "")).strip()
            character_id = str(data.get("character_id", "")).strip()
            name = str(data.get("name", user_id)).strip() or user_id
            entry = self._character_or_none(character_id)
            if not scope_id or not user_id or not entry or entry.get("kind") == EXPERIENCE_BALL_KIND:
                return jsonify({"status": "error", "message": "scope_id、user_id 或 character_id 无效。"}), 400
            player = self._get_player_by_scope(scope_id, user_id, name)
            created = self._grant_character(player, character_id)
            self._save_db()
            return jsonify({"ok": True, "created": created, "player": player})

        async def revoke_character():
            data = (await request.get_json()) or {}
            scope_id = str(data.get("scope_id", "")).strip()
            user_id = str(data.get("user_id", "")).strip()
            character_id = str(data.get("character_id", "")).strip()
            try:
                amount = max(1, min(9999, int(data.get("amount", 1) or 1)))
            except (TypeError, ValueError):
                amount = 1
            if not scope_id or not user_id or not self._character_or_none(character_id):
                return jsonify({"status": "error", "message": "scope_id、user_id 或 character_id 无效。"}), 400
            player = self._existing_player_by_scope(scope_id, user_id)
            if player is None:
                return jsonify({"status": "error", "message": "没有找到该群/会话中的玩家记录。"}), 404
            result = self._revoke_character(player, character_id, amount)
            if not result.get("removed"):
                return jsonify({"status": "error", "message": result.get("message") or "玩家未拥有该资产。"}), 400
            self._save_db()
            return jsonify({"ok": True, "result": result, "player": player})

        async def grant_exclusive_item():
            data = (await request.get_json()) or {}
            scope_id = str(data.get("scope_id", "")).strip()
            user_id = str(data.get("user_id", "")).strip()
            companion_id = str(data.get("companion_id", "")).strip()
            exclusive_name = str(data.get("exclusive_name", "")).strip()
            name = str(data.get("name", user_id)).strip() or user_id
            if not scope_id or not user_id or not companion_id:
                return jsonify({"status": "error", "message": "scope_id、user_id 或 companion_id 无效。"}), 400
            player = self._get_player_by_scope(scope_id, user_id, name)
            created = self._grant_exclusive_item(player, companion_id, exclusive_name)
            if not created:
                return jsonify({"status": "error", "message": "同伴不存在、未设置该专属物品，或玩家已拥有该专属物品。"}), 400
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

        async def get_status_asset(filename: str):
            path = self.status_assets_dir / Path(filename).name
            if not path.exists():
                return jsonify({"status": "error", "message": "状态栏模板图片不存在。"}), 404
            return await send_file(path)

        context.register_web_api(f"/{PLUGIN_NAME}/characters", list_characters, ["GET"], "List NPC characters")
        context.register_web_api(f"/{PLUGIN_NAME}/characters", save_character, ["POST"], "Save NPC character")
        context.register_web_api(f"/{PLUGIN_NAME}/characters/<character_id>/delete", delete_character, ["POST"], "Delete NPC character")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-image", upload_image, ["POST"], "Upload NPC image")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-image/data-url", upload_image_data_url, ["POST"], "Upload NPC image fallback")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates", list_checkin_templates, ["GET"], "List check-in templates")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates", save_checkin_template, ["POST"], "Save check-in template")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates/<template_id>/delete", delete_checkin_template, ["POST"], "Delete check-in template")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-checkin-background", upload_checkin_background, ["POST"], "Upload check-in background")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-checkin-background/data-url", upload_checkin_background_data_url, ["POST"], "Upload check-in background fallback")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-checkin-image", upload_checkin_image, ["POST"], "Upload check-in template layer")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-checkin-image/data-url", upload_checkin_image_data_url, ["POST"], "Upload check-in template layer fallback")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-templates/preview", preview_checkin_template, ["POST"], "Preview check-in template")
        context.register_web_api(f"/{PLUGIN_NAME}/status-templates", list_status_templates, ["GET"], "List status templates")
        context.register_web_api(f"/{PLUGIN_NAME}/status-templates", save_status_template, ["POST"], "Save status template")
        context.register_web_api(f"/{PLUGIN_NAME}/status-templates/<template_id>/delete", delete_status_template, ["POST"], "Delete status template")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-status-image", upload_status_image, ["POST"], "Upload status template layer")
        context.register_web_api(f"/{PLUGIN_NAME}/upload-status-image/data-url", upload_status_image_data_url, ["POST"], "Upload status template layer fallback")
        context.register_web_api(f"/{PLUGIN_NAME}/status-templates/preview", preview_status_template, ["POST"], "Preview status template")
        context.register_web_api(f"/{PLUGIN_NAME}/grant", grant_character, ["POST"], "Grant NPC character")
        context.register_web_api(f"/{PLUGIN_NAME}/revoke", revoke_character, ["POST"], "Revoke NPC character or item")
        context.register_web_api(f"/{PLUGIN_NAME}/grant-exclusive", grant_exclusive_item, ["POST"], "Grant companion exclusive item")
        context.register_web_api(f"/{PLUGIN_NAME}/settings", get_settings, ["GET"], "Get companion visual settings")
        context.register_web_api(f"/{PLUGIN_NAME}/settings", save_settings, ["POST"], "Save companion visual settings")
        context.register_web_api(f"/{PLUGIN_NAME}/assets/<filename>", get_asset, ["GET"], "Get NPC image")
        context.register_web_api(f"/{PLUGIN_NAME}/checkin-assets/<filename>", get_checkin_asset, ["GET"], "Get check-in background")
        context.register_web_api(f"/{PLUGIN_NAME}/status-assets/<filename>", get_status_asset, ["GET"], "Get status template layer")

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
            "bound_entry_id": "",
            "priority": 0,
            "background_image": "",
            "panel_image": "",
            "portrait_frame_image": "",
            # Keep the legacy field so existing WebUI clients and old JSON keep
            # resolving their background after the schema upgrade.
            "image": "",
            "enabled": True,
            "show_companion": True,
            "portrait_scale": 1.0,
            "portrait_offset_x": 0.0,
            "portrait_offset_y": 0.0,
            "font_family": "default",
            "message": "今日也要和同伴一起前进。",
            "panel_color": "#152238",
            "texts": {
                "title": {"text": "{title}", "x": 0.07, "y": 0.14, "size": 0.062, "color": "#ffffff", "bold": True},
                "reward": {"text": "{reward}", "x": 0.08, "y": 0.30, "size": 0.042, "color": "#eaf4ff", "bold": True},
                "coins": {"text": "当前星币：{coins}", "x": 0.08, "y": 0.41, "size": 0.038, "color": "#d7e6f5", "bold": False},
                "message": {"text": "{message}", "x": 0.08, "y": 0.58, "size": 0.030, "color": "#c8d9ea", "bold": False},
                "user": {"text": "打开者：{user_name}", "x": 0.08, "y": 0.70, "size": 0.027, "color": "#b8cadd", "bold": False},
            },
        }

    def _default_status_template(self) -> Dict[str, Any]:
        return {
            "id": "default",
            "name": "默认状态栏样式",
            "bound_entry_id": "",
            "priority": 0,
            "background_image": "",
            "panel_image": "",
            "portrait_frame_image": "",
            "image": "",
            "enabled": True,
            "show_companion": True,
            "portrait_scale": 1.0,
            "portrait_offset_x": 0.0,
            "portrait_offset_y": 0.0,
            "font_family": "default",
            "panel_color": "#ffffff",
            "texts": {
                "user": {"text": "打开者：{user_name}｜ID：{user_id}", "x": 0.45, "y": 0.105, "size": 0.020, "color": "#6d9bc6", "bold": False},
                "name": {"text": "{character_name}", "x": 0.441, "y": 0.190, "size": 0.042, "color": "#172033", "bold": True},
                "subtitle": {"text": "{subtitle_name}  |  {quality}  |  {bonus}", "x": 0.441, "y": 0.265, "size": 0.020, "color": "#6d9bc6", "bold": True},
                "stars": {"text": "{stars}", "x": 0.441, "y": 0.323, "size": 0.031, "color": "#f5b642", "bold": True},
                "level": {"text": "Lv.{level}  {current}/{need} EXP", "x": 0.441, "y": 0.390, "size": 0.021, "color": "#6d9bc6", "bold": True},
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

    def _load_status_templates(self):
        if not self.status_templates_path.exists():
            self.status_templates = [self._default_status_template()]
            self._save_status_templates()
            return
        try:
            raw = json.loads(self.status_templates_path.read_text(encoding="utf-8"))
            templates = raw.get("templates", raw) if isinstance(raw, dict) else raw
            self.status_templates = [self._normalize_status_template(item) for item in templates if isinstance(item, dict)]
        except Exception as exc:
            logger.error(f"读取状态栏模板失败，将使用默认样式：{exc}")
            self.status_templates = []
        if not self.status_templates:
            self.status_templates = [self._default_status_template()]
        self._save_status_templates()

    def _save_status_templates(self):
        self._write_json_atomic(self.status_templates_path, {"templates": self.status_templates})

    def _normalize_checkin_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._normalize_visual_template(data, self._default_checkin_template())

    def _normalize_status_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._normalize_visual_template(data, self._default_status_template())

    def _normalize_visual_template(self, data: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate and validate a role-bound card template without dropping text rows.

        Earlier versions normalized only four hard-coded check-in rows.  That
        silently discarded operator-created text such as tickets/probability.
        Every valid text entry is now retained and rendered, including future
        custom rows, while the known defaults remain available for new cards.
        """
        template_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(data.get("id") or "").strip()).strip("_")
        prefix = "status" if "状态栏" in str(base.get("name") or "") else "checkin"
        base["id"] = template_id or f"{prefix}_{int(datetime.now().timestamp())}"
        base["name"] = str(data.get("name") or base["name"]).strip()[:60]
        background = Path(str(data.get("background_image") or data.get("image") or "")).name
        base["background_image"] = background
        base["image"] = background
        base["panel_image"] = Path(str(data.get("panel_image") or "")).name
        base["portrait_frame_image"] = Path(str(data.get("portrait_frame_image") or "")).name
        bound_entry_id = str(data.get("bound_entry_id") or data.get("bound_character_id") or "").strip()
        bound = self._character_or_none(bound_entry_id)
        base["bound_entry_id"] = bound_entry_id if bound and bound.get("kind") in {COMPANION_KIND, SKIN_KIND} else ""
        try:
            base["priority"] = max(-100, min(100, int(data.get("priority", base.get("priority", 0)) or 0)))
        except (TypeError, ValueError):
            base["priority"] = int(base.get("priority", 0) or 0)
        base["enabled"] = bool(data.get("enabled", True))
        base["show_companion"] = bool(data.get("show_companion", True))
        base["portrait_scale"] = self._template_number(data.get("portrait_scale"), base.get("portrait_scale", 1.0), 0.5, 1.5)
        base["portrait_offset_x"] = self._template_number(data.get("portrait_offset_x"), base.get("portrait_offset_x", 0.0), -0.35, 0.35)
        base["portrait_offset_y"] = self._template_number(data.get("portrait_offset_y"), base.get("portrait_offset_y", 0.0), -0.35, 0.35)
        family = str(data.get("font_family") or base.get("font_family") or "default").strip().lower()
        base["font_family"] = family if family in FONT_FAMILIES else "default"
        # v2 adds per-row font, weight and shadow controls.  Previously every
        # row was implicitly saved as ``default``, which made changing the
        # template font appear to do nothing.  Migrate those implicit values to
        # inheritance once; new rows can still explicitly select a font.
        try:
            text_style_version = int(data.get("text_style_version", 1) or 1)
        except (TypeError, ValueError):
            text_style_version = 1
        base["text_style_version"] = 2
        if "message" in base or "message" in data:
            base["message"] = str(data.get("message") or base.get("message") or "").strip()[:180]
        panel_color = str(data.get("panel_color") or base["panel_color"])
        base["panel_color"] = panel_color if re.fullmatch(r"#[0-9a-fA-F]{6}", panel_color) else base["panel_color"]
        raw_texts = data.get("texts") if isinstance(data.get("texts"), dict) else {}
        normalized_texts: Dict[str, Dict[str, Any]] = {}
        default_texts = base.get("texts", {})
        keys = list(default_texts)
        keys.extend(key for key in raw_texts if key not in default_texts)
        for key in keys:
            safe_key = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(key)).strip("_")[:40]
            if not safe_key:
                continue
            defaults = default_texts.get(key, {"text": "", "x": 0.08, "y": 0.72, "size": 0.03, "color": "#ffffff", "bold": False})
            source = raw_texts.get(key) if isinstance(raw_texts.get(key), dict) else {}
            text = str(source.get("text", defaults.get("text", "")) or "")[:180]
            color = str(source.get("color") or defaults.get("color", "#ffffff"))
            item_family = str(source.get("font_family") or "").lower()
            if text_style_version < 2 and item_family == "default":
                item_family = ""
            raw_weight = source.get("font_weight")
            if raw_weight is None:
                raw_weight = 700 if bool(source.get("bold", defaults.get("bold", False))) else 400
            normalized_texts[safe_key] = {
                "text": text,
                "x": self._template_number(source.get("x"), float(defaults.get("x", 0.08)), 0, 1),
                "y": self._template_number(source.get("y"), float(defaults.get("y", 0.72)), 0, 1),
                "size": self._template_number(source.get("size"), float(defaults.get("size", 0.03)), 0.015, 0.15),
                "color": color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else str(defaults.get("color", "#ffffff")),
                "font_weight": int(self._template_number(raw_weight, 400, 100, 900)),
                # Kept for v1 readers only.  The renderer uses font_weight.
                "bold": int(self._template_number(raw_weight, 400, 100, 900)) >= 600,
                "font_family": item_family if item_family in FONT_FAMILIES else "",
                "shadow_color": str(source.get("shadow_color") or defaults.get("shadow_color") or DEFAULT_TEXT_SHADOW["shadow_color"]),
                "shadow_offset_x": self._template_number(source.get("shadow_offset_x"), float(defaults.get("shadow_offset_x", DEFAULT_TEXT_SHADOW["shadow_offset_x"])), -40, 40),
                "shadow_offset_y": self._template_number(source.get("shadow_offset_y"), float(defaults.get("shadow_offset_y", DEFAULT_TEXT_SHADOW["shadow_offset_y"])), -40, 40),
                "shadow_blur": self._template_number(source.get("shadow_blur"), float(defaults.get("shadow_blur", DEFAULT_TEXT_SHADOW["shadow_blur"])), 0, 12),
                "shadow_opacity": int(self._template_number(source.get("shadow_opacity"), float(defaults.get("shadow_opacity", DEFAULT_TEXT_SHADOW["shadow_opacity"])), 0, 255)),
            }
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", normalized_texts[safe_key]["shadow_color"]):
                normalized_texts[safe_key]["shadow_color"] = DEFAULT_TEXT_SHADOW["shadow_color"]
        base["texts"] = normalized_texts
        return base

    @staticmethod
    def _template_number(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            return max(minimum, min(maximum, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_exclusive_item_names(value: Any) -> List[str]:
        """Accept legacy text as well as the multi-item operator form."""
        if isinstance(value, dict):
            value = value.get("items") or value.get("names") or value.get("name") or []
        if isinstance(value, str):
            values = re.split(r"[\r\n,，;；]+", value)
        elif isinstance(value, (list, tuple, set)):
            values = value
        else:
            values = []
        names: List[str] = []
        seen = set()
        for raw in values:
            name = str(raw.get("name", "") if isinstance(raw, dict) else raw).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name[:40])
            if len(names) >= 20:
                break
        return names

    def _save_characters(self):
        self.data_dir.mkdir(exist_ok=True)
        payload = {"characters": self.characters}
        self._write_json_atomic(self.characters_path, payload)

    def _normalize_character(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize library entries while retaining legacy character JSON.

        Experience balls intentionally live in the library but are not player
        assets.  They are a separate reward kind so a draw can add EXP directly
        without ever creating an item-inventory record.
        """
        raw_kind = str(data.get("kind") or data.get("type") or COMPANION_KIND).lower()
        # Older drafts exposed separate normal/middle/high item choices.  Keep
        # those saves usable, but migrate them into the one weighted item pool
        # requested by the customer instead of turning them into companions.
        if raw_kind in {
            "normal_item", "low_item", "middle_item", "mid_item", "high_item",
            "advanced_item", "normal", "middle", "advanced", "普通道具", "中级道具", "高级道具",
        }:
            raw_kind = ITEM_KIND
        kind = raw_kind if raw_kind in {COMPANION_KIND, SKIN_KIND, ITEM_KIND, EXPERIENCE_BALL_KIND} else COMPANION_KIND
        name = str(data.get("name") or data.get("id") or "未命名同伴").strip()
        character_id = self._slug(str(data.get("id") or name))
        quality = str(data.get("quality") or data.get("star") or ("道具" if kind == ITEM_KIND else "R")).strip().upper()
        if kind != ITEM_KIND and quality not in QUALITY_RANK:
            quality = "R"
        colors = data.get("colors") or ["#6c8cff", "#f4d35e", "#10172a"]
        if not isinstance(colors, list) or len(colors) < 3:
            colors = ["#6c8cff", "#f4d35e", "#10172a"]
        image = Path(str(data.get("image") or f"{character_id}.png").strip()).name

        if kind == EXPERIENCE_BALL_KIND:
            return {
                "id": character_id,
                "kind": EXPERIENCE_BALL_KIND,
                "name": name,
                "english_name": str(data.get("english_name") or "").strip(),
                "quality": str(data.get("quality") or "经验球").strip()[:20] or "经验球",
                "exp_amount": int(self._template_number(data.get("exp_amount"), 10, 1, 999999)),
                "draw_weight": int(self._template_number(data.get("draw_weight"), 10, 1, 1000)),
                "image": image,
                "in_pool": bool(data.get("in_pool", data.get("featured", True))),
                "focal_x": self._template_number(data.get("focal_x"), 0.5, 0, 1),
                "focal_y": self._template_number(data.get("focal_y"), 0.5, 0, 1),
                "colors": [str(colors[0]), str(colors[1]), str(colors[2])],
            }

        if kind == ITEM_KIND:
            return {
                "id": character_id,
                "kind": ITEM_KIND,
                "name": name,
                "english_name": str(data.get("english_name") or "").strip(),
                # Items no longer have high/middle/normal tiers.  Their one
                # shared 13% draw slot selects among enabled items by weight.
                "quality": "道具",
                "draw_weight": int(self._template_number(data.get("draw_weight"), 10, 1, 10000)),
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

        raw_exclusive_items = data.get("exclusive_items")
        if raw_exclusive_items in (None, "", []):
            raw_exclusive_items = data.get("exclusive_item")
        exclusive_items = self._normalize_exclusive_item_names(raw_exclusive_items)
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
            # ``exclusive_item`` is retained for legacy clients and old player
            # saves; the new list is the source of truth and can hold many items.
            "exclusive_item": exclusive_items[0] if exclusive_items else "",
            "exclusive_items": exclusive_items,
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
            # New accounts receive a starter companion.  Administrators may
            # later remove even that last asset; this marker prevents the
            # migration routine from silently granting it back.
            "allow_empty_npcs": False,
            "draw_state": {"pity_count": 0, "next_pity_kind": "random"},
        }

    def _get_player(self, event: AstrMessageEvent) -> Dict[str, Any]:
        return self._get_player_by_id(event, self._sender_id(event), event.get_sender_name())

    def _get_player_by_id(self, event: AstrMessageEvent, user_id: str, name: str) -> Dict[str, Any]:
        return self._get_player_by_scope(self._scope_id(event), user_id, name)

    def _existing_player_by_scope(self, scope_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Find an existing player without accidentally creating an account.

        A destructive WebUI request with a mistyped QQ must not leave behind a
        new starter player, which is why revoke uses this instead of the normal
        get-or-create path.
        """
        scope = self.db.get("scopes", {}).get(str(scope_id))
        if not isinstance(scope, dict):
            return None
        players = scope.get("players")
        if not isinstance(players, dict):
            return None
        player = players.get(str(user_id))
        if not isinstance(player, dict):
            return None
        # Reuse the canonical migration/default logic now that existence has
        # already been proved.
        return self._get_player_by_scope(scope_id, str(user_id), str(player.get("name") or user_id))

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
        player.setdefault("allow_empty_npcs", False)
        player.setdefault("draw_state", {"pity_count": 0, "next_pity_kind": "random"})
        self._migrate_player_npcs(player)
        if not player["npcs"] and not player.get("allow_empty_npcs"):
            starter = "rin" if self._character_or_none("rin") else self._companions()[0]["id"]
            player["npcs"][starter] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
        player.setdefault("current_npc", next(iter(player["npcs"]), ""))
        current = self._character_or_none(str(player.get("current_npc") or ""))
        if player["current_npc"] not in player["npcs"] or not current or current.get("kind") != COMPANION_KIND:
            player["current_npc"] = next(
                (
                    character_id for character_id in player["npcs"]
                    if (entry := self._character_or_none(character_id)) and entry.get("kind") == COMPANION_KIND
                ),
                "",
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
            companion = self._character_or_none(str(companion_id))
            names = self._exclusive_item_names(companion)
            legacy_name = names[0] if names else "__legacy__"
            if isinstance(value, str):
                exclusive_items[companion_id] = {legacy_name: {"owned_at": value}}
                continue
            if not isinstance(value, dict):
                exclusive_items[companion_id] = {legacy_name: {"owned_at": ""}}
                continue
            # v2 stored one record directly under the companion ID.  v2.1
            # stores one ownership record per exclusive item name.
            if "owned_at" in value:
                exclusive_items[companion_id] = {
                    legacy_name: {"owned_at": str(value.get("owned_at") or "")}
                }
                continue
            normalized_owned = {}
            for item_name, record in value.items():
                name = str(item_name).strip()
                if not name:
                    continue
                if isinstance(record, str):
                    normalized_owned[name] = {"owned_at": record}
                elif isinstance(record, dict):
                    normalized_owned[name] = {"owned_at": str(record.get("owned_at") or "")}
            exclusive_items[companion_id] = normalized_owned

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

    def _experience_balls(self) -> List[Dict[str, Any]]:
        return [
            item for item in self.characters
            if item.get("kind") == EXPERIENCE_BALL_KIND and item.get("in_pool", False)
        ]

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

    def _find_item(self, value: str) -> Optional[Dict[str, Any]]:
        """Look up only a consumable item, never a character or EXP ball."""
        value = (value or "").strip()
        if not value:
            return None
        if (entry := self._character_or_none(value)) and entry.get("kind") == ITEM_KIND:
            return entry
        lowered = value.lower()
        items = self._items()
        for item in items:
            if lowered in {str(item.get("name") or "").lower(), str(item.get("english_name") or "").lower()}:
                return item
        return next((item for item in items if lowered in str(item.get("name") or "").lower()), None)

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
        if entry.get("kind") == EXPERIENCE_BALL_KIND:
            # Experience balls are draw rewards only and must never enter a
            # player's normal inventory through an accidental backend grant.
            return False
        if entry["id"] in player["npcs"]:
            return False
        player["npcs"][entry["id"]] = {"exp": 0, "owned_at": now, "full_at": ""}
        player["allow_empty_npcs"] = False
        return True

    def _consume_item(self, player: Dict[str, Any], item_id: str, amount: int = 1) -> Dict[str, Any]:
        amount = max(1, int(amount or 1))
        items = player.setdefault("items", {})
        record = items.get(item_id)
        available = int(record.get("count", 0) or 0) if isinstance(record, dict) else 0
        if available < amount:
            return {"removed": 0, "remaining": available}
        remaining = available - amount
        if remaining:
            record["count"] = remaining
        else:
            items.pop(item_id, None)
        return {"removed": amount, "remaining": remaining}

    def _revoke_character(self, player: Dict[str, Any], character_id: str, amount: int = 1) -> Dict[str, Any]:
        """Remove an owned companion, skin or item without touching the master library."""
        entry = self._character_or_none(character_id)
        if not entry or entry.get("kind") == EXPERIENCE_BALL_KIND:
            return {"removed": 0, "remaining": 0, "message": "条目不存在或不是可发放资产。"}
        kind = entry.get("kind")
        if kind == ITEM_KIND:
            result = self._consume_item(player, entry["id"], amount)
            result["message"] = "道具数量不足。" if not result["removed"] else "道具已扣除。"
            return result
        if kind == SKIN_KIND:
            if entry["id"] not in player.get("skins", {}):
                return {"removed": 0, "remaining": 0, "message": "玩家未拥有该皮肤。"}
            player["skins"].pop(entry["id"], None)
            if player.get("current_skin") == entry["id"]:
                player["current_skin"] = ""
            return {"removed": 1, "remaining": 0, "message": "皮肤已扣除。"}
        if entry["id"] not in player.get("npcs", {}):
            return {"removed": 0, "remaining": 0, "message": "玩家未拥有该同伴。"}
        player["npcs"].pop(entry["id"], None)
        player.setdefault("exclusive_items", {}).pop(entry["id"], None)
        if player.get("current_npc") == entry["id"]:
            player["current_skin"] = ""
            remaining_id = next(
                (
                    npc_id for npc_id in player.get("npcs", {})
                    if (npc := self._character_or_none(npc_id)) and npc.get("kind") == COMPANION_KIND
                ),
                "",
            )
            player["current_npc"] = remaining_id
        if not player.get("npcs"):
            player["allow_empty_npcs"] = True
            player["current_npc"] = ""
            player["current_skin"] = ""
        return {"removed": 1, "remaining": len(player.get("npcs", {})), "message": "同伴已扣除。"}

    def _exclusive_item_names(self, companion: Optional[Dict[str, Any]]) -> List[str]:
        if not companion or companion.get("kind") != COMPANION_KIND:
            return []
        names = self._normalize_exclusive_item_names(companion.get("exclusive_items"))
        if not names:
            names = self._normalize_exclusive_item_names(companion.get("exclusive_item"))
        return names

    def _owned_exclusive_item_names(self, player: Dict[str, Any], companion_id: str) -> List[str]:
        owned = player.get("exclusive_items", {}).get(companion_id, {})
        if not isinstance(owned, dict):
            return []
        return [str(name) for name in owned if str(name) != "__legacy__"]

    def _grant_exclusive_item(
        self,
        player: Dict[str, Any],
        companion_id: str,
        exclusive_name: str = "",
    ) -> bool:
        companion = self._character_or_none(companion_id)
        available = self._exclusive_item_names(companion)
        if not available:
            return False
        owned = player.setdefault("exclusive_items", {}).setdefault(companion_id, {})
        if not isinstance(owned, dict):
            player["exclusive_items"][companion_id] = owned = {}
        requested = str(exclusive_name or "").strip()
        if requested and requested not in available:
            return False
        target = requested or next((name for name in available if name not in owned), "")
        if not target or target in owned:
            return False
        owned[target] = {"owned_at": datetime.now().strftime("%Y-%m-%d")}
        return True

    def _has_exclusive_item(
        self, player: Dict[str, Any], companion_id: str, exclusive_name: str = ""
    ) -> bool:
        owned = player.get("exclusive_items", {}).get(companion_id, {})
        if not isinstance(owned, dict):
            return False
        if exclusive_name:
            return exclusive_name in owned
        return bool(owned)

    def _npc_exp(self, player: Dict[str, Any], character_id: str) -> int:
        return int(player["npcs"].get(character_id, {}).get("exp", 0))

    def _add_exp(self, player: Dict[str, Any], character_id: str, exp: int) -> int:
        entry = self._character_or_none(character_id)
        if not entry or entry.get("kind") != COMPANION_KIND:
            return 0
        if character_id not in player["npcs"] and not self._grant_character(player, character_id):
            return 0
        record = player["npcs"][character_id]
        before = int(record.get("exp", 0) or 0)
        granted = max(0, int(exp))
        record["exp"] = before + granted
        full_exp = sum(LEVEL_REQUIREMENTS)
        if before < full_exp <= record["exp"] and not record.get("full_at"):
            record["full_at"] = datetime.now().isoformat(timespec="seconds")
        return granted

    def _level_info(self, exp: int) -> Tuple[int, int, int, float]:
        spent = 0
        for index, requirement in enumerate(LEVEL_REQUIREMENTS, start=1):
            if exp < spent + requirement:
                current = exp - spent
                return index, current, requirement, current / requirement
            spent += requirement
        return 5, LEVEL_REQUIREMENTS[-1], LEVEL_REQUIREMENTS[-1], 1.0

    def _arg_text(self, event: AstrMessageEvent) -> str:
        """Return command arguments for both raw-message and parsed-command events.

        AstrBot passes the complete message to event hooks, but command-decorated
        handlers can receive only their argument string.  The previous fallback
        stripped any leading Chinese/word characters, which erased valid values
        such as ``2`` and ``灵儿``.  That made documented pagination and companion
        switching appear unavailable.
        """
        text = str(getattr(event, "message_str", "") or "").strip().lstrip("/!！").strip()
        command_prefixes = [
            "剧本杀帮助", "同伴帮助", "伙伴帮助", "赠送星币", "发放星币", "赠送同伴", "赠送角色", "赠送NPC", "赠送皮肤", "赠送专属", "赠送专属物品",
            "切换同伴", "切换角色", "更换角色", "选择角色", "NPC信息", "npc信息", "查询NPC",
            "角色信息", "每日打卡", "我的星币", "NPC仓库", "npc仓库", "我的NPC",
            "状态栏", "角色状态", "抽奖", "npc抽奖", "NPC抽奖", "星币", "钱包",
            "中奖号码", "开奖", "打卡", "查NPC", "同伴栏", "物品栏", "道具栏", "我的道具", "道具仓库", "使用道具", "使用",
        ]
        for prefix in sorted(command_prefixes, key=len, reverse=True):
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        # With a command decorator, ``message_str`` may already be the parsed
        # argument.  Return it intact rather than treating player names and page
        # numbers as a command prefix.
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

    def _draw_pool(self, kind: str) -> List[Dict[str, Any]]:
        entries = [
            entry for entry in self.characters
            if entry.get("kind") == kind and entry.get("in_pool", False)
        ]
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

        The published odds include a weighted item pool as well as a featured
        companion and skin. Charging before all three pools exist would turn a
        valid probability slot into an empty reward and is hard to repair for
        the operator, so the command blocks before deducting currency.
        """
        gaps: List[str] = []
        if not self._draw_pool(COMPANION_KIND):
            gaps.append("同伴")
        if not self._draw_pool(SKIN_KIND):
            gaps.append("皮肤")
        if not self._draw_pool(ITEM_KIND):
            gaps.append("道具")
        return gaps

    def _enforce_single_featured_pool(self, saved_entry: Dict[str, Any]) -> None:
        """Keep one active companion and one active skin in the current pool.

        The item pool intentionally remains many-to-one: every enabled item is
        a candidate and its configured draw weight determines the selection.
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

    def _roll_experience_ball(self, player: Dict[str, Any], current_id: str) -> Dict[str, Any]:
        """Resolve the fixed experience-ball reward slot without touching inventory.

        Operators can add any number of independently weighted balls in the
        library.  Older installs without custom balls retain the original three
        rewards so an update never creates an empty 75% reward bracket.
        """
        configured = self._experience_balls()
        if configured:
            weights = [max(1, int(entry.get("draw_weight", 1) or 1)) for entry in configured]
            entry = random.choices(configured, weights=weights, k=1)[0]
            exp = self._add_exp(player, current_id, int(entry.get("exp_amount", 0) or 0))
            return {
                "kind": "经验球",
                "name": entry["name"],
                "exp": exp,
                "character_id": current_id,
                "entry_id": entry["id"],
                "entry_kind": EXPERIENCE_BALL_KIND,
                "image": entry.get("image", ""),
            }
        legacy_weights = [rate for rate, _, _, _ in EXPERIENCE_BALLS]
        _, name, exp, image = random.choices(EXPERIENCE_BALLS, weights=legacy_weights, k=1)[0]
        granted = self._add_exp(player, current_id, exp)
        return {
            "kind": "经验球",
            "name": name,
            "exp": granted,
            "character_id": current_id,
            "entry_kind": EXPERIENCE_BALL_KIND,
            "image": image,
        }

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
        # Keep the original 75% experience-ball bracket.  Custom balls change
        # only which ball is selected inside that bracket, not the published
        # odds of the other reward classes.
        cursor += sum(rate for rate, _, _, _ in EXPERIENCE_BALLS)
        if roll < cursor:
            return self._roll_experience_ball(player, current_id)

        # The former normal/middle/high item brackets totalled 13%.  Keep that
        # published total while putting all items into one weighted pool.
        cursor += 13
        if roll < cursor:
            pool = self._draw_pool(ITEM_KIND)
            if not pool:
                return {"kind": "道具池为空", "name": "未配置道具", "exp": 0, "character_id": current_id, "entry_kind": ITEM_KIND}
            weights = [max(1, int(entry.get("draw_weight", 1) or 1)) for entry in pool]
            return self._grant_draw_entry(player, random.choices(pool, weights=weights, k=1)[0], "道具")

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
        self._validate_uploaded_image(dest)
        return saved_name

    async def _save_data_url_image(
        self,
        payload: Dict[str, Any],
        destination: Optional[Path] = None,
        prefix: str = "custom",
    ) -> str:
        """Store a FileReader data URL when the browser multipart bridge is unavailable."""
        if not isinstance(payload, dict):
            raise ValueError("上传数据格式无效。")
        data_url = str(payload.get("data_url") or "").strip()
        header, separator, encoded = data_url.partition(",")
        if not separator or ";base64" not in header.lower():
            raise ValueError("没有收到有效的图片数据。")
        raw_name = Path(str(payload.get("filename") or "character.png")).name
        suffix = Path(raw_name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            mime = header.split(";", 1)[0].lower()
            suffix = {
                "data:image/png": ".png",
                "data:image/jpeg": ".jpg",
                "data:image/webp": ".webp",
            }.get(mime, "")
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("仅支持 PNG、JPG、JPEG 或 WebP 图片。")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("图片数据已损坏，请重新选择图片。") from exc
        if not content:
            raise ValueError("图片内容为空。")
        if len(content) > 15 * 1024 * 1024:
            raise ValueError("图片不能超过 15MB。")
        saved_name = f"{prefix}_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}{suffix}"
        dest = (destination or self.assets_dir) / saved_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        self._validate_uploaded_image(dest)
        return saved_name

    @staticmethod
    def _validate_uploaded_image(dest: Path) -> None:
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
        self.font_dir.mkdir(exist_ok=True)
        for filename, url, minimum_bytes in DOWNLOADABLE_FONTS:
            path = self.font_dir / filename
            if path.exists() and path.stat().st_size >= minimum_bytes:
                continue
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            try:
                logger.info(f"正在下载中文字体：{filename}")
                tmp_path.unlink(missing_ok=True)
                urllib.request.urlretrieve(url, tmp_path)
                if tmp_path.stat().st_size < minimum_bytes:
                    raise RuntimeError("字体文件下载不完整")
                tmp_path.replace(path)
            except Exception as exc:
                tmp_path.unlink(missing_ok=True)
                if path.exists() and path.stat().st_size < minimum_bytes:
                    path.unlink(missing_ok=True)
                logger.error(f"下载中文字体失败：{filename}，原因：{exc}")

    def _find_font_file(self, bold: bool = False, family: str = "default") -> Optional[Path]:
        family = str(family or "default").lower()
        if family not in FONT_FAMILIES:
            family = "default"
        local_bold = [self.font_dir / "NotoSansCJKsc-Bold.otf", self.font_dir / "SourceHanSansSC-Bold.otf"]
        local_regular = [self.font_dir / "NotoSansCJKsc-Regular.otf", self.font_dir / "SourceHanSansSC-Regular.otf"]
        # The display fonts ship as one regular face.  They remain selectable at
        # every weight; the renderer adds a controlled stroke for heavy weights.
        # This keeps their visual character instead of silently falling back to
        # Noto whenever a user selects 600+.
        bundled_display = [self.font_dir / FONT_ASSET_FILES[family]] if family in FONT_ASSET_FILES else []
        family_bold = {
            "msyh": [Path("C:/Windows/Fonts/msyhbd.ttc"), Path("C:/Windows/Fonts/msyh.ttc")],
            "simhei": [Path("C:/Windows/Fonts/simhei.ttf")],
            "simsun": [Path("C:/Windows/Fonts/simsun.ttc")],
            "kaiti": [Path("C:/Windows/Fonts/simkai.ttf")],
            "fangsong": [Path("C:/Windows/Fonts/simfang.ttf")],
            "dengxian": [Path("C:/Windows/Fonts/dengb.ttf"), Path("C:/Windows/Fonts/deng.ttf")],
            "lisu": [Path("C:/Windows/Fonts/simli.ttf")],
            "youyuan": [Path("C:/Windows/Fonts/simyou.ttf")],
            "stxingkai": [Path("C:/Windows/Fonts/stxingka.ttf")],
            "stfangsong": [Path("C:/Windows/Fonts/stfangso.ttf")],
            "stsong": [Path("C:/Windows/Fonts/stsong.ttf")],
            "stxihei": [Path("C:/Windows/Fonts/stxihei.ttf")],
        }
        family_regular = {
            "msyh": [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyhbd.ttc")],
            "simhei": [Path("C:/Windows/Fonts/simhei.ttf")],
            "simsun": [Path("C:/Windows/Fonts/simsun.ttc")],
            "kaiti": [Path("C:/Windows/Fonts/simkai.ttf")],
            "fangsong": [Path("C:/Windows/Fonts/simfang.ttf")],
            "dengxian": [Path("C:/Windows/Fonts/deng.ttf"), Path("C:/Windows/Fonts/dengb.ttf")],
            "lisu": [Path("C:/Windows/Fonts/simli.ttf")],
            "youyuan": [Path("C:/Windows/Fonts/simyou.ttf")],
            "stxingkai": [Path("C:/Windows/Fonts/stxingka.ttf")],
            "stfangsong": [Path("C:/Windows/Fonts/stfangso.ttf")],
            "stsong": [Path("C:/Windows/Fonts/stsong.ttf")],
            "stxihei": [Path("C:/Windows/Fonts/stxihei.ttf")],
        }
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

        preferred = bundled_display + (family_bold.get(family, []) if bold else family_regular.get(family, []))
        candidates = preferred + (local_bold + system_bold if bold else local_regular + system_regular)
        if bold:
            candidates += local_regular + system_regular

        for font_path in candidates:
            if not font_path.exists():
                continue
            min_size = 64 * 1024 if self.font_dir in font_path.parents else 1024
            if font_path.stat().st_size > min_size:
                return font_path
        return None

    def _font(self, size: int, bold: bool = False, family: str = "default") -> ImageFont.FreeTypeFont:
        family = str(family or "default").lower()
        if family not in FONT_FAMILIES:
            family = "default"
        cache_key = (size, bold, family)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_path = self._find_font_file(bold, family)
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

    def _select_role_template(
        self,
        templates: List[Dict[str, Any]],
        player: Dict[str, Any],
        companion_id: str,
        fallback: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Choose a deterministic template: equipped skin → companion → general.

        This replaces the old global random check-in choice.  An operator can
        therefore design a card once for a particular skin/companion and be
        certain it is the card emitted after a player switches to it.
        """
        enabled = [item for item in templates if item.get("enabled")]
        candidates = enabled or templates
        if not candidates:
            return fallback
        skin = self._active_skin(player, companion_id) if companion_id else None
        targets = [skin["id"]] if skin else []
        if companion_id:
            targets.append(companion_id)
        targets.append("")
        for target in targets:
            matches = [item for item in candidates if str(item.get("bound_entry_id") or "") == target]
            if matches:
                return sorted(matches, key=lambda item: (-int(item.get("priority", 0) or 0), str(item.get("id") or "")))[0]
        return sorted(candidates, key=lambda item: (-int(item.get("priority", 0) or 0), str(item.get("id") or "")))[0]

    @staticmethod
    def _template_color(value: Any, fallback: str) -> str:
        value = str(value or fallback)
        return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback

    def _composite_template_layer(
        self,
        canvas: Image.Image,
        assets_dir: Path,
        filename: str,
        target_box: Tuple[int, int, int, int],
    ) -> bool:
        """Apply a transparent template layer either as a full canvas or a block.

        Designers may upload a 1280-wide transparent overlay (maximum control)
        or a smaller left/right panel asset.  Full-canvas art is placed exactly
        over the card; smaller art is contained and centered in its matching
        block without flattening PNG alpha.
        """
        path = assets_dir / Path(str(filename or "")).name
        if not path.is_file():
            return False
        try:
            with Image.open(path) as opened:
                layer = ImageOps.exif_transpose(opened).convert("RGBA")
            full_w, full_h = canvas.size
            source_ratio = layer.width / max(1, layer.height)
            full_ratio = full_w / max(1, full_h)
            if abs(source_ratio - full_ratio) / full_ratio <= 0.05:
                if layer.size != canvas.size:
                    layer = layer.resize(canvas.size, Image.Resampling.LANCZOS)
                canvas.alpha_composite(layer, (0, 0))
                return True
            x, y, width, height = target_box
            layer.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
            canvas.alpha_composite(layer, (x + (width - layer.width) // 2, y + (height - layer.height) // 2))
            return True
        except Exception as exc:
            logger.warning(f"读取模板图层失败：{path.name}，原因：{exc}")
            return False

    def _composite_template_portrait(
        self,
        canvas: Image.Image,
        entry: Dict[str, Any],
        base_size: Tuple[int, int],
        origin: Tuple[int, int],
        template: Dict[str, Any],
        radius: int,
    ) -> None:
        scale = self._template_number(template.get("portrait_scale"), 1.0, 0.5, 1.5)
        width = max(1, round(base_size[0] * scale))
        height = max(1, round(base_size[1] * scale))
        portrait = self._portrait(entry, (width, height))
        # Preserve transparent PNG edges and combine them with the optional
        # rounded clipping mask instead of replacing alpha via putalpha(mask).
        alpha = portrait.getchannel("A")
        mask = Image.new("L", portrait.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=max(0, round(radius * scale)), fill=255)
        portrait.putalpha(ImageChops.multiply(alpha, mask))
        offset_x = int(self._template_number(template.get("portrait_offset_x"), 0, -0.35, 0.35) * base_size[0])
        offset_y = int(self._template_number(template.get("portrait_offset_y"), 0, -0.35, 0.35) * base_size[1])
        x = origin[0] + (base_size[0] - width) // 2 + offset_x
        y = origin[1] + (base_size[1] - height) // 2 + offset_y
        canvas.alpha_composite(portrait, (x, y))

    def _draw_template_texts(
        self,
        canvas: Image.Image,
        template: Dict[str, Any],
        values: Dict[str, Any],
        size: Tuple[int, int],
        keys: Optional[List[str]] = None,
    ) -> None:
        texts = template.get("texts", {})
        if not isinstance(texts, dict):
            return
        entries = ((key, texts.get(key)) for key in keys) if keys else texts.items()
        for _, item in entries:
            if not isinstance(item, dict):
                continue
            text = self._format_template_text(str(item.get("text") or ""), values)
            if not text:
                continue
            font_size = max(14, int(float(item.get("size", 0.04)) * size[0]))
            family = str(item.get("font_family") or template.get("font_family") or "default")
            weight = int(self._template_number(item.get("font_weight"), 700 if item.get("bold") else 400, 100, 900))
            font = self._font(font_size, weight >= 600, family)
            x = int(float(item.get("x", 0)) * size[0])
            y = int(float(item.get("y", 0)) * size[1])
            color = self._template_color(item.get("color"), "#ffffff")
            # Use a real, optional blur layer instead of the former hard-coded
            # black +2px copy.  It is softer by default and each part can be
            # changed per text row in the management UI.
            shadow_opacity = int(self._template_number(item.get("shadow_opacity"), DEFAULT_TEXT_SHADOW["shadow_opacity"], 0, 255))
            shadow_blur = self._template_number(item.get("shadow_blur"), DEFAULT_TEXT_SHADOW["shadow_blur"], 0, 12)
            if shadow_opacity:
                shadow_color = self._template_color(item.get("shadow_color"), DEFAULT_TEXT_SHADOW["shadow_color"])
                shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow_layer)
                shadow_rgb = tuple(int(shadow_color[index:index + 2], 16) for index in (1, 3, 5))
                shadow_draw.text(
                    (
                        x + int(self._template_number(item.get("shadow_offset_x"), DEFAULT_TEXT_SHADOW["shadow_offset_x"], -40, 40)),
                        y + int(self._template_number(item.get("shadow_offset_y"), DEFAULT_TEXT_SHADOW["shadow_offset_y"], -40, 40)),
                    ),
                    text,
                    font=font,
                    fill=shadow_rgb + (shadow_opacity,),
                )
                if shadow_blur:
                    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))
                canvas.alpha_composite(shadow_layer)
            stroke_width = 2 if weight >= 900 else (1 if weight >= 800 else 0)
            ImageDraw.Draw(canvas).text(
                (x, y), text, font=font, fill=color,
                stroke_width=stroke_width, stroke_fill=color,
            )

    def _render_checkin_card(self, player: Dict[str, Any], title: str, reward: str, today: str = "") -> Path:
        """Render a full-bleed 16:9 check-in card using its role-bound template."""
        companion = self._character_or_none(str(player.get("current_npc") or ""))
        companion_id = companion["id"] if companion else ""
        template = self._select_role_template(
            self.checkin_templates,
            player,
            companion_id,
            self._default_checkin_template(),
        )
        skin = self._active_skin(player, companion_id) if companion else None
        values = {
            "title": title,
            "reward": reward,
            "coins": player.get("coins", 0),
            "date": today or datetime.now().strftime("%Y-%m-%d"),
            "message": template.get("message") or "今日也要和同伴一起前进。",
            "user_name": str(player.get("name") or player.get("user_id") or "玩家"),
            "user_id": str(player.get("user_id") or ""),
            "_portrait_entry": skin or companion,
        }
        img = self._compose_checkin_image(template, values)
        path = self.render_dir / f"checkin_{player['user_id']}_{datetime.now().timestamp()}.png"
        img.save(path)
        return path

    def _compose_checkin_image(self, template: Dict[str, Any], values: Dict[str, Any]) -> Image.Image:
        """Compose one check-in template for both WebUI preview and QQ output."""
        size = (1280, 720)
        background_name = str(template.get("background_image") or template.get("image") or "")
        background_path = self.checkin_assets_dir / Path(background_name).name
        if background_name and background_path.exists():
            img = self._cover_image(background_path, size)
        else:
            img = self._gradient(size, "#18243c", "#2f6b6d").convert("RGBA")
        draw = ImageDraw.Draw(img)
        panel_box = (48, 56, 662, 608)
        portrait_box = (748, 46, 480, 630)
        panel_image = str(template.get("panel_image") or "")
        frame_image = str(template.get("portrait_frame_image") or "")
        if not panel_image:
            panel_color = self._template_color(template.get("panel_color"), "#152238")
            rgb = Image.new("RGB", (1, 1), panel_color).getpixel((0, 0))
            draw.rounded_rectangle((48, 56, 710, 664), radius=30, fill=rgb + (205,))
        portrait_entry = values.get("_portrait_entry")
        if template.get("show_companion", True) and isinstance(portrait_entry, dict):
            self._composite_template_portrait(img, portrait_entry, (480, 630), (748, 46), template, 28)
            if not frame_image:
                draw.rounded_rectangle((748, 46, 1228, 676), radius=28, outline=(255, 255, 255, 185), width=3)
        if panel_image:
            self._composite_template_layer(img, self.checkin_assets_dir, panel_image, panel_box)
        if frame_image:
            self._composite_template_layer(img, self.checkin_assets_dir, frame_image, portrait_box)
        self._draw_template_texts(img, template, values, size)
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
        template = self._select_role_template(
            self.status_templates,
            player,
            character["id"],
            self._default_status_template(),
        )
        img = self._compose_status_image(template, player, character, banner)
        path = self.render_dir / f"status_{player['user_id']}_{character['id']}.png"
        img.save(path)
        return path

    def _compose_status_image(
        self,
        template: Dict[str, Any],
        player: Dict[str, Any],
        character: Dict[str, Any],
        banner: str = "",
    ) -> Image.Image:
        """Compose a role-bound status card with the established left/right layout."""
        size = (1280, 840)
        main, _, dark = character["colors"]
        skin = self._active_skin(player, character["id"])
        visual = skin or character
        panel_color = self._template_color(template.get("panel_color"), self.settings["status_panel_color"])
        background_name = str(template.get("background_image") or template.get("image") or "")
        background_path = self.status_assets_dir / Path(background_name).name
        if background_name and background_path.exists():
            img = self._cover_image(background_path, size)
        else:
            img = self._gradient(size, dark, panel_color).convert("RGBA")
        draw = ImageDraw.Draw(img)
        panel_box = (530, 70, 685, 735)
        portrait_box = (55, 70, 520, 730)
        panel_image = str(template.get("panel_image") or "")
        frame_image = str(template.get("portrait_frame_image") or "")
        if not panel_image:
            panel_rgb = Image.new("RGB", (1, 1), panel_color).getpixel((0, 0))
            draw.rounded_rectangle((530, 70, 1215, 805), radius=24, fill=panel_rgb + (235,))
        if template.get("show_companion", True):
            self._composite_template_portrait(img, visual, (520, 730), (55, 70), template, 24)
        if panel_image:
            self._composite_template_layer(img, self.status_assets_dir, panel_image, panel_box)
        if frame_image:
            self._composite_template_layer(img, self.status_assets_dir, frame_image, portrait_box)

        exp = self._npc_exp(player, character["id"])
        level, current, need, ratio = self._level_info(exp)
        subtitle_name = (skin or character).get("english_name") or (skin or character).get("name")
        quality = (skin or character).get("quality") or character.get("star", "R")
        values = {
            "user_name": str(player.get("name") or player.get("user_id") or "玩家"),
            "user_id": str(player.get("user_id") or ""),
            "character_name": character["name"],
            "subtitle_name": subtitle_name,
            "quality": quality,
            "bonus": character.get("bonus") or "",
            "stars": "★" * level + "☆" * (5 - level),
            "level": level,
            "current": current,
            "need": need,
            "exp": exp,
        }
        text_defaults = {
            "user": {"text": "打开者：{user_name}｜ID：{user_id}", "x": 0.441, "y": 0.105, "size": 0.020, "color": self.settings["status_meta_color"], "bold": False},
            "name": {"text": "{character_name}", "x": 0.441, "y": 0.190, "size": 0.042, "color": self.settings["status_name_color"], "bold": True},
            "subtitle": {"text": "{subtitle_name}  |  {quality}  |  {bonus}", "x": 0.441, "y": 0.265, "size": 0.020, "color": self.settings["status_meta_color"], "bold": True},
            "stars": {"text": "{stars}", "x": 0.441, "y": 0.323, "size": 0.031, "color": "#f5b642", "bold": True},
            "level": {"text": "Lv.{level}  {current}/{need} EXP", "x": 0.441, "y": 0.390, "size": 0.021, "color": self.settings["status_meta_color"], "bold": True},
        }
        # Templates saved before a status text field was introduced still keep
        # the familiar layout and derive their colors from the global status
        # palette instead of disappearing.
        effective_template = {**template, "texts": {**text_defaults, **(template.get("texts") or {})}}
        if banner:
            draw.rounded_rectangle((920, 96, 1148, 136), radius=16, fill=main)
            draw.text((938, 102), banner, font=self._font(20, True, effective_template.get("font_family", "default")), fill="white")
        self._draw_template_texts(img, effective_template, values, size, ["user", "name", "subtitle", "stars", "level"])
        draw.rounded_rectangle((565, 370, 1148, 406), radius=18, fill="#dbe2ef")
        if ratio:
            draw.rounded_rectangle((565, 370, 565 + int(583 * ratio), 406), radius=18, fill=main)

        family = str(effective_template.get("font_family") or "default")
        y = 445
        for threshold, (skill, desc) in zip([2, 3, 5], character["skills"]):
            unlocked = level >= threshold
            text_fill = "#172033" if unlocked else "#8a94a6"
            chip = main if unlocked else "#cfd6e4"
            draw.rounded_rectangle((565, y, 1148, y + 36), radius=14, fill=chip)
            draw.text((585, y + 5), f"{threshold}星 {skill}", font=self._font(20, True, family), fill="white" if unlocked else "#566071")
            draw.text((585, y + 41), desc, font=self._font(18, False, family), fill=self.settings["status_meta_color"] if unlocked else text_fill)
            y += 64
        return img

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
            all_groups.append(
                (
                    sort_key,
                    companion,
                    own_companion,
                    owned_skins,
                    exp,
                    self._exclusive_item_names(companion),
                )
            )
        all_groups.sort(key=lambda group: group[0])

        # A companion can own many skins.  Split those skins into small visual
        # groups before page slicing so one heavily customized companion cannot
        # make the image unboundedly tall.  Continued segments intentionally
        # repeat the parent row, keeping every skin visibly attached to it.
        # Keep a typical companion and its full skin collection together.  The
        # compact rows below still grow safely for unusually large collections.
        skins_per_segment = 4
        segmented_groups = []
        for sort_key, companion, own_companion, owned_skins, exp, exclusive_items in all_groups:
            if not owned_skins:
                segmented_groups.append((sort_key, companion, own_companion, [], exp, 0, exclusive_items))
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
                        exclusive_items,
                    )
                )

        # Two large rows made the companion shelf spill to a new page almost
        # immediately.  The compact layout is intentionally sized for six
        # normal companion groups per page.
        per_page = 6
        total_pages = max(1, (len(segmented_groups) + per_page - 1) // per_page)
        page = max(1, min(total_pages, page))
        groups = segmented_groups[(page - 1) * per_page: page * per_page]
        def companion_row_height(exclusive_items: List[str]) -> int:
            # Customer-requested three exclusive items per row.
            rows = (len(exclusive_items) + 2) // 3
            return 106 + max(0, rows - 1) * 24

        height = max(
            720,
            152 + sum(
                companion_row_height(exclusive_items) + len(skins) * 50 + 4
                for _, _, _, skins, _, _, exclusive_items in groups
            ) + 32,
        )
        path = self.render_dir / f"companions_{player['user_id']}_{page}.png"
        img = self._gradient((1280, height), "#173044", "#edf3f7").convert("RGBA")
        draw = ImageDraw.Draw(img)
        title_color = self.settings["companion_name_color"]
        meta_color = self.settings["companion_meta_color"]
        border_color = self.settings["companion_border_color"]
        exclusive_color = self.settings["exclusive_item_color"]
        exclusive_border = self.settings["exclusive_item_border_color"]
        draw.text((58, 30), "同伴栏", font=self._font(48, True), fill="white")
        owned_total = len(player.get("npcs", {})) + len(player.get("skins", {}))
        current_entry = self._character_or_none(str(player.get("current_npc") or ""))
        current_name = current_entry["name"] if current_entry else "未选择"
        draw.text((60, 88), f"当前同伴：{current_name}    已拥有：{owned_total}    第 {page}/{total_pages} 页", font=self._font(22), fill="#dbe7f0")

        if not groups:
            draw.rounded_rectangle((55, 175, 1225, 565), radius=24, fill=(255, 255, 255, 238))
            draw.text((105, 310), "暂未获得同伴或皮肤", font=self._font(38, True), fill=title_color)
            draw.text((105, 370), "可通过抽奖、活动或管理员赠送获得。", font=self._font(25), fill=meta_color)
            img.save(path)
            return path

        y = 132
        for _, companion, own_companion, owned_skins, exp, skin_offset, exclusive_items in groups:
            row_height = companion_row_height(exclusive_items)
            main = companion["colors"][0]
            row_fill = (255, 255, 255, 238) if own_companion else (229, 234, 240, 232)
            draw.rounded_rectangle((52, y, 1228, y + row_height), radius=16, fill=row_fill, outline=border_color, width=3)
            portrait = self._portrait(companion, (144, 92))
            if not own_companion:
                portrait = ImageEnhance.Color(portrait).enhance(0.05).filter(ImageFilter.GaussianBlur(0.45))
            img.alpha_composite(portrait, (68, y + 6))
            name_fill = title_color if own_companion else "#8b94a6"
            sub_fill = meta_color if own_companion else "#9aa4b3"
            draw.text((232, y + 8), companion["name"], font=self._font(26, True), fill=name_fill)
            draw.text((232, y + 37), f"{companion.get('english_name') or '—'}  |  {companion.get('quality', companion.get('star', 'R'))}  |  {companion['bonus']}", font=self._font(16), fill=sub_fill)
            level, current, need, ratio = self._level_info(exp) if own_companion else (0, 0, LEVEL_REQUIREMENTS[0], 0)
            draw.rounded_rectangle((232, y + 62, 644, y + 78), radius=8, fill="#dbe2ef")
            if own_companion:
                draw.rounded_rectangle((232, y + 62, 232 + int(412 * ratio), y + 78), radius=8, fill=main)
            draw.text((660, y + 58), f"{'已拥有' if own_companion else '未获得'}  Lv.{level}  {current}/{need}", font=self._font(16), fill=sub_fill)
            for item_index, exclusive_name in enumerate(exclusive_items):
                column, item_row = item_index % 3, item_index // 3
                item_x = 232 + column * 309
                item_y = y + 82 + item_row * 24
                exclusive_owned = self._has_exclusive_item(player, companion["id"], exclusive_name)
                item_color = exclusive_color if exclusive_owned else "#9aa4b3"
                item_border = exclusive_border if exclusive_owned else "#c5ccd6"
                draw.rounded_rectangle((item_x, item_y, item_x + 292, item_y + 20), radius=7, outline=item_border, width=1, fill=(255, 255, 255, 35))
                label = f"专属物品：{exclusive_name}"
                draw.text((item_x + 8, item_y + 2), label[:18], font=self._font(13, True), fill=item_color)
            if companion["id"] == player.get("current_npc"):
                draw.rounded_rectangle((1134, y + 10, 1204, y + 36), radius=10, fill=main)
                draw.text((1147, y + 13), "当前", font=self._font(14, True), fill="white")
            if skin_offset:
                draw.rounded_rectangle((1038, y + 10, 1124, y + 36), radius=10, fill="#7d8798")
                draw.text((1050, y + 13), "皮肤续页", font=self._font(13, True), fill="white")
            # Skin rows deliberately meet the parent card with no blank strip.
            y += row_height

            for skin in owned_skins:
                # Skins start flush with their parent card (rather than an
                # indented floating box), so the association is immediate and
                # there is no blank vertical strip between companion and skin.
                draw.rounded_rectangle((52, y, 1228, y + 48), radius=11, fill=(255, 255, 255, 225), outline=border_color, width=2)
                portrait = self._portrait(skin, (100, 44))
                img.alpha_composite(portrait, (68, y + 2))
                draw.text((184, y + 4), f"皮肤：{skin['name']}", font=self._font(19, True), fill=title_color)
                draw.text((184, y + 26), f"{skin.get('english_name') or skin['name']}  |  {skin.get('quality', skin.get('star', 'R'))}", font=self._font(14), fill=meta_color)
                if skin["id"] == player.get("current_skin"):
                    draw.rounded_rectangle((1060, y + 11, 1133, y + 37), radius=10, fill=companion["colors"][0])
                    draw.text((1072, y + 14), "已装备", font=self._font(13, True), fill="white")
                y += 50
            # Keep a small separation between companion groups, while skins
            # remain flush with the parent card above.
            y += 4
        img.save(path)
        return path

    def _render_item_inventory(self, player: Dict[str, Any], page: int = 1) -> Path:
        owned_items = [
            item for item in self._items()
            if int(player.get("items", {}).get(item["id"], {}).get("count", 0) or 0) > 0
        ]
        owned_items.sort(key=lambda item: (item["name"], item["id"]))
        per_page = 8
        total_pages = max(1, (len(owned_items) + per_page - 1) // per_page)
        page = max(1, min(total_pages, page))
        entries = owned_items[(page - 1) * per_page: page * per_page]
        path = self.render_dir / f"items_{player['user_id']}_{page}.png"
        img = self._gradient((1280, 920), "#173044", "#edf3f7").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.text((58, 38), "道具栏", font=self._font(54, True), fill="white")
        draw.text((60, 105), f"已获得道具：{sum(int(value.get('count', 0) or 0) for value in player.get('items', {}).values())}    第 {page}/{total_pages} 页", font=self._font(24), fill="#dbe7f0")
        owner_label = str(player.get("name") or player.get("user_id") or "玩家")[:20]
        draw.text((720, 105), f"查询者：{owner_label}｜ID：{player.get('user_id', '')}", font=self._font(22, True), fill="#dbe7f0")
        # Keep the shelf visually complete on an empty or partly-filled page.
        # Entries are capped at 8 per page, so they always stay inside this area.
        draw.rounded_rectangle((45, 160, 1235, 860), radius=24, fill=(255, 255, 255, 222))
        if not entries:
            draw.text((105, 470), "暂未获得道具", font=self._font(38, True), fill=self.settings["item_name_color"])
            draw.text((105, 530), "抽奖、活动和管理员赠送获得的道具会陈列在这里。", font=self._font(22), fill=self.settings["item_effect_color"])
            img.save(path)
            return path
        for index, item in enumerate(entries):
            col, row = index % 4, index // 4
            x = 55 + col * 294
            y = 170 + row * 352
            draw.rounded_rectangle((x, y, x + 260, y + 315), radius=18, fill=(255, 255, 255, 238), outline=self.settings["companion_border_color"], width=2)
            img.alpha_composite(self._portrait(item, (226, 130)), (x + 17, y + 17))
            draw.text((x + 18, y + 164), item["name"], font=self._font(25, True), fill=self.settings["item_name_color"])
            draw.text((x + 18, y + 202), "道具", font=self._font(20, True), fill=self.settings["item_quality_color"])
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
