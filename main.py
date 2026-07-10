import json
import inspect
import random
import re
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from quart import jsonify, request, send_file


LEVEL_REQUIREMENTS = [1000, 2000, 3000, 4000, 5000]
DRAW_COST = 10
WINNING_NUMBER_MIN = 1
WINNING_NUMBER_MAX = 100
CHECKIN_REWARDS = [
    ("星币", 1, 45),
    ("星币", 2, 30),
    ("星币", 3, 20),
    ("免费入场券", 1, 5),
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


DEFAULT_CHARACTERS: List[Dict[str, Any]] = [
    {
        "id": "rin",
        "name": "星见凛",
        "base": "星见凛",
        "skin": "默认",
        "star": "SSR",
        "route": "月度大奖池 / 新人初始赠送",
        "bonus": "推理经验 +10%",
        "intro": "来自星轨剧团的侦探少女，擅长从细碎证词里找出不合拍的音符。",
        "skills": [["星屑直觉", "调查阶段额外获得一条线索提示。"], ["幕间追问", "每局可指定一次追问方向。"], ["终幕推演", "结算经验额外 +20%。"]],
        "colors": ["#6c8cff", "#f4d35e", "#10172a"],
        "image": "rin.png",
        "featured": True,
    },
    {
        "id": "yue",
        "name": "月白",
        "base": "月白",
        "skin": "默认",
        "star": "SR",
        "route": "月度大奖池 / 抽奖概率获得",
        "bonus": "社交经验 +8%",
        "intro": "温柔但危险的情报商，越是安静的房间，越藏着她想要的答案。",
        "skills": [["银月侧写", "社交检定经验提升。"], ["无声交易", "礼物转化经验 +10%。"], ["月影同盟", "队友结算加成 +5%。"]],
        "colors": ["#9ad7ff", "#f7f7ff", "#213047"],
        "image": "yue.png",
        "featured": True,
    },
    {
        "id": "mika",
        "name": "赤羽弥香",
        "base": "赤羽弥香",
        "skin": "默认",
        "star": "SSR",
        "route": "月度大奖池限定",
        "bonus": "战斗经验 +12%",
        "intro": "红发行动派，喜欢用最直接的办法把谜题砸开，再把碎片拼回真相。",
        "skills": [["焰羽突入", "行动类任务经验增加。"], ["破局连击", "抽奖礼物经验 +12%。"], ["红莲审判", "大奖池角色经验 +25%。"]],
        "colors": ["#ff6464", "#ffd166", "#2a1018"],
        "image": "mika.png",
        "featured": True,
    },
    {
        "id": "noa",
        "name": "诺娅",
        "base": "诺娅",
        "skin": "默认",
        "star": "R",
        "route": "常驻抽奖 / 活动兑换",
        "bonus": "通用经验 +5%",
        "intro": "负责记录档案的机械少女，表情很少，但数据库里从不遗漏任何异常。",
        "skills": [["档案索引", "查看 NPC 信息时显示额外备注。"], ["数据补正", "每日打卡星币 +1 概率提升。"], ["零点归档", "每月首次抽奖半价。"]],
        "colors": ["#62d6c7", "#e8f7ff", "#102825"],
        "image": "noa.png",
        "featured": False,
    },
    {
        "id": "iori",
        "name": "伊织",
        "base": "伊织",
        "skin": "默认",
        "star": "SR",
        "route": "常驻抽奖",
        "bonus": "观察经验 +8%",
        "intro": "旧书店的看板娘，能从纸张气味和墨迹深浅里读到时间留下的暗语。",
        "skills": [["书页暗纹", "线索阅读经验增加。"], ["旧章回声", "失败结算保底经验提升。"], ["未署名真相", "隐藏线索概率提升。"]],
        "colors": ["#c89b6d", "#fff0d6", "#2b2017"],
        "image": "iori.png",
        "featured": False,
    },
    {
        "id": "sora",
        "name": "空",
        "base": "空",
        "skin": "默认",
        "star": "R",
        "route": "常驻抽奖 / 免费入场券活动",
        "bonus": "移动经验 +6%",
        "intro": "轻装潜入者，总是笑着说自己只是路过，但每次路过都能带走关键证据。",
        "skills": [["轻身步", "探索经验增加。"], ["屋顶视野", "获得额外场景提示。"], ["夜风归途", "消耗入场券时经验提升。"]],
        "colors": ["#7bd88f", "#efffdc", "#122816"],
        "image": "sora.png",
        "featured": False,
    },
    {
        "id": "kuro",
        "name": "黑泽莲",
        "base": "黑泽莲",
        "skin": "默认",
        "star": "SSR",
        "route": "月度大奖池限定",
        "bonus": "心理经验 +12%",
        "intro": "冷静的心理医生，擅长让谎言在沉默里自己露出破绽。",
        "skills": [["微表情", "审讯经验增加。"], ["沉默处方", "可减少一次错误惩罚。"], ["深渊共鸣", "心理线结算经验 +30%。"]],
        "colors": ["#5e5ce6", "#b8b5ff", "#111122"],
        "image": "kuro.png",
        "featured": True,
    },
    {
        "id": "hana",
        "name": "花梨",
        "base": "花梨",
        "skin": "默认",
        "star": "R",
        "route": "常驻抽奖",
        "bonus": "治愈经验 +5%",
        "intro": "医学院实习生，随身携带糖果、绷带，以及一套过分锋利的推理逻辑。",
        "skills": [["急救包", "团队支援经验增加。"], ["甜味安抚", "打卡获得礼物概率提升。"], ["白花宣誓", "队友失败时返还少量经验。"]],
        "colors": ["#ff9ac8", "#fff1f6", "#321322"],
        "image": "hana.png",
        "featured": False,
    },
    {
        "id": "akito",
        "name": "晓斗",
        "base": "晓斗",
        "skin": "默认",
        "star": "SR",
        "route": "常驻抽奖 / 活动兑换",
        "bonus": "机关经验 +8%",
        "intro": "钟表匠少年，迷恋所有会转动的机关，也擅长让时间为自己作证。",
        "skills": [["齿轮听诊", "机关检定经验增加。"], ["倒转秒针", "每日一次小额经验补偿。"], ["零时钟塔", "机关线结算经验 +25%。"]],
        "colors": ["#f6b93b", "#e9f5ff", "#2a210d"],
        "image": "akito.png",
        "featured": False,
    },
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
        "image": "blue_hour_cafe.png",
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
        "image": "noble_afternoon.png",
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
        "image": "cafe_lumiere.png",
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
        "image": "ash_silver_blade.png",
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
        "image": "blue_cafe_morning.png",
        "featured": False,
    },
]


@register("astrbot_plugin_juben_npc", "Codex", "剧本杀 NPC 数据库、角色皮肤、星币、打卡、状态栏与抽奖插件", "1.1.0")
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
        self.db: Dict[str, Any] = {"scopes": {}}
        self.characters: List[Dict[str, Any]] = []
        self.checkin_templates: List[Dict[str, Any]] = []
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
        self._ensure_fonts()
        self._ensure_assets()
        logger.info("剧本杀 NPC 数据库插件已加载。")

    async def terminate(self):
        self._save_db()
        self._save_characters()
        self._save_checkin_templates()

    @filter.command("剧本杀帮助", alias={"npc帮助", "NPC帮助"})
    async def help_cmd(self, event: AstrMessageEvent):
        path = self._render_text_card(
            "剧本杀 NPC 数据库",
            [
                "/打卡 - 每天领取 1-3 星币或免费入场券",
                "/星币 - 查看自己的星币与入场券",
                "/赠送星币 @群友 数量 - 转赠星币",
                "/赠送角色 @群友 角色名 - 赠送 NPC 或皮肤",
                "/状态栏 - 查看当前 NPC 状态",
                "/切换角色 角色名 - 更换当前 NPC 或皮肤",
                "/抽奖 [次数] - 10 星币一次，入场券可抵一次",
                "/中奖号码 - 机器人在固定范围内随机生成中奖号",
                "/物品栏 - 长条列表查看 NPC 与皮肤",
                "/NPC信息 角色名 - 查询获取途径、加成与技能",
            ],
            subtitle="后台 Plugin Page 可新增角色、上传图片、修改信息并赠送给指定玩家。",
        )
        yield event.image_result(str(path))

    @filter.event_message_type(filter.EventMessageType.ALL, priority=8)
    async def direct_command_cmd(self, event: AstrMessageEvent):
        text = (event.message_str or "").strip().lstrip("/!！")
        no_space_handlers = {
            "切换角色": self.switch_cmd,
            "更换角色": self.switch_cmd,
            "选择角色": self.switch_cmd,
            "NPC信息": self.npc_info_cmd,
            "npc信息": self.npc_info_cmd,
            "查NPC": self.npc_info_cmd,
            "查询NPC": self.npc_info_cmd,
            "角色信息": self.npc_info_cmd,
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

    @filter.command("星币", alias={"钱包", "我的星币"})
    async def wallet_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_text_card(
            "星币钱包",
            [
                f"持有星币：{player['coins']}",
                f"免费入场券：{player['tickets']}",
                f"当前角色：{self._character(player['current_npc'])['name']}",
            ],
            subtitle="星币可用于抽奖，10 星币一次；免费入场券可抵扣一次单抽。",
        )
        yield event.image_result(str(path))

    @filter.command("赠送星币", alias={"发放星币", "给星币", "加星币"})
    async def transfer_cmd(self, event: AstrMessageEvent):
        target_id, target_label, amount = self._parse_transfer(event)
        if not target_id or amount <= 0:
            path = self._render_text_card("发放失败", ["格式：/赠送星币 @群友 数量", "例如：/赠送星币 @小明 20"])
            yield event.image_result(str(path))
            return

        target = self._get_player_by_id(event, target_id, target_label)
        target["coins"] += amount
        self._save_db()

        path = self._render_text_card(
            "星币已发放",
            [f"对象：{target_label}", f"发放数量：{amount}", f"对方余额：{target['coins']}"],
            subtitle="可用此命令给群员补发活动星币。",
        )
        yield event.image_result(str(path))

    @filter.command("赠送角色", alias={"赠送NPC", "赠送皮肤", "给角色"})
    async def grant_character_cmd(self, event: AstrMessageEvent):
        target_id, target_label = self._parse_target_user(event)
        character_name = self._parse_character_after_target(event)
        character = self._find_character(character_name)
        if not target_id or not character:
            path = self._render_text_card(
                "赠送失败",
                ["格式：/赠送角色 @群友 角色名", "例如：/赠送角色 @小明 蓝时咖啡"],
                subtitle="也可以在插件后台页面选择已记录的玩家赠送。",
            )
            yield event.image_result(str(path))
            return

        target = self._get_player_by_id(event, target_id, target_label)
        created = self._grant_character(target, character["id"])
        self._save_db()
        path = self._render_text_card(
            "角色已赠送",
            [f"对象：{target_label}", f"角色：{character['name']} / {character.get('skin', '默认')}", f"结果：{'新增拥有' if created else '已拥有，未重复添加'}"],
        )
        yield event.image_result(str(path))

    @filter.command("打卡", alias={"每日打卡"})
    async def checkin_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        today = datetime.now().strftime("%Y-%m-%d")
        if player.get("last_checkin") == today:
            path = self._render_checkin_card(player, "今日已打卡", "已领取", today=today)
            yield event.image_result(str(path))
            return

        reward_type, amount = self._roll_checkin()
        if reward_type == "星币":
            player["coins"] += amount
        else:
            player["tickets"] += amount
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
            path = self._render_text_card("没有找到角色", [f"输入：{character_name}", "可用 /物品栏 或 /NPC信息 查看角色。"])
            yield event.image_result(str(path))
            return
        if character["id"] not in player["npcs"]:
            path = self._render_text_card("尚未拥有", [f"{character['name']} 还没有加入你的队伍。", "可通过抽奖、活动或后台赠送获取。"])
            yield event.image_result(str(path))
            return

        path = self._render_status(player, character)
        yield event.image_result(str(path))

    @filter.command("切换角色", alias={"更换角色", "选择角色"})
    async def switch_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        character_name = self._arg_text(event)
        character = self._find_character(character_name)
        if not character:
            path = self._render_text_card("切换失败", [f"没有找到角色：{character_name or '空'}", "格式：/切换角色 蓝时咖啡"])
            yield event.image_result(str(path))
            return
        if character["id"] not in player["npcs"]:
            path = self._render_text_card("切换失败", [f"你尚未拥有 {character['name']}。", "可通过抽奖、活动或后台赠送获取。"])
            yield event.image_result(str(path))
            return

        player["current_npc"] = character["id"]
        self._save_db()
        path = self._render_status(player, character, banner="已切换当前角色")
        yield event.image_result(str(path))

    @filter.command("抽奖", alias={"npc抽奖", "NPC抽奖"})
    async def draw_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        count = self._parse_count(event, default=1, max_count=10)
        total_cost = count * DRAW_COST
        ticket_used = 0
        coin_cost = total_cost
        if count == 1 and player["tickets"] > 0:
            ticket_used = 1
            coin_cost = 0

        if player["coins"] < coin_cost:
            path = self._render_text_card(
                "星币不足",
                [f"本次需要：{coin_cost} 星币", f"当前持有：{player['coins']} 星币", "单抽若有免费入场券会优先抵扣。"],
            )
            yield event.image_result(str(path))
            return

        player["coins"] -= coin_cost
        player["tickets"] -= ticket_used
        results = [self._roll_draw(player) for _ in range(count)]
        self._save_db()

        path = self._render_draw(player, results, coin_cost, ticket_used)
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

    @filter.command("物品栏", alias={"NPC仓库", "npc仓库", "我的NPC"})
    async def inventory_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_inventory(player)
        yield event.image_result(str(path))

    @filter.command("NPC信息", alias={"npc信息", "查NPC", "查询NPC", "角色信息"})
    async def npc_info_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        character_name = self._arg_text(event)
        character = self._find_character(character_name)
        if not character:
            names = "、".join(character["name"] for character in self.characters[:18])
            path = self._render_text_card("角色查询", [f"没有找到：{character_name or '空'}", "可查询：" + names])
            yield event.image_result(str(path))
            return
        path = self._render_npc_info(player, character)
        yield event.image_result(str(path))

    def _register_page_apis(self, context: Context):
        if not hasattr(context, "register_web_api"):
            return

        async def list_characters():
            return jsonify(
                {
                    "characters": self.characters,
                    "players": self._known_players(),
                    "checkin_templates": self.checkin_templates,
                }
            )

        async def save_character():
            data = await request.json()
            data = data or {}
            character = self._normalize_character(data)
            exists = False
            for index, item in enumerate(self.characters):
                if item["id"] == character["id"]:
                    self.characters[index] = character
                    exists = True
                    break
            if not exists:
                self.characters.append(character)
            self._save_characters()
            self._ensure_assets()
            return jsonify({"ok": True, "character": character})

        async def delete_character(character_id: str):
            if character_id == "rin":
                return jsonify({"status": "error", "message": "默认初始角色不能删除。"}), 400
            before = len(self.characters)
            self.characters = [item for item in self.characters if item["id"] != character_id]
            self._save_characters()
            return jsonify({"ok": True, "deleted": before != len(self.characters)})

        async def upload_image():
            files = await request.files()
            file = None
            if hasattr(files, "get"):
                file = files.get("file")
            elif isinstance(files, list):
                file = files[0] if files else None
            if file is None:
                return jsonify({"status": "error", "message": "没有收到图片文件。"}), 400
            saved_name = await self._save_uploaded_image(file)
            return jsonify({"ok": True, "image": saved_name, "url": f"assets/{saved_name}"})

        async def list_checkin_templates():
            return jsonify({"checkin_templates": self.checkin_templates})

        async def save_checkin_template():
            data = (await request.json()) or {}
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
            files = await request.files()
            file = files.get("file") if hasattr(files, "get") else (files[0] if files else None)
            if file is None:
                return jsonify({"status": "error", "message": "没有收到背景图片文件。"}), 400
            saved_name = await self._save_uploaded_image(file, self.checkin_assets_dir, "checkin")
            return jsonify({"ok": True, "image": saved_name, "url": f"checkin-assets/{saved_name}"})

        async def grant_character():
            data = await request.json()
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
        context.register_web_api(f"/{PLUGIN_NAME}/grant", grant_character, ["POST"], "Grant NPC character")
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

    def _save_db(self):
        self.data_dir.mkdir(exist_ok=True)
        self.db_path.write_text(json.dumps(self.db, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_characters(self):
        if not self.characters_path.exists():
            self.characters = [self._normalize_character(item) for item in DEFAULT_CHARACTERS]
            self._save_characters()
            return
        try:
            loaded = json.loads(self.characters_path.read_text(encoding="utf-8"))
            characters = loaded.get("characters", loaded) if isinstance(loaded, dict) else loaded
            self.characters = [self._normalize_character(item) for item in characters]
        except Exception as exc:
            logger.error(f"读取角色配置失败，将使用默认角色：{exc}")
            self.characters = [self._normalize_character(item) for item in DEFAULT_CHARACTERS]

        known_ids = {item["id"] for item in self.characters}
        for item in DEFAULT_CHARACTERS:
            if item["id"] not in known_ids:
                self.characters.append(self._normalize_character(item))
        self._save_characters()

    def _default_checkin_template(self) -> Dict[str, Any]:
        return {
            "id": "default",
            "name": "默认打卡样式",
            "image": "",
            "enabled": True,
            "texts": {
                "title": {"text": "{title}", "x": 0.07, "y": 0.10, "size": 0.075, "color": "#172033", "bold": True},
                "reward": {"text": "{reward}", "x": 0.08, "y": 0.30, "size": 0.045, "color": "#243044", "bold": False},
                "coins": {"text": "当前星币：{coins}", "x": 0.08, "y": 0.40, "size": 0.045, "color": "#243044", "bold": False},
                "tickets": {"text": "免费入场券：{tickets}", "x": 0.08, "y": 0.50, "size": 0.045, "color": "#243044", "bold": False},
                "probability": {"text": "概率：1星币45% / 2星币30% / 3星币20% / 入场券5%", "x": 0.08, "y": 0.82, "size": 0.030, "color": "#657086", "bold": False},
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
        self.checkin_templates_path.write_text(
            json.dumps({"templates": self.checkin_templates}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _normalize_checkin_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        base = self._default_checkin_template()
        template_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(data.get("id") or "").strip()).strip("_")
        base["id"] = template_id or f"checkin_{int(datetime.now().timestamp())}"
        base["name"] = str(data.get("name") or base["name"]).strip()[:60]
        base["image"] = Path(str(data.get("image") or "")).name
        base["enabled"] = bool(data.get("enabled", True))
        raw_texts = data.get("texts") if isinstance(data.get("texts"), dict) else {}
        for key, defaults in base["texts"].items():
            source = raw_texts.get(key) if isinstance(raw_texts.get(key), dict) else {}
            defaults["text"] = str(source.get("text") or defaults["text"])[:180]
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
        self.characters_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_character(self, data: Dict[str, Any]) -> Dict[str, Any]:
        name = str(data.get("name") or data.get("id") or "未命名角色").strip()
        character_id = self._slug(str(data.get("id") or name))
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

        colors = data.get("colors") or ["#6c8cff", "#f4d35e", "#10172a"]
        if not isinstance(colors, list) or len(colors) < 3:
            colors = ["#6c8cff", "#f4d35e", "#10172a"]

        image = str(data.get("image") or f"{character_id}.png").strip()
        return {
            "id": character_id,
            "name": name,
            "base": str(data.get("base") or name).strip(),
            "skin": str(data.get("skin") or "默认").strip(),
            "star": str(data.get("star") or "R").strip().upper(),
            "route": str(data.get("route") or "运营后台添加").strip(),
            "bonus": str(data.get("bonus") or "通用经验 +5%").strip(),
            "intro": str(data.get("intro") or "这个角色还没有介绍。").strip(),
            "skills": normalized_skills,
            "colors": [str(colors[0]), str(colors[1]), str(colors[2])],
            "image": Path(image).name,
            "featured": bool(data.get("featured", False)),
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
                        "owned_count": len(player.get("npcs", {})),
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

    def _scope(self, event: AstrMessageEvent) -> Dict[str, Any]:
        return self._db_scope(self._scope_id(event))

    def _db_scope(self, scope_id: str) -> Dict[str, Any]:
        scopes = self.db.setdefault("scopes", {})
        return scopes.setdefault(str(scope_id), {"players": {}})

    def _new_player(self, user_id: str, name: str) -> Dict[str, Any]:
        starter = "rin" if self._character_or_none("rin") else self.characters[0]["id"]
        return {
            "user_id": user_id,
            "name": name,
            "coins": 20,
            "tickets": 0,
            "last_checkin": "",
            "current_npc": starter,
            "npcs": {starter: {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}},
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
        self._migrate_player_npcs(player)
        if not player["npcs"]:
            starter = "rin" if self._character_or_none("rin") else self.characters[0]["id"]
            player["npcs"][starter] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
        player.setdefault("current_npc", next(iter(player["npcs"])))
        if player["current_npc"] not in player["npcs"]:
            player["current_npc"] = next(iter(player["npcs"]))
        return player

    def _migrate_player_npcs(self, player: Dict[str, Any]):
        npcs = player.setdefault("npcs", {})
        for character_id, value in list(npcs.items()):
            if isinstance(value, int):
                npcs[character_id] = {"exp": value, "owned_at": ""}
            elif isinstance(value, dict):
                value.setdefault("exp", 0)
                value.setdefault("owned_at", "")
            else:
                npcs[character_id] = {"exp": 0, "owned_at": ""}
        for character_id in list(npcs.keys()):
            if not self._character_or_none(character_id):
                logger.info(f"玩家拥有未知角色 {character_id}，暂时保留数据。")

    def _character(self, character_id: str) -> Dict[str, Any]:
        return self._character_or_none(character_id) or self.characters[0]

    def _character_or_none(self, character_id: str) -> Optional[Dict[str, Any]]:
        for character in self.characters:
            if character["id"] == character_id:
                return character
        return None

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
        if character_id in player["npcs"]:
            return False
        player["npcs"][character_id] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
        return True

    def _npc_exp(self, player: Dict[str, Any], character_id: str) -> int:
        return int(player["npcs"].get(character_id, {}).get("exp", 0))

    def _add_exp(self, player: Dict[str, Any], character_id: str, exp: int):
        if character_id not in player["npcs"]:
            self._grant_character(player, character_id)
        player["npcs"][character_id]["exp"] = int(player["npcs"][character_id].get("exp", 0)) + exp

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
            "剧本杀帮助", "赠送星币", "发放星币", "赠送角色", "赠送NPC", "赠送皮肤",
            "切换角色", "更换角色", "选择角色", "NPC信息", "npc信息", "查询NPC",
            "角色信息", "每日打卡", "我的星币", "NPC仓库", "npc仓库", "我的NPC",
            "状态栏", "角色状态", "抽奖", "npc抽奖", "NPC抽奖", "星币", "钱包",
            "中奖号码", "开奖", "打卡", "查NPC", "物品栏",
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

    def _monthly_pool(self) -> List[Dict[str, Any]]:
        seed = datetime.now().strftime("%Y-%m")
        rng = random.Random(seed)
        featured = [item for item in self.characters if item.get("featured") or item["star"] in {"SSR", "SR"}]
        return rng.sample(featured, k=min(3, len(featured))) if featured else self.characters[:3]

    def _roll_draw(self, player: Dict[str, Any]) -> Dict[str, Any]:
        roll = random.random()
        current_id = player.get("current_npc", self.characters[0]["id"])
        if roll < 0.06:
            character = random.choice(self._monthly_pool())
            already_owned = character["id"] in player["npcs"]
            if already_owned:
                exp = 600
                self._add_exp(player, character["id"], exp)
                return {"kind": "大奖重复转经验", "name": character["name"], "exp": exp, "character_id": character["id"]}
            self._grant_character(player, character["id"])
            return {"kind": "大奖角色", "name": character["name"], "exp": 0, "character_id": character["id"]}

        gift_table = [
            ("线索书签", 80),
            ("微光糖果", 120),
            ("剧团胸针", 180),
            ("银色怀表", 260),
            ("限定花束", 420),
        ]
        gift, exp = random.choices(gift_table, weights=[35, 30, 20, 10, 5], k=1)[0]
        self._add_exp(player, current_id, exp)
        return {"kind": "礼物", "name": gift, "exp": exp, "character_id": current_id}

    def _slug(self, value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"\s+", "_", value)
        value = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]", "", value)
        return value or f"character_{int(datetime.now().timestamp())}"

    async def _save_uploaded_image(self, upload: Any, destination: Optional[Path] = None, prefix: str = "custom") -> str:
        raw_name = Path(getattr(upload, "filename", "") or "character.png").name
        suffix = Path(raw_name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            suffix = ".png"
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
                raise RuntimeError("当前 AstrBot 上传对象不支持保存。")
        Image.open(dest).verify()
        return saved_name

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
        draw.text((112, 220), character.get("skin", "默认"), font=self._font(34, True), fill=Image.new("RGB", (1, 1), accent).getpixel((0, 0)) + (255,))
        draw.text((112, 285), "请在插件后台上传角色图片", font=self._font(28), fill=(255, 255, 255, 215))
        draw.text((112, 335), character["star"], font=self._font(38, True), fill=(255, 240, 170, 255))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)

    def _portrait(self, character: Dict[str, Any], size: Tuple[int, int]) -> Image.Image:
        path = self.assets_dir / character["image"]
        if not path.exists():
            self._draw_placeholder_portrait(character, path)
        img = Image.open(path).convert("RGBA")
        scale = max(size[0] / img.width, size[1] / img.height)
        resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
        left = max(0, (resized.width - size[0]) // 2)
        top = max(0, (resized.height - size[1]) // 2)
        return resized.crop((left, top, left + size[0], top + size[1]))

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

    def _render_checkin_card(self, player: Dict[str, Any], title: str, reward: str, today: str = "") -> Path:
        """Render a full-bleed 16:9 check-in card using a template's own text layout."""
        enabled = [item for item in self.checkin_templates if item.get("enabled")]
        template = random.choice(enabled or self.checkin_templates or [self._default_checkin_template()])
        size = (1280, 720)
        image_name = str(template.get("image") or "")
        background_path = self.checkin_assets_dir / Path(image_name).name
        if image_name and background_path.exists():
            img = self._cover_image(background_path, size)
        else:
            img = self._gradient(size, "#18243c", "#2f6b6d").convert("RGBA")

        draw = ImageDraw.Draw(img)
        values = {
            "title": title,
            "reward": reward,
            "coins": player.get("coins", 0),
            "tickets": player.get("tickets", 0),
            "date": today or datetime.now().strftime("%Y-%m-%d"),
        }
        for item in template.get("texts", {}).values():
            text = str(item.get("text") or "").format(**values)
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
        path = self.render_dir / f"checkin_{player['user_id']}_{datetime.now().timestamp()}.png"
        img.save(path)
        return path

    @staticmethod
    def _cover_image(path: Path, size: Tuple[int, int]) -> Image.Image:
        source = Image.open(path).convert("RGBA")
        scale = max(size[0] / source.width, size[1] / source.height)
        resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
        left = max(0, (resized.width - size[0]) // 2)
        top = max(0, (resized.height - size[1]) // 2)
        return resized.crop((left, top, left + size[0], top + size[1]))

    def _render_status(self, player: Dict[str, Any], character: Dict[str, Any], banner: str = "") -> Path:
        path = self.render_dir / f"status_{player['user_id']}_{character['id']}.png"
        main, _, dark = character["colors"]
        img = self._gradient((1280, 840), dark, "#f4f7fb").convert("RGBA")
        draw = ImageDraw.Draw(img)
        img.alpha_composite(self._portrait(character, (520, 730)), (55, 70))
        draw.rounded_rectangle((530, 70, 1215, 805), radius=24, fill=(255, 255, 255, 235))

        if banner:
            draw.rounded_rectangle((565, 95, 845, 142), radius=18, fill=main)
            draw.text((588, 103), banner, font=self._font(24, True), fill="white")

        exp = self._npc_exp(player, character["id"])
        level, current, need, ratio = self._level_info(exp)
        display_name = character["name"]
        skin = character.get("skin", "默认")
        draw.text((565, 160), display_name, font=self._font(54, True), fill="#172033")
        draw.text((565, 222), f"{skin}  |  {character['star']}  |  {character['bonus']}", font=self._font(25, True), fill=main)
        stars = "★" * level + "☆" * (5 - level)
        draw.text((565, 272), stars, font=self._font(40, True), fill="#f5b642")
        draw.text((565, 328), f"Lv.{level}  {current}/{need} EXP", font=self._font(26, True), fill="#26364d")
        draw.rounded_rectangle((565, 370, 1148, 406), radius=18, fill="#dbe2ef")
        draw.rounded_rectangle((565, 370, 565 + int(583 * ratio), 406), radius=18, fill=main)

        y = 445
        for line in self._wrap(draw, character["intro"], self._font(24), 570)[:3]:
            draw.text((565, y), line, font=self._font(24), fill="#344056")
            y += 34

        y = 535
        for threshold, (skill, desc) in zip([2, 3, 5], character["skills"]):
            unlocked = level >= threshold
            fill = "#172033" if unlocked else "#8a94a6"
            chip = main if unlocked else "#cfd6e4"
            draw.rounded_rectangle((565, y, 1148, y + 36), radius=14, fill=chip)
            draw.text((585, y + 5), f"{threshold}星 {skill}", font=self._font(20, True), fill="white" if unlocked else "#566071")
            draw.text((585, y + 41), desc, font=self._font(18), fill=fill)
            y += 64
        img.save(path)
        return path

    def _render_inventory(self, player: Dict[str, Any]) -> Path:
        row_h = 172
        height = max(760, 170 + len(self.characters) * row_h + 55)
        path = self.render_dir / f"inventory_{player['user_id']}.png"
        img = self._gradient((1180, height), "#173044", "#f2f6f9").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.text((60, 42), "NPC / 皮肤物品栏", font=self._font(52, True), fill="white")
        draw.text((60, 105), f"当前角色：{self._character(player['current_npc'])['name']}    已拥有：{len(player['npcs'])}/{len(self.characters)}", font=self._font(25), fill="#dbe7f0")

        y = 165
        for character in self.characters:
            owned = character["id"] in player["npcs"]
            main = character["colors"][0]
            draw.rounded_rectangle((55, y, 1125, y + 138), radius=18, fill=(255, 255, 255, 238))
            portrait = self._portrait(character, (220, 124))
            if not owned:
                portrait = ImageEnhance.Color(portrait).enhance(0.08).filter(ImageFilter.GaussianBlur(0.5))
            img.alpha_composite(portrait, (70, y + 7))
            draw.text((315, y + 18), character["name"], font=self._font(31, True), fill="#172033" if owned else "#7b8496")
            draw.text((315, y + 58), f"{character.get('skin', '默认')}  |  {character['star']}  |  {character['bonus']}", font=self._font(22), fill=main if owned else "#8b94a6")
            exp = self._npc_exp(player, character["id"]) if owned else 0
            level, current, need, ratio = self._level_info(exp) if owned else (0, 0, LEVEL_REQUIREMENTS[0], 0)
            draw.rounded_rectangle((315, y + 96, 820, y + 118), radius=11, fill="#dbe2ef")
            if owned:
                draw.rounded_rectangle((315, y + 96, 315 + int(505 * ratio), y + 118), radius=11, fill=main)
            draw.text((840, y + 91), f"{'已拥有' if owned else '未获得'}  Lv.{level}  {current}/{need}", font=self._font(20), fill="#526071")
            if character["id"] == player.get("current_npc"):
                draw.rounded_rectangle((1015, y + 18, 1095, y + 52), radius=12, fill=main)
                draw.text((1033, y + 22), "当前", font=self._font(18, True), fill="white")
            y += row_h
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
        draw.text((62, 112), f"消耗：{coin_cost} 星币 / {ticket_used} 免费入场券    余额：{player['coins']} 星币", font=self._font(24), fill="#eaf2ff")

        pool = self._monthly_pool()
        draw.rounded_rectangle((760, 55, 1120, 225), radius=20, fill=(255, 255, 255, 226))
        draw.text((790, 82), "本月大奖池", font=self._font(28, True), fill="#172033")
        draw.text((790, 126), "、".join(item["name"] for item in pool), font=self._font(22), fill="#3e4a5e")
        draw.text((790, 164), "大奖概率 6%，重复转 600 EXP", font=self._font(20), fill="#657086")

        y = 190
        for index, result in enumerate(results, start=1):
            character = self._character(result["character_id"])
            x = 65 + ((index - 1) % 2) * 540
            yy = y + ((index - 1) // 2) * 100
            draw.rounded_rectangle((x, yy, x + 500, yy + 78), radius=18, fill=(255, 255, 255, 232))
            color = character["colors"][0]
            draw.rounded_rectangle((x + 18, yy + 18, x + 92, yy + 60), radius=16, fill=color)
            draw.text((x + 38, yy + 24), str(index), font=self._font(24, True), fill="white")
            draw.text((x + 112, yy + 13), result["name"], font=self._font(25, True), fill="#172033")
            detail = result["kind"] if result["exp"] == 0 else f"{result['kind']} -> {character['name']} +{result['exp']} EXP"
            draw.text((x + 112, yy + 45), detail, font=self._font(19), fill="#526071")
        img.save(path)
        return path
