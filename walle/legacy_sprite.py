"""WALL-E 形象矢量绘制。

使用 QPainter 纯代码绘制 WALL-E 机器人形象，避免依赖外部图片资源，
保证打包后单文件即可运行。支持不同表情/状态：
    idle   - 普通待机
    happy  - 开心（完成任务时）
    rest   - 休息提醒（眼睛眯起、举手）
    sleep  - 睡眠（眼睛闭合）
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

# WALL-E 经典配色
BODY_COLOR = QColor(0xC8, 0x8A, 0x3A)      # 锈黄色机身
BODY_DARK = QColor(0x9A, 0x66, 0x22)
METAL = QColor(0x6B, 0x6B, 0x6B)            # 金属灰
METAL_DARK = QColor(0x3A, 0x3A, 0x3A)
EYE_RING = QColor(0x4A, 0x4A, 0x4A)
EYE_GLASS = QColor(0x1B, 0x1B, 0x1B)
EYE_GLOW = QColor(0x9F, 0xD8, 0xF0)         # 镜头泛蓝光
TREAD = QColor(0x2C, 0x2C, 0x2C)


def render_walle(size: int, state: str = "idle", blink: bool = False) -> QPixmap:
    """绘制指定尺寸与状态的 WALL-E，返回带透明背景的 QPixmap。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    # 以 100x100 为设计稿，再缩放到目标尺寸
    p.scale(size / 100.0, size / 100.0)

    _draw_treads(p)
    _draw_body(p)
    _draw_arms(p, state)
    _draw_neck(p)
    _draw_eyes(p, state, blink)

    p.end()
    return pm


def _draw_treads(p: QPainter) -> None:
    """绘制左右履带（轮子）。"""
    p.setPen(Qt.NoPen)
    for x in (8, 64):
        rect = QRectF(x, 64, 28, 30)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, METAL)
        grad.setColorAt(1, METAL_DARK)
        p.setBrush(QBrush(grad))
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.drawPath(path)
        # 履带纹路
        p.setBrush(TREAD)
        for i in range(4):
            p.drawRoundedRect(QRectF(x + 3 + i * 6, 70, 4, 18), 2, 2)


def _draw_body(p: QPainter) -> None:
    """绘制方形身体。"""
    rect = QRectF(20, 34, 60, 40)
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, BODY_COLOR)
    grad.setColorAt(1, BODY_DARK)
    p.setPen(QPen(BODY_DARK, 1))
    p.setBrush(QBrush(grad))
    path = QPainterPath()
    path.addRoundedRect(rect, 8, 8)
    p.drawPath(path)

    # 胸前的太阳能/面板细节
    p.setPen(QPen(BODY_DARK, 1))
    p.setBrush(QColor(0xB0, 0x76, 0x2E))
    p.drawRoundedRect(QRectF(28, 42, 44, 22), 4, 4)
    p.setPen(QPen(BODY_DARK, 0.8))
    for gx in range(34, 70, 8):
        p.drawLine(QPointF(gx, 44), QPointF(gx, 62))
    # 小红色指示灯
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0xE0, 0x4F, 0x3A))
    p.drawEllipse(QPointF(64, 68), 2.2, 2.2)
    p.setBrush(QColor(0x4F, 0xC0, 0x6A))
    p.drawEllipse(QPointF(56, 68), 2.2, 2.2)


def _draw_arms(p: QPainter, state: str) -> None:
    """绘制两侧机械臂。休息状态时手臂上举。"""
    p.setPen(Qt.NoPen)
    p.setBrush(METAL)
    # 左臂
    p.drawRoundedRect(QRectF(14, 40, 8, 26), 4, 4)
    # 右臂
    if state == "rest":
        # 举手提醒
        p.save()
        p.translate(82, 44)
        p.rotate(-35)
        p.drawRoundedRect(QRectF(-4, -22, 8, 26), 4, 4)
        p.restore()
    else:
        p.drawRoundedRect(QRectF(78, 40, 8, 26), 4, 4)


def _draw_neck(p: QPainter) -> None:
    """绘制连接头部的伸缩颈。"""
    p.setPen(Qt.NoPen)
    p.setBrush(METAL_DARK)
    p.drawRoundedRect(QRectF(44, 24, 12, 14), 3, 3)


def _draw_eyes(p: QPainter, state: str, blink: bool) -> None:
    """绘制 WALL-E 标志性的双筒望远镜眼睛。"""
    # 横向支架
    p.setPen(QPen(METAL_DARK, 3))
    p.drawLine(QPointF(34, 18), QPointF(66, 18))

    for cx in (33, 67):
        # 外圈金属
        p.setPen(Qt.NoPen)
        p.setBrush(EYE_RING)
        p.drawEllipse(QPointF(cx, 18), 15, 15)
        p.setBrush(METAL_DARK)
        p.drawEllipse(QPointF(cx, 18), 13, 13)
        # 镜片
        p.setBrush(EYE_GLASS)
        p.drawEllipse(QPointF(cx, 18), 10, 10)

        if state == "sleep" or blink:
            # 闭眼：一条横线
            p.setPen(QPen(EYE_GLOW, 2))
            p.drawLine(QPointF(cx - 8, 18), QPointF(cx + 8, 18))
            continue

        # 镜头内的发光与瞳孔
        if state == "rest":
            p.setBrush(EYE_GLOW)
            path = QPainterPath()
            path.moveTo(cx - 8, 18)
            path.arcTo(QRectF(cx - 8, 10, 16, 16), 0, -180)
            p.setPen(Qt.NoPen)
            p.drawPath(path)
        else:
            p.setBrush(EYE_GLOW)
            p.drawEllipse(QPointF(cx, 18), 6, 6)
            p.setBrush(QColor(255, 255, 255, 200))
            p.drawEllipse(QPointF(cx + 2, 16), 2.2, 2.2)

        if state == "happy":
            # 开心：眼睛上翘弧线
            p.setPen(QPen(EYE_GLOW, 2))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cx - 9, 12, 18, 14), 20 * 16, 140 * 16)
