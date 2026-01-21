import csv
import random
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, QSize, QTimer
from PyQt6.QtGui import QPainter, QPixmap, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QMessageBox


class GamerData:
    """玩家数据管理类：负责从CSV读取玩家姓名和编号，并提供随机分组功能。

    参数:
        csv_path: CSV文件路径对象。

    属性:
        csv_path: CSV文件路径。
        names: 玩家姓名列表（str）。
        numbers: 玩家编号列表（int）。
    """

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.names: list[str] = []
        self.numbers: list[int] = []

    def load(self) -> None:
        """从CSV文件读取玩家数据并填充姓名与编号列表。

        参数:
            无。

        返回:
            None。
        """
        self.names.clear()
        self.numbers.clear()

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                name = row[0].strip()
                number_str = row[1].strip()
                if not name or not number_str:
                    continue
                try:
                    number = int(number_str)
                except ValueError:
                    continue
                self.names.append(name)
                self.numbers.append(number)

    def select_groups(self, group_size: int) -> dict[str, list[int]]:
        """按照给定人数随机抽取红黄蓝紫四组玩家编号。

        参数:
            group_size: 每组人数，只支持2或3。

        返回:
            一个字典，键为'red'、'yellow'、'blue'、'purple'，
            值为对应组内玩家编号列表。
        """
        if group_size not in (2, 3):
            raise ValueError("每组人数仅支持2或3。")

        total_needed = 4 * group_size
        if len(self.numbers) < total_needed:
            raise ValueError(f"玩家数量不足，需要至少{total_needed}人。")

        selected = random.sample(self.numbers, total_needed)
        groups: dict[str, list[int]] = {
            "red": [],
            "yellow": [],
            "blue": [],
            "purple": [],
        }

        index = 0
        for key in groups.keys():
            groups[key] = selected[index:index + group_size]
            index += group_size

        return groups


class DrawWidget(QWidget):
    """绘制和交互组件：负责背景绘制、结果显示和按钮区域点击处理。

    参数:
        gamer_data: 玩家数据管理实例。
        background_path: 背景图片路径对象。
    """

    DESIGN_WIDTH = 6826
    DESIGN_HEIGHT = 3840

    def __init__(self, gamer_data: GamerData, background_path: Path) -> None:
        super().__init__()
        self.gamer_data = gamer_data
        self.background_pixmap = QPixmap(str(background_path))

        # 设计坐标系下的显示区域与按钮区域
        self.group_rects_design: dict[str, QRectF] = {
            "red": QRectF(1705, 651, 1595, 768),
            "yellow": QRectF(3555, 651, 1595, 768),
            "blue": QRectF(1705, 1711, 1595, 768),
            "purple": QRectF(3555, 1711, 1595, 768),
        }
        self.button_rects_design: dict[str, QRectF] = {
            "two": QRectF(1942, 2743, 1386, 274),
            "three": QRectF(3514, 2743, 1386, 274),
        }

        # 当前缩放与偏移，用于把设计坐标转换为屏幕坐标
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0

        # 当前抽取结果
        self.group_results: dict[str, list[int]] = {
            "red": [],
            "yellow": [],
            "blue": [],
            "purple": [],
        }

        # 自动清空计时器
        self.clear_timer = QTimer(self)
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(self._clear_results)

        self.setMinimumSize(QSize(800, 450))

    def _update_transform(self) -> None:
        """根据当前窗口大小和背景图尺寸更新缩放与偏移量。

        参数:
            无。

        返回:
            None。
        """
        if self.background_pixmap.isNull():
            self._scale_x = 1.0
            self._scale_y = 1.0
            self._offset_x = 0.0
            self._offset_y = 0.0
            return

        widget_width = float(self.width())
        widget_height = float(self.height())

        design_ratio = self.DESIGN_WIDTH / self.DESIGN_HEIGHT
        widget_ratio = widget_width / widget_height if widget_height > 0 else design_ratio

        if widget_ratio > design_ratio:
            # 以高度为基准缩放
            scaled_height = widget_height
            scaled_width = scaled_height * design_ratio
        else:
            # 以宽度为基准缩放
            scaled_width = widget_width
            scaled_height = scaled_width / design_ratio

        self._scale_x = scaled_width / self.DESIGN_WIDTH
        self._scale_y = scaled_height / self.DESIGN_HEIGHT
        self._offset_x = (widget_width - scaled_width) / 2.0
        self._offset_y = (widget_height - scaled_height) / 2.0

    def _design_to_screen_rect(self, rect: QRectF) -> QRectF:
        """把设计坐标系中的矩形转换为当前窗口中的实际显示矩形。

        参数:
            rect: 设计坐标系中的矩形。

        返回:
            转换后的屏幕坐标矩形。
        """
        x = self._offset_x + rect.x() * self._scale_x
        y = self._offset_y + rect.y() * self._scale_y
        w = rect.width() * self._scale_x
        h = rect.height() * self._scale_y
        return QRectF(x, y, w, h)

    def _draw_background(self, painter: QPainter) -> None:
        """绘制缩放后的背景图。

        参数:
            painter: QPainter绘图对象。

        返回:
            None。
        """
        if self.background_pixmap.isNull():
            return

        scaled_width = self.DESIGN_WIDTH * self._scale_x
        scaled_height = self.DESIGN_HEIGHT * self._scale_y
        target_rect = QRectF(
            self._offset_x,
            self._offset_y,
            scaled_width,
            scaled_height,
        )
        source_rect = QRectF(
            0.0,
            0.0,
            float(self.background_pixmap.width()),
            float(self.background_pixmap.height()),
        )
        painter.drawPixmap(target_rect, self.background_pixmap, source_rect)

    def _draw_results(self, painter: QPainter) -> None:
        """在各组结果区域绘制抽取出的玩家编号。

        参数:
            painter: QPainter绘图对象。

        返回:
            None。
        """
        painter.setPen(Qt.GlobalColor.black)

        for group_key, numbers in self.group_results.items():
            if not numbers:
                continue
            design_rect = self.group_rects_design.get(group_key)
            if design_rect is None:
                continue
            screen_rect = self._design_to_screen_rect(design_rect)

            font_size = max(int(screen_rect.height() * 0.35), 10)
            font = QFont()
            font.setPointSize(font_size)
            painter.setFont(font)

            text = ", ".join(str(n) for n in numbers)
            painter.drawText(
                screen_rect,
                int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
                text,
            )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """重绘事件：负责计算缩放并绘制背景和抽取结果。"""
        self._update_transform()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self._draw_background(painter)
        self._draw_results(painter)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """鼠标按下事件：判断是否点击了2人或3人按钮并触发抽取。"""
        pos = event.position() if hasattr(event, "position") else event.pos()
        click_point = QPointF(float(pos.x()), float(pos.y()))

        two_rect = self._design_to_screen_rect(self.button_rects_design["two"])
        three_rect = self._design_to_screen_rect(self.button_rects_design["three"])

        if two_rect.contains(click_point):
            self._handle_draw(2)
        elif three_rect.contains(click_point):
            self._handle_draw(3)
        else:
            super().mousePressEvent(event)

    def _handle_draw(self, group_size: int) -> None:
        """执行抽取操作并刷新界面显示。

        参数:
            group_size: 每组人数，2或3。

        返回:
            None。
        """
        try:
            results = self.gamer_data.select_groups(group_size)
        except ValueError as exc:
            QMessageBox.warning(self, "抽取失败", str(exc))
            return

        self.group_results = results
        self.update()

        self._start_clear_timer()

    def _start_clear_timer(self) -> None:
        """启动或重启自动清空计时器，在指定时间后恢复初始状态。

        参数:
            无。

        返回:
            None。
        """
        self.clear_timer.stop()
        self.clear_timer.start(600_000)

    def _clear_results(self) -> None:
        """清空当前抽取结果，使界面恢复到初始未抽取状态。

        参数:
            无。

        返回:
            None。
        """
        for key in self.group_results.keys():
            self.group_results[key] = []
        self.update()


class MainWindow(QMainWindow):
    """主窗口类：承载绘制组件并初始化整个应用。"""

    def __init__(self, csv_path: Path, background_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("随机分组抽签")

        gamer_data = GamerData(csv_path)
        gamer_data.load()

        self.draw_widget = DrawWidget(gamer_data, background_path)
        self.setCentralWidget(self.draw_widget)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    csv_file = base_dir / "gamer.csv"
    background_file = base_dir / "background.png"

    app = QApplication(sys.argv)

    window = MainWindow(csv_file, background_file)
    window.resize(1360, 765)
    window.show()

    sys.exit(app.exec())
