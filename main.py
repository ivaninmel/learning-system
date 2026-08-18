"""学习记录、复盘与专注监督桌面应用入口。"""
from __future__ import annotations

import ctypes
import html
import json
import random
import sys
from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QComboBox, QDateTimeEdit, QDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget,
)

from database import Database
from services import LearningService



def button(text: str, accent: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if accent:
        widget.setProperty("accent", True)
    return widget


def configure_datetime(editor: QDateTimeEdit) -> None:
    """日期和时间均可点选、鼠标滚轮调整或直接键盘输入。"""
    editor.setDisplayFormat("yyyy-MM-dd  HH:mm")
    editor.setCalendarPopup(True)
    editor.setKeyboardTracking(True)
    editor.setDateTime(QDateTime.currentDateTime())


class FloatingWidget(QDialog):
    """置顶的专注小窗，倒计时期间会启动轻量的离开确认。"""
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__(main_window, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.main_window = main_window
        self.setWindowTitle("专注小窗")
        self.setFixedSize(370, 330)
        self.setModal(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)
        heading = QLabel("现在只做这一件事")
        heading.setObjectName("floatHeading")
        self.goal = QLineEdit("完成今天的学习计划")
        self.phrase = QLineEdit("先完成，再休息。")
        self.remaining = QLabel("25:00")
        self.remaining.setObjectName("timer")
        self.remaining.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 180)
        self.minutes.setSuffix(" 分钟")
        self.minutes.setValue(25)
        self.start = button("开始专注模式", True)
        self.stop = button("停止本次专注")
        self.status = QLabel("打开小窗后，其他任务栏窗口会自动最小化。")
        self.status.setWordWrap(True)
        self.completed = QLabel("已专注：00:00")
        self.completed.setObjectName("completed")
        layout.addWidget(heading)
        self.form = QFormLayout()
        self.form.addRow("专注目标", self.goal)
        self.form.addRow("提醒短语", self.phrase)
        self.form.addRow("持续时间", self.minutes)
        self.settings_panel = QWidget()
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(10)
        settings_layout.addLayout(self.form)
        settings_layout.addWidget(self.start)
        layout.addWidget(self.settings_panel)
        self.running_panel = QWidget()
        running_layout = QVBoxLayout(self.running_panel)
        running_layout.setContentsMargins(0, 4, 0, 0)
        self.running_goal = QLabel()
        self.running_goal.setObjectName("runningGoal")
        self.running_goal.setWordWrap(True)
        self.running_phrase = QLabel()
        self.running_phrase.setObjectName("runningPhrase")
        self.running_phrase.setWordWrap(True)
        running_layout.addWidget(self.running_goal)
        running_layout.addWidget(self.running_phrase)
        running_layout.addWidget(self.remaining)
        running_layout.addWidget(self.stop)
        self.running_panel.hide()
        layout.addWidget(self.running_panel)
        layout.addWidget(self.completed)
        layout.addWidget(self.status)
        self.seconds = self.minutes.value() * 60
        self.focused_seconds = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.start.clicked.connect(self.start_timer)
        self.stop.clicked.connect(self.stop_timer)

    def start_timer(self) -> None:
        self.seconds = self.minutes.value() * 60
        self.timer.start(1000)
        self.running_goal.setText(f"专注目标　{self.goal.text()}")
        self.running_phrase.setText(f"提醒　{self.phrase.text()}")
        self.settings_panel.hide(); self.running_panel.show()
        self.status.setText("专注进行中。若切换到其他窗口，系统会请你再次确认。")
        self.main_window.start_focus_guard()
        self.tick()

    def stop_timer(self) -> None:
        if self.timer.isActive():
            self.focused_seconds += self.minutes.value() * 60 - self.seconds
        self.timer.stop()
        self.main_window.stop_focus_guard()
        self.completed.setText(f"已专注：{self.focused_seconds // 60:02d}:{self.focused_seconds % 60:02d}")
        self.status.setText("本次专注已停止。切换窗口确认也已关闭。")
        self.settings_panel.show(); self.running_panel.hide(); self.start.setText("再次开始专注模式")

    def tick(self) -> None:
        self.remaining.setText(f"{self.seconds // 60:02d}:{self.seconds % 60:02d}")
        if self.seconds <= 0:
            self.timer.stop()
            self.main_window.stop_focus_guard()
            self.focused_seconds += self.minutes.value() * 60
            self.completed.setText(f"已专注：{self.focused_seconds // 60:02d}:{self.focused_seconds % 60:02d}")
            self.settings_panel.show(); self.running_panel.hide(); self.start.setText("再次开始专注模式")
            QMessageBox.information(self, "本轮完成", "做得好，本轮专注完成，可以稍作休息。")
            return
        self.seconds -= 1


class TimelinePage(QWidget):
    def __init__(self, service: LearningService, open_review) -> None:
        super().__init__()
        self.service = service
        self.open_review = open_review
        self.editing_id: int | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        left_card = QFrame(); left_card.setObjectName("card")
        left = QVBoxLayout(left_card)
        right_card = QFrame(); right_card.setObjectName("card")
        right = QVBoxLayout(right_card)
        left.addWidget(self.title_label("日程与打卡", "记录今天的每一段专注时光"))
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.selectionChanged.connect(self.refresh)
        left.addWidget(self.calendar)
        left.addWidget(QLabel("快捷打卡"))
        self.tag_box = QHBoxLayout()
        left.addLayout(self.tag_box)
        self.tag_input = QLineEdit(); self.tag_input.setPlaceholderText("添加常用活动，例如：阅读")
        add_tag = button("添加")
        add_tag.clicked.connect(self.add_tag)
        tag_row = QHBoxLayout(); tag_row.addWidget(self.tag_input); tag_row.addWidget(add_tag)
        left.addLayout(tag_row)
        self.event_title = QLineEdit(); self.event_title.setPlaceholderText("例如：算法训练")
        self.event_time = QDateTimeEdit(); configure_datetime(self.event_time)
        self.event_note = QTextEdit(); self.event_note.setFixedHeight(70); self.event_note.setPlaceholderText("记录一点过程或感受（可选）")
        self.review_link = QComboBox()
        self.save = button("保存日程", True); self.save.clicked.connect(self.save_schedule)
        self.cancel = button("取消编辑"); self.cancel.clicked.connect(self.clear_editor); self.cancel.hide()
        form = QFormLayout()
        form.addRow("日程名称", self.event_title)
        form.addRow("日期与时间", self.event_time)
        form.addRow("关联复盘", self.review_link)
        form.addRow("备注", self.event_note)
        actions = QHBoxLayout(); actions.addWidget(self.save); actions.addWidget(self.cancel)
        form.addRow(actions)
        left.addLayout(form)
        right.addWidget(self.title_label("当日时间轴", "单击编辑；双击已关联项目可查看复盘"))
        self.events = QListWidget()
        self.events.itemClicked.connect(self.load_event)
        self.events.itemDoubleClicked.connect(self.open_event_review)
        right.addWidget(self.events)
        layout.addWidget(left_card, 2); layout.addWidget(right_card, 3)
        self.refresh_tags(); self.refresh_review_links(); self.refresh()

    @staticmethod
    def title_label(title: str, subtitle: str) -> QLabel:
        label = QLabel(f"<b>{title}</b><br><span style='color:#7b8e8b'>{subtitle}</span>")
        label.setObjectName("sectionTitle")
        return label

    def selected_day(self) -> str:
        return self.calendar.selectedDate().toString("yyyy-MM-dd")

    def refresh_tags(self) -> None:
        while self.tag_box.count():
            item = self.tag_box.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for row in self.service.tags():
            quick = button(row["name"])
            quick.clicked.connect(lambda _, name=row["name"]: self.quick_log(name))
            self.tag_box.addWidget(quick)
        self.tag_box.addStretch()

    def add_tag(self) -> None:
        if self.tag_input.text().strip():
            self.service.add_tag(self.tag_input.text())
            self.tag_input.clear(); self.refresh_tags()

    def quick_log(self, name: str) -> None:
        self.service.add_schedule(name, datetime.now())
        self.calendar.setSelectedDate(QDate.currentDate())
        self.refresh()

    def refresh_review_links(self) -> None:
        selected = self.review_link.currentData()
        self.review_link.clear(); self.review_link.addItem("不关联复盘", None)
        for row in self.service.reviews():
            self.review_link.addItem(f"{row['review_date']} · {row['title']}", row["id"])
        index = self.review_link.findData(selected)
        self.review_link.setCurrentIndex(max(index, 0))

    def save_schedule(self) -> None:
        title = self.event_title.text().strip()
        if not title:
            QMessageBox.warning(self, "请补充日程", "请先填写日程名称。")
            return
        values = (title, self.event_time.dateTime().toPython(), self.event_note.toPlainText(), self.review_link.currentData())
        if self.editing_id is None:
            self.service.add_schedule(*values)
        else:
            self.service.update_schedule(self.editing_id, *values)
        self.calendar.setSelectedDate(self.event_time.date())
        self.clear_editor(); self.refresh()

    def clear_editor(self) -> None:
        self.editing_id = None
        self.event_title.clear(); self.event_note.clear(); configure_datetime(self.event_time)
        self.refresh_review_links(); self.save.setText("保存日程"); self.cancel.hide()
        self.events.clearSelection()

    def refresh(self) -> None:
        self.events.clear()
        for row in self.service.schedules(self.selected_day()):
            linked = f"  ·  复盘：{row['review_title']}" if row["review_title"] else ""
            notes = f"\n{row['notes']}" if row["notes"] else ""
            item = QListWidgetItem(f"{row['happened_at'][11:16]}   {row['title']}{linked}{notes}")
            item.setData(Qt.ItemDataRole.UserRole, dict(row))
            self.events.addItem(item)

    def load_event(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole)
        self.editing_id = row["id"]
        self.event_title.setText(row["title"])
        self.event_time.setDateTime(QDateTime.fromString(row["happened_at"], Qt.DateFormat.ISODate))
        self.event_note.setPlainText(row["notes"])
        self.refresh_review_links()
        self.review_link.setCurrentIndex(max(self.review_link.findData(row["review_id"]), 0))
        self.save.setText("更新选中日程"); self.cancel.show()

    def open_event_review(self, item: QListWidgetItem) -> None:
        review_id = item.data(Qt.ItemDataRole.UserRole)["review_id"]
        if review_id:
            self.open_review(review_id)


class ReviewPage(QWidget):
    def __init__(self, service: LearningService) -> None:
        super().__init__()
        self.service = service
        self.fields: dict[str, QTextEdit] = {}
        self.editing_id: int | None = None
        layout = QHBoxLayout(self); layout.setContentsMargins(26, 24, 26, 24)
        edit_card = QFrame(); edit_card.setObjectName("card"); editor = QVBoxLayout(edit_card)
        list_card = QFrame(); list_card.setObjectName("card"); listing = QVBoxLayout(list_card)
        editor.addWidget(TimelinePage.title_label("复盘卡片", "写下思考，让每一次练习都留下收获"))
        self.category = QComboBox(); self.category.currentIndexChanged.connect(self.rebuild_fields)
        self.title = QLineEdit(); self.title.setPlaceholderText("本次复盘标题")
        self.date = QDateTimeEdit(); configure_datetime(self.date)
        self.tags = QLineEdit(); self.tags.setPlaceholderText("例如：数组，贪心")
        self.field_layout = QFormLayout()
        add_field = button("+ 临时增加记录项目")
        add_field.clicked.connect(self.add_temporary_field)
        category_button = button("管理复盘板块")
        category_button.clicked.connect(self.add_category)
        self.save = button("保存复盘卡片", True); self.save.clicked.connect(self.save_review)
        self.cancel = button("取消编辑"); self.cancel.clicked.connect(self.clear_editor); self.cancel.hide()
        form = QFormLayout(); form.addRow("复盘类型", self.category); form.addRow("标题", self.title); form.addRow("日期与时间", self.date); form.addRow("标签", self.tags)
        editor.addLayout(form); editor.addWidget(category_button); editor.addLayout(self.field_layout); editor.addWidget(add_field)
        row = QHBoxLayout(); row.addWidget(self.save); row.addWidget(self.cancel); editor.addLayout(row); editor.addStretch()
        listing.addWidget(TimelinePage.title_label("已记录复盘", "单击载入并编辑，右下角查看清晰详情"))
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索标题、标签或内容")
        self.search.textChanged.connect(self.refresh_list)
        self.cards = QListWidget(); self.cards.itemClicked.connect(self.load_review)
        self.detail = QTextBrowser(); self.detail.setOpenExternalLinks(True)
        listing.addWidget(self.search); listing.addWidget(self.cards, 2); listing.addWidget(self.detail, 2)
        layout.addWidget(edit_card, 2); layout.addWidget(list_card, 3)
        self.load_categories(); self.refresh_list()

    def load_categories(self) -> None:
        current = self.category.currentData()
        current_id = current["id"] if current else None
        self.category.clear()
        for row in self.service.categories(): self.category.addItem(row["name"], dict(row))
        self.category.setCurrentIndex(max(self.category.findData(current_id), 0))
        self.rebuild_fields()

    def clear_fields(self) -> None:
        while self.field_layout.rowCount(): self.field_layout.removeRow(0)
        self.fields = {}

    def rebuild_fields(self) -> None:
        self.clear_fields()
        category = self.category.currentData()
        if not category: return
        for name in json.loads(category["fields_json"]): self.add_field(name)

    def add_field(self, name: str, value: str = "") -> None:
        field = QTextEdit(); field.setFixedHeight(58); field.setPlainText(value)
        self.fields[name] = field; self.field_layout.addRow(f"{name}：", field)

    def add_temporary_field(self) -> None:
        dialog = QDialog(self); dialog.setWindowTitle("增加记录项目")
        form = QFormLayout(dialog); name = QLineEdit(); name.setPlaceholderText("例如：第二次补充复盘")
        confirm = button("添加", True); form.addRow("项目名称", name); form.addRow(confirm)
        confirm.clicked.connect(lambda: (self.add_field(name.text().strip()), dialog.accept()) if name.text().strip() and name.text().strip() not in self.fields else None)
        dialog.exec()

    def save_review(self) -> None:
        if not self.title.text().strip():
            QMessageBox.warning(self, "请补充标题", "请先填写本次复盘的标题。")
            return
        category = self.category.currentData()
        content = {name: field.toPlainText() for name, field in self.fields.items()}
        values = (category["id"], self.title.text(), self.date.date().toString("yyyy-MM-dd"), self.tags.text(), content)
        if self.editing_id is None: self.service.add_review(*values)
        else: self.service.update_review(self.editing_id, *values)
        self.clear_editor(); self.refresh_list()

    def clear_editor(self) -> None:
        self.editing_id = None; self.title.clear(); self.tags.clear(); configure_datetime(self.date); self.rebuild_fields()
        self.save.setText("保存复盘卡片"); self.cancel.hide(); self.cards.clearSelection()

    def refresh_list(self) -> None:
        self.cards.clear()
        for row in self.service.reviews(term=self.search.text().strip()):
            item = QListWidgetItem(f"{row['review_date']} · {row['category_name']}\n{row['title']}    #{row['tags']}")
            item.setData(Qt.ItemDataRole.UserRole, dict(row)); self.cards.addItem(item)

    def load_review(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole); self.editing_id = row["id"]
        self.category.setCurrentIndex(max(self.category.findData(row["category_id"]), 0)); self.rebuild_fields()
        self.title.setText(row["title"]); self.date.setDateTime(QDateTime.fromString(row["review_date"] + "T00:00", Qt.DateFormat.ISODate)); self.tags.setText(row["tags"])
        content = json.loads(row["content_json"])
        for name, value in content.items():
            if name not in self.fields: self.add_field(name, value)
            else: self.fields[name].setPlainText(value)
        self.save.setText("更新选中复盘"); self.cancel.show(); self.show_detail(row)

    def show_detail(self, row: dict) -> None:
        content = json.loads(row["content_json"])
        items = "".join(f"<section><h4>{html.escape(name)}</h4><p>{html.escape(value).replace(chr(10), '<br>') or '（未填写）'}</p></section>" for name, value in content.items())
        self.detail.setHtml(f"<h2>{html.escape(row['title'])}</h2><div class='meta'>复盘日期：{row['review_date']}　　标签：{html.escape(row['tags']) or '无'}</div>{items}")

    def open_review(self, review_id: int) -> None:
        self.search.clear(); self.refresh_list()
        for index in range(self.cards.count()):
            item = self.cards.item(index)
            if item.data(Qt.ItemDataRole.UserRole)["id"] == review_id:
                self.cards.setCurrentItem(item); self.load_review(item); break

    def add_category(self) -> None:
        dialog = QDialog(self); dialog.setWindowTitle("新增自定义复盘板块")
        form = QFormLayout(dialog); name = QLineEdit(); fields = QTextEdit(); fields.setPlaceholderText("每行一个项目，例如：新的发现")
        save = button("添加板块", True); form.addRow("板块名称", name); form.addRow("默认项目", fields); form.addRow(save)
        def create() -> None:
            values = [value.strip() for value in fields.toPlainText().splitlines() if value.strip()]
            if name.text().strip() and values:
                self.service.add_category(name.text(), values); dialog.accept(); self.load_categories()
        save.clicked.connect(create); dialog.exec()


class BilibiliPage(QWidget):
    """启动 Electron 控制的 Chromium 学习窗口，并显示回写的学习审计。"""
    def __init__(self, service: LearningService) -> None:
        super().__init__(); self.service = service
        layout = QVBoxLayout(self); layout.setContentsMargins(26, 24, 26, 24)
        card = QFrame(); card.setObjectName("card"); content = QVBoxLayout(card)
        content.addWidget(TimelinePage.title_label("B站学习", "在受控学习窗口中搜索和播放，不调用默认浏览器"))
        notice = QLabel("✓ 点击后会打开应用专属的 Chromium 学习窗口。搜索、视频标题、链接和观看时长会自动回写到这里。")
        notice.setObjectName("notice"); notice.setWordWrap(True); content.addWidget(notice)
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索学习内容，例如：abc444 题解")
        search_button = button("打开纯净学习窗口", True); search_button.clicked.connect(self.open_search)
        search_row = QHBoxLayout(); search_row.addWidget(self.search); search_row.addWidget(search_button); content.addLayout(search_row)
        self.url = QLineEdit(); self.url.setPlaceholderText("或者粘贴 B 站视频链接，直接在学习窗口播放")
        video_button = button("直接播放视频", True); video_button.clicked.connect(self.open_video)
        video_row = QHBoxLayout(); video_row.addWidget(self.url); video_row.addWidget(video_button); content.addLayout(video_row)
        self.status = QLabel("学习窗口关闭后会自动结算本次观看时长。")
        self.status.setObjectName("muted"); content.addWidget(self.status)
        self.report = QListWidget(); content.addWidget(QLabel("今日学习与浏览记录")); content.addWidget(self.report, 1)
        layout.addWidget(card)
        self.sync_timer = QTimer(self); self.sync_timer.timeout.connect(self.sync_events); self.sync_timer.start(1500)
        self.refresh_report()

    def open_window(self, target: str) -> None:
        if not target.strip():
            QMessageBox.warning(self, "缺少内容", "请输入搜索词或视频链接。")
            return
        if self.service.launch_bili_learning_window(target.strip()):
            self.status.setText("学习窗口已打开。完成后关闭学习窗口，时长会自动回写。")
        else:
            QMessageBox.critical(self, "学习窗口不可用", "Electron 运行时尚未准备好，请重新安装应用依赖。")

    def open_search(self) -> None: self.open_window(self.search.text())
    def open_video(self) -> None: self.open_window(self.url.text())

    def sync_events(self) -> None:
        if self.service.import_bili_events(): self.refresh_report()

    def refresh_report(self) -> None:
        self.report.clear(); total = 0
        for row in self.service.video_logs_today():
            total += row["duration_seconds"]
            description = row["keyword"] or row["video_title"] or row["video_url"]
            self.report.addItem(f"{row['started_at'][11:16]}  ·  {row['action']}  ·  {description}  ·  {row['duration_seconds'] // 60} 分钟")
        self.report.insertItem(0, f"今日累计已记录学习时长：{total // 60} 分钟")


class FocusConfirmation(QDialog):
    """用醒目的确认框增加切换到非学习窗口的思考成本。"""
    MESSAGES = [
        ("小侦探，先停一下！", "你正处于专注学习中。这个窗口真的能帮助完成当前目标吗？"),
        ("注意力小火车到站检查", "别让“我就看一眼”变成半小时。这个操作和学习有关吗？"),
        ("专注结界提醒", "现在离开学习界面，是否是为了完成正在做的学习任务？"),
        ("分心怪兽正在敲门", "请认真确认：打开这个窗口，是学习需要，还是分心诱惑？"),
    ]

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint)
        title, message = random.choice(self.MESSAGES)
        self.setWindowTitle("专注确认")
        self.setFixedSize(540, 310)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        layout = QVBoxLayout(self); layout.setContentsMargins(34, 30, 34, 28); layout.setSpacing(16)
        icon = QLabel("⚠")
        icon.setObjectName("warningIcon"); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QLabel(title); heading.setObjectName("warningTitle"); heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(message + "\n\n选择“是，我确认”后继续；否则将回到专注小窗。")
        body.setObjectName("warningBody"); body.setAlignment(Qt.AlignmentFlag.AlignCenter); body.setWordWrap(True)
        yes = button("是，我确认与学习有关", True); no = button("否，回到专注小窗")
        yes.clicked.connect(self.accept); no.clicked.connect(self.reject)
        actions = QHBoxLayout(); actions.addWidget(no); actions.addWidget(yes)
        layout.addWidget(icon); layout.addWidget(heading); layout.addWidget(body); layout.addLayout(actions)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__(); self.setWindowTitle("学习记录与专注监督"); self.resize(1240, 790)
        self.db = Database(); self.service = LearningService(self.db); self.focus_guard = False; self.guard_dialog_open = False
        root = QWidget(); layout = QHBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(216); side_layout = QVBoxLayout(side); side_layout.setContentsMargins(16, 26, 16, 20)
        brand = QLabel("学习小助手"); brand.setObjectName("brandTitle")
        subtitle = QLabel("记录 · 复盘 · 专注"); subtitle.setObjectName("brandSubtitle")
        side_layout.addWidget(brand); side_layout.addWidget(subtitle)
        side_layout.addSpacing(22)
        self.stack = QStackedWidget(); self.review = ReviewPage(self.service); self.timeline = TimelinePage(self.service, self.go_to_review); self.video = BilibiliPage(self.service)
        self.stack.addWidget(self.timeline); self.stack.addWidget(self.review); self.stack.addWidget(self.video)
        for index, text in enumerate(["日程与打卡", "复盘卡片", "B站学习"]):
            nav = button(text); nav.setObjectName("nav"); nav.clicked.connect(lambda _, page=index: self.show_page(page)); side_layout.addWidget(nav)
        side_layout.addStretch(); self.floating = FloatingWidget(self)
        floating = button("进入专注小窗", True); floating.clicked.connect(self.open_floating); side_layout.addWidget(floating)
        layout.addWidget(side); layout.addWidget(self.stack, 1); self.setCentralWidget(root)
        QApplication.instance().applicationStateChanged.connect(self.on_application_state_changed)

    def show_page(self, index: int) -> None:
        if index == 0: self.timeline.refresh_review_links(); self.timeline.refresh()
        if index == 1: self.review.refresh_list()
        if index == 2: self.video.refresh_report()
        self.stack.setCurrentIndex(index)

    def open_floating(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.floating.move(screen.right() - self.floating.width() - 24, screen.top() + 24)
        self.floating.show(); self.floating.raise_(); self.floating.activateWindow()
        self.minimize_other_windows()

    def go_to_review(self, review_id: int) -> None:
        self.stack.setCurrentWidget(self.review); self.review.open_review(review_id)

    def start_focus_guard(self) -> None:
        self.focus_guard = True
        self.minimize_other_windows()

    def stop_focus_guard(self) -> None:
        self.focus_guard = False

    def minimize_other_windows(self) -> None:
        """仅在 Windows 中最小化其它普通窗口，不关闭任何应用。"""
        if sys.platform != "win32": return
        own_handles = {int(self.winId()), int(self.floating.winId())}
        user32 = ctypes.windll.user32
        user32.ShowWindowAsync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def minimize(handle, _):
            handle_value = int(handle)
            if handle_value not in own_handles and user32.IsWindowVisible(handle) and not user32.IsIconic(handle):
                user32.ShowWindowAsync(handle, 6)
            return True
        user32.EnumWindows(callback_type(minimize), 0)
        QTimer.singleShot(250, lambda: self._minimize_remaining_windows(own_handles))

    @staticmethod
    def _minimize_remaining_windows(own_handles: set[int]) -> None:
        """处理首轮枚举时正在动画或延迟创建的任务栏窗口。"""
        if sys.platform != "win32": return
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def minimize(handle, _):
            if int(handle) not in own_handles and user32.IsWindowVisible(handle) and not user32.IsIconic(handle):
                user32.ShowWindowAsync(handle, 6)
            return True
        user32.EnumWindows(callback_type(minimize), 0)

    def on_application_state_changed(self, state: Qt.ApplicationState) -> None:
        if not self.focus_guard or self.guard_dialog_open or state != Qt.ApplicationState.ApplicationInactive:
            return
        QTimer.singleShot(300, self.ask_focus_reason)

    def ask_focus_reason(self) -> None:
        if not self.focus_guard or self.guard_dialog_open or QApplication.applicationState() != Qt.ApplicationState.ApplicationInactive:
            return
        self.guard_dialog_open = True
        answer = FocusConfirmation(self).exec()
        self.guard_dialog_open = False
        if answer != QDialog.DialogCode.Accepted:
            self.floating.show(); self.floating.raise_(); self.floating.activateWindow()

    def closeEvent(self, event) -> None:
        self.db.close(); event.accept()


STYLE = """
QWidget { background: #f3f5f2; color: #273633; font-family: 'Microsoft YaHei'; font-size: 14px; }
#sidebar { background: #1f3732; } #brandTitle { background: transparent; color: #eef4ef; font-size: 22px; font-weight: 700; padding: 8px 10px 0; }
#brandSubtitle { background: transparent; color: #aec8bd; font-size: 12px; padding: 0 10px; } #nav { color: #d7e8df; background: transparent; border: 0; text-align: left; padding: 12px; margin: 2px 0; }
#nav:hover { background: #36564e; color: white; } QFrame#card { background: #fdfefd; border: 1px solid #e0e8e3; border-radius: 16px; }
QPushButton { background: #f6faf7; border: 1px solid #cbdad3; border-radius: 8px; padding: 9px 12px; text-align: center; color: #29443c; }
QPushButton:hover { background: #e3eee8; } QPushButton[accent="true"] { background: #3d7564; color: white; border: 1px solid #3d7564; font-weight: 600; }
QPushButton[accent="true"]:hover { background: #2d5d4f; } QLineEdit, QTextEdit, QTextBrowser, QComboBox, QDateTimeEdit, QSpinBox, QListWidget { background: #fff; border: 1px solid #cfddd6; border-radius: 8px; padding: 7px; selection-background-color: #b9d8cb; }
QCalendarWidget QWidget { background: #fff; } QListWidget::item { padding: 10px; border-bottom: 1px solid #edf1ee; } QListWidget::item:selected { background: #e4f0ea; color: #213e35; }
#sectionTitle { font-size: 18px; padding: 4px 2px 16px; } #sectionTitle b { color: #264d42; } #timer { font-size: 40px; font-weight: 700; color: #2f6b5a; padding: 4px; }
#floatHeading { font-size: 19px; font-weight: 700; color: #244b40; } #notice { background: #e6f2eb; border-radius: 8px; padding: 10px; color: #315b4d; } #muted { color: #758782; } #videoTitle { padding: 8px 2px; font-weight: 600; color: #315f52; }
QTextBrowser h2 { color: #2e5b4e; font-size: 22px; } QTextBrowser h4 { color: #27584a; background: #e4f0ea; border-left: 4px solid #4d8a75; padding: 7px 9px; margin: 16px 0 5px; font-size: 16px; } QTextBrowser p { color: #42554f; margin: 0 8px; line-height: 1.7; font-size: 15px; } QTextBrowser .meta { color: #74847f; padding: 5px 0 10px; }
#completed { color: #52766b; font-weight: 600; text-align: center; } #warningIcon { color: #e06539; font-size: 50px; font-weight: bold; } #warningTitle { color: #b84328; font-size: 24px; font-weight: 700; } #warningBody { color: #5c362c; font-size: 16px; line-height: 1.6; }
"""

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyleSheet(STYLE); window = MainWindow(); window.show(); sys.exit(app.exec())
