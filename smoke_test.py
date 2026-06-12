"""离屏冒烟测试：验证模块导入、动画加载、对话与番茄钟逻辑，不弹出窗口。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from walle import walle_sprite as sprite  # noqa: E402
from walle.animator import SpriteAnimator  # noqa: E402
from walle.chatbot import ChatBot  # noqa: E402
from walle.pomodoro import PomodoroState, PomodoroTimer  # noqa: E402
from walle.todo_manager import TodoManager  # noqa: E402
from walle.walle_sprite import render_walle  # noqa: E402


def main() -> None:
    app = QApplication([])

    # 1. 动画资源 + 各状态首帧绘制
    assert sprite.assets_available(), "动画资源缺失"
    anims = sprite.list_animations()
    assert {"idle", "rest", "happy", "cheer", "love", "talk"} <= set(anims), anims
    for state in ("idle", "happy", "rest", "sleep", "love", "cheer"):
        pm = render_walle(160, state=state)
        assert not pm.isNull(), f"绘制失败: {state}"
    # 动画播放器能逐帧驱动
    label = QLabel()
    an = SpriteAnimator(label, size=120)
    an.play("idle")
    assert label.pixmap() is not None and not label.pixmap().isNull()
    print(f"[OK] 动画资源正常，共 {len(anims)} 组动作")

    # 2. 待办 + 聊天机器人
    todo = TodoManager()
    todo.clear_all()
    bot = ChatBot(todo)

    # 2a. 明确添加才入待办
    reply, action = bot.respond("记一下 写周报、回复邮件")
    assert len(todo.pending()) == 2, "显式添加多条任务失败"
    print("[OK] 显式添加任务:", reply)

    # 2b. 日常闲聊不应产生待办
    before = len(todo.tasks)
    reply, action = bot.respond("今天天气真好啊")
    assert len(todo.tasks) == before, "闲聊不应新增待办"
    assert "action" not in action, "闲聊不应触发动作"
    print("[OK] 闲聊不入待办:", reply)

    # 2c. 情绪陪伴
    reply, action = bot.respond("好累啊压力好大")
    assert len(todo.tasks) == before, "情绪倾诉不应新增待办"
    print("[OK] 情绪陪伴:", reply)

    # 2d. 完成任务
    reply, action = bot.respond("完成 写周报")
    assert len(todo.completed()) == 1, "完成任务失败"
    print("[OK] 完成任务:", reply)

    # 2e. 计时指令
    reply, action = bot.respond("开始工作")
    assert action.get("action") == "start_timer"
    print("[OK] 指令解析:", reply)

    # 3. 番茄钟状态机（快速参数）
    timer = PomodoroTimer()
    timer.configure(1, 1, 2)
    states = []
    timer.state_changed.connect(lambda s: states.append(s))
    timer.start()
    assert timer.state == PomodoroState.WORKING
    timer.skip_to_rest()
    assert timer.state == PomodoroState.RESTING
    timer.end_rest_now()
    assert timer.state == PomodoroState.WORKING and timer.current_cycle == 2
    timer.skip_to_rest()
    timer.end_rest_now()
    assert timer.state == PomodoroState.FINISHED
    print("[OK] 番茄钟状态机正常，状态序列:", [s.value for s in states])

    todo.clear_all()
    print("\n全部测试通过 ✅")


if __name__ == "__main__":
    main()
