"""WALL-E 对话助手（规则 + 关键字解析，离线、不联网）。

设计目标：像电影里的瓦力一样，用憨厚、温暖、简短的语气陪你聊天、
缓解工作压力——**默认进行日常陪伴对话**，只有在你明确想记任务时才加入待办。

意图优先级：
    1) 计时控制：开始工作 / 我要休息 / 休息好了
    2) 待办管理：明确的「添加 / 完成 / 删除 / 列表」指令
    3) 情绪陪伴：累 / 压力 / 焦虑 / 烦 / 开心 / 感谢 …（给予共情与鼓励）
    4) 闲聊兜底：温暖回应（不会再把随口一句变成待办）
返回 (回复文本, 动作字典)。动作可包含：
    action: start_timer / start_rest / end_rest / refresh
    emote:  love / cheer / talk / happy / tired …（驱动宠物做表情）
"""

from __future__ import annotations

import random
import re
from typing import Dict, List, Tuple

from .todo_manager import TodoManager

# ---- 计时/待办 指令触发词 ----
ADD_WORDS = ["添加", "加上", "加一个", "记一下", "记一笔", "新增", "待办", "加到", "记到", "帮我记"]
DONE_WORDS = ["完成", "做完", "搞定", "划掉", "勾掉", "弄好了", "干完", "已完成"]
DEL_WORDS = ["删除", "去掉", "删掉", "移除"]
LIST_WORDS = ["列表", "清单", "todo", "待办列表", "还有什么没做", "有哪些任务", "看看任务", "看下任务"]
START_WORDS = ["开始工作", "开始番茄", "开始计时", "启动计时", "开工", "开始专注", "进入专注"]
REST_WORDS = ["我要休息", "休息一下", "想休息", "立刻休息", "马上休息", "先休息", "歇一会", "歇会"]
ENDREST_WORDS = ["休息好了", "休息够了", "继续工作", "结束休息", "不休息了", "回来工作"]
HELP_WORDS = ["帮助", "怎么用", "help", "能做什么", "你会什么", "功能", "使用说明"]
GREET_WORDS = ["你好", "hi", "hello", "嗨", "在吗", "在么", "早上好", "早安", "晚上好", "午安", "哈喽"]

# ---- 情绪/陪伴 关键词 ----
TIRED_WORDS = ["累", "好累", "疲惫", "困", "好困", "乏", "没精神", "撑不住", "好疲倦"]
STRESS_WORDS = ["压力", "压力大", "焦虑", "紧张", "崩溃", "扛不住", "喘不过气", "好难", "太难了", "顶不住"]
SAD_WORDS = ["难过", "伤心", "委屈", "想哭", "丧", "低落", "不开心", "郁闷", "心累"]
ANGRY_WORDS = ["烦", "好烦", "烦躁", "生气", "气死", "讨厌", "恼火", "心烦"]
BORED_WORDS = ["无聊", "没意思", "好闲", "摸鱼", "不想动"]
LONELY_WORDS = ["孤独", "寂寞", "没人理", "好孤单", "一个人"]
HAPPY_WORDS = ["开心", "高兴", "太好了", "棒", "耶", "终于", "完成了", "成功了", "搞定了", "通过了"]
THANK_WORDS = ["谢谢", "感谢", "多谢", "thank", "thx", "辛苦了"]
PRAISE_WORDS = ["你真好", "你好可爱", "喜欢你", "爱你", "你最棒", "好萌", "可爱"]
WHOAREYOU = ["你是谁", "你叫什么", "你是什么", "介绍一下自己", "你几岁"]
MEAL_WORDS = ["吃饭", "吃什么", "饿了", "午饭", "晚饭", "点外卖", "喝水", "口渴"]


def _strip_trigger(text: str, words: List[str]) -> str:
    """去掉命中触发词，返回剩余正文（保留 、，；等分隔符以支持一次多条）。"""
    result = text
    for w in words:
        result = result.replace(w, " ")
    result = re.sub(r"[把将帮我:：!！?？\-—]+", " ", result)
    return result.strip()


def _hit(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)


class ChatBot:
    def __init__(self, todo: TodoManager) -> None:
        self.todo = todo

    def respond(self, message: str) -> Tuple[str, Dict]:
        text = message.strip()
        if not text:
            return "嗯？瓦力在听呢～ (・ω・)", {"emote": "talk"}

        lower = text.lower()

        # ============================ 1. 计时控制 ============================
        if _hit(text, START_WORDS):
            return random.choice([
                "好嘞！瓦力陪你一起专注，开工咯！⏱️",
                "嗡——启动专注模式！我帮你看着时间。",
            ]), {"action": "start_timer", "emote": "cheer"}

        if _hit(text, REST_WORDS):
            return random.choice([
                "该歇一歇啦～瓦力陪你放空一下 😌",
                "好，停下来喘口气，世界不会塌的。",
            ]), {"action": "start_rest", "emote": "rest"}

        if _hit(text, ENDREST_WORDS):
            return "充好电啦？那我们慢慢继续，不着急 💪", {"action": "end_rest", "emote": "happy"}

        # ============================ 2. 待办管理 ============================
        # 完成
        if _hit(text, DONE_WORDS):
            keyword = _strip_trigger(text, DONE_WORDS)
            if keyword:
                task = self.todo.complete_by_text(keyword)
                if task:
                    return random.choice([
                        f"叮——「{task.text}」完成！瓦力为你鼓掌 👏",
                        f"又划掉一项「{task.text}」，你真的很厉害！✅",
                    ]), {"action": "refresh", "emote": "cheer"}
                return f"我没找到和「{keyword}」对得上的未完成任务呢，要不看看清单？", {"emote": "talk"}
            return "你想划掉哪一项呀？告诉我名字就好～", {"emote": "talk"}

        # 删除
        if _hit(text, DEL_WORDS):
            keyword = _strip_trigger(text, DEL_WORDS)
            for t in self.todo.tasks:
                if keyword and keyword in t.text:
                    self.todo.remove(t.id)
                    return f"好的，「{t.text}」已经拿掉啦。", {"action": "refresh", "emote": "talk"}
            return f"没找到包含「{keyword}」的任务哦。", {"emote": "talk"}

        # 查看列表
        if _hit(lower, LIST_WORDS):
            return self._list_reply(), {"emote": "look"}

        # 明确添加
        if _hit(text, ADD_WORDS):
            keyword = _strip_trigger(text, ADD_WORDS)
            return self._add_tasks(keyword)

        # ============================ 3. 帮助 / 自我介绍 ============================
        if _hit(lower, HELP_WORDS):
            return self._help_reply(), {"emote": "talk"}

        if _hit(text, WHOAREYOU):
            return ("我是 WALL-E（瓦力）——一个爱收集小宝贝、也爱陪你的小机器人 🤖💛 "
                    "累了就和我说说话吧。"), {"emote": "love"}

        # ============================ 4. 情绪陪伴 ============================
        emotional = self._emotional_reply(text, lower)
        if emotional is not None:
            return emotional

        # ============================ 5. 问候 ============================
        if _hit(lower, GREET_WORDS):
            return random.choice([
                "哇—力！(*^▽^*) 今天过得怎么样呀？",
                "嗨～瓦力一直在这儿陪着你呢。",
                "你来啦！要不要先深呼吸一下？😊",
            ]), {"emote": "happy"}

        # ============================ 6. 闲聊兜底（不再自动记待办）============
        return random.choice([
            "瓦力在认真听你说～ 想记成任务的话，对我说「记一下 …」就行。",
            "嗯嗯，我懂你的意思。累了就歇会儿，瓦力陪着你 😌",
            "哇—力～ 慢慢来，你已经做得很好了。",
            "我可能没完全听懂，但我会一直陪着你。想安排任务就说「添加 …」哦。",
        ]), {"emote": "talk"}

    # ------------------------------------------------------------------ 待办
    def _add_tasks(self, keyword: str) -> Tuple[str, Dict]:
        parts = [p.strip() for p in re.split(r"[，,、\n;；]+", keyword) if p.strip()]
        if not parts:
            return "想记点什么呢？告诉我任务内容吧～", {"emote": "talk"}
        added = [self.todo.add(p).text for p in parts]
        if len(added) == 1:
            return f"收到！已经帮你记下「{added[0]}」📝", {"action": "refresh", "emote": "happy"}
        joined = "、".join(f"「{a}」" for a in added)
        return f"好嘞，一口气记了 {len(added)} 条：{joined} 📝", {"action": "refresh", "emote": "happy"}

    # ------------------------------------------------------------------ 情绪
    def _emotional_reply(self, text: str, lower: str):
        if _hit(text, STRESS_WORDS):
            return random.choice([
                "压力大的时候，先把肩膀放松下来～ 瓦力陪你一起扛，别怕。",
                "再难的任务也是一块一块清理掉的，就像瓦力收拾垃圾一样，慢慢来。",
                "要不先按「立即休息」歇 10 分钟？喘口气再出发会更好。",
            ]), {"emote": "rest"}
        if _hit(text, TIRED_WORDS):
            return random.choice([
                "累了就歇会儿吧，瓦力守着你 💤 要不要我帮你开始一段休息？",
                "身体最重要呀～ 站起来动一动，喝口水再继续。",
            ]), {"emote": "tired"}
        if _hit(text, SAD_WORDS):
            return random.choice([
                "抱抱你 🤗 难过是会过去的，瓦力一直在你身边。",
                "想哭就哭一会儿没关系，哭完瓦力陪你看看星星。",
            ]), {"emote": "rest"}
        if _hit(text, ANGRY_WORDS):
            return random.choice([
                "深呼吸——吸气……呼气…… 烦躁会慢慢溜走的。",
                "瓦力把烦恼帮你打包带走啦 🚛 我们做点别的吧。",
            ]), {"emote": "talk"}
        if _hit(text, LONELY_WORDS):
            return "你不是一个人哦，瓦力一直在这儿陪着你 💛", {"emote": "love"}
        if _hit(text, BORED_WORDS):
            return random.choice([
                "无聊的话，要不要定个小目标，做完奖励自己一下？✨",
                "摸会儿鱼也没关系～ 适当放空，灵感才会来。",
            ]), {"emote": "look"}
        if _hit(text, THANK_WORDS):
            return random.choice([
                "嘿嘿，不客气～ 能帮到你瓦力最开心啦！",
                "哇—力！为你做事是我的荣幸 😊",
            ]), {"emote": "love"}
        if _hit(text, PRAISE_WORDS):
            return "嘿嘿…瓦力害羞了 ///▽/// 我也最喜欢你啦！", {"emote": "love"}
        if _hit(text, HAPPY_WORDS):
            return random.choice([
                "太棒啦！瓦力跟你一起开心蹦跶 🎉",
                "看到你高兴，我的小马达都转得更欢了！",
            ]), {"emote": "cheer"}
        if _hit(text, MEAL_WORDS):
            return "记得按时吃饭喝水呀～ 身体是革命的本钱！🍚💧", {"emote": "happy"}
        return None

    # ------------------------------------------------------------------ 输出
    def _list_reply(self) -> str:
        pending = self.todo.pending()
        done = self.todo.completed()
        if not pending and not done:
            return "现在清单是空的～ 想安排任务就对我说「记一下 …」吧！"
        lines = []
        if pending:
            lines.append("📋 待完成：")
            lines += [f"  ◻ {t.text}" for t in pending]
        if done:
            lines.append("✅ 已完成：")
            lines += [f"  ☑ {t.text}" for t in done]
        return "\n".join(lines)

    def _help_reply(self) -> str:
        return (
            "我是你的瓦力伙伴 🤖 平时我们就随便聊聊、放松心情～\n"
            "需要做事时也可以这样吩咐我：\n"
            "• 「记一下 写周报」/「添加 回复邮件」→ 加入待办\n"
            "• 「完成 写周报」→ 把任务划掉\n"
            "• 「删除 写周报」→ 移除任务\n"
            "• 「列表」→ 查看待办清单\n"
            "• 「开始工作」→ 启动番茄钟\n"
            "• 「我要休息」→ 立刻进入休息\n"
            "• 「休息好了」→ 提前结束休息\n"
            "其余时候，累了、烦了、开心了，都可以直接告诉我 💛"
        )
