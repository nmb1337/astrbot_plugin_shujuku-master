import json
import math
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


LEVEL_REQUIREMENTS = [1000, 2000, 3000, 4000, 5000]
DRAW_COST = 10
CHECKIN_REWARDS = [
    ("星币", 1, 45),
    ("星币", 2, 30),
    ("星币", 3, 20),
    ("免费入场券", 1, 5),
]

NPCS: List[Dict[str, Any]] = [
    {
        "id": "rin",
        "name": "星见凛",
        "star": "SSR",
        "route": "月度大奖池 / 新人初始赠送",
        "bonus": "推理经验 +10%",
        "intro": "来自星轨剧团的侦探少女，擅长从细碎证词里找出不合拍的音符。",
        "skills": [
            ("星屑直觉", "2星解锁：调查阶段额外获得一条线索提示。"),
            ("幕间追问", "3星解锁：每局可指定一次追问方向。"),
            ("终幕推演", "5星解锁：结算经验额外 +20%。"),
        ],
        "colors": ("#6c8cff", "#f4d35e", "#10172a"),
    },
    {
        "id": "yue",
        "name": "月白",
        "star": "SR",
        "route": "月度大奖池 / 抽奖概率获得",
        "bonus": "社交经验 +8%",
        "intro": "温柔但危险的情报商，越是安静的房间，越藏着她想要的答案。",
        "skills": [
            ("银月侧写", "2星解锁：社交检定经验提升。"),
            ("无声交易", "3星解锁：礼物转化经验 +10%。"),
            ("月影同盟", "5星解锁：队友结算加成 +5%。"),
        ],
        "colors": ("#9ad7ff", "#f7f7ff", "#213047"),
    },
    {
        "id": "mika",
        "name": "赤羽弥香",
        "star": "SSR",
        "route": "月度大奖池限定",
        "bonus": "战斗经验 +12%",
        "intro": "红发行动派，喜欢用最直接的办法把谜题砸开，再把碎片拼回真相。",
        "skills": [
            ("焰羽突入", "2星解锁：行动类任务经验增加。"),
            ("破局连击", "3星解锁：抽奖礼物经验 +12%。"),
            ("红莲审判", "5星解锁：大奖池角色经验 +25%。"),
        ],
        "colors": ("#ff6464", "#ffd166", "#2a1018"),
    },
    {
        "id": "noa",
        "name": "诺娅",
        "star": "R",
        "route": "常驻抽奖 / 活动兑换",
        "bonus": "通用经验 +5%",
        "intro": "负责记录档案的机械少女，表情很少，但数据库里从不遗漏任何异常。",
        "skills": [
            ("档案索引", "2星解锁：查看 NPC 信息时显示额外备注。"),
            ("数据补正", "3星解锁：每日打卡星币 +1 概率提升。"),
            ("零点归档", "5星解锁：每月首次抽奖半价。"),
        ],
        "colors": ("#62d6c7", "#e8f7ff", "#102825"),
    },
    {
        "id": "iori",
        "name": "伊织",
        "star": "SR",
        "route": "常驻抽奖",
        "bonus": "观察经验 +8%",
        "intro": "旧书店的看板娘，能从纸张气味和墨迹深浅里读到时间留下的暗语。",
        "skills": [
            ("书页暗纹", "2星解锁：线索阅读经验增加。"),
            ("旧章回声", "3星解锁：失败结算保底经验提升。"),
            ("未署名真相", "5星解锁：隐藏线索概率提升。"),
        ],
        "colors": ("#c89b6d", "#fff0d6", "#2b2017"),
    },
    {
        "id": "sora",
        "name": "空",
        "star": "R",
        "route": "常驻抽奖 / 免费入场券活动",
        "bonus": "移动经验 +6%",
        "intro": "轻装潜入者，总是笑着说自己只是路过，但每次路过都能带走关键证据。",
        "skills": [
            ("轻身步", "2星解锁：探索经验增加。"),
            ("屋顶视野", "3星解锁：获得额外场景提示。"),
            ("夜风归途", "5星解锁：消耗入场券时经验提升。"),
        ],
        "colors": ("#7bd88f", "#efffdc", "#122816"),
    },
    {
        "id": "kuro",
        "name": "黑泽莲",
        "star": "SSR",
        "route": "月度大奖池限定",
        "bonus": "心理经验 +12%",
        "intro": "冷静的心理医生，擅长让谎言在沉默里自己露出破绽。",
        "skills": [
            ("微表情", "2星解锁：审讯经验增加。"),
            ("沉默处方", "3星解锁：可减少一次错误惩罚。"),
            ("深渊共鸣", "5星解锁：心理线结算经验 +30%。"),
        ],
        "colors": ("#5e5ce6", "#b8b5ff", "#111122"),
    },
    {
        "id": "hana",
        "name": "花梨",
        "star": "R",
        "route": "常驻抽奖",
        "bonus": "治愈经验 +5%",
        "intro": "医学院实习生，随身携带糖果、绷带，以及一套过分锋利的推理逻辑。",
        "skills": [
            ("急救包", "2星解锁：团队支援经验增加。"),
            ("甜味安抚", "3星解锁：打卡获得礼物概率提升。"),
            ("白花宣誓", "5星解锁：队友失败时返还少量经验。"),
        ],
        "colors": ("#ff9ac8", "#fff1f6", "#321322"),
    },
    {
        "id": "akito",
        "name": "晓斗",
        "star": "SR",
        "route": "常驻抽奖 / 活动兑换",
        "bonus": "机关经验 +8%",
        "intro": "钟表匠少年，迷恋所有会转动的机关，也擅长让时间为自己作证。",
        "skills": [
            ("齿轮听诊", "2星解锁：机关检定经验增加。"),
            ("倒转秒针", "3星解锁：每日一次小额经验补偿。"),
            ("零时钟塔", "5星解锁：机关线结算经验 +25%。"),
        ],
        "colors": ("#f6b93b", "#e9f5ff", "#2a210d"),
    },
]

NPC_BY_NAME = {npc["name"]: npc for npc in NPCS}
NPC_BY_ID = {npc["id"]: npc for npc in NPCS}


@register("astrbot_plugin_juben_npc", "Codex", "剧本杀 NPC 数据库、星币、打卡、状态栏与抽奖插件", "1.0.0")
class JubenNpcPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = Path(__file__).parent
        self.data_dir = self.plugin_dir / "data"
        self.assets_dir = self.data_dir / "npc_assets"
        self.render_dir = self.data_dir / "rendered"
        self.db_path = self.data_dir / "players.json"
        self.db: Dict[str, Any] = {"scopes": {}}

    async def initialize(self):
        self.data_dir.mkdir(exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        self.render_dir.mkdir(exist_ok=True)
        self._load_db()
        self._ensure_assets()
        logger.info("剧本杀 NPC 数据库插件已加载。")

    async def terminate(self):
        self._save_db()

    @filter.command("剧本杀帮助", alias={"npc帮助", "NPC帮助"})
    async def help_cmd(self, event: AstrMessageEvent):
        path = self._render_text_card(
            "剧本杀 NPC 数据库",
            [
                "/打卡 - 每天领取 1-3 星币或免费入场券",
                "/星币 - 查看自己的星币与入场券",
                "/赠送星币 @群友 数量 - 转赠星币",
                "/状态栏 - 查看当前 NPC 状态",
                "/切换角色 NPC名 - 更换当前 NPC",
                "/抽奖 [次数] - 10 星币一次，入场券可抵一次",
                "/物品栏 - 九宫格查看已拥有 NPC",
                "/NPC信息 NPC名 - 查询获取途径、加成与技能",
            ],
            subtitle="所有主要信息均以图片展示。角色立绘可替换 data/npc_assets 下的同名 PNG。",
        )
        yield event.image_result(str(path))

    @filter.command("星币", alias={"钱包", "我的星币"})
    async def wallet_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_text_card(
            "星币钱包",
            [
                f"持有星币：{player['coins']}",
                f"免费入场券：{player['tickets']}",
                f"当前角色：{self._npc(player['current_npc'])['name']}",
            ],
            subtitle="星币可用于抽奖，10 星币一次；免费入场券可抵扣一次单抽。",
        )
        yield event.image_result(str(path))

    @filter.command("赠送星币", alias={"转账星币", "给星币"})
    async def transfer_cmd(self, event: AstrMessageEvent):
        sender = self._get_player(event)
        target_id, target_label, amount = self._parse_transfer(event)
        if not target_id or amount <= 0:
            path = self._render_text_card("赠送失败", ["格式：/赠送星币 @群友 数量", "例如：/赠送星币 @小明 20"])
            yield event.image_result(str(path))
            return
        if sender["coins"] < amount:
            path = self._render_text_card("星币不足", [f"你的星币：{sender['coins']}", f"需要赠送：{amount}"])
            yield event.image_result(str(path))
            return

        target = self._get_player_by_id(event, target_id, target_label)
        sender["coins"] -= amount
        target["coins"] += amount
        self._save_db()

        path = self._render_text_card(
            "赠送成功",
            [f"你赠送给 {target_label} {amount} 个星币。", f"你的余额：{sender['coins']}", f"对方余额：{target['coins']}"],
            subtitle="星币在本群剧本杀档案内流通。",
        )
        yield event.image_result(str(path))

    @filter.command("打卡", alias={"每日打卡"})
    async def checkin_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        today = datetime.now().strftime("%Y-%m-%d")
        if player.get("last_checkin") == today:
            path = self._render_text_card(
                "今日已打卡",
                [f"日期：{today}", f"星币：{player['coins']}", f"免费入场券：{player['tickets']}"],
                subtitle="明天再来，档案室会刷新新的补给。",
            )
            yield event.image_result(str(path))
            return

        reward_type, amount = self._roll_checkin()
        if reward_type == "星币":
            player["coins"] += amount
        else:
            player["tickets"] += amount
        player["last_checkin"] = today
        self._save_db()

        path = self._render_text_card(
            "打卡成功",
            [f"获得：{amount} {reward_type}", f"当前星币：{player['coins']}", f"免费入场券：{player['tickets']}"],
            subtitle="概率：1星币45% / 2星币30% / 3星币20% / 入场券5%",
        )
        yield event.image_result(str(path))

    @filter.command("状态栏", alias={"角色状态", "我的角色"})
    async def status_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        npc_name = self._arg_text(event)
        npc = NPC_BY_NAME.get(npc_name) if npc_name else self._npc(player["current_npc"])
        if not npc:
            path = self._render_text_card("没有找到 NPC", [f"输入：{npc_name}", "可用 /物品栏 或 /NPC信息 查看角色。"])
            yield event.image_result(str(path))
            return
        if npc["id"] not in player["npcs"]:
            path = self._render_text_card("尚未拥有", [f"{npc['name']} 还没有加入你的队伍。", "可通过抽奖或活动获取。"])
            yield event.image_result(str(path))
            return

        path = self._render_status(player, npc)
        yield event.image_result(str(path))

    @filter.command("切换角色", alias={"更换角色", "选择角色"})
    async def switch_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        npc_name = self._arg_text(event)
        npc = NPC_BY_NAME.get(npc_name)
        if not npc:
            path = self._render_text_card("切换失败", [f"没有找到 NPC：{npc_name or '空'}", "格式：/切换角色 星见凛"])
            yield event.image_result(str(path))
            return
        if npc["id"] not in player["npcs"]:
            path = self._render_text_card("切换失败", [f"你尚未拥有 {npc['name']}。", "可通过抽奖或活动获取。"])
            yield event.image_result(str(path))
            return

        player["current_npc"] = npc["id"]
        self._save_db()
        path = self._render_status(player, npc, banner="已切换当前角色")
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

    @filter.command("物品栏", alias={"NPC仓库", "npc仓库", "我的NPC"})
    async def inventory_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        path = self._render_inventory(player)
        yield event.image_result(str(path))

    @filter.command("NPC信息", alias={"npc信息", "查NPC", "查询NPC"})
    async def npc_info_cmd(self, event: AstrMessageEvent):
        player = self._get_player(event)
        npc_name = self._arg_text(event)
        npc = NPC_BY_NAME.get(npc_name)
        if not npc:
            path = self._render_text_card("NPC 查询", [f"没有找到：{npc_name or '空'}", "可查询：" + "、".join(npc["name"] for npc in NPCS)])
            yield event.image_result(str(path))
            return
        path = self._render_npc_info(player, npc)
        yield event.image_result(str(path))

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
        scope_id = self._scope_id(event)
        scopes = self.db.setdefault("scopes", {})
        return scopes.setdefault(scope_id, {"players": {}})

    def _new_player(self, user_id: str, name: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "name": name,
            "coins": 20,
            "tickets": 0,
            "last_checkin": "",
            "current_npc": "rin",
            "npcs": {"rin": {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}},
        }

    def _get_player(self, event: AstrMessageEvent) -> Dict[str, Any]:
        return self._get_player_by_id(event, self._sender_id(event), event.get_sender_name())

    def _get_player_by_id(self, event: AstrMessageEvent, user_id: str, name: str) -> Dict[str, Any]:
        players = self._scope(event).setdefault("players", {})
        player = players.setdefault(user_id, self._new_player(user_id, name))
        player["name"] = name or player.get("name") or user_id
        player.setdefault("coins", 0)
        player.setdefault("tickets", 0)
        player.setdefault("current_npc", "rin")
        player.setdefault("npcs", {})
        if not player["npcs"]:
            player["npcs"]["rin"] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
        return player

    def _npc(self, npc_id: str) -> Dict[str, Any]:
        return NPC_BY_ID.get(npc_id, NPCS[0])

    def _npc_exp(self, player: Dict[str, Any], npc_id: str) -> int:
        return int(player["npcs"].get(npc_id, {}).get("exp", 0))

    def _add_exp(self, player: Dict[str, Any], npc_id: str, exp: int):
        if npc_id not in player["npcs"]:
            player["npcs"][npc_id] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
        player["npcs"][npc_id]["exp"] = int(player["npcs"][npc_id].get("exp", 0)) + exp

    def _level_info(self, exp: int) -> Tuple[int, int, int, float]:
        spent = 0
        for index, requirement in enumerate(LEVEL_REQUIREMENTS, start=1):
            if exp < spent + requirement:
                current = exp - spent
                return index, current, requirement, current / requirement
            spent += requirement
        return 5, LEVEL_REQUIREMENTS[-1], LEVEL_REQUIREMENTS[-1], 1.0

    def _arg_text(self, event: AstrMessageEvent) -> str:
        text = event.message_str.strip()
        text = re.sub(r"^[/！!]?[\w\u4e00-\u9fff]+", "", text, count=1).strip()
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
        target_id = self._extract_at_id(event)
        target_label = target_id or ""

        if not target_id:
            arg = self._arg_text(event)
            tokens = arg.split()
            if len(tokens) >= 2:
                target_id = tokens[0].strip("@")
                target_label = target_id
        else:
            target_label = f"用户{target_id}"
        return target_id, target_label, amount

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
        featured = [npc for npc in NPCS if npc["star"] in {"SSR", "SR"}]
        return rng.sample(featured, k=min(3, len(featured)))

    def _roll_draw(self, player: Dict[str, Any]) -> Dict[str, Any]:
        roll = random.random()
        current_id = player.get("current_npc", "rin")
        if roll < 0.06:
            npc = random.choice(self._monthly_pool())
            already_owned = npc["id"] in player["npcs"]
            if already_owned:
                exp = 600
                self._add_exp(player, npc["id"], exp)
                return {"kind": "大奖重复转经验", "name": npc["name"], "exp": exp, "npc_id": npc["id"]}
            player["npcs"][npc["id"]] = {"exp": 0, "owned_at": datetime.now().strftime("%Y-%m-%d")}
            return {"kind": "大奖角色", "name": npc["name"], "exp": 0, "npc_id": npc["id"]}

        gift_table = [
            ("线索书签", 80),
            ("微光糖果", 120),
            ("剧团胸针", 180),
            ("银色怀表", 260),
            ("限定花束", 420),
        ]
        gift, exp = random.choices(gift_table, weights=[35, 30, 20, 10, 5], k=1)[0]
        self._add_exp(player, current_id, exp)
        return {"kind": "礼物", "name": gift, "exp": exp, "npc_id": current_id}

    def _font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        for font_path in candidates:
            if Path(font_path).exists():
                return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()

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
        for npc in NPCS:
            path = self.assets_dir / f"{npc['id']}.png"
            if path.exists():
                continue
            self._draw_placeholder_portrait(npc, path)

    def _draw_placeholder_portrait(self, npc: Dict[str, Any], path: Path):
        main, accent, dark = npc["colors"]
        img = self._gradient((600, 820), dark, main).convert("RGBA")
        draw = ImageDraw.Draw(img)
        rng = random.Random(npc["id"])
        for _ in range(70):
            x = rng.randint(0, 600)
            y = rng.randint(0, 820)
            r = rng.randint(1, 3)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(50, 150)))

        cx = 300
        draw.ellipse((130, 550, 470, 980), fill=Image.new("RGB", (1, 1), main).getpixel((0, 0)) + (230,))
        skin = (255, 224, 205, 255)
        hair = Image.new("RGB", (1, 1), accent).getpixel((0, 0)) + (255,)
        draw.ellipse((170, 145, 430, 430), fill=hair)
        draw.polygon([(180, 250), (125, 565), (245, 405)], fill=hair)
        draw.polygon([(420, 250), (485, 565), (355, 405)], fill=hair)
        draw.ellipse((190, 190, 410, 455), fill=skin)
        draw.pieslice((170, 135, 430, 370), 180, 360, fill=hair)
        for i in range(8):
            x = 170 + i * 35
            draw.polygon([(x, 170), (x + 45, 165), (x + 20, 290)], fill=hair)
        eye_color = Image.new("RGB", (1, 1), main).getpixel((0, 0)) + (255,)
        draw.ellipse((225, 300, 270, 333), fill=(255, 255, 255, 255))
        draw.ellipse((330, 300, 375, 333), fill=(255, 255, 255, 255))
        draw.ellipse((240, 302, 265, 332), fill=eye_color)
        draw.ellipse((345, 302, 370, 332), fill=eye_color)
        draw.ellipse((248, 306, 256, 314), fill=(255, 255, 255, 255))
        draw.ellipse((353, 306, 361, 314), fill=(255, 255, 255, 255))
        draw.arc((270, 346, 330, 382), 20, 160, fill=(170, 90, 100, 255), width=4)
        draw.rectangle((245, 475, 355, 575), fill=skin)
        draw.polygon([(175, 820), (250, 520), (350, 520), (425, 820)], fill=(245, 245, 255, 235))
        draw.line((250, 520, 300, 650, 350, 520), fill=Image.new("RGB", (1, 1), main).getpixel((0, 0)) + (255,), width=8)
        draw.text((42, 42), npc["name"], font=self._font(48, True), fill=(255, 255, 255, 245))
        draw.text((44, 102), npc["star"], font=self._font(30, True), fill=Image.new("RGB", (1, 1), accent).getpixel((0, 0)) + (255,))
        img.save(path)

    def _portrait(self, npc: Dict[str, Any], size: Tuple[int, int]) -> Image.Image:
        path = self.assets_dir / f"{npc['id']}.png"
        if not path.exists():
            self._draw_placeholder_portrait(npc, path)
        img = Image.open(path).convert("RGBA")
        img.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.alpha_composite(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
        return canvas

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

    def _render_status(self, player: Dict[str, Any], npc: Dict[str, Any], banner: str = "") -> Path:
        path = self.render_dir / f"status_{player['user_id']}_{npc['id']}.png"
        main, accent, dark = npc["colors"]
        img = self._gradient((1280, 760), dark, "#f4f7fb").convert("RGBA")
        draw = ImageDraw.Draw(img)
        img.alpha_composite(self._portrait(npc, (470, 650)), (65, 70))
        draw.rounded_rectangle((520, 70, 1215, 725), radius=24, fill=(255, 255, 255, 235))

        if banner:
            draw.rounded_rectangle((555, 95, 820, 142), radius=18, fill=main)
            draw.text((578, 103), banner, font=self._font(24, True), fill="white")

        exp = self._npc_exp(player, npc["id"])
        level, current, need, ratio = self._level_info(exp)
        draw.text((555, 160), npc["name"], font=self._font(58, True), fill="#172033")
        draw.text((555, 230), f"{npc['star']}  |  {npc['bonus']}", font=self._font(28, True), fill=main)
        stars = "★" * level + "☆" * (5 - level)
        draw.text((555, 280), stars, font=self._font(42, True), fill="#f5b642")
        draw.text((555, 340), f"Lv.{level}  {current}/{need} EXP", font=self._font(26, True), fill="#26364d")
        draw.rounded_rectangle((555, 382, 1145, 418), radius=18, fill="#dbe2ef")
        draw.rounded_rectangle((555, 382, 555 + int(590 * ratio), 418), radius=18, fill=main)

        y = 455
        for line in self._wrap(draw, npc["intro"], self._font(25), 580)[:3]:
            draw.text((555, y), line, font=self._font(25), fill="#344056")
            y += 36

        y = 535
        thresholds = [2, 3, 5]
        for threshold, (skill, desc) in zip(thresholds, npc["skills"]):
            unlocked = level >= threshold
            fill = "#172033" if unlocked else "#8a94a6"
            chip = main if unlocked else "#cfd6e4"
            draw.rounded_rectangle((555, y, 1145, y + 36), radius=14, fill=chip)
            draw.text((575, y + 5), f"{threshold}星 {skill}", font=self._font(20, True), fill="white" if unlocked else "#566071")
            draw.text((575, y + 41), desc, font=self._font(18), fill=fill)
            y += 64
        img.save(path)
        return path

    def _render_inventory(self, player: Dict[str, Any]) -> Path:
        path = self.render_dir / f"inventory_{player['user_id']}.png"
        img = self._gradient((1120, 1120), "#173044", "#f2f6f9").convert("RGBA")
        draw = ImageDraw.Draw(img)
        draw.text((60, 45), "NPC 物品栏", font=self._font(54, True), fill="white")
        draw.text((60, 105), f"当前角色：{self._npc(player['current_npc'])['name']}", font=self._font(26), fill="#dbe7f0")

        start_x, start_y = 70, 170
        cell, gap = 300, 28
        for idx, npc in enumerate(NPCS[:9]):
            row, col = divmod(idx, 3)
            x = start_x + col * (cell + gap)
            y = start_y + row * (cell + gap)
            owned = npc["id"] in player["npcs"]
            draw.rounded_rectangle((x, y, x + cell, y + cell), radius=18, fill=(255, 255, 255, 238))
            portrait = self._portrait(npc, (cell - 30, 210))
            if not owned:
                portrait = ImageEnhance.Color(portrait).enhance(0.05).filter(ImageFilter.GaussianBlur(0.5))
            img.alpha_composite(portrait, (x + 15, y + 14))
            draw.text((x + 20, y + 230), npc["name"], font=self._font(26, True), fill="#172033" if owned else "#798395")
            exp = self._npc_exp(player, npc["id"]) if owned else 0
            level = self._level_info(exp)[0] if owned else 0
            draw.text((x + 20, y + 265), f"{'已拥有' if owned else '未获得'}  Lv.{level}", font=self._font(20), fill="#526071")
            if npc["id"] == player.get("current_npc"):
                draw.rounded_rectangle((x + 188, y + 258, x + 280, y + 288), radius=12, fill=npc["colors"][0])
                draw.text((x + 203, y + 261), "当前", font=self._font(18, True), fill="white")
        img.save(path)
        return path

    def _render_npc_info(self, player: Dict[str, Any], npc: Dict[str, Any]) -> Path:
        owned = npc["id"] in player["npcs"]
        path = self.render_dir / f"npc_{npc['id']}.png"
        main, _, dark = npc["colors"]
        img = self._gradient((1180, 760), dark, "#eef3f8").convert("RGBA")
        draw = ImageDraw.Draw(img)
        img.alpha_composite(self._portrait(npc, (410, 650)), (55, 70))
        draw.rounded_rectangle((470, 70, 1125, 690), radius=22, fill=(255, 255, 255, 235))
        draw.text((510, 115), npc["name"], font=self._font(54, True), fill="#172033")
        draw.text((510, 180), f"{npc['star']}  |  {'已拥有' if owned else '未拥有'}", font=self._font(28, True), fill=main)
        blocks = [
            ("获取途径", npc["route"]),
            ("经验加成", npc["bonus"]),
            ("角色介绍", npc["intro"]),
        ]
        y = 245
        for title, text in blocks:
            draw.text((510, y), title, font=self._font(26, True), fill=main)
            y += 38
            for wrapped in self._wrap(draw, text, self._font(24), 555)[:3]:
                draw.text((510, y), wrapped, font=self._font(24), fill="#344056")
                y += 34
            y += 15
        draw.text((510, y), "技能", font=self._font(26, True), fill=main)
        y += 40
        for idx, (skill, desc) in enumerate(npc["skills"]):
            draw.text((510, y), f"{[2, 3, 5][idx]}星 {skill}", font=self._font(22, True), fill="#172033")
            y += 30
            draw.text((510, y), desc, font=self._font(20), fill="#526071")
            y += 38
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
        draw.text((790, 126), "、".join(npc["name"] for npc in pool), font=self._font(22), fill="#3e4a5e")
        draw.text((790, 164), "大奖概率 6%，重复转 600 EXP", font=self._font(20), fill="#657086")

        y = 190
        for index, result in enumerate(results, start=1):
            npc = self._npc(result["npc_id"])
            x = 65 + ((index - 1) % 2) * 540
            yy = y + ((index - 1) // 2) * 100
            draw.rounded_rectangle((x, yy, x + 500, yy + 78), radius=18, fill=(255, 255, 255, 232))
            color = npc["colors"][0]
            draw.rounded_rectangle((x + 18, yy + 18, x + 92, yy + 60), radius=16, fill=color)
            draw.text((x + 38, yy + 24), str(index), font=self._font(24, True), fill="white")
            draw.text((x + 112, yy + 13), result["name"], font=self._font(25, True), fill="#172033")
            detail = result["kind"] if result["exp"] == 0 else f"{result['kind']} -> {npc['name']} +{result['exp']} EXP"
            draw.text((x + 112, yy + 45), detail, font=self._font(19), fill="#526071")
        img.save(path)
        return path
