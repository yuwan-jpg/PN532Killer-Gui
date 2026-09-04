import tempfile
import sys
import subprocess
import platform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel, QTextEdit, QPlainTextEdit,
                           QComboBox, QStatusBar, QMessageBox, QTabWidget, QGridLayout, QFileDialog,
                           QLineEdit, QSpinBox, QCheckBox, QGroupBox, QRadioButton, QButtonGroup,
                           QTreeWidget, QTreeWidgetItem, QSplitter, QScrollArea, QDialog, QMenu, QSizePolicy, QLayout, QFrame,
                           QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QIcon, QDesktopServices, QFont, QColor, QAction, QPixmap


# 给 QTextEdit 加 setMaximumBlockCount 兼容方法(QPlainTextEdit 才有此方法)
# 通过 monkey-patch 避免全部迁移到 QPlainTextEdit
if not hasattr(QTextEdit, 'setMaximumBlockCount'):
    def _qtextedit_set_max_block_count(self, n):
        pass  # no-op,日志以 setHtml() 替代清空
    QTextEdit.setMaximumBlockCount = _qtextedit_set_max_block_count
from pn532_communication import SerialCommunication
from pn532_cmd import Pn532CMD
from pn532_com import Pn532Com
from pn532_enum import Status, PN532KillerMode, PN532KillerTagType, PN532KillerSnifferMode
from mfd_parser import MFDParser
import serial.tools.list_ports
import time
import shutil
import os

# 导入新的模块
from path_manager import PathManager
from thread_workers import FormatCardThread, OneClickWriteThread, SerialWriteHelper, EmulatorThread, DumpReadThread, WriteCardThread
from card_operations import DumpReader, SingleBlockOperator, CardFormatter, UidOperator, CardDetector, NtagHelper, Iso15693Operator, Em4100Operator, EmulatorOperator
from ui_components import ConfigDialog
from data_manager import DataManager
from i18n import i18n

# 导入优化模块
from config import Config, VERSION
from logger import app_logger, ui_logger, perf_logger
from performance_monitor import performance_monitor
from resource_manager import resource_manager
from error_handler import ErrorHandler, set_global_error_handler, error_handler, ErrorCategory, ErrorSeverity


def _font(name, size, weight=None, style=None):
    """跨平台字体，自动回退。Linux 上 'Microsoft YaHei' 不可用。"""
    if name == 'Microsoft YaHei' and platform.system() != 'Windows':
        name = 'sans-serif'
    elif name == 'Consolas' and platform.system() != 'Windows':
        name = 'monospace'
    f = QFont(name, size)
    if weight is not None:
        f.setWeight(weight)
    if style is not None:
        f.setStyle(style)
    return f




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化配置系统
        self.config = Config()
        
        # 初始化错误处理器
        self.error_handler = ErrorHandler(self)
        set_global_error_handler(self.error_handler)
        
        # 启动性能监控
        performance_monitor.start_monitoring(interval=10.0)
        
        # 记录应用启动
        app_logger.info("PN532 GUI应用程序启动")
        
        self.pn532_com = None
        self.current_thread = None
        self.current_command_id = None
        self.write_card_thread = None
        
        # 初始化模块实例
        self.path_manager = PathManager()
        self.data_manager = DataManager()
        
        self._current_mfd_path = None

        # 注册资源到资源管理器
        resource_manager.register_resource(self)
        
        self.initUI()
    # 处理打包后的资源路径
    def resource_path(self, relative_path):
        """获取打包后资源文件的绝对路径"""
        try:
            # PyInstaller 创建临时文件夹，并将路径存储在 _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            # 未打包时使用当前目录
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    
    def initUI(self):
        # 从配置加载窗口设置
        window_config = self.config.get('window', {})
        
        self.setWindowTitle(f'PN532Killer Gui {VERSION}')
        
        icon_path = self.resource_path('ico.png')
        self.setWindowIcon(QIcon(icon_path))
        
        # 设置窗口大小
        min_width = window_config.get('min_width', 1200)
        min_height = window_config.get('min_height', 700)
        self.setMinimumSize(min_width, min_height)
        
        ui_logger.info("初始化用户界面")
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        top_widget = QWidget()
        top_widget.setStyleSheet("background-color: #f8f9fa; border-radius: 6px;")
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(8, 2, 8, 2)
        top_layout.setSpacing(5)
        top_layout.addStretch()
        lang_label = QLabel("语言:")
        lang_label.setStyleSheet("font-size: 12px; color: #495057;")
        top_layout.addWidget(lang_label)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文", "English"])
        lang_to_index = {"zh": 0, "en": 1}
        self.language_combo.setCurrentIndex(lang_to_index.get(i18n.get_current_language(), 0))
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        self.language_combo.setFixedWidth(100)
        self.language_combo.setStyleSheet("""
            QComboBox { font-size: 12px; padding: 3px 8px; background: #fff; border: 1px solid #e0e0e0; border-radius: 4px; color: #495057; }
            QComboBox:hover { border-color: #007bff; }
            QComboBox QAbstractItemView { color: #333; background: #fff; selection-background-color: #007bff; selection-color: #fff; }
        """)
        top_layout.addWidget(self.language_combo)
        main_layout.addWidget(top_widget)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 4px;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 24px;
                margin-right: 4px;
                font-size: 14px;
                color: #495057;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #007bff;
                border-bottom: 2px solid #007bff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e9ecef;
            }
        """)
        
        # 添加标签页控件到主布局
        main_layout.addWidget(self.tab_widget, 1)
        
        # 创建中心控件并设置布局
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self.work_mode_tab = QWidget()
        self.init_work_mode_tab()
        self.tab_widget.addTab(self.work_mode_tab, i18n.get_text('tab_function'))
        self.card_tools_tab = QWidget()
        self.init_card_tools_tab()
        self.tab_widget.addTab(self.card_tools_tab, i18n.get_text('tab_card_tools'))
        self.read_card_tab = QWidget()
        self.init_read_card_tab()
        self.tab_widget.addTab(self.read_card_tab, i18n.get_text('tab_sector_tools'))

        # 重新挂载 NTAG 标签页(之前 init_ntag_tab 没被调用)
        self.ntag_tab = QWidget()
        self.init_ntag_tab()
        self.tab_widget.addTab(self.ntag_tab, i18n.get_text('tab_ntag'))

        # 重新挂载 ISO15693/EM4100 高级功能页
        self.advanced_tab = QWidget()
        self.init_advanced_tab()
        self.tab_widget.addTab(self.advanced_tab, i18n.get_text('tab_advanced'))

        self.about_tab = QWidget()
        self.init_about_tab()
        self.tab_widget.addTab(self.about_tab, i18n.get_text('tab_about'))
        self.setStatusBar(QStatusBar(self))
        self.setAcceptDrops(True)  # 拖放 MFD 文件支持
        self._setup_shortcuts()  # 注册快捷键
        self.on_mode_changed(self.reader_mode_btn)

    def _setup_shortcuts(self):
        """注册常用快捷键。

        Ctrl+O: 打开 MFD
        Ctrl+S: 保存当前 MFD
        Ctrl+R: 读取全卡
        Ctrl+W: 写卡
        Ctrl+E: 修 UID
        Ctrl+T: 卡类型检测
        F5: 切换工作模式
        F1: 关于页
        """
        from PyQt6.QtGui import QShortcut, QKeySequence as _KS
        shortcuts = [
            ('Ctrl+O', self.import_sector_data),
            ('Ctrl+S', self.save_sector_data),
            ('Ctrl+R', self.on_dump_read),
            ('Ctrl+T', self.on_detect_card),
            ('F5', lambda: self.on_mode_changed(self.reader_mode_btn)),
            ('F1', lambda: self.tab_widget.setCurrentIndex(5)),  # 关于
        ]
        for seq, slot in shortcuts:
            sc = QShortcut(_KS(seq), self)
            sc.activated.connect(slot)
    def init_about_tab(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        main_container = QWidget()
        main_container.setStyleSheet("background-color: #f5f7fa;")
        main_layout = QVBoxLayout(main_container)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #ffffff; border-radius: 16px;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(50, 50, 50, 50)

        icon_label = QLabel()
        icon_label.setFixedSize(100, 100)
        # 使用软件图标作为关于页面的图标
        ico_path = self.resource_path('pn532.ico')
        pixmap = QPixmap(ico_path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel("PN532Killer Gui")
        title_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #1a1a2e; margin: 0;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title_label)

        self.version_label = QLabel(i18n.get_text('about_version'))
        self.version_label.setStyleSheet("font-size: 16px; color: #6c757d; margin: 8px 0 20px 0;")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.version_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #e9ecef; margin: 10px 0; max-height: 1px;")
        content_layout.addWidget(line)

        content_layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        self.project_button = QPushButton(i18n.get_text('project_link'))
        self.project_button.setFixedHeight(44)
        self.project_button.setMinimumWidth(160)
        self.project_button.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: 500;
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004494;
            }
        """)
        self.project_button.clicked.connect(self.open_project_link)
        button_layout.addWidget(self.project_button)

        self.feedback_button = QPushButton(i18n.get_text('feedback_link'))
        self.feedback_button.setFixedHeight(44)
        self.feedback_button.setMinimumWidth(160)
        self.feedback_button.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: 500;
                padding: 10px 20px;
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        self.feedback_button.clicked.connect(self.open_feedback_link)
        button_layout.addWidget(self.feedback_button)

        button_container = QWidget()
        button_container.setLayout(button_layout)
        content_layout.addWidget(button_container, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(content_widget)
        scroll_area.setWidget(main_container)

        layout = QVBoxLayout()
        layout.addWidget(scroll_area)
        self.about_tab.setLayout(layout)
    def open_project_link(self):
        url = QUrl("https://github.com/yuwan-jpg/PN532Killer-Gui")
        QDesktopServices.openUrl(url)
    def open_feedback_link(self):
        url = QUrl("https://github.com/yuwan-jpg/PN532Killer-Gui/issues")
        QDesktopServices.openUrl(url)
    def init_read_card_tab(self):
        layout = QVBoxLayout(self.read_card_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        _group_style = """
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #1a1a2e;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                color: #1a1a2e;
            }
        """

        self.sector_card = QGroupBox(i18n.get_text('sector_data'))
        self.sector_card.setStyleSheet(_group_style)

        sector_layout = QVBoxLayout(self.sector_card)
        sector_layout.setContentsMargins(12, 20, 12, 12)
        sector_layout.setSpacing(8)

        self.card_info_label = QLabel(i18n.get_text('no_card_data_loaded'))
        self.card_info_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #555; padding: 2px 4px; background: transparent;")
        sector_layout.addWidget(self.card_info_label)

        self.sector_display_widget = self.create_sector_display_widget()
        sector_layout.addWidget(self.sector_display_widget)

        splitter.addWidget(self.sector_card)

        self.log_card = QGroupBox(i18n.get_text('operation_log'))
        self.log_card.setStyleSheet(_group_style)

        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(12, 20, 12, 12)
        log_layout.setSpacing(6)

        self.read_card_log = QTextEdit()
        self.read_card_log.setReadOnly(True)
        self.read_card_log.setMinimumHeight(100)
        self.read_card_log.setMaximumBlockCount(500)
        self.read_card_log.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.read_card_log)

        self.log_card.setMinimumHeight(120)
        splitter.addWidget(self.log_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)
        self.mfd_parser = None
        
    def _mb(self, mbox_type, title_zh, msg_zh):
        """自动翻译的 QMessageBox 包装。title_zh / msg_zh 是中文文案,
        英文模式下会查 lang/en.json 反向表翻译,中文模式直接返回。
        """
        try:
            from PyQt6.QtWidgets import QMessageBox as _QMB
            title = i18n.tr(title_zh) if i18n.current_language != 'zh' else title_zh
            msg = i18n.tr(msg_zh) if i18n.current_language != 'zh' else msg_zh
            mb = _QMB(self)
            mb.setIcon(mbox_type)
            mb.setWindowTitle(title)
            mb.setText(msg)
            mb.setStandardButtons(_QMB.StandardButton.Ok)
            mb.exec()
        except Exception:
            pass

    def _mb_choice(self, mbox_type, title_zh, msg_zh, std_buttons):
        """Yes/No 等选择型对话框的自动翻译包装。返回值同 QMessageBox.StandardButton."""
        try:
            from PyQt6.QtWidgets import QMessageBox as _QMB
            title = i18n.tr(title_zh) if i18n.current_language != 'zh' else title_zh
            msg = i18n.tr(msg_zh) if i18n.current_language != 'zh' else msg_zh
            mb = _QMB(self)
            mb.setIcon(mbox_type)
            mb.setWindowTitle(title)
            mb.setText(msg)
            mb.setStandardButtons(std_buttons)
            return mb.exec()
        except Exception:
            return _QMB.StandardButton.Yes

    # ===== 拖放支持 =====
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(('.mfd', '.bin')) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        try:
            urls = event.mimeData().urls()
            for url in urls:
                fp = url.toLocalFile()
                if fp.lower().endswith(('.mfd', '.bin')):
                    if self.load_sector_data_from_mfd(fp):
                        self.log_message(f"已通过拖放加载: {fp}")
                        self.tab_widget.setCurrentIndex(2)  # 切换到扇区工具
                    return
        except Exception as e:
            self.log_message(f"拖放失败: {e}")

    def on_language_changed(self, index):
        """处理语言切换事件"""
        index_to_lang = {0: "zh", 1: "en"}
        language_code = index_to_lang.get(index, "zh")
        language_code = index_to_lang.get(index, "zh")
        i18n.switch_language(language_code)
        try:
            import json as _j
            try:
                _pf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lang', 'en.json')
                with open(_pf, 'r', encoding='utf-8') as _f:
                    _em = _j.load(_f)
                _em_rev = {v: k for k, v in _em.items()}
            except Exception:
                _em = {}; _em_rev = {}

            # --- 第1步：通用遍历 QLabel/QPushButton/QCheckBox/QRadioButton ---
            for _w in self.centralWidget().findChildren((QLabel, QPushButton, QCheckBox, QRadioButton)):
                try:
                    _t = _w.text()
                    if _t in _em:
                        _w.setText(_em[_t])
                    elif _t in _em_rev:
                        _w.setText(_em_rev[_t])
                except Exception:
                    pass

            # --- 第2步：GroupBox 标题（不属于 text()）---
            for name in ('log_card', 'sector_card', 'work_mode_log_card', 'mode_card', 'connection_card',
                         'iso_group', 'em_group', 'fmt_group'):
                w = getattr(self, name, None)
                if w is not None:
                    key = {'log_card': 'operation_log', 'sector_card': 'sector_data',
                           'work_mode_log_card': 'operation_log', 'mode_card': 'work_mode',
                           'connection_card': 'device_connection',
                           'iso_group': 'iso_group', 'em_group': 'em_group',
                           'fmt_group': 'format_card'}[name]
                    w.setTitle(i18n.get_text(key))

            # --- 第3步：标签页标题 ---
            self.tab_widget.setTabText(0, i18n.get_text('tab_function'))
            self.tab_widget.setTabText(1, i18n.get_text('tab_card_tools'))
            self.tab_widget.setTabText(2, i18n.get_text('tab_sector_tools'))
            self.tab_widget.setTabText(3, i18n.get_text('tab_ntag'))
            self.tab_widget.setTabText(4, i18n.get_text('tab_advanced'))
            self.tab_widget.setTabText(5, i18n.get_text('tab_about'))

            # --- 第4步：卡工具子标签页 ---
            try:
                _ct = self.card_tools_tab.findChildren(QTabWidget)[0]
                for _i, _k in enumerate(['tab_read_full','tab_modify_uid','tab_manual_block','tab_card_detect','tab_write_card']):
                    _ct.setTabText(_i, i18n.get_text(_k))
            except Exception:
                pass

            # --- 第5步：树控件表头 ---
            if hasattr(self, 'sector_tree'):
                self.sector_tree.setHeaderLabels([
                    i18n.get_text('sector_block'), i18n.get_text('data'), i18n.get_text('description')
                ])

            # --- 第6步：ComboBox 下拉框内容（items 不属于 text()）---
            if hasattr(self, 'type_combo'):
                _idx = self.type_combo.currentIndex()
                self.type_combo.clear()
                self.type_combo.addItems([
                    i18n.get_text('card_type_mifare1_4b1k'), i18n.get_text('card_type_ntag'),
                    i18n.get_text('card_type_15693'), i18n.get_text('card_type_em4100'),
                    i18n.get_text('card_type_t5557')
                ])
                self.type_combo.setCurrentIndex(min(_idx, self.type_combo.count() - 1))

            if hasattr(self, 'sniffer_mode_combo'):
                _idx = self.sniffer_mode_combo.currentIndex()
                self.sniffer_mode_combo.clear()
                self.sniffer_mode_combo.addItems([
                    i18n.get_text('sniffer_mode_without_tag'), i18n.get_text('sniffer_mode_with_tag')
                ])
                self.sniffer_mode_combo.setCurrentIndex(min(_idx, 1))

            if hasattr(self, 'emu_type_combo'):
                _i = self.emu_type_combo.currentIndex()
                self.emu_type_combo.clear()
                self.emu_type_combo.addItems([
                    i18n.get_text('emu_card_mifare'), i18n.get_text('emu_card_ntag'),
                    i18n.get_text('emu_card_15693')
                ])
                self.emu_type_combo.setCurrentIndex(min(_i, 2))

            if hasattr(self, 'emu_slot'):
                _i2 = self.emu_slot.currentIndex()
                self.emu_slot.clear()
                self.emu_slot.addItems([i18n.get_text('emu_slot_n').format(i) for i in range(8)])
                self.emu_slot.setCurrentIndex(min(_i2, 7))

            # --- 第7步：模拟器槽位按钮 ---
            if hasattr(self, 'slot_buttons'):
                for i, btn in enumerate(self.slot_buttons):
                    try:
                        btn.setText(i18n.get_text(f'slot_{i}'))
                    except Exception:
                        pass

            # --- 第8步：连接状态（特殊判断）---
            if hasattr(self, 'connect_btn'):
                _txt = self.connect_btn.text()
                if _txt in (_em.get('断开连接', '断开连接'), _em.get('Disconnect', 'Disconnect'),
                            i18n.get_text('disconnect')):
                    self.connect_btn.setText(i18n.get_text('disconnect'))
                    if hasattr(self, 'device_info_label'):
                        self.device_info_label.setText(i18n.get_text('connected'))
                else:
                    self.connect_btn.setText(i18n.get_text('connect_device'))
                    if hasattr(self, 'device_info_label'):
                        self.device_info_label.setText(i18n.get_text('not_connected'))

            # --- 第9步：关于页面 ---
            if hasattr(self, 'version_label'):
                self.version_label.setText(i18n.get_text('about_version'))
            if hasattr(self, 'project_button'):
                self.project_button.setText(i18n.get_text('project_link'))
            if hasattr(self, 'feedback_button'):
                self.feedback_button.setText(i18n.get_text('feedback_link'))

            # --- 第10步：placeholder 和 tooltip ---
            for _obj, _key in [
                (self.dump_path, 'dump_placeholder'), (self.uid_new_input, 'uid_placeholder'),
                (self.mb_data, 'data_placeholder'), (self.write_mfd_path, 'mfd_placeholder'),
                (self.emu_mfd, 'emu_mfd_placeholder'), (self.emu_uid, 'uid_8hex')
            ]:
                try:
                    _obj.setPlaceholderText(i18n.get_text(_key))
                except Exception:
                    pass
            for _obj, _key in [
                (self.dump_keyfile_btn, 'key_format_hint'),
                (self.write_read_keys_check, 'read_keys_before_write_tip'),
                (self.fmt_keyfile_btn, 'key_format_hint'),
            ]:
                try:
                    _obj.setToolTip(i18n.get_text(_key))
                except Exception:
                    pass
            try:
                self.write_progressbar.setFormat(i18n.get_text('write_progress_format'))
            except Exception:
                pass

        except RuntimeError:
            app_logger.warning("语言切换时部分Qt对象已被删除，跳过刷新")
        except Exception as e:
            app_logger.error(f"语言切换时发生错误: {e}")
    
    # 外部工具功能已移除，改用纯串口协议
    def reconnect_device(self, port):
        try:
            if self.pn532_com is not None:
                self.log_message(i18n.get_text('already_connected'))
                return
            self.log_message_connection(i18n.get_text('reconnecting').format(port=port))
            self.pn532_com = Pn532Com()
            self.pn532_com.open(port)
            if not self.pn532_com.isOpen():
                raise Exception(i18n.get_text('cannot_reopen').format(port=port))
            self.cmd = Pn532CMD(self.pn532_com)
            version = self.cmd.get_firmware_version()
            if not version:
                raise Exception(i18n.get_text('no_fw_version'))
            self.log_message_connection(i18n.get_text('reconnect_ok').format(version=version))
            self.connect_btn.setText('断开连接')
            self.statusBar.showMessage(i18n.get_text('device_connected'))
            self.log_message(i18n.get_text('reconnect_done'))
        except Exception as e:
            self.log_message_connection(i18n.get_text('reconnect_fail') + str(e))
            QMessageBox.critical(self, '重连失败', f'尝试重新连接到 {port} 失败: {str(e)}')
            if self.pn532_com:
                self.pn532_com.close()
            self.pn532_com = None
            self.connect_btn.setText(i18n.get_text('connect_device'))
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: 500;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
                QPushButton:pressed {
                    background-color: #004494;
                }
            """)
            self.statusBar().showMessage('设备已断开')
            self.device_info_label.setText(i18n.get_text('not_connected'))
            self.device_info_label.setStyleSheet("font-size: 14px; color: #6c757d;")
    def init_work_mode_tab(self):
        main_layout = QVBoxLayout(self.work_mode_tab)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        self.connection_card = QGroupBox(i18n.get_text('device_connection'))
        self.connection_card.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)
        connection_layout = QHBoxLayout(self.connection_card)
        connection_layout.setSpacing(10)
        connection_layout.setContentsMargins(12, 4, 12, 4)

        self.connect_btn = QPushButton(i18n.get_text('connect_device'))
        self.connect_btn.setFixedHeight(36)
        self.connect_btn.setMinimumWidth(120)
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-weight: 500;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:pressed { background-color: #004494; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        connection_layout.addWidget(self.connect_btn)

        self.device_info_label = QLabel(i18n.get_text('not_connected'))
        self.device_info_label.setStyleSheet("font-size: 13px; color: #6c757d;")
        connection_layout.addWidget(self.device_info_label)
        connection_layout.addStretch()
        main_layout.addWidget(self.connection_card)

        self.mode_card = QGroupBox(i18n.get_text('work_mode'))
        self.mode_card.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)
        mode_layout = QVBoxLayout(self.mode_card)
        mode_layout.setSpacing(6)
        mode_layout.setContentsMargins(12, 6, 12, 10)

        # Row 0: Mode radio buttons
        self.mode_row = QWidget()
        mode_row_layout = QHBoxLayout(self.mode_row)
        mode_row_layout.setContentsMargins(0, 0, 0, 0)
        mode_row_layout.setSpacing(4)

        self.select_mode_label = QLabel(i18n.get_text('select_mode'))
        self.select_mode_label.setStyleSheet("font-size: 13px; color: #555;")
        mode_row_layout.addWidget(self.select_mode_label)

        self.mode_btn_group = QButtonGroup()
        self.reader_mode_btn = QRadioButton(i18n.get_text('reader_mode'))
        self.emulator_mode_btn = QRadioButton(i18n.get_text('emulator_mode'))
        self.sniffer_mode_btn = QRadioButton(i18n.get_text('sniffer_mode'))
        for btn in [self.reader_mode_btn, self.emulator_mode_btn, self.sniffer_mode_btn]:
            btn.setStyleSheet("""
                QRadioButton { font-size: 13px; padding: 4px 12px; spacing: 6px; }
                QRadioButton::indicator { width: 16px; height: 16px; }
                QRadioButton::indicator:unchecked { border: 2px solid #e0e0e0; border-radius: 8px; background-color: #ffffff; }
                QRadioButton::indicator:checked { border: 2px solid #007bff; border-radius: 8px; background-color: #007bff; }
            """)
            self.mode_btn_group.addButton(btn)
            mode_row_layout.addWidget(btn)
        self.reader_mode_btn.setChecked(True)
        self.mode_btn_group.buttonToggled.connect(self.on_mode_changed)
        mode_row_layout.addStretch()
        mode_layout.addWidget(self.mode_row)

        # Row 1: Type selection (visible in emulator/sniffer)
        self.type_row = QWidget()
        type_row_layout = QHBoxLayout(self.type_row)
        type_row_layout.setContentsMargins(0, 0, 0, 0)
        type_row_layout.setSpacing(8)
        self.type_label = QLabel(i18n.get_text('select_type'))
        self.type_label.setStyleSheet("font-size: 13px; color: #555;")
        type_row_layout.addWidget(self.type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            i18n.get_text('card_type_mifare1_4b1k'),
            i18n.get_text('card_type_ntag'),
            i18n.get_text('card_type_15693'),
            i18n.get_text('card_type_em4100'),
            i18n.get_text('card_type_t5557')
        ])
        self.type_combo.setStyleSheet("""
            QComboBox { font-size: 13px; padding: 4px 8px; border: 1px solid #e0e0e0; border-radius: 4px; min-width: 140px; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)
        self.type_combo.setFixedHeight(30)
        type_row_layout.addWidget(self.type_combo)
        type_row_layout.addStretch()
        self.type_row.setVisible(False)
        mode_layout.addWidget(self.type_row)

        # Row 2: Sniffer mode selection (visible only in sniffer mode)
        self.sniffer_mode_row = QWidget()
        sniffer_mode_row_layout = QHBoxLayout(self.sniffer_mode_row)
        sniffer_mode_row_layout.setContentsMargins(0, 0, 0, 0)
        sniffer_mode_row_layout.setSpacing(8)
        self.sniffer_mode_label = QLabel(i18n.get_text('sniffer_mode_label'))
        self.sniffer_mode_label.setStyleSheet("font-size: 13px; color: #555;")
        sniffer_mode_row_layout.addWidget(self.sniffer_mode_label)
        self.sniffer_mode_combo = QComboBox()
        self.sniffer_mode_combo.addItems([
            i18n.get_text('sniffer_mode_without_tag'),
            i18n.get_text('sniffer_mode_with_tag')
        ])
        self.sniffer_mode_combo.setStyleSheet("""
            QComboBox { font-size: 13px; padding: 4px 8px; border: 1px solid #e0e0e0; border-radius: 4px; min-width: 140px; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)
        self.sniffer_mode_combo.setFixedHeight(30)
        sniffer_mode_row_layout.addWidget(self.sniffer_mode_combo)
        sniffer_mode_row_layout.addStretch()
        self.sniffer_mode_row.setVisible(False)
        mode_layout.addWidget(self.sniffer_mode_row)

        # Row 3: Slot selection (visible only in emulator mode)
        self.slot_row = QWidget()
        slot_row_layout = QHBoxLayout(self.slot_row)
        slot_row_layout.setContentsMargins(0, 0, 0, 0)
        slot_row_layout.setSpacing(6)
        self.slot_label = QLabel(i18n.get_text('select_slot'))
        self.slot_label.setStyleSheet("font-size: 13px; color: #555;")
        slot_row_layout.addWidget(self.slot_label)
        self.slot_btn_group = QButtonGroup()
        self.slot_buttons = []
        for i in range(8):
            btn = QPushButton(i18n.get_text(f'slot_{i}'))
            btn.setCheckable(True)
            btn.setFixedSize(52, 30)
            btn.setStyleSheet("""
                QPushButton { font-size: 11px; border: 1px solid #e0e0e0; border-radius: 4px; background-color: #ffffff; color: #333; }
                QPushButton:checked { background-color: #007bff; color: white; border-color: #007bff; }
                QPushButton:hover:!checked { background-color: #e9ecef; }
            """)
            self.slot_btn_group.addButton(btn, i)
            self.slot_buttons.append(btn)
            slot_row_layout.addWidget(btn)
        self.slot_buttons[0].setChecked(True)
        slot_row_layout.addStretch()
        self.slot_row.setVisible(False)
        mode_layout.addWidget(self.slot_row)

        # Row 4: Emulator controls (visible only in emulator mode)
        self.emu_ctrl_row = QWidget()
        emu_ctrl_layout = QVBoxLayout(self.emu_ctrl_row)
        emu_ctrl_layout.setContentsMargins(0, 0, 0, 0)
        emu_ctrl_layout.setSpacing(6)

        emu_line1 = QHBoxLayout()
        emu_line1.setSpacing(8)
        emu_line1.addWidget(QLabel(i18n.get_text('emu_card_type')))
        self.emu_type_combo = QComboBox()
        self.emu_type_combo.addItems([i18n.get_text('emu_card_mifare'), i18n.get_text('emu_card_ntag'), i18n.get_text('emu_card_15693')])
        self.emu_type_combo.setFixedWidth(110)
        self.emu_type_combo.setStyleSheet("font-size:12px;padding:2px 6px;")
        emu_line1.addWidget(self.emu_type_combo)
        emu_line1.addWidget(QLabel(i18n.get_text('emu_slot')))
        self.emu_slot = QComboBox()
        self.emu_slot.addItems([i18n.get_text('emu_slot_n').format(i) for i in range(8)])
        self.emu_slot.setFixedWidth(80)
        self.emu_slot.setStyleSheet("font-size:12px;padding:2px 6px;")
        emu_line1.addWidget(self.emu_slot)
        emu_line1.addWidget(QLabel(i18n.get_text('emu_uid')))
        self.emu_uid = QLineEdit()
        self.emu_uid.setMaxLength(8)
        self.emu_uid.setFixedWidth(90)
        self.emu_uid.setPlaceholderText(i18n.get_text('uid_8hex'))
        self.emu_uid.setStyleSheet("font-size:12px;padding:2px 6px;")
        emu_line1.addWidget(self.emu_uid)
        self.emu_setuid_btn = QPushButton(i18n.get_text('set_uid'))
        self.emu_setuid_btn.setFixedHeight(26)
        self.emu_setuid_btn.clicked.connect(self.on_emu_setuid)
        self.emu_setuid_btn.setStyleSheet("font-size:11px;background:#ffc107;color:#000;border:none;border-radius:4px;padding:2px 10px;")
        emu_line1.addWidget(self.emu_setuid_btn)
        self.emu_read_btn = QPushButton(i18n.get_text('emu_read'))
        self.emu_read_btn.setFixedHeight(26)
        self.emu_read_btn.clicked.connect(self.on_emu_read)
        self.emu_read_btn.setStyleSheet("font-size:11px;background:#17a2b8;color:#fff;border:none;border-radius:4px;padding:2px 10px;")
        emu_line1.addWidget(self.emu_read_btn)
        emu_line1.addStretch()
        emu_ctrl_layout.addLayout(emu_line1)

        emu_line2 = QHBoxLayout()
        emu_line2.setSpacing(8)
        self.emu_mfd = QLineEdit()
        self.emu_mfd.setPlaceholderText(i18n.get_text('emu_mfd_placeholder'))
        self.emu_mfd.setStyleSheet("font-size:12px;padding:2px 6px;")
        emu_line2.addWidget(self.emu_mfd, 1)
        self.emu_browse_btn = QPushButton(i18n.get_text('browse'))
        self.emu_browse_btn.setFixedHeight(26)
        self.emu_browse_btn.clicked.connect(lambda: self._browse_file(self.emu_mfd))
        self.emu_browse_btn.setStyleSheet("font-size:11px;background:#6c757d;color:#fff;border:none;border-radius:4px;padding:2px 10px;")
        emu_line2.addWidget(self.emu_browse_btn)
        self.emu_load_btn = QPushButton(i18n.get_text('load_to_emu'))
        self.emu_load_btn.setFixedHeight(26)
        self.emu_load_btn.clicked.connect(self.on_emu_load)
        self.emu_load_btn.setStyleSheet("font-size:11px;background:#28a745;color:#fff;border:none;border-radius:4px;padding:2px 10px;")
        emu_line2.addWidget(self.emu_load_btn)
        emu_line2.addStretch()
        emu_ctrl_layout.addLayout(emu_line2)

        self.emu_progress = QTextEdit()
        self.emu_progress.setReadOnly(True)
        self.emu_progress.setMaximumHeight(80)
        self.emu_progress.setMaximumBlockCount(500)
        self.emu_progress.setStyleSheet("font-family:Consolas;font-size:10px;background:#fff;border:1px solid #ddd;border-radius:4px;padding:4px;")
        emu_ctrl_layout.addWidget(self.emu_progress)

        self.emu_ctrl_row.setVisible(False)
        mode_layout.addWidget(self.emu_ctrl_row)

        # Row 5: Sniff buttons (visible only in sniffer mode)
        self.sniff_btn_row = QWidget()
        sniff_btn_row_layout = QHBoxLayout(self.sniff_btn_row)
        sniff_btn_row_layout.setContentsMargins(0, 0, 0, 0)
        sniff_btn_row_layout.setSpacing(10)
        self.read_sniff_without = QPushButton(i18n.get_text('sniff_without_tag'))
        self.read_sniff_without.clicked.connect(self.on_read_sniff_without)
        self.read_sniff_without.setStyleSheet("""
            QPushButton { font-size: 12px; padding: 6px 14px; background-color: #17a2b8; color: white; border: none; border-radius: 4px; min-width: 140px; }
            QPushButton:hover { background-color: #138496; }
        """)
        self.read_sniff_without.setFixedHeight(30)
        sniff_btn_row_layout.addWidget(self.read_sniff_without)
        self.read_sniff_with = QPushButton(i18n.get_text('sniff_with_tag'))
        self.read_sniff_with.clicked.connect(self.on_read_sniff_with)
        self.read_sniff_with.setStyleSheet("""
            QPushButton { font-size: 12px; padding: 6px 14px; background-color: #17a2b8; color: white; border: none; border-radius: 4px; min-width: 140px; }
            QPushButton:hover { background-color: #138496; }
        """)
        self.read_sniff_with.setFixedHeight(30)
        sniff_btn_row_layout.addWidget(self.read_sniff_with)
        sniff_btn_row_layout.addStretch()
        self.sniff_btn_row.setVisible(False)
        mode_layout.addWidget(self.sniff_btn_row)

        # Row 5: Set mode button
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(0)
        self.set_mode_btn = QPushButton(i18n.get_text('set_work_mode'))
        self.set_mode_btn.setFixedSize(140, 36)
        self.set_mode_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-weight: 500;
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:pressed { background-color: #1e7e34; }
        """)
        self.set_mode_btn.clicked.connect(self.on_set_mode_clicked)
        btn_row_layout.addWidget(self.set_mode_btn)
        btn_row_layout.addStretch()
        mode_layout.addWidget(btn_row)

        main_layout.addWidget(self.mode_card)

        self.work_mode_log_card = QGroupBox(i18n.get_text('operation_log'))
        self.work_mode_log_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.work_mode_log_card.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)
        log_layout = QVBoxLayout(self.work_mode_log_card)
        log_layout.setContentsMargins(6, 4, 6, 6)

        self.work_mode_log = QTextEdit()
        self.work_mode_log.setReadOnly(True)
        self.work_mode_log.setMaximumBlockCount(500)
        self.work_mode_log.setStyleSheet("""
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 6px;
            font-family: Consolas, Monaco, monospace;
            font-size: 12px;
        """)
        log_layout.addWidget(self.work_mode_log)
        main_layout.addWidget(self.work_mode_log_card)
    def on_mode_changed(self, button):
        is_reader_mode = button == self.reader_mode_btn
        is_emulator_mode = button == self.emulator_mode_btn
        is_sniffer_mode = button == self.sniffer_mode_btn
        self.type_row.setVisible(is_emulator_mode or is_sniffer_mode)
        self.sniffer_mode_row.setVisible(is_sniffer_mode)
        self.slot_row.setVisible(is_emulator_mode)
        self.emu_ctrl_row.setVisible(is_emulator_mode)
        self.sniff_btn_row.setVisible(is_sniffer_mode)
        self.type_combo.clear()
        if is_sniffer_mode:
            self.type_combo.addItems(['Mifare1-4B1K'])
            self.type_combo.setEnabled(False)
        else:
            self.type_combo.addItems(['Mifare1-4B1K', 'Ntag', '15693', 'EM4100', 'T5557'])
            self.type_combo.setEnabled(is_emulator_mode)
        QTimer.singleShot(0, self._update_work_mode_layout)

    def _update_work_mode_layout(self):
        self.work_mode_tab.updateGeometry()
        self.work_mode_tab.update()
    def on_set_mode_clicked(self):
        if not self._check_serial(): return
        try:
            if self.reader_mode_btn.isChecked():
                mode_index = 1
            elif self.emulator_mode_btn.isChecked():
                mode_index = 2
            else:
                mode_index = 3
            type_index = self.type_combo.currentIndex() + 1
            if mode_index == PN532KillerMode.SNIFFER.value:
                if type_index != PN532KillerTagType.MFC.value:
                    raise ValueError("嗅探模式只支持 Mifare Classic 卡片类型")
                index = self.sniffer_mode_combo.currentIndex()
            else:
                index = self.slot_btn_group.checkedId()
            success = self.set_work_mode(mode_index, type_index, index)
            if success:
                self.work_mode_log.append("工作模式设置成功")
                if mode_index == PN532KillerMode.SNIFFER.value:
                    sniffer_mode = "无标签嗅探" if index == 0 else "带标签嗅探"
                    self.work_mode_log.append(f"当前模式：嗅探模式 ({sniffer_mode})")
            else:
                self.work_mode_log.append("工作模式设置失败")
        except Exception as e:
            self.work_mode_log.append(f"错误：{str(e)}")
            QMessageBox.critical(self, "错误", str(e))
    def set_work_mode(self, mode_index: int, type_index: int, index: int = 0) -> bool:
        try:
            mode = PN532KillerMode(mode_index)
            type_obj = PN532KillerTagType(type_index)
            if mode == PN532KillerMode.SNIFFER:
                if type_obj != PN532KillerTagType.MFC:
                    raise ValueError("嗅探模式只支持 Mifare Classic 卡片类型")
                sniffer_mode = PN532KillerSnifferMode(index)
                response = self.pn532_com.set_work_mode(mode, type_obj, 0, sniffer_mode)
            else:
                response = self.pn532_com.set_work_mode(mode, type_obj, index)
            if response.status != Status.HF_TAG_OK and response.status != Status.SUCCESS:
                raise ValueError(f"设置工作模式失败，错误码：{response.status}，错误信息：{str(response.status)}")
            return True
        except Exception as e:
            self.statusBar().showMessage(f"设置工作模式出错：{str(e)}")
            return False
    def on_read_sniff_without(self):
        self.handle_sniff_and_calc(PN532KillerSnifferMode.WITHOUT_TAG)
    def on_read_sniff_with(self):
        self.handle_sniff_and_calc(PN532KillerSnifferMode.WITH_TAG)
    def handle_sniff_and_calc(self, sniff_mode: PN532KillerSnifferMode):
        import re
        MFKEY_TIMEOUT_SEC = 30  # mfkey 单条计算最长 30 秒
        mode_text = "无标签" if sniff_mode == PN532KillerSnifferMode.WITHOUT_TAG else "有标签"
        self.work_mode_log.append(f"开始 {mode_text} 嗅探及密钥计算...")
        try:
            if not self.pn532_com:
                raise ValueError('设备未连接')
            discovered_keys = set()
            # 开始新会话前清空固件嗅探缓冲,避免读到上次会话的数据
            try:
                if hasattr(self.pn532_com, 'clear_sniffer_log'):
                    cleared = self.pn532_com.clear_sniffer_log()
                    self.work_mode_log.append(f"清空固件嗅探缓冲: {'成功' if cleared else '失败(继续)'}")
            except Exception as e:
                self.work_mode_log.append(f"清空嗅探缓冲异常: {e}")

            self.work_mode_log.append("开始读取嗅探数据...")
            resp = self.pn532_com.read_sniffer_data(sniff_mode)
            if resp.status != Status.SUCCESS:
                raise ValueError(f"读取嗅探数据失败: {resp.status}")
            if not resp.parsed or 'records' not in resp.parsed or not resp.parsed['records']:
                self.work_mode_log.append("未找到嗅探数据或数据格式不正确")
                if resp.data:
                    self.work_mode_log.append(f"原始嗅探数据 (raw): {resp.data.hex().upper()}")
                return
            all_data = b''.join(resp.parsed['records'])

            # 嗅探数据落盘,允许后续用 mfkey 工具离线分析
            try:
                sniff_dir = PathManager.get_history_dir() if hasattr(PathManager, 'get_history_dir') else None
                if sniff_dir is None:
                    sniff_dir = os.path.join(os.path.dirname(PathManager.get_mfkey_tool_path('mfkey64')), 'history')
                os.makedirs(sniff_dir, exist_ok=True)
                from datetime import datetime
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                sniff_file = os.path.join(sniff_dir, f"sniff_{mode_text}_{ts}.bin")
                with open(sniff_file, 'wb') as f:
                    f.write(resp.data)  # 写原始响应(含 mode_flag)
                self.work_mode_log.append(f"嗅探原始数据已保存: {sniff_file}")
            except Exception as e:
                self.work_mode_log.append(f"保存嗅探数据失败: {e}")

            self.work_mode_log.append(f"合并后的嗅探数据: {all_data.hex().upper()}")
            self.work_mode_log.append("开始解析认证数据...")
            auth_data = self.pn532_com.parse_sniffer_auth_data(all_data, sniff_mode)
            if not auth_data:
                self.work_mode_log.append("解析认证数据失败，未找到有效认证记录")
                return
            self.work_mode_log.append(f"解析成功，找到 {len(auth_data)} 组认证数据:")
            for item in auth_data:
                self.work_mode_log.append(str(item))
            self.work_mode_log.append("开始尝试计算密钥...")
            if sniff_mode == PN532KillerSnifferMode.WITH_TAG:
                self.work_mode_log.append("使用 mfkey64 (有标签模式)，逐条处理认证记录...")
                for item in auth_data:
                    required_keys = ['uid', 'nt', 'nr', 'ar', 'at']
                    if not all(k in item for k in required_keys):
                        self.work_mode_log.append(f"记录不完整，跳过: {item}")
                        continue
                    uid = item['uid']
                    nt = item['nt']
                    nr = item['nr']
                    ar = item['ar']
                    at = item['at']
                    # 校验 hex 长度,避免无效数据调 mfkey 卡死
                    if not all(re.fullmatch(r'[0-9A-Fa-f]{8,32}', x or '') for x in (uid, nt, nr, ar, at)):
                        self.work_mode_log.append(f"记录字段格式错误,跳过: {item}")
                        continue
                    mfkey64_path = PathManager.get_mfkey_tool_path("mfkey64")
                    cmd_list = [mfkey64_path, uid, nt, nr, ar, at]
                    self.work_mode_log.append(f"调用 mfkey64 命令： {' '.join(cmd_list)}")
                    try:
                        if PathManager.is_windows():
                            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                            result = subprocess.check_output(
                                cmd_list, stderr=subprocess.STDOUT,
                                text=True, errors='ignore',
                                creationflags=creationflags, timeout=MFKEY_TIMEOUT_SEC)
                        else:
                            result = subprocess.check_output(
                                cmd_list, stderr=subprocess.STDOUT,
                                text=True, errors='ignore', timeout=MFKEY_TIMEOUT_SEC)
                        self.work_mode_log.append("mfkey64 输出:")
                        self.work_mode_log.append(result)
                        key_match = re.search(r'Found Key: \[(.*?)\]', result)
                        if key_match:
                            key = key_match.group(1)
                            if key not in discovered_keys:
                                discovered_keys.add(key)
                                self.save_keys_to_history({key}, uid)
                                self._show_key_recovery_dialog(key, uid, str(item))
                    except subprocess.TimeoutExpired:
                        self.work_mode_log.append(f"mfkey64 计算超时({MFKEY_TIMEOUT_SEC}s),跳过此条")
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        self.work_mode_log.append(f"调用 {cmd_list[0]} 失败: {e}")
            else:
                self.work_mode_log.append("使用 mfkey32v2 (无标签模式)，尝试为每个UID寻找两条记录进行计算...")
                grouped_by_uid = {}
                for record in auth_data:
                    uid = record.get('uid')
                    if uid:
                        if uid not in grouped_by_uid:
                            grouped_by_uid[uid] = []
                        grouped_by_uid[uid].append(record)
                if not grouped_by_uid:
                    self.work_mode_log.append("未找到任何可分组的认证记录。")
                    return
                found_key = False
                for uid, records in grouped_by_uid.items():
                    if len(records) < 2:
                        self.work_mode_log.append(f"为 UID {uid} 找到的记录少于2条，无法进行计算。")
                        continue
                    self.work_mode_log.append(f"为 UID {uid} 找到 {len(records)} 条记录，尝试所有连续配对进行计算。")
                    for i in range(len(records) - 1):
                        r0 = records[i]
                        r1 = records[i+1]
                        self.work_mode_log.append(f"尝试配对记录 {i} 和 {i+1}...")
                        nt0 = r0.get('nt_0')
                        nr0 = r0.get('nr_0')
                        ar0 = r0.get('ar_0')
                        nt1 = r1.get('nt_0')
                        nr1 = r1.get('nr_0')
                        ar1 = r1.get('ar_0')
                        if all([uid, nt0, nr0, ar0, nt1, nr1, ar1]):
                            # 校验 hex 长度
                            if not all(re.fullmatch(r'[0-9A-Fa-f]{8,32}', x or '') for x in
                                       (uid, nt0, nr0, ar0, nt1, nr1, ar1)):
                                self.work_mode_log.append(f"UID {uid} 字段格式错误,跳过配对 {i}")
                                continue
                            mfkey32v2_path = PathManager.get_mfkey_tool_path("mfkey32v2")
                            cmd_list = [mfkey32v2_path, uid, nt0, nr0, ar0, nt1, nr1, ar1]
                            self.work_mode_log.append(f"调用 mfkey32v2 命令： {' '.join(cmd_list)}")
                            try:
                                if PathManager.is_windows():
                                    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                    result = subprocess.check_output(
                                        cmd_list, stderr=subprocess.STDOUT,
                                        text=True, errors='ignore',
                                        creationflags=creationflags, timeout=MFKEY_TIMEOUT_SEC)
                                else:
                                    result = subprocess.check_output(
                                        cmd_list, stderr=subprocess.STDOUT,
                                        text=True, errors='ignore', timeout=MFKEY_TIMEOUT_SEC)
                                self.work_mode_log.append("mfkey32v2 输出:")
                                self.work_mode_log.append(result)
                                key_match = re.search(r'Found Key: \[(.*?)\]', result)
                                if key_match:
                                    key = key_match.group(1)
                                    if key not in discovered_keys:
                                        discovered_keys.add(key)
                                        self.work_mode_log.append(f"成功为 UID {uid} 找到密钥！")
                                        found_key = True
                                        self.save_keys_to_history({key}, uid)
                                        raw_data = f"记录 0: {str(r0)}\n记录 1: {str(r1)}"
                                        self._show_key_recovery_dialog(key, uid, raw_data)
                            except subprocess.TimeoutExpired:
                                self.work_mode_log.append(f"mfkey32v2 计算超时({MFKEY_TIMEOUT_SEC}s),跳过此配对")
                            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                                self.work_mode_log.append(f"调用 {cmd_list[0]} 失败: {e}")
                        else:
                            self.work_mode_log.append(f"UID {uid} 的记录对 (索引 {i}, {i+1}) 不完整，跳过。")
                if not found_key:
                    self.work_mode_log.append("在所有尝试的配对中，未能成功计算出任何密钥。")
        except Exception as e:
            self.work_mode_log.append(f"处理失败：{str(e)}")
            QMessageBox.critical(self, '错误', str(e))
    
    def _show_key_recovery_dialog(self, key, uid, raw_data):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
        from PyQt6.QtGui import QFont, QCursor
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        
        dialog = QDialog(self)
        dialog.setWindowTitle('密钥恢复成功')
        dialog.setModal(True)
        dialog.resize(500, 350)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_label = QLabel('密钥恢复成功')
        title_label.setFont(_font('Microsoft YaHei', 16, QFont.Weight.Bold))
        title_label.setStyleSheet('color: #28a745;')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        key_label = QLabel(f'<strong>Key:</strong> <span style="font-family: Consolas; font-size: 14px; color: #007bff;">{key}</span>')
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(key_label)
        
        uid_label = QLabel(f'<strong>UID:</strong> <span style="font-family: Consolas; font-size: 14px; color: #007bff;">{uid}</span>')
        uid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(uid_label)
        
        copy_key_btn = QPushButton(f"点击复制 Key: {key}")
        copy_key_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        copy_key_btn.setStyleSheet('''
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        ''')
        
        def copy_key():
            clipboard = QApplication.clipboard()
            clipboard.setText(key)
            copy_key_btn.setText("已复制！")
            copy_key_btn.setStyleSheet('''
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 13px;
                    padding: 8px 16px;
                }
            ''')
            QTimer.singleShot(1500, lambda: restore_button())
        
        def restore_button():
            copy_key_btn.setText(f"点击复制 Key: {key}")
            copy_key_btn.setStyleSheet('''
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 13px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
            ''')
        
        copy_key_btn.clicked.connect(copy_key)
        layout.addWidget(copy_key_btn)
        
        data_label = QLabel('原始数据:')
        data_label.setFont(_font('Microsoft YaHei', 12, QFont.Weight.Bold))
        layout.addWidget(data_label)
        
        data_text = QTextEdit()
        data_text.setPlainText(raw_data)
        data_text.setReadOnly(True)
        data_text.setFont(_font('Consolas', 11))
        data_text.setStyleSheet('''
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        ''')
        data_text.setMinimumHeight(100)
        layout.addWidget(data_text)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton('确定')
        ok_btn.setFixedSize(100, 35)
        ok_btn.setStyleSheet('''
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        ''')
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    def log_message(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.read_card_log.append(formatted_message)
        # 同时记录到新的日志系统
        app_logger.info(f"NFC工具: {message}")
    
    def log_message_connection(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.work_mode_log.append(formatted_message)
        # 同时记录到新的日志系统
        app_logger.info(f"连接: {message}")
    
    def log_message_work_mode(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.work_mode_log.append(formatted_message)
        # 同时记录到新的日志系统
        app_logger.info(f"工作模式: {message}")
    def init_connection_tab(self):
        layout = QVBoxLayout(self.connection_tab)
        self.connect_btn = QPushButton('连接设备')
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)
        self.log_text.setStyleSheet("background-color: #ffffff; color: #333333; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px;")
        layout.addWidget(self.log_text)
    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if not ports:
            self._mb(QMessageBox.Icon.Warning, '警告', '未检测到可用串口')
            return
        self.log_message_connection('已刷新可用串口列表')
    def toggle_connection(self):
        if self.pn532_com is None:
            try:
                config_dialog = ConfigDialog('UART')
                config_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                config_dialog.show()
                # ConfigDialog 是 QWidget 而非 QDialog, accept()/reject() 是普通方法
                # 不会发出 accepted/rejected 信号,只能用同步循环等窗口关闭
                # 用 QApplication.processEvents 让 UI 仍能响应,但 100ms 间隔不让主线程一直忙
                import time as _t
                while config_dialog.isVisible():
                    QApplication.processEvents()
                    _t.sleep(0.05)
                if config_dialog.result is None:
                    return
                port, baud = config_dialog.result
                self.log_message_connection(i18n.get_text('try_connect').format(port=port, baud=baud))
                self.pn532_com = Pn532Com()
                self.pn532_com.open(port, baud)
                if not self.pn532_com.isOpen():
                    self.log_message_connection(i18n.get_text('open_port_fail').format(port=port))
                    return
                self.log_message_connection(i18n.get_text('open_port_ok').format(port=port, baud=baud))
                self.log_message_connection(i18n.get_text('init_cmd'))
                self.cmd = Pn532CMD(self.pn532_com)
                self.log_message_connection(i18n.get_text('init_cmd_done'))
                self.connect_btn.setText(i18n.get_text('disconnect'))
                self.device_info_label.setText(i18n.get_text('connected'))
                self.log_message_connection(i18n.get_text('success_connected'))
            except Exception as e:
                self._mb(QMessageBox.Icon.Critical, '错误', f'连接失败: {str(e)}')
                self.log_message_connection(i18n.get_text('error_details') + str(e))
                if hasattr(self, 'pn532_com') and self.pn532_com:
                    self.pn532_com.close()
                self.pn532_com = None
        else:
            if hasattr(self, 'pn532_com') and self.pn532_com:
                self.pn532_com.close()
            self.pn532_com = None
            if hasattr(self, 'cmd'):
                self.cmd = None
            self.connect_btn.setText(i18n.get_text('connect_device'))
            self.device_info_label.setText(i18n.get_text('not_connected'))
            self.statusBar().showMessage(i18n.get_text('disconnected'))
    def show_timed_message_box(self, title, message, icon=QMessageBox.Icon.Information, timeout=3000):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        QTimer.singleShot(timeout, msg_box.close)
        msg_box.exec()
    def create_sector_display_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.sector_tree = QTreeWidget()
        self.sector_tree.setHeaderLabels([i18n.get_text('sector_block'), i18n.get_text('data'), i18n.get_text('description')])
        self.sector_tree.setAlternatingRowColors(True)
        self.sector_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sector_tree.customContextMenuRequested.connect(self.show_sector_context_menu)
        self.sector_tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.EditKeyPressed)
        self.sector_tree.itemChanged.connect(self.on_sector_item_changed)
        self.sector_tree.setColumnWidth(0, 130)
        self.sector_tree.setColumnWidth(1, 480)
        self.sector_tree.setColumnWidth(2, 200)
        self.sector_tree.setStyleSheet("""
            QTreeWidget {
                font-size: 13px;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                background-color: #ffffff;
                padding: 4px;
                alternate-background-color: #f5f7fa;
            }
            QTreeWidget::item {
                padding: 4px 2px;
                min-height: 24px;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1a1a2e;
            }
            QTreeWidget::header {
                font-size: 13px;
                font-weight: bold;
                color: #495057;
                background-color: #f8f9fa;
                border: none;
                border-bottom: 2px solid #dee2e6;
                padding: 6px;
            }
            QTreeWidget::header:section {
                background-color: #f8f9fa;
                border: none;
                border-right: 1px solid #e9ecef;
                padding: 6px 10px;
            }
        """)

        layout.addWidget(self.sector_tree, 1)

        btn_bar = QFrame()
        btn_bar.setFrameShape(QFrame.Shape.NoFrame)
        btn_bar.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(btn_bar)
        button_layout.setContentsMargins(0, 4, 0, 0)
        button_layout.setSpacing(10)

        _btn_tpl = """
            QPushButton {{
                font-size: 12px;
                font-weight: 500;
                padding: 6px 18px;
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: {pressed}; }}
            QPushButton:disabled {{ background-color: #adb5bd; }}
        """

        btn_configs = [
            ('import_btn', 'import', self.import_sector_data, '#17a2b8', '#138496', '#0e7a8a'),
            ('export_btn', 'export', self.export_sector_data, '#28a745', '#218838', '#1e7e34'),
            ('save_btn', 'save', self.save_sector_data, '#007bff', '#0056b3', '#004494'),
            ('clear_sector_btn', 'clear', self.clear_sector_display, '#dc3545', '#c82333', '#bd2130'),
            ('history_keys_btn', 'keys', self.show_history_keys, '#6c757d', '#5a6268', '#545b62'),
        ]

        for attr, key, handler, bg, hover, pressed in btn_configs:
            btn = QPushButton(i18n.get_text(key))
            btn.setFixedHeight(32)
            btn.setStyleSheet(_btn_tpl.format(bg=bg, hover=hover, pressed=pressed))
            btn.clicked.connect(handler)
            setattr(self, attr, btn)
            button_layout.addWidget(btn)

        self.export_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        button_layout.addStretch()
        layout.addWidget(btn_bar)
        return widget
    def load_sector_data_from_mfd(self, mfd_file_path):
        try:
            if self.mfd_parser is None:
                self.mfd_parser = MFDParser(mfd_file_path)
            success = self.mfd_parser.parse_mfd_file(mfd_file_path)
            if success:
                self._current_mfd_path = mfd_file_path
                self.log_message("成功解析MFD文件，正在加载扇区数据...")
                card_info = self.mfd_parser.get_card_info()
                self.card_info_label.setText(f"{card_info['card_type']} - {card_info['total_sectors']}个扇区")
                self.sector_tree.clear()
                self.sector_tree.itemChanged.disconnect(self.on_sector_item_changed)
                try:
                    sectors_data = self.mfd_parser.get_sectors_data()
                    for sector_data in sectors_data:
                        self.add_sector_to_tree(sector_data)
                finally:
                    self.sector_tree.itemChanged.connect(self.on_sector_item_changed)
                self.sector_tree.expandAll()
                self.export_btn.setEnabled(True)
                self.save_btn.setEnabled(True)
                self.log_message(f"已加载 {len(sectors_data)} 个扇区的数据")
                return True
            else:
                self.log_message("解析MFD文件失败")
                return False
        except Exception as e:
            self.log_message(f"加载扇区数据时出错: {str(e)}")
            return False
    def add_sector_to_tree(self, sector_data):
        sector_num = sector_data['sector_num']
        sector_item = QTreeWidgetItem(self.sector_tree)
        sector_item.setText(0, f"扇区 {sector_num}")
        key_text = f"Key A: {sector_data['key_a']} | Key B: {sector_data['key_b']}"
        sector_item.setText(1, key_text)
        # 第三列显示 access bits 解析结果
        access_decoded = sector_data.get('access_decoded')
        access_bits_hex = sector_data.get('access_bits')
        if access_decoded:
            c1, c2, c3 = access_decoded['c1_nibble'], access_decoded['c2_nibble'], access_decoded['c3_nibble']
            sector_item.setText(2, f"{sector_data['block_count']} 个块 | AC: C1={c1:X} C2={c2:X} C3={c3:X} GPB={access_decoded['gpb']:02X}")
        elif access_bits_hex:
            sector_item.setText(2, f"{sector_data['block_count']} 个块 | AC: ⚠ {access_bits_hex} (反码校验失败)")
        else:
            sector_item.setText(2, f"{sector_data['block_count']} 个块")
        sector_item.setBackground(0, QColor(230, 240, 250))
        sector_item.setBackground(1, QColor(255, 255, 200))
        key_font = QFont()
        key_font.setBold(True)
        sector_item.setFont(1, key_font)
        sector_item.setForeground(1, QColor(139, 69, 19))
        for block in sector_data['blocks']:
            block_item = QTreeWidgetItem(sector_item)
            block_num = block['block_num']
            hex_data = block['hex_data']
            if len(hex_data) < 32:
                hex_data = hex_data.ljust(32, '0')
            elif len(hex_data) > 32:
                hex_data = hex_data[:32]
            try:
                int(hex_data, 16)
            except ValueError:
                hex_data = '0' * 32
                self.log_message(f"块 {block_num} 包含无效十六进制字符，已重置为全0")
            formatted_hex = ' '.join([hex_data[i:i+4] for i in range(0, len(hex_data), 4)])
            block_item.setText(0, f"块 {block_num}")
            block_item.setText(1, formatted_hex)
            block_item.setFlags(block_item.flags() | Qt.ItemFlag.ItemIsEditable)
            block_item.setData(1, Qt.ItemDataRole.UserRole, hex_data)
            if block_num % 4 == 3:
                # 尾块:显示 access bits 解析 + KeyA/KeyB 权限
                trailer_label = "尾块 (密钥+访问控制)"
                if access_decoded:
                    from mfd_parser import (access_condition_for_block,
                                              get_trailer_block_permission,
                                              format_trailer_perm)
                    cond = access_condition_for_block(block_num, block_num,
                                                     access_decoded['normal'])
                    pa = get_trailer_block_permission(cond, 'A')
                    pb = get_trailer_block_permission(cond, 'B')
                    trailer_label += (
                        f"\n  AC={cond} | KeyA:{format_trailer_perm(pa)}"
                        f"\n  KeyB:{format_trailer_perm(pb)}"
                    )
                block_item.setText(2, trailer_label)
                block_item.setBackground(0, QColor(255, 240, 240))
                block_item.setBackground(1, QColor(255, 245, 238))
                block_item.setForeground(1, QColor(139, 69, 19))
            else:
                # 数据块:显示 access condition + KeyA/B 权限
                block_label = "数据块"
                if access_decoded:
                    from mfd_parser import (access_condition_for_block,
                                              get_data_block_permission,
                                              format_data_perm)
                    # 计算此 block 的 trailer_block 号(用于 4K 高扇区)
                    if block_num < 128:
                        trailer_block = (block_num // 4) * 4 + 3
                    else:
                        trailer_block = 128 + ((block_num - 128) // 16) * 16 + 15
                    cond = access_condition_for_block(block_num, trailer_block,
                                                     access_decoded['normal'])
                    pa = get_data_block_permission(cond, 'A')
                    pb = get_data_block_permission(cond, 'B')
                    block_label += f" | AC={cond} | KeyA:{format_data_perm(pa)} KeyB:{format_data_perm(pb)}"
                block_item.setText(2, block_label)
                block_item.setBackground(0, QColor(240, 255, 240))
    def clear_sector_display(self):
        self.sector_tree.clear()
        self.card_info_label.setText(i18n.get_text('no_card_data_loaded'))
        self.export_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self._current_mfd_path = None
        self.log_message("已清空扇区显示")
    def save_sector_data(self):
        if not self._current_mfd_path or not os.path.exists(self._current_mfd_path):
            self._mb(QMessageBox.Icon.Warning, "警告", "没有可保存的源文件，请先导入或读取卡片数据")
            return
        try:
            data = bytearray(1024)
            for i in range(self.sector_tree.topLevelItemCount()):
                sector_item = self.sector_tree.topLevelItem(i)
                for j in range(sector_item.childCount()):
                    child = sector_item.child(j)
                    block_text = child.text(0)
                    block_num = int(block_text.split()[-1])
                    hex_data = child.data(1, Qt.ItemDataRole.UserRole)
                    if not hex_data:
                        hex_data = self.clean_hex_data(child.text(1))
                    block_bytes = bytes.fromhex(hex_data)
                    offset = block_num * 16
                    if offset + 16 <= len(data):
                        data[offset:offset + 16] = block_bytes
            with open(self._current_mfd_path, 'wb') as f:
                f.write(data)
            self.log_message(f"数据已保存到: {self._current_mfd_path}")
            self._mb(QMessageBox.Icon.Information, "保存成功", f"扇区数据已保存到:\n{self._current_mfd_path}")
        except Exception as e:
            self.log_message(f"保存数据时出错: {str(e)}")
            self._mb(QMessageBox.Icon.Critical, "保存失败", f"保存数据时出错:\n{str(e)}")
    def export_sector_data(self):
        if self.mfd_parser is None or not hasattr(self.mfd_parser, 'sectors') or not self.mfd_parser.sectors:
            self._mb(QMessageBox.Icon.Warning, "警告", "没有可导出的扇区数据！")
            return
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("Text Files (*.txt);;All Files (*)")
        file_dialog.setDefaultSuffix("txt")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_dialog.selectFile(f"sector_data_{timestamp}.txt")
        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                export_path = selected_files[0]
                try:
                    if self.mfd_parser.export_to_text(export_path):
                        self.log_message(f"扇区数据已导出到: {export_path}")
                        self._mb(QMessageBox.Icon.Information, "导出成功", f"扇区数据已成功导出到:\n{export_path}")
                    else:
                        self.log_message("导出扇区数据失败")
                        self._mb(QMessageBox.Icon.Warning, "导出失败", "导出扇区数据时发生错误")
                except Exception as e:
                    self.log_message(f"导出扇区数据时出错: {str(e)}")
                    self._mb(QMessageBox.Icon.Warning, "导出失败", f"导出时发生错误:\n{str(e)}")

    def show_sector_context_menu(self, position):
        item = self.sector_tree.itemAt(position)
        if not item:
            return
        menu = QMenu(self)
        copy_text_action = QAction("复制文本", self)
        copy_text_action.triggered.connect(lambda: self.copy_item_text(item))
        menu.addAction(copy_text_action)
        copy_data_action = QAction("复制数据", self)
        copy_data_action.triggered.connect(lambda: self.copy_item_data(item))
        menu.addAction(copy_data_action)
        if item.parent() is None:
            menu.addSeparator()
            copy_keys_action = QAction("复制密钥", self)
            copy_keys_action.triggered.connect(lambda: self.copy_sector_keys(item))
            menu.addAction(copy_keys_action)
            menu.addSeparator()
            parse_sector_action = QAction("解析扇区", self)
            parse_sector_action.triggered.connect(lambda: self.parse_sector_data(item))
            menu.addAction(parse_sector_action)
        menu.exec(self.sector_tree.mapToGlobal(position))
    def copy_item_text(self, item):
        text_parts = []
        for i in range(self.sector_tree.columnCount()):
            text = item.text(i)
            if text:
                text_parts.append(text)
        full_text = " | ".join(text_parts)
        QApplication.clipboard().setText(full_text)
        self.log_message(f"已复制: {full_text[:50]}...")
    def copy_item_data(self, item):
        data_text = item.text(1)
        if data_text:
            QApplication.clipboard().setText(data_text)
            self.log_message(f"已复制数据: {data_text[:50]}...")
        else:
            self.log_message("没有可复制的数据")
    def copy_sector_keys(self, sector_item):
        key_text = sector_item.text(1)
        if "Key A:" in key_text and "Key B:" in key_text:
            QApplication.clipboard().setText(key_text)
            self.log_message(f"已复制密钥: {key_text}")
        else:
            self.log_message("无法获取密钥信息")
    def parse_sector_data(self, sector_item):
        sector_text = sector_item.text(0)
        sector_num = sector_text.replace("扇区 ", "")
        try:
            sector_num = int(sector_num)
            block_data = []
            for i in range(sector_item.childCount()):
                child = sector_item.child(i)
                hex_data = child.text(1).replace(" ", "")
                block_data.append(hex_data)
            parsed_info = self.analyze_sector_content(sector_num, block_data)
            self.show_sector_analysis_dialog(sector_num, parsed_info)
        except ValueError:
            self.log_message("无法解析扇区编号")
        except Exception as e:
            self.log_message(f"解析扇区时出错: {str(e)}")
    def analyze_sector_content(self, sector_num, block_data):
        """
        分析扇区内容
        
        此方法现在调用独立的 SectorAnalyzer 模块。
        """
        from sector_manager import SectorAnalyzer
        return SectorAnalyzer.analyze_sector_content(sector_num, block_data)
    def show_sector_analysis_dialog(self, sector_num, analysis):
        """
        显示扇区分析对话框
        
        此方法现在使用独立的 SectorAnalysisDialog。
        """
        from sector_manager import SectorAnalysisDialog
        dialog = SectorAnalysisDialog(self, sector_num, analysis)
        dialog.exec()
    def import_sector_data(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("导入扇区数据")
        dialog.setMinimumSize(500, 400)
        layout = QVBoxLayout(dialog)
        method_group = QGroupBox("选择导入方式")
        method_layout = QVBoxLayout(method_group)
        self.import_from_file_radio = QRadioButton("从MFD文件导入")
        self.import_from_file_radio.setChecked(True)
        self.import_from_clipboard_radio = QRadioButton("从剪贴板导入")
        self.import_manual_radio = QRadioButton("手动输入数据")
        method_layout.addWidget(self.import_from_file_radio)
        method_layout.addWidget(self.import_from_clipboard_radio)
        method_layout.addWidget(self.import_manual_radio)
        layout.addWidget(method_group)
        file_group = QGroupBox("文件选择")
        file_layout = QHBoxLayout(file_group)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择MFD文件...")
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.browse_mfd_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_btn)
        layout.addWidget(file_group)
        manual_group = QGroupBox("手动输入数据")
        manual_layout = QVBoxLayout(manual_group)
        manual_info = QLabel("请输入十六进制数据，每行一个块，或粘贴完整的扇区数据：")
        manual_info.setWordWrap(True)
        manual_layout.addWidget(manual_info)
        self.manual_data_edit = QTextEdit()
        self.manual_data_edit.setPlaceholderText("示例:\n04A1B2C3D4E5F6...\n或粘贴从其他地方复制的扇区数据")
        self.manual_data_edit.setFont(_font("Consolas", 10))
        manual_layout.addWidget(self.manual_data_edit)
        paste_btn = QPushButton("从剪贴板粘贴")
        paste_btn.clicked.connect(self.paste_from_clipboard)
        manual_layout.addWidget(paste_btn)
        layout.addWidget(manual_group)
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setFont(_font("Consolas", 9))
        preview_layout.addWidget(self.preview_text)
        layout.addWidget(preview_group)
        button_layout = QHBoxLayout()
        preview_btn = QPushButton("预览数据")
        preview_btn.clicked.connect(self.preview_import_data)
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(lambda: self.execute_import(dialog))
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(preview_btn)
        button_layout.addStretch()
        button_layout.addWidget(import_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.import_from_file_radio.toggled.connect(self.update_import_controls)
        self.import_from_clipboard_radio.toggled.connect(self.update_import_controls)
        self.import_manual_radio.toggled.connect(self.update_import_controls)
        self.update_import_controls()
        dialog.exec()
    def update_import_controls(self):
        file_enabled = self.import_from_file_radio.isChecked()
        manual_enabled = self.import_manual_radio.isChecked() or self.import_from_clipboard_radio.isChecked()
        self.file_path_edit.setEnabled(file_enabled)
        self.browse_btn.setEnabled(file_enabled)
        self.manual_data_edit.setEnabled(manual_enabled)
    def browse_mfd_file(self):
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setNameFilter("MFD Files (*.mfd);;All Files (*)")
        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.file_path_edit.setText(selected_files[0])
    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.manual_data_edit.setPlainText(text)
            self.log_message("已从剪贴板粘贴数据")
        else:
            self.log_message("剪贴板中没有文本数据")
    def preview_import_data(self):
        try:
            data_text = ""
            if self.import_from_file_radio.isChecked():
                file_path = self.file_path_edit.text().strip()
                if not file_path:
                    self._mb(QMessageBox.Icon.Warning, "警告", "请选择MFD文件！")
                    return
                if not os.path.exists(file_path):
                    self._mb(QMessageBox.Icon.Warning, "警告", "文件不存在！")
                    return
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        hex_data = data.hex().upper()
                        data_text = f"文件: {os.path.basename(file_path)}\n"
                        data_text += f"大小: {len(data)} 字节\n"
                        data_text += f"前64字节: {hex_data[:128]}..."
                except Exception as e:
                    self._mb(QMessageBox.Icon.Warning, "错误", f"读取文件失败: {str(e)}")
                    return
            elif self.import_from_clipboard_radio.isChecked():
                clipboard = QApplication.clipboard()
                clipboard_text = clipboard.text()
                if not clipboard_text:
                    self._mb(QMessageBox.Icon.Warning, "警告", "剪贴板中没有数据！")
                    return
                data_text = f"剪贴板数据预览:\n{clipboard_text[:200]}..."
            elif self.import_manual_radio.isChecked():
                manual_text = self.manual_data_edit.toPlainText().strip()
                if not manual_text:
                    self._mb(QMessageBox.Icon.Warning, "警告", "请输入数据！")
                    return
                data_text = f"手动输入数据预览:\n{manual_text[:200]}..."
            self.preview_text.setPlainText(data_text)
        except Exception as e:
            self._mb(QMessageBox.Icon.Warning, "错误", f"预览数据时出错: {str(e)}")
    def execute_import(self, dialog):
        try:
            success = False
            if self.import_from_file_radio.isChecked():
                file_path = self.file_path_edit.text().strip()
                if not file_path or not os.path.exists(file_path):
                    self._mb(QMessageBox.Icon.Warning, "警告", "请选择有效的MFD文件！")
                    return
                success = self.load_sector_data_from_mfd(file_path)
            elif self.import_from_clipboard_radio.isChecked():
                clipboard = QApplication.clipboard()
                clipboard_text = clipboard.text()
                if not clipboard_text:
                    self._mb(QMessageBox.Icon.Warning, "警告", "剪贴板中没有数据！")
                    return
                success = self.import_from_text_data(clipboard_text)
            elif self.import_manual_radio.isChecked():
                manual_text = self.manual_data_edit.toPlainText().strip()
                if not manual_text:
                    self._mb(QMessageBox.Icon.Warning, "警告", "请输入数据！")
                    return
                success = self.import_from_text_data(manual_text)
            if success:
                self.log_message("扇区数据导入成功！")
                self._mb(QMessageBox.Icon.Information, "成功", "扇区数据导入成功！")
                dialog.accept()
            else:
                self._mb(QMessageBox.Icon.Warning, "失败", "导入扇区数据失败，请检查数据格式！")
        except Exception as e:
            self.log_message(f"导入数据时出错: {str(e)}")
            self._mb(QMessageBox.Icon.Warning, "错误", f"导入时发生错误:\n{str(e)}")
    def import_from_text_data(self, text_data):
        try:
            lines = text_data.strip().split('\n')
            hex_blocks = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                hex_line = ''.join(c for c in line.upper() if c in '0123456789ABCDEF')
                if len(hex_line) >= 32 and len(hex_line) % 32 == 0:
                    for i in range(0, len(hex_line), 32):
                        block_data = hex_line[i:i+32]
                        if len(block_data) == 32:
                            hex_blocks.append(block_data)
            if not hex_blocks:
                self.log_message("未找到有效的十六进制块数据")
                return False
            sectors_data = []
            blocks_per_sector = 4
            for sector_idx in range(0, len(hex_blocks), blocks_per_sector):
                sector_blocks = hex_blocks[sector_idx:sector_idx + blocks_per_sector]
                if len(sector_blocks) < blocks_per_sector:
                    while len(sector_blocks) < blocks_per_sector:
                        sector_blocks.append("00" * 32)
                trailer_block = sector_blocks[-1]
                key_a = trailer_block[:12] if len(trailer_block) >= 12 else "FFFFFFFFFFFF"
                key_b = trailer_block[20:32] if len(trailer_block) >= 32 else "FFFFFFFFFFFF"
                sector_data = {
                    'sector_num': len(sectors_data),
                    'key_a': key_a,
                    'key_b': key_b,
                    'block_count': len(sector_blocks),
                    'blocks': []
                }
                for block_idx, block_hex in enumerate(sector_blocks):
                    block_info = {
                        'block_num': block_idx,
                        'hex_data': block_hex
                    }
                    sector_data['blocks'].append(block_info)
                sectors_data.append(sector_data)
            self.sector_tree.clear()
            self.card_info_label.setText(f"导入数据 - {len(sectors_data)}个扇区")
            for sector_data in sectors_data:
                self.add_sector_to_tree(sector_data)
            self.sector_tree.expandAll()
            self.export_btn.setEnabled(True)
            return True
        except Exception as e:
            self.log_message(f"解析文本数据时出错: {str(e)}")
            return False
    def on_sector_item_changed(self, item, column):
        if column != 1:
            return
        new_value = item.text(1)
        if not self.validate_hex_data(new_value):
            original_data = item.data(1, Qt.ItemDataRole.UserRole)
            if original_data:
                formatted_hex = ' '.join([original_data[i:i+4] for i in range(0, len(original_data), 4)])
                item.setText(1, formatted_hex)
            self.log_message("数据格式错误，已恢复原始值。请输入有效的十六进制数据。")
            return
        clean_hex = self.clean_hex_data(new_value)
        if len(clean_hex) != 32:
            if len(clean_hex) < 32:
                clean_hex = clean_hex.ljust(32, '0')
                self.log_message(f"数据长度不足，已自动补齐到32字符: {clean_hex}")
            else:
                clean_hex = clean_hex[:32]
                self.log_message(f"数据长度超出，已截取到32字符: {clean_hex}")
        item.setData(1, Qt.ItemDataRole.UserRole, clean_hex)
        formatted_hex = ' '.join([clean_hex[i:i+4] for i in range(0, len(clean_hex), 4)])
        item.setText(1, formatted_hex)
        item.setBackground(1, QColor(255, 255, 200))
        self.log_message("数据已更新并验证通过")
    def validate_hex_data(self, data):
        clean_data = ''.join(data.split())
        try:
            int(clean_data, 16)
            return True
        except ValueError:
            return False
    def clean_hex_data(self, data):
        return ''.join(data.split()).upper()

    def load_default_keys(self):
        return self.data_manager.load_default_keys()
    def extract_sector_data_from_tree(self, sector_item):
        try:
            sector_text = sector_item.text(0)
            sector_num = int(sector_text.split()[1])
            key_text = sector_item.text(1)
            key_parts = key_text.split('|')
            key_a = key_parts[0].split(':')[1].strip().replace(' ', '')
            key_b = key_parts[1].split(':')[1].strip().replace(' ', '')
            blocks = []
            for i in range(sector_item.childCount()):
                block_item = sector_item.child(i)
                block_text = block_item.text(0)
                block_num = int(block_text.split()[1])
                hex_data = block_item.data(1, Qt.ItemDataRole.UserRole)
                if not hex_data:
                    hex_data = self.clean_hex_data(block_item.text(1))
                blocks.append({
                    'block_num': block_num,
                    'hex_data': hex_data
                })
            return {
                'sector_num': sector_num,
                'key_a': key_a,
                'key_b': key_b,
                'blocks': blocks,
                'block_count': len(blocks)
            }
        except Exception as e:
            self.log_message(f"提取扇区数据时出错: {str(e)}")
            return None


    def cleanup_temp_files(self, file_paths):
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    self.log_message(f"清理临时文件失败 {file_path}: {str(e)}")
    def save_keys_from_sectors(self, card_uid=None):
        self.log_message("Attempting to save keys from sectors...")
        try:
            if self.sector_tree.topLevelItemCount() == 0:
                self.log_message("No sectors found in the tree. Aborting key save.")
                return
            if not card_uid:
                try:
                    sector_0_item = self.sector_tree.topLevelItem(0)
                    if sector_0_item and sector_0_item.childCount() > 0:
                        block_0_item = sector_0_item.child(0)
                        block_0_data = block_0_item.data(1, Qt.ItemDataRole.UserRole)
                        if not block_0_data:
                            block_0_data = self.clean_hex_data(block_0_item.text(1))
                        if block_0_data and len(block_0_data) >= 8:
                            card_uid = block_0_data[:8].upper()
                            self.log_message(f"从扇区0提取到卡号: {card_uid}")
                except Exception as e:
                    self.log_message(f"提取卡号时出错: {str(e)}")
            keys_to_save = set()
            for i in range(self.sector_tree.topLevelItemCount()):
                sector_item = self.sector_tree.topLevelItem(i)
                key_text = sector_item.text(1)
                if "Key A:" in key_text and "Key B:" in key_text:
                    key_parts = key_text.split('|')
                    if len(key_parts) >= 2:
                        key_a = key_parts[0].split(':')[1].strip().replace(' ', '').upper()
                        key_b = key_parts[1].split(':')[1].strip().replace(' ', '').upper()
                        if len(key_a) == 12 and self.validate_hex_data(key_a):
                            keys_to_save.add(key_a)
                        if len(key_b) == 12 and self.validate_hex_data(key_b):
                            keys_to_save.add(key_b)
            self.log_message(f"Found {len(keys_to_save)} keys to save: {keys_to_save}")
            if keys_to_save:
                saved_count = self.save_keys_to_history(keys_to_save, card_uid)
                if saved_count > 0:
                    if card_uid:
                        self.log_message(f"成功保存 {saved_count} 个新密钥到历史文件 (卡号: {card_uid})")
                    else:
                        self.log_message(f"成功保存 {saved_count} 个新密钥到历史文件")
                else:
                    self.log_message("所有密钥已存在于历史文件中")
            else:
                self.log_message("No new keys to save.")
        except Exception as e:
            self.log_message(f"保存密钥时出错: {str(e)}")
    def save_keys_to_history(self, new_keys, card_uid=None):
        self.log_message(f"Attempting to save {len(new_keys)} new keys to history.")
        try:
            import datetime
            history_file_path = PathManager.get_history_keys_path()
            existing_keys = set()
            if os.path.exists(history_file_path):
                with open(history_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key_part = line.split()[0].upper() if line.split() else ""
                            if len(key_part) == 12:
                                existing_keys.add(key_part)
            self.log_message(f"Found {len(existing_keys)} existing keys in history.")
            keys_to_add = new_keys - existing_keys
            self.log_message(f"Found {len(keys_to_add)} keys to add to history: {keys_to_add}")
            if keys_to_add:
                with open(history_file_path, 'a', encoding='utf-8') as f:
                    if not os.path.exists(history_file_path) or os.path.getsize(history_file_path) == 0:
                        f.write("# 历史密钥文件 - 自动生成\n")
                        f.write("# 格式：密钥 时间 [卡号]\n")
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for key in sorted(keys_to_add):
                        if card_uid:
                            f.write(f"{key} {current_time} {card_uid}\n")
                        else:
                            f.write(f"{key} {current_time}\n")
                return len(keys_to_add)
            return 0
        except Exception as e:
            self.log_message(f"保存历史密钥时出错: {str(e)}")
            return 0
    def load_history_keys(self):
        try:
            history_file_path = PathManager.get_history_keys_path()
            if not os.path.exists(history_file_path):
                return []
            keys = []
            seen_keys = set()
            with open(history_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key_part = line.split()[0].upper() if line.split() else ""
                        if len(key_part) == 12 and self.validate_hex_data(key_part):
                            if key_part not in seen_keys:
                                keys.append(key_part)
                                seen_keys.add(key_part)
            return keys
        except Exception as e:
            self.log_message(f"加载历史密钥时出错: {str(e)}")
            return []
    def show_history_keys(self):
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QMessageBox
            dialog = QDialog(self)
            dialog.setWindowTitle("历史密钥管理")
            dialog.setModal(True)
            dialog.resize(800, 600)
            layout = QVBoxLayout(dialog)
            title_label = QLabel("历史密钥管理")
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(title_label)
            info_label = QLabel("以下是从一键解密中自动保存的历史密钥（包含时间和卡号信息）：")
            layout.addWidget(info_label)
            self.history_text = QTextEdit()
            self.history_text.setReadOnly(True)
            self.history_text.setMaximumBlockCount(500)
            layout.addWidget(self.history_text)
            self.refresh_history_keys_with_info(self.history_text)
            button_layout = QHBoxLayout()
            refresh_btn = QPushButton("刷新")
            refresh_btn.clicked.connect(lambda: self.refresh_history_keys_with_info(self.history_text))
            button_layout.addWidget(refresh_btn)
            clear_btn = QPushButton("清空历史")
            clear_btn.clicked.connect(lambda: self.clear_history_keys(self.history_text))
            clear_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; }")
            button_layout.addWidget(clear_btn)
            button_layout.addStretch()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)
            dialog.exec()
        except Exception as e:
            self.log_message(f"显示历史密钥界面时出错: {str(e)}")
    def refresh_history_keys_with_info(self, text_widget):
        try:
            history_file_path = PathManager.get_history_keys_path()
            if not os.path.exists(history_file_path):
                text_widget.setPlainText("暂无历史密钥记录")
                return
            key_entries = []
            with open(history_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 3:
                            key = parts[0].upper()
                            date = parts[1]
                            time = parts[2]
                            card_uid = parts[3] if len(parts) > 3 else "未知"
                            key_entries.append((key, f"{date} {time}", card_uid))
                        elif len(parts) == 3:
                            key = parts[0].upper()
                            date = parts[1]
                            time = parts[2]
                            key_entries.append((key, f"{date} {time}", "未知"))
            if key_entries:
                unique_keys = {}
                for key, timestamp, card_uid in key_entries:
                    if key not in unique_keys:
                        unique_keys[key] = (timestamp, card_uid)
                key_text = f"共找到 {len(unique_keys)} 个唯一历史密钥：\n\n"
                key_text += f"{'序号':<4} {'密钥':<14} {'保存时间':<20} {'卡号':<12}\n"
                key_text += "-" * 60 + "\n"
                for i, (key, (timestamp, card_uid)) in enumerate(unique_keys.items(), 1):
                    key_text += f"{i:<4} {key:<14} {timestamp:<20} {card_uid:<12}\n"
            else:
                key_text = "暂无历史密钥记录"
            text_widget.setPlainText(key_text)
        except Exception as e:
            text_widget.setPlainText(f"读取历史密钥时出错: {str(e)}")
    def refresh_history_keys(self, text_widget):
        self.refresh_history_keys_with_info(text_widget)
    def clear_history_keys(self, text_widget):
        try:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, '确认清空', 
                                       '确定要清空所有历史密钥吗？\n此操作不可撤销！',
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                history_file_path = PathManager.get_history_keys_path()
                if os.path.exists(history_file_path):
                    os.remove(history_file_path)
                    self.log_message("历史密钥已清空")
                    text_widget.setPlainText("暂无历史密钥记录")
                else:
                    self.log_message("历史密钥文件不存在")
        except Exception as e:
            self.log_message(f"清空历史密钥时出错: {str(e)}")
    def on_load_mfd_from_sector(self):
        if not hasattr(self, 'mfd_parser') or self.mfd_parser is None or not self.mfd_parser.sectors:
            self._mb(QMessageBox.Icon.Warning, "无数据", "扇区工具中没有已加载的数据\n请先读取全卡或导入MFD文件")
            return
        try:
            sectors = self.mfd_parser.sectors
            total = self.mfd_parser.total_sectors
            size = total * 64
            buf = bytearray(size)
            for s in sectors:
                for b in s.blocks:
                    bn = b['block_num']
                    off = bn * 16
                    if off + 16 <= size:
                        buf[off:off+16] = b['data']
            tmp = PathManager.get_temp_file_path(f"sector_write_{int(time.time()*1000)}.mfd")
            with open(tmp, 'wb') as f:
                f.write(buf)
            self.write_mfd_path.setText(tmp)
            self.write_progress.append(f"已从扇区数据加载MFD: {len(sectors)}个扇区, {size}字节")
        except Exception as e:
            self.write_progress.append(f"从扇区加载失败: {e}")

    def on_browse_mfd_for_write(self):
        fd = QFileDialog()
        fd.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        fd.setNameFilter("MFD Files (*.mfd);;All Files (*)")
        if fd.exec() == QFileDialog.DialogCode.Accepted:
            files = fd.selectedFiles()
            if files:
                self.write_mfd_path.setText(files[0])
                self.write_progress.append(f"选择文件: {files[0]}")

    def on_detect_card_write(self):
        if not self.pn532_com or not self.pn532_com.isOpen():
            self.write_progress.append("错误: 串口未连接，请在[工作模式]中先连接设备")
            return
        if not hasattr(self, 'cmd') or not self.cmd:
            self.write_progress.append("错误: 设备未初始化")
            return
        self.write_progress.append("正在检测卡片...")
        try:
            scan_result, supported, card_gen = self._detect_block0_support(scan_result=False, full=True)
            if scan_result:
                tag = scan_result[0]
                uid_hex = tag['uid'].hex().upper() if hasattr(tag['uid'], 'hex') else tag['uid']
                sak_hex = tag['sak'].hex().upper()
                atqa_hex = tag['atqa'].hex().upper()
                self.write_card_info.setText(f"UID: {uid_hex} | SAK: {sak_hex} | ATQA: {atqa_hex}")
                self.write_progress.append(f"检测到卡片: UID={uid_hex} SAK={sak_hex}")
                self.write_card_info.setText(self.write_card_info.text() + f" | {card_gen}")
                self.write_progress.append(f"卡片类型: {card_gen}")
                refresh_idx = self.write_block0_checkbox is not None
                if supported:
                    self.write_progress.append("该卡支持写块0(UID),可勾选\"写入块0(UID)\"再写卡")
                else:
                    self.write_progress.append("该卡不支持写块0(UID),已自动取消勾选,写卡将跳过块0")
                    if refresh_idx:
                        if self.write_block0_checkbox.isChecked():
                            self.write_block0_checkbox.setChecked(False)
            else:
                self.write_progress.append("未检测到卡片，请确认卡片已放在读卡器上")
        except Exception as e:
            self.write_progress.append(f"检测失败: {str(e)}")

    def _detect_block0_support(self, scan_result=None, full=False):
        """检测卡片,并判断该卡是否支持写块0(UID)。

        Returns:
          full=False -> (supported, card_gen)
          full=True  -> (scan_result, supported, card_gen)
        """
        supported = False
        card_gen = "Unknown"
        if scan_result is None:
            try:
                scan_result = self.cmd.hf_14a_scan()
            except Exception:
                scan_result = None
        if not scan_result:
            if full:
                return None, False, card_gen
            return False, card_gen
        tag = scan_result[0]
        if hasattr(tag, 'get'):
            sak = tag.get('sak', b'') if isinstance(tag.get('sak'), bytes) else bytes([tag.get('sak', 0)])
        else:
            sak = b'\x08'
        # 卡类型识别
        gen = "Standard"
        try:
            from card_operations import UidOperator
            gen = UidOperator(self.cmd)._detect_gen(scan_result)
        except Exception:
            gen = "Standard"
        card_gen = gen
        # 块0可写的条件: CUID/UID/FUID/UFUID(Gen3/Gen4/Gen1A) 支持; 标准 MIFARE Classic 不支持
        supported = gen != "Standard"
        if full:
            return scan_result, supported, card_gen
        return supported, card_gen

    def on_start_write_card(self):
        if not self.pn532_com or not self.pn532_com.isOpen():
            self._log(self.write_progress, "错误: 串口未连接")
            self._mb(QMessageBox.Icon.Warning, "错误", "请先在[工作模式]中连接设备")
            return
        if not hasattr(self, 'cmd') or not self.cmd:
            self._log(self.write_progress, "错误: 设备未初始化")
            return
        mfd_path = self.write_mfd_path.text().strip()
        if not mfd_path:
            self._log(self.write_progress, "错误: 请选择MFD文件")
            self._mb(QMessageBox.Icon.Warning, "错误", "请选择要写入的MFD文件")
            return
        if not os.path.exists(mfd_path):
            self._log(self.write_progress, f"错误: MFD文件不存在: {mfd_path}")
            return
        key_text = self.write_key_input.text().strip()
        if not key_text:
            key_text = "FFFFFFFFFFFF"
        if len(key_text) != 12:
            self._log(self.write_progress, "错误: 密钥必须为12位十六进制字符")
            return
        write_block0 = self.write_block0_checkbox.isChecked()
        force_write_block0 = False

        # 写卡前检测卡类型:避免在标准卡/不支持写块0的卡上误写块0造成损坏
        block0_supported, card_gen = self._detect_block0_support()
        if write_block0:
            if not block0_supported:
                # 检测为不支持写块0,弹窗让用户选择:取消勾选 or 强制写入(用户自知是CUID)
                reply = QMessageBox.warning(self, i18n.get_text('write_block0_title'),
                    i18n.get_text('write_block0_force_msg').format(card_gen=card_gen),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    force_write_block0 = True
                    self._log(self.write_progress,
                        f"检测到该卡为[{card_gen}],但用户选择强制写入块0(CUID/UID卡)")
                else:
                    self.write_block0_checkbox.setChecked(False)
                    write_block0 = False
                    self._log(self.write_progress,
                        f"检测到该卡为[{card_gen}],不支持写块0,已自动取消勾选\"写入块0(UID)\"")
            else:
                reply = QMessageBox.warning(self, i18n.get_text('write_block0_title'),
                    i18n.get_text('write_block0_msg_supported').format(card_gen=card_gen),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    self._log(self.write_progress, "用户取消了写入块0")
                    return

        self.write_progress.clear()
        self._log(self.write_progress, "===== 开始写卡 =====")
        self._log(self.write_progress, f"MFD: {os.path.basename(mfd_path)}")
        self._log(self.write_progress, f"密钥: {key_text}")
        self._log(self.write_progress, f"写入块0: {'是' if write_block0 else '否'}")
        self._log(self.write_progress, "块0写入策略: CUID→标准写 | UID/FUID/UFUID→Gen1A解锁写 | 普通卡→跳过")

        self.write_detect_btn.setEnabled(False)
        self.write_start_btn.setEnabled(False)
        self.write_mfd_btn.setEnabled(False)
        self.write_stop_btn.setEnabled(True)
        if hasattr(self, 'write_progressbar'):
            self.write_progressbar.setVisible(True)
            self.write_progressbar.setRange(0, 0)

        try:
            with open(mfd_path, 'rb') as f:
                mfd_data = f.read()
        except Exception as e:
            self._log(self.write_progress, f"错误: 读取MFD文件失败: {e}")
            self.write_detect_btn.setEnabled(True)
            self.write_start_btn.setEnabled(True)
            self.write_mfd_btn.setEnabled(True)
            self.write_stop_btn.setEnabled(False)
            if hasattr(self, 'write_progressbar'):
                self.write_progressbar.setVisible(False)
            return

        self._log(self.write_progress, f"读取MFD文件: {os.path.basename(mfd_path)} ({len(mfd_data)} bytes)")

        scan_result = self.cmd.hf_14a_scan()
        if not scan_result:
            self._log(self.write_progress, "错误: 未检测到卡片")
            self.write_detect_btn.setEnabled(True)
            self.write_start_btn.setEnabled(True)
            self.write_mfd_btn.setEnabled(True)
            self.write_stop_btn.setEnabled(False)
            if hasattr(self, 'write_progressbar'):
                self.write_progressbar.setVisible(False)
            return

        uid = scan_result[0]['uid']
        self._log(self.write_progress, f"卡片 UID: {uid.hex().upper()}")

        # 选:写卡前先读卡获取真实密钥
        card_keys = {}
        if getattr(self, 'write_read_keys_check', None) and self.write_read_keys_check.isChecked():
            self.write_progress.append("正在读取卡片密钥(写卡前认证用)...")
            for sector in range(16):
                tb = sector * 4 + 3
                try:
                    self.cmd.hf_14a_scan()
                    resp = self.cmd.mf1_read_block(tb, bytes.fromhex(key_text))
                    if resp and resp.parsed and len(resp.parsed) >= 16:
                        ka = bytes(resp.parsed[:6])
                        card_keys[sector] = ka
                except Exception:
                    pass
            if card_keys:
                self.write_progress.append(f"已获取 {len(card_keys)}/16 个扇区的真实密钥")
            else:
                self.write_progress.append("未获取到任何扇区密钥,使用 MFD 默认密钥")

        self.write_thread = WriteCardThread(
            self.cmd, mfd_data, uid, bytes.fromhex(key_text), write_block0, card_keys,
            force_write_block0=force_write_block0
        )
        self.write_thread.progress.connect(self.on_write_progress)
        self.write_thread.finished.connect(self.on_write_finished)
        self.write_thread.start()

    def on_write_progress(self, msg):
        self.write_progress.append(msg)
        # 解析 "[N/Total]" 格式自动更新进度条
        if hasattr(self, 'write_progressbar'):
            import re as _re
            m = _re.match(r'^\[(\d+)/(\d+)\]', msg)
            if m:
                cur, total = int(m.group(1)), int(m.group(2))
                self.write_progressbar.setRange(0, total)
                self.write_progressbar.setValue(cur)

    def on_write_finished(self, success, msg):
        self.write_detect_btn.setEnabled(True)
        self.write_start_btn.setEnabled(True)
        self.write_mfd_btn.setEnabled(True)
        self.write_stop_btn.setEnabled(False)
        if hasattr(self, 'write_progressbar'):
            self.write_progressbar.setVisible(False)
        if success:
            self.write_progress.append(f"写卡完成: {msg}")
            self.log_message_work_mode(f"写卡完成: {msg}")
        else:
            self.write_progress.append(f"写卡失败: {msg}")
            self.log_message_work_mode(f"写卡失败: {msg}")

    def on_write_card_cancel(self):
        if hasattr(self, 'write_thread') and self.write_thread and self.write_thread.isRunning():
            self.write_thread.cancel()
            self.write_thread.wait(3000)
            self.write_progress.append("正在停止写卡...")
            self.write_stop_btn.setEnabled(False)

    def init_card_tools_tab(self):
        layout = QVBoxLayout(self.card_tools_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { background: #fff; border: 1px solid #ddd; border-radius: 4px; }
            QTabBar::tab { padding: 6px 16px; font-size: 12px; border: 1px solid #ddd; border-bottom: none; border-radius: 4px 4px 0 0; margin-right: 2px; }
            QTabBar::tab:selected { background: #fff; color: #007bff; border-bottom: 2px solid #007bff; }
        """)

        # --- Read Dump tab ---
        read_tab = QWidget()
        read_layout = QVBoxLayout(read_tab)
        read_layout.setSpacing(4)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel(i18n.get_text('save_to')))
        self.dump_path = QLineEdit()
        self.dump_path.setPlaceholderText(i18n.get_text('dump_placeholder'))
        r1.addWidget(self.dump_path)
        self.dump_browse_btn = QPushButton(i18n.get_text('browse'))
        self.dump_browse_btn.clicked.connect(lambda: self._browse_save("dump"))
        r1.addWidget(self.dump_browse_btn)
        read_layout.addLayout(r1)

        r2 = QHBoxLayout()
        self.dump_custom_only = QCheckBox(i18n.get_text('custom_keys_only'))
        self.dump_custom_only.setStyleSheet("font-size:11px;color:#dc3545;font-weight:bold;")
        r2.addWidget(self.dump_custom_only)
        self.dump_keyfile_btn = QPushButton(i18n.get_text('key_file_btn'))
        self.dump_keyfile_btn.setFixedHeight(26)
        self.dump_keyfile_btn.setStyleSheet("font-size:10px;background:#6c757d;color:#fff;border:none;border-radius:4px;padding:2px 8px;")
        self.dump_keyfile_btn.clicked.connect(self._on_dump_select_keyfile)
        self.dump_keyfile_btn.setToolTip(i18n.get_text('key_format_hint'))
        r2.addWidget(self.dump_keyfile_btn)
        r2.addWidget(QLabel(i18n.get_text('default_key')))
        self.dump_key_input = QLineEdit("FFFFFFFFFFFF")
        self.dump_key_input.setMaxLength(12)
        self.dump_key_input.setFixedWidth(100)
        r2.addWidget(self.dump_key_input)
        self.dump_use_history = QCheckBox(i18n.get_text('use_history'))
        self.dump_use_history.setChecked(True)
        self.dump_use_history.setStyleSheet("font-size:11px;")
        r2.addWidget(self.dump_use_history)
        self.dump_read_btn = QPushButton(i18n.get_text('start_read'))
        self.dump_read_btn.clicked.connect(self.on_dump_read)
        self.dump_read_btn.setStyleSheet("background:#28a745;color:#fff;border:none;border-radius:4px;padding:4px 16px;")
        r2.addWidget(self.dump_read_btn)
        self.dump_cancel_btn = QPushButton(i18n.get_text('stop'))
        self.dump_cancel_btn.clicked.connect(self.on_dump_cancel)
        self.dump_cancel_btn.setVisible(False)
        self.dump_cancel_btn.setStyleSheet("background:#dc3545;color:#fff;border:none;border-radius:4px;padding:4px 16px;")
        r2.addWidget(self.dump_cancel_btn)
        r2.addWidget(QLabel("   "))
        read_layout.addLayout(r2)

        self.dump_progress = QTextEdit()
        self.dump_progress.setReadOnly(True)
        self.dump_progress.setMaximumHeight(200)
        self.dump_progress.setMaximumBlockCount(500)  # 防止长会话日志无限增长
        self.dump_progress.setStyleSheet("font-family:Consolas;font-size:11px;")
        read_layout.addWidget(self.dump_progress)
        self.dump_progressbar = QProgressBar()
        self.dump_progressbar.setRange(0, 16)
        self.dump_progressbar.setValue(0)
        self.dump_progressbar.setFormat("扇区 %v / %m")
        self.dump_progressbar.setVisible(False)
        read_layout.addWidget(self.dump_progressbar)

        tabs.addTab(read_tab, i18n.get_text('tab_read_full'))

        # --- UID Modify tab ---
        uid_tab = QWidget()
        uid_layout = QVBoxLayout(uid_tab)
        uid_layout.setSpacing(4)
        u1 = QHBoxLayout()
        u1.addWidget(QLabel(i18n.get_text('new_uid')))
        self.uid_new_input = QLineEdit()
        self.uid_new_input.setMaxLength(8)
        self.uid_new_input.setFixedWidth(100)
        self.uid_new_input.setPlaceholderText(i18n.get_text('uid_placeholder'))
        u1.addWidget(self.uid_new_input)
        self.uid_detect_btn = QPushButton(i18n.get_text('detect_card'))
        self.uid_detect_btn.clicked.connect(self.on_uid_detect)
        u1.addWidget(self.uid_detect_btn)
        self.uid_set_btn = QPushButton(i18n.get_text('write_new_uid'))
        self.uid_set_btn.clicked.connect(self.on_uid_set)
        self.uid_set_btn.setStyleSheet("background:#ffc107;color:#000;border:none;border-radius:4px;padding:4px 16px;")
        u1.addWidget(self.uid_set_btn)
        u1.addStretch()
        uid_layout.addLayout(u1)
        self.uid_progress = QTextEdit()
        self.uid_progress.setReadOnly(True)
        self.uid_progress.setMaximumHeight(200)
        self.uid_progress.setMaximumBlockCount(500)
        self.uid_progress.setStyleSheet("font-family:Consolas;font-size:11px;")
        uid_layout.addWidget(self.uid_progress)
        tabs.addTab(uid_tab, i18n.get_text('tab_modify_uid'))

        # --- Manual Block tab ---
        mb_tab = QWidget()
        mb_layout = QVBoxLayout(mb_tab)
        mb_layout.setSpacing(4)
        m1 = QHBoxLayout()
        m1.addWidget(QLabel(i18n.get_text('block_num')))
        self.mb_block = QSpinBox()
        self.mb_block.setRange(0, 255)  # 支持 MIFARE Classic 4K 高扇区(块 64-255)
        self.mb_block.setFixedWidth(60)
        m1.addWidget(self.mb_block)
        m1.addWidget(QLabel(i18n.get_text('key_colon')))
        self.mb_key = QLineEdit("FFFFFFFFFFFF")
        self.mb_key.setMaxLength(12)
        self.mb_key.setFixedWidth(100)
        m1.addWidget(self.mb_key)
        # 显式 Key A/B 选择 (默认 Auto = 自动尝试)
        m1.addWidget(QLabel(i18n.get_text('key_type')))
        self.mb_key_type = QComboBox()
        self.mb_key_type.addItems(["Auto (A→B)", "Key A", "Key B"])
        m1.addWidget(self.mb_key_type)
        m1.addStretch()
        self.mb_read_btn = QPushButton(i18n.get_text('read'))
        self.mb_read_btn.clicked.connect(self.on_mb_read)
        m1.addWidget(self.mb_read_btn)
        self.mb_write_btn = QPushButton(i18n.get_text('write'))
        self.mb_write_btn.clicked.connect(self.on_mb_write)
        m1.addWidget(self.mb_write_btn)
        mb_layout.addLayout(m1)
        m2 = QHBoxLayout()
        m2.addWidget(QLabel(i18n.get_text('data_32hex')))
        self.mb_data = QLineEdit()
        self.mb_data.setPlaceholderText(i18n.get_text('data_placeholder'))
        self.mb_data.setStyleSheet("font-family:Consolas;")
        m2.addWidget(self.mb_data)
        mb_layout.addLayout(m2)
        self.mb_progress = QTextEdit()
        self.mb_progress.setReadOnly(True)
        self.mb_progress.setMaximumHeight(150)
        self.mb_progress.setMaximumBlockCount(500)
        self.mb_progress.setStyleSheet("font-family:Consolas;font-size:11px;")
        mb_layout.addWidget(self.mb_progress)
        tabs.addTab(mb_tab, i18n.get_text('tab_manual_block'))

        # --- Card Detect tab ---
        det_tab = QWidget()
        det_layout = QVBoxLayout(det_tab)
        det_layout.setSpacing(4)
        d1 = QHBoxLayout()
        self.det_btn = QPushButton(i18n.get_text('detect_card_type'))
        self.det_btn.clicked.connect(self.on_detect_card)
        self.det_btn.setStyleSheet("background:#17a2b8;color:#fff;border:none;border-radius:4px;padding:6px 20px;")
        d1.addWidget(self.det_btn)
        d1.addStretch()
        det_layout.addLayout(d1)
        self.det_info = QTextEdit()
        self.det_info.setReadOnly(True)
        self.det_info.setMaximumHeight(200)
        self.det_info.setMaximumBlockCount(500)
        self.det_info.setStyleSheet("font-family:Consolas;font-size:12px;")
        det_layout.addWidget(self.det_info)
        tabs.addTab(det_tab, i18n.get_text('tab_card_detect'))

        # --- Write Card tab ---
        write_tab = QWidget()
        write_layout = QVBoxLayout(write_tab)
        write_layout.setSpacing(4)
        w1 = QHBoxLayout()
        w1.addWidget(QLabel(i18n.get_text('mfd_file')))
        self.write_mfd_path = QLineEdit()
        self.write_mfd_path.setPlaceholderText(i18n.get_text('mfd_placeholder'))
        self.write_mfd_path.setStyleSheet("font-size: 12px; padding: 3px 6px; border: 1px solid #e0e0e0; border-radius: 4px;")
        self.write_mfd_btn = QPushButton(i18n.get_text('browse'))
        self.write_mfd_btn.setFixedHeight(28)
        self.write_mfd_btn.setStyleSheet("font-size: 11px; background-color: #6c757d; color: white; border: none; border-radius: 4px; padding: 2px 10px;")
        self.write_mfd_btn.clicked.connect(self.on_browse_mfd_for_write)
        self.load_sector_btn = QPushButton(i18n.get_text('load_from_sector'))
        self.load_sector_btn.setFixedHeight(28)
        self.load_sector_btn.setStyleSheet("font-size: 11px; background-color: #17a2b8; color: white; border: none; border-radius: 4px; padding: 2px 10px;")
        self.load_sector_btn.clicked.connect(self.on_load_mfd_from_sector)
        w1.addWidget(self.write_mfd_path, 1)
        w1.addWidget(self.load_sector_btn)
        w1.addWidget(self.write_mfd_btn)
        write_layout.addLayout(w1)
        w2 = QHBoxLayout()
        w2.addWidget(QLabel(i18n.get_text('default_key')))
        self.write_key_input = QLineEdit("FFFFFFFFFFFF")
        self.write_key_input.setMaxLength(12)
        self.write_key_input.setFixedWidth(100)
        self.write_key_input.setStyleSheet("font-size: 12px; padding: 3px 6px; border: 1px solid #e0e0e0; border-radius: 4px;")
        w2.addWidget(self.write_key_input)
        self.write_block0_checkbox = QCheckBox(i18n.get_text('write_block0'))
        self.write_block0_checkbox.setChecked(True)
        self.write_block0_checkbox.setToolTip(i18n.get_text('write_block0_tip'))
        self.write_block0_checkbox.setStyleSheet("font-size: 12px; spacing: 4px;")
        w2.addWidget(self.write_block0_checkbox)
        self.write_read_keys_check = QCheckBox(i18n.get_text('read_keys_before_write'))
        self.write_read_keys_check.setChecked(True)
        self.write_read_keys_check.setToolTip(i18n.get_text('read_keys_before_write_tip'))
        self.write_read_keys_check.setStyleSheet("font-size:11px;color:#8B4513;")
        w2.addWidget(self.write_read_keys_check)
        self.write_detect_btn = QPushButton(i18n.get_text('detect_card_write'))
        self.write_detect_btn.setFixedHeight(28)
        self.write_detect_btn.setStyleSheet("font-size: 11px; background-color: #17a2b8; color: white; border: none; border-radius: 4px; padding: 2px 10px;")
        self.write_detect_btn.clicked.connect(self.on_detect_card_write)
        w2.addWidget(self.write_detect_btn)
        self.write_start_btn = QPushButton(i18n.get_text('start_write'))
        self.write_start_btn.setFixedHeight(28)
        self.write_start_btn.setStyleSheet("font-size: 11px; background-color: #28a745; color: white; border: none; border-radius: 4px; padding: 2px 10px;")
        self.write_start_btn.clicked.connect(self.on_start_write_card)
        w2.addWidget(self.write_start_btn)
        self.write_stop_btn = QPushButton(i18n.get_text('stop'))
        self.write_stop_btn.setFixedHeight(28)
        self.write_stop_btn.setEnabled(False)
        self.write_stop_btn.setStyleSheet("font-size: 11px; background-color: #dc3545; color: white; border: none; border-radius: 4px; padding: 2px 10px;")
        self.write_stop_btn.clicked.connect(self.on_write_card_cancel)
        w2.addWidget(self.write_stop_btn)
        w2.addStretch()
        write_layout.addLayout(w2)
        self.write_card_info = QLabel(i18n.get_text('no_card'))
        self.write_card_info.setStyleSheet("font-size: 12px; color: #6c757d; padding: 2px 4px;")
        write_layout.addWidget(self.write_card_info)
        hint = QLabel(i18n.get_text('write_hint'))
        hint.setStyleSheet("font-size: 10px; color: #888;")
        hint.setWordWrap(True)
        write_layout.addWidget(hint)
        self.write_progress = QTextEdit()
        self.write_progress.setReadOnly(True)
        self.write_progress.setMaximumHeight(120)
        self.write_progress.setMaximumBlockCount(500)
        self.write_progress.setStyleSheet("background-color: #ffffff; color: #333333; border: 1px solid #e0e0e0; border-radius: 4px; padding: 4px; font-family: Consolas, Monaco, monospace; font-size: 11px;")
        write_layout.addWidget(self.write_progress)
        self.write_progressbar = QProgressBar()
        self.write_progressbar.setRange(0, 64)
        self.write_progressbar.setValue(0)
        self.write_progressbar.setFormat(i18n.get_text('write_progress_format'))
        self.write_progressbar.setVisible(False)
        write_layout.addWidget(self.write_progressbar)

        write_layout.addSpacing(8)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        write_layout.addWidget(sep)
        self.fmt_group = QGroupBox(i18n.get_text('format_card'))
        fmt_layout = QVBoxLayout(self.fmt_group)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(i18n.get_text('format_key')))
        self.fmt_key = QLineEdit("FFFFFFFFFFFF")
        self.fmt_key.setMaxLength(12)
        self.fmt_key.setFixedWidth(100)
        fmt_row.addWidget(self.fmt_key)
        self.fmt_use_history = QCheckBox(i18n.get_text('use_history'))
        self.fmt_use_history.setChecked(True)
        self.fmt_use_history.setStyleSheet("font-size:11px;color:#555;")
        fmt_row.addWidget(self.fmt_use_history)
        self.fmt_keyfile_btn = QPushButton(i18n.get_text('key_file_btn'))
        self.fmt_keyfile_btn.setFixedHeight(24)
        self.fmt_keyfile_btn.setStyleSheet("font-size:10px;background:#6c757d;color:#fff;border:none;border-radius:4px;padding:2px 8px;")
        self.fmt_keyfile_btn.clicked.connect(self._on_fmt_select_keyfile)
        self.fmt_keyfile_btn.setToolTip(i18n.get_text('key_format_hint'))
        fmt_row.addWidget(self.fmt_keyfile_btn)
        self.fmt_btn = QPushButton(i18n.get_text('format_card'))
        self.fmt_btn.setStyleSheet("background:#dc3545;color:#fff;border:none;border-radius:4px;padding:4px 16px;")
        self.fmt_btn.clicked.connect(self.on_format_card)
        fmt_row.addWidget(self.fmt_btn)
        self.fmt_cancel_btn = QPushButton(i18n.get_text('stop'))
        self.fmt_cancel_btn.setStyleSheet("background:#6c757d;color:#fff;border:none;border-radius:4px;padding:4px 16px;")
        self.fmt_cancel_btn.clicked.connect(self.on_format_cancel)
        self.fmt_cancel_btn.setVisible(False)
        fmt_row.addWidget(self.fmt_cancel_btn)
        fmt_row.addStretch()
        fmt_layout.addLayout(fmt_row)
        self.fmt_progress = QTextEdit()
        self.fmt_progress.setReadOnly(True)
        self.fmt_progress.setMaximumHeight(100)
        self.fmt_progress.setMaximumBlockCount(500)
        self.fmt_progress.setStyleSheet("font-family:Consolas;font-size:11px;background:#fff5f5;")
        fmt_layout.addWidget(self.fmt_progress)
        write_layout.addWidget(self.fmt_group)
        tabs.addTab(write_tab, i18n.get_text('tab_write_card'))

        layout.addWidget(tabs)

    def init_ntag_tab(self):
        layout = QVBoxLayout(self.ntag_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        n1 = QHBoxLayout()
        self.ntag_read_btn = QPushButton(i18n.get_text('read_ntag'))
        self.ntag_read_btn.clicked.connect(self.on_ntag_read)
        self.ntag_read_btn.setStyleSheet("background:#28a745;color:#fff;border:none;border-radius:4px;padding:6px 20px;")
        self.ntag_write_btn = QPushButton(i18n.get_text('write_ndef_url'))
        self.ntag_write_btn.clicked.connect(self.on_ntag_write)
        self.ntag_write_btn.setStyleSheet("background:#ffc107;color:#000;border:none;border-radius:4px;padding:6px 20px;")
        n1.addWidget(self.ntag_read_btn)
        n1.addWidget(self.ntag_write_btn)
        n1.addWidget(QLabel("URL:"))
        self.ntag_url = QLineEdit("https://example.com")
        n1.addWidget(self.ntag_url, 1)
        layout.addLayout(n1)
        self.ntag_progress = QTextEdit()
        self.ntag_progress.setReadOnly(True)
        self.ntag_progress.setMaximumBlockCount(500)
        self.ntag_progress.setStyleSheet("font-family:Consolas;font-size:11px;")
        layout.addWidget(self.ntag_progress)

    def init_advanced_tab(self):
        layout = QVBoxLayout(self.advanced_tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # ===== ISO15693 区 =====
        self.iso_group = QGroupBox(i18n.get_text('iso_group'))
        iso_layout = QVBoxLayout(self.iso_group)
        iso_row = QHBoxLayout()
        self.iso_scan_btn = QPushButton(i18n.get_text('scan'))
        self.iso_scan_btn.clicked.connect(self.on_iso_scan)
        self.iso_info_btn = QPushButton(i18n.get_text('read_info'))
        self.iso_info_btn.clicked.connect(self.on_iso_info)
        iso_layout.addLayout(iso_row)
        iso_row.addWidget(self.iso_scan_btn)
        iso_row.addWidget(self.iso_info_btn)
        iso_row.addWidget(QLabel(i18n.get_text('block_num')))
        self.iso_block_input = QSpinBox()
        self.iso_block_input.setRange(0, 255)
        iso_row.addWidget(self.iso_block_input)
        self.iso_read_btn = QPushButton(i18n.get_text('read_block'))
        self.iso_read_btn.clicked.connect(self.on_iso_read)
        self.iso_write_btn = QPushButton(i18n.get_text('write_block'))
        self.iso_write_btn.clicked.connect(self.on_iso_write)
        iso_row.addWidget(self.iso_read_btn)
        iso_row.addWidget(self.iso_write_btn)
        self.iso_progress = QTextEdit()
        self.iso_progress.setReadOnly(True)
        self.iso_progress.setMaximumBlockCount(500)
        self.iso_progress.setStyleSheet("font-family:Consolas;font-size:11px;")
        iso_layout.addWidget(self.iso_progress)
        layout.addWidget(self.iso_group)

        # ===== EM4100 区 =====
        self.em_group = QGroupBox(i18n.get_text('em_group'))
        em_layout = QVBoxLayout(self.em_group)
        em_row = QHBoxLayout()
        self.em_scan_btn = QPushButton(i18n.get_text('scan'))
        self.em_scan_btn.clicked.connect(self.on_em_scan)
        em_row.addWidget(self.em_scan_btn)
        em_layout.addLayout(em_row)
        self.em_progress = QTextEdit()
        self.em_progress.setReadOnly(True)
        self.em_progress.setMaximumBlockCount(500)
        self.em_progress.setStyleSheet("font-family:Consolas;font-size:11px;")
        em_layout.addWidget(self.em_progress)
        layout.addWidget(self.em_group)
        layout.addStretch(1)

    # ===== Action Handlers =====
    def _browse_file(self, lineedit):
        fd = QFileDialog()
        fd.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        fd.setNameFilter("All Files (*)")
        if fd.exec() == QFileDialog.DialogCode.Accepted:
            files = fd.selectedFiles()
            if files: lineedit.setText(files[0])

    def _browse_save(self, prefix):
        fd = QFileDialog()
        fd.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        if prefix == "dump":
            fd.setNameFilter("MFD Files (*.mfd);;All Files (*)")
            fd.selectFile(f"dump_{time.strftime('%Y%m%d_%H%M%S')}.mfd")
        if fd.exec() == QFileDialog.DialogCode.Accepted:
            files = fd.selectedFiles()
            if files:
                if prefix == "dump":
                    self.dump_path.setText(files[0])

    def _check_serial(self):
        if not self.pn532_com or not self.pn532_com.isOpen():
            self._mb(QMessageBox.Icon.Warning, "错误", "请先在[工作模式]中连接设备")
            return False
        if not hasattr(self, 'cmd') or not self.cmd:
            self._mb(QMessageBox.Icon.Warning, "错误", "请先在[工作模式]中连接设备")
            return False
        return True

    def _log(self, widget, msg):
        """线程安全的日志追加。依赖 Qt 信号自动 queued connection,不调用 processEvents。"""
        try:
            if widget is None:
                return
            if i18n.current_language != 'zh':
                msg = i18n.tr(msg)
            # 兜底:若上游漏配 blockCount,运行时再补一次(避免无限增长)
            try:
                if widget.maximumBlockCount() <= 0:
                    widget.setMaximumBlockCount(500)
            except Exception:
                pass
            widget.append(msg)
        except RuntimeError:
            # widget 已被销毁(关闭事件),静默忽略
            pass

    # Dump Reader
    def _on_dump_select_keyfile(self):
        fd = QFileDialog()
        fd.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        fd.setNameFilter("密钥文件 (*.txt *.key *.mfd *.dic);;All Files (*)")
        if fd.exec() == QFileDialog.DialogCode.Accepted:
            files = fd.selectedFiles()
            if files:
                self.dump_keyfile_path = files[0]
                self._log(self.dump_progress, f"密钥文件: {files[0]}")

    def _load_keys_from_file(self, path):
        keys = []
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('//'):
                        continue
                    for token in line.replace(',', ' ').replace(';', ' ').replace('\t', ' ').split():
                        token = token.strip().replace('-', '').replace(' ', '')
                        clean = ''.join(c for c in token if c in '0123456789abcdefABCDEF')
                        if len(clean) == 12:
                            keys.append(bytes.fromhex(clean))
                        elif len(clean) == 10:
                            keys.append(bytes.fromhex(clean))
            if keys:
                self._log(self.dump_progress, f"从文件加载 {len(keys)} 个自定义密钥")
        except Exception as e:
            self._log(self.dump_progress, f"读取密钥文件失败: {e}")
        return keys

    def on_dump_read(self):
        if not self._check_serial(): return
        out = self.dump_path.text().strip()
        if not out:
            out_dir = PathManager.get_output_dir()
            out = os.path.join(out_dir, f"dump_{time.strftime('%Y%m%d_%H%M%S')}.mfd")
            self.dump_path.setText(out)
        key = self.dump_key_input.text().strip() or "FFFFFFFFFFFF"
        history = []
        if self.dump_use_history.isChecked():
            try:
                history = self.load_history_keys()
            except:
                pass
        custom_keys = []
        if hasattr(self, 'dump_keyfile_path') and self.dump_keyfile_path:
            custom_keys = self._load_keys_from_file(self.dump_keyfile_path)
        custom_only = self.dump_custom_only.isChecked()
        self.dump_progress.clear()
        self.dump_read_btn.setEnabled(False)
        self.dump_cancel_btn.setVisible(True)
        self._log(self.dump_progress, f"输出: {out}")
        self._log(self.dump_progress, f"默认密钥: {key}")
        if custom_only:
            self._log(self.dump_progress, "模式: 仅自定义密钥(禁用内置弱口令)")
            history = custom_keys
        else:
            self._log(self.dump_progress, f"历史密钥: {len(history)}个  自定义文件: {len(custom_keys)}个")

        self.dump_thread = DumpReadThread(self.cmd, bytes.fromhex(key), history, custom_keys, custom_only)
        self.dump_thread.progress.connect(self._on_dump_progress)
        self.dump_thread.finished.connect(lambda *a: self._dump_finished(*a, out))
        self.dump_progressbar.setRange(0, 16)
        self.dump_progressbar.setValue(0)
        self.dump_progressbar.setVisible(True)
        self.dump_thread.start()

    def _on_dump_progress(self, msg):
        self._log(self.dump_progress, msg)
        # 解析 "扇区 N" 自动更新进度条
        import re as _re
        m = _re.search(r'扇区\s*(\d+)', msg)
        if m and hasattr(self, 'dump_progressbar'):
            sector = int(m.group(1))
            self.dump_progressbar.setValue(sector + 1)

    def on_dump_cancel(self):
        if hasattr(self, 'dump_thread') and self.dump_thread and self.dump_thread.isRunning():
            self.dump_thread.cancel()
            self.dump_thread.wait()
            self._log(self.dump_progress, "读取已取消")
        self.dump_read_btn.setEnabled(True)
        self.dump_cancel_btn.setVisible(False)

    def _dump_finished(self, *args):
        self.dump_read_btn.setEnabled(True)
        self.dump_cancel_btn.setVisible(False)
        if hasattr(self, 'dump_progressbar'):
            self.dump_progressbar.setVisible(False)
        ok = args[0] if len(args) > 0 else False
        out = args[-1] if len(args) > 1 else ""
        data = args[1] if len(args) >= 2 and isinstance(args[1], (bytes, bytearray)) else None
        if ok and data:
            try:
                with open(out, 'wb') as f:
                    f.write(bytes(data))
                self._log(self.dump_progress, f"MFD已保存: {out}")
                if self.load_sector_data_from_mfd(out):
                    self._log(self.dump_progress, "数据已自动加载到扇区工具")
                    self.tab_widget.setCurrentIndex(2)
            except Exception as e:
                self._log(self.dump_progress, f"保存失败: {e}")
        else:
            msg = args[1] if len(args) >= 2 and isinstance(args[1], str) else "读取失败"
            self._log(self.dump_progress, f"未保存: {msg}")


    # Format
    def on_format_card(self):
        if not self._check_serial(): return
        key = self.fmt_key.text().strip() or "FFFFFFFFFFFF"
        reply = QMessageBox.warning(self, i18n.get_text('format_confirm_title'),
            i18n.get_text('format_confirm_msg'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        self.fmt_progress.clear()
        self.fmt_btn.setEnabled(False)
        self.fmt_cancel_btn.setVisible(True)

        extra = []
        if self.fmt_use_history.isChecked():
            try:
                extra = self.load_history_keys()
            except Exception:
                pass
        if hasattr(self, 'fmt_keyfile_path') and self.fmt_keyfile_path:
            try:
                custom = self._load_keys_from_file(self.fmt_keyfile_path)
                for k in custom:
                    if k not in extra:
                        extra.append(k)
            except Exception:
                pass
        if extra:
            self._log(self.fmt_progress, f"已加载 {len(extra)} 个额外密钥")

        scan = self.cmd.hf_14a_scan()
        if not scan:
            self._log(self.fmt_progress, "未检测到卡片")
            self.fmt_btn.setEnabled(True)
            self.fmt_cancel_btn.setVisible(False)
            return
        uid = scan[0]['uid']
        self._log(self.fmt_progress, f"UID: {uid.hex().upper()}")
        self._log(self.fmt_progress, "正在格式化，请稍候...")
        self.fmt_thread = FormatCardThread(self.cmd, uid, key, extra_keys=extra)
        self.fmt_thread.progress.connect(lambda m: self._log(self.fmt_progress, m))
        self.fmt_thread.finished.connect(self._on_format_done)
        self.fmt_thread.start()

    def _on_fmt_select_keyfile(self):
        fd = QFileDialog()
        fd.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        fd.setNameFilter("密钥文件 (*.txt *.key *.mfd *.dic);;所有文件 (*)")
        if fd.exec() == QFileDialog.DialogCode.Accepted:
            files = fd.selectedFiles()
            if files:
                self.fmt_keyfile_path = files[0]
                self._log(self.fmt_progress, f"已选择密钥文件: {files[0]}")

    def _on_format_done(self, ok, msg):
        self.fmt_btn.setEnabled(True)
        self.fmt_cancel_btn.setVisible(False)
        self.fmt_thread = None
        self._log(self.fmt_progress, msg)

    def on_format_cancel(self):
        if hasattr(self, 'fmt_thread') and self.fmt_thread and self.fmt_thread.isRunning():
            self.fmt_thread.cancel()
            self.fmt_thread.wait()
            self._log(self.fmt_progress, "格式化已取消")
            self.fmt_btn.setEnabled(True)
            self.fmt_cancel_btn.setVisible(False)

    # UID
    def on_uid_detect(self):
        if not self._check_serial(): return
        self.uid_progress.clear()
        scan = self.cmd.hf_14a_scan()
        if not scan:
            self._log(self.uid_progress, "未检测到卡片")
            return
        uid = scan[0]['uid'].hex().upper()
        self._log(self.uid_progress, f"当前UID: {uid}")
        det = CardDetector(self.cmd)
        info = det.detect(lambda m: self._log(self.uid_progress, m))
        for k, v in info.items():
            self._log(self.uid_progress, f"  {k}: {v}")

    def on_uid_set(self):
        if not self._check_serial(): return
        new_uid = self.uid_new_input.text().strip()
        if len(new_uid) != 8:
            self._mb(QMessageBox.Icon.Warning, "错误", "UID必须为8位十六进制字符")
            return
        reply = self._mb_choice(QMessageBox.Icon.Warning, "确认修改UID", "⚠️ 修改UID为不可逆操作!\nFUID卡写入后永久锁定。确认?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        self.uid_progress.clear()
        self._log(self.uid_progress, f"设置UID: {new_uid}")
        self.uid_set_btn.setEnabled(False)
        op = UidOperator(self.cmd)
        op.set_uid(new_uid,
            lambda m: self._log(self.uid_progress, m),
            lambda ok, m: self._log(self.uid_progress, f"{'成功' if ok else '失败'}: {m}"))
        self.uid_set_btn.setEnabled(True)

    # Manual Block
    def on_mb_read(self):
        if not self._check_serial(): return
        block = self.mb_block.value()
        key = self.mb_key.text().strip() or "FFFFFFFFFFFF"
        key_type_map = {0: "auto", 1: "A", 2: "B"}
        key_type = key_type_map.get(self.mb_key_type.currentIndex(), "auto")
        self.mb_progress.clear()
        scan = self.cmd.hf_14a_scan()
        if not scan:
            self._log(self.mb_progress, "未检测到卡片")
            return
        uid = scan[0]['uid']
        op = SingleBlockOperator(self.cmd)
        data = op.read_block(uid, block, key, lambda m: self._log(self.mb_progress, m), key_type=key_type)
        if data:
            hex_str = data.hex().upper()
            self.mb_data.setText(' '.join(hex_str[i:i+2] for i in range(0, 32, 2)))

    def on_mb_write(self):
        if not self._check_serial(): return
        block = self.mb_block.value()
        key = self.mb_key.text().strip() or "FFFFFFFFFFFF"
        key_type_map = {0: "auto", 1: "A", 2: "B"}
        key_type = key_type_map.get(self.mb_key_type.currentIndex(), "auto")
        data = self.mb_data.text().strip()
        if not data:
            self._mb(QMessageBox.Icon.Warning, "错误", "请输入数据")
            return
        self.mb_progress.clear()
        scan = self.cmd.hf_14a_scan()
        if not scan:
            self._log(self.mb_progress, "未检测到卡片")
            return
        uid = scan[0]['uid']
        op = SingleBlockOperator(self.cmd)
        op.write_block(uid, block, key, data, lambda m: self._log(self.mb_progress, m), key_type=key_type)

    # Card Detect (in card tools tab)
    def on_detect_card(self):
        if not self._check_serial(): return
        self.det_info.clear()
        det = CardDetector(self.cmd)
        info = det.detect(lambda m: self._log(self.det_info, m))
        self.det_info.clear()
        uid = info.get('uid', '')
        sak = info.get('sak', '')
        atqa = info.get('atqa', '')
        card_type = info.get('type', '未知')
        size = info.get('size', '')
        gen = info.get('gen', '')
        sa = sak.zfill(2)
        atqa_bytes = bytes.fromhex(atqa) if len(atqa) >= 2 else b''
        atqa_desc = self._parse_atqa(atqa_bytes) if atqa_bytes else ''
        html = f"""
        <div style='font-family:Consolas,monospace; font-size:13px; padding:8px;'>
            <div style='background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:12px;'>
                <div style='font-size:18px; font-weight:bold; color:#007bff; margin-bottom:10px;'>📇 卡片检测报告</div>
                <table style='width:100%; border-collapse:collapse;'>
                    <tr style='background:#e9ecef;'><td style='padding:6px 10px; font-weight:bold; width:100px;'>UID</td><td style='padding:6px 10px; font-family:Consolas; color:#333;'>{uid}</td></tr>
                    <tr><td style='padding:6px 10px; font-weight:bold;'>SAK</td><td style='padding:6px 10px;'>{sa}</td></tr>
                    <tr style='background:#e9ecef;'><td style='padding:6px 10px; font-weight:bold;'>ATQA</td><td style='padding:6px 10px;'>{atqa}{' (' + atqa_desc + ')' if atqa_desc else ''}</td></tr>
                    <tr><td style='padding:6px 10px; font-weight:bold;'>类型</td><td style='padding:6px 10px;'><span style='background:#007bff; color:white; padding:2px 8px; border-radius:4px;'>{card_type}</span></td></tr>
                    <tr style='background:#e9ecef;'><td style='padding:6px 10px; font-weight:bold;'>容量</td><td style='padding:6px 10px;'>{size}</td></tr>
                    <tr><td style='padding:6px 10px; font-weight:bold;'>世代</td><td style='padding:6px 10px;'>{gen}</td></tr>
                </table>
            </div>
        </div>
        """
        self.det_info.setHtml(html)

    def _parse_atqa(self, atqa):
        if len(atqa) < 2: return ''
        b0, b1 = atqa[0], atqa[1]
        descs = []
        if b0 & 0x80: descs.append('UID大小4字节')
        if b0 & 0x40: descs.append('UID大小7字节')
        if b0 & 0x20: descs.append('UID大小10字节')
        if b1 & 0x0F:
            rate = {1: '106kbps', 2: '212kbps', 4: '424kbps', 8: '847kbps'}
            descs.append(rate.get(b1 & 0x0F, f'{b1&0x0F}x'))
        if b0 & 0x1F:
            coding = {0x01: 'MIFARE Classic', 0x02: 'MIFARE Ultralight/NTAG', 0x04: 'MIFARE Plus', 0x08: 'MIFARE DESFire'}
            val = b0 & 0x1F
            descs.append(coding.get(val, f'专有(0x{val:02X})'))
        return ', '.join(descs) if descs else '标准'

    # NTAG
    def on_ntag_read(self):
        if not self._check_serial(): return
        self.ntag_progress.clear()
        self.ntag_read_btn.setEnabled(False)
        nt = NtagHelper(self.cmd)
        nt.read_ntag(
            lambda m: self._log(self.ntag_progress, m),
            lambda ok, msg, data: self._ntag_read_finished(ok, msg, data))
        self.ntag_read_btn.setEnabled(True)

    def _ntag_read_finished(self, ok, msg, data):
        if ok and data:
            hex_str = ' '.join(f'{b:02X}' for b in data)
            self._log(self.ntag_progress, f"\n数据: {hex_str}")
            try:
                out_dir = PathManager.get_output_dir()
                path = os.path.join(out_dir, f"ntag_{time.strftime('%Y%m%d_%H%M%S')}.bin")
                with open(path, 'wb') as f:
                    f.write(data)
                self._log(self.ntag_progress, f"已保存: {path}")
            except Exception as e:
                self._log(self.ntag_progress, f"保存失败: {e}")
        else:
            self._log(self.ntag_progress, f"失败: {msg}")

    def on_ntag_write(self):
        if not self._check_serial(): return
        url = self.ntag_url.text().strip()
        if not url:
            self._mb(QMessageBox.Icon.Warning, "错误", "请输入URL")
            return
        self.ntag_progress.clear()
        self.ntag_write_btn.setEnabled(False)
        nt = NtagHelper(self.cmd)
        nt.write_ndef_url(url,
            lambda m: self._log(self.ntag_progress, m),
            lambda ok, m: self._log(self.ntag_progress, f"{'成功' if ok else '失败'}: {m}"))
        self.ntag_write_btn.setEnabled(True)

    # ISO15693
    def on_iso_scan(self):
        if not self._check_serial(): return
        self.iso_progress.clear()
        op = Iso15693Operator(self.cmd)
        op.scan(lambda m: self._log(self.iso_progress, m))

    def on_iso_info(self):
        if not self._check_serial(): return
        self.iso_progress.clear()
        op = Iso15693Operator(self.cmd)
        op.info(lambda m: self._log(self.iso_progress, m))

    def on_iso_read(self):
        if not self._check_serial(): return
        block = self.iso_block_input.value()
        self.iso_progress.clear()
        op = Iso15693Operator(self.cmd)
        data = op.read_block(block, lambda m: self._log(self.iso_progress, m))
        if data:
            self.iso_data_edit = data.hex().upper()
            self._log(self.iso_progress, f"读块 {block} = {self.iso_data_edit}")

    def on_iso_write(self):
        if not self._check_serial(): return
        block = self.iso_block_input.value()
        # 简化: 直接读后写回(写按钮主要用于演示,实际生产应提供数据输入框)
        op = Iso15693Operator(self.cmd)
        data = op.read_block(block, lambda m: self._log(self.iso_progress, m))
        if data:
            self.iso_progress.clear()
            op.write_block(block, data.hex().upper(), lambda m: self._log(self.iso_progress, m))
            self._log(self.iso_progress, f"块 {block} 已写回相同数据")

    # EM4100
    def on_em_scan(self):
        if not self._check_serial(): return
        self.em_progress.clear()
        op = Em4100Operator(self.cmd)
        op.scan(lambda m: self._log(self.em_progress, m))

    # Emulator
    def _stop_emu_thread(self):
        if hasattr(self, 't') and self.t and self.t.isRunning():
            self.t.quit()
            self.t.wait(1000)

    def on_emu_load(self):
        if not self._check_serial(): return
        path = self.emu_mfd.text().strip()
        if not path or not os.path.exists(path):
            self._mb(QMessageBox.Icon.Warning, "错误", "请选择有效的MFD文件")
            return
        slot = self.emu_slot.currentIndex() + 1
        self.emu_progress.clear()
        self._log(self.emu_progress, f"加载 {path} 到槽位{slot}...")
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except Exception as e:
            self._log(self.emu_progress, f"读取文件错误: {e}")
            return
        self.emu_load_btn.setEnabled(False)
        self._stop_emu_thread()
        self.t = EmulatorThread(self.cmd, "load", slot, data=data)
        self.t.progress.connect(lambda m: self._log(self.emu_progress, m))
        self.t.finished.connect(lambda r: self._emu_done("load", r))
        self.t.start()

    def on_emu_setuid(self):
        if not self._check_serial(): return
        uid = self.emu_uid.text().strip()
        if len(uid) != 8:
            self._mb(QMessageBox.Icon.Warning, "错误", "UID必须为8位十六进制")
            return
        slot = self.emu_slot.currentIndex() + 1
        self.emu_progress.clear()
        self.emu_setuid_btn.setEnabled(False)
        self._stop_emu_thread()
        self.t = EmulatorThread(self.cmd, "setuid", slot, uid_hex=uid)
        self.t.progress.connect(lambda m: self._log(self.emu_progress, m))
        self.t.finished.connect(lambda r: self._emu_done("setuid", r))
        self.t.start()

    def on_emu_read(self):
        if not self._check_serial(): return
        slot = self.emu_slot.currentIndex() + 1
        card_type = self.emu_type_combo.currentIndex() + 1
        self.emu_progress.clear()
        self.emu_read_btn.setEnabled(False)
        self._stop_emu_thread()
        self.t = EmulatorThread(self.cmd, "read", slot, card_type=card_type)
        self.t.progress.connect(lambda m: self._log(self.emu_progress, m))
        self.t.finished.connect(self._emu_read_done)
        self.t.start()

    def _emu_done(self, op, result):
        self.emu_load_btn.setEnabled(True)
        self.emu_setuid_btn.setEnabled(True)
        self.emu_read_btn.setEnabled(True)
        if result:
            self._log(self.emu_progress, f"{op} 成功")
        else:
            self._log(self.emu_progress, f"{op} 失败")

    def _emu_read_done(self, dump):
        self.emu_read_btn.setEnabled(True)
        self.emu_load_btn.setEnabled(True)
        self.emu_setuid_btn.setEnabled(True)
        if dump:
            self._log(self.emu_progress, f"读取到 {len(dump)} 字节")
            uid = dump[:4].hex().upper()
            self._log(self.emu_progress, f"UID: {uid}")
            # 自动保存为 MFD 文件到 dumps 目录
            try:
                from path_manager import PathManager
                from datetime import datetime
                out_dir = PathManager.get_output_dir()
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                slot = self.emu_slot.currentIndex() + 1
                out_path = os.path.join(out_dir, f"emulator_slot{slot}_{ts}.mfd")
                with open(out_path, 'wb') as f:
                    f.write(dump)
                self._log(self.emu_progress, f"已保存到: {out_path}")
                # 自动加载到扇区工具(若是 1K MFC)
                if len(dump) in (1024, 4096):
                    if self.load_sector_data_from_mfd(out_path):
                        self._log(self.emu_progress, "已自动加载到扇区工具")
            except Exception as e:
                self._log(self.emu_progress, f"保存模拟器数据失败: {e}")
        else:
            self._log(self.emu_progress, "读取失败")

    def closeEvent(self, event):
        app_logger.info("应用程序正在关闭...")
        try:
            self.config.save()
        except Exception:
            pass
        if hasattr(self, 'fmt_thread') and self.fmt_thread and self.fmt_thread.isRunning():
            self.fmt_thread.cancel()
            self.fmt_thread.wait(500)
        if hasattr(self, 'write_thread') and self.write_thread and self.write_thread.isRunning():
            self.write_thread.cancel()
            self.write_thread.wait(1000)
        if hasattr(self, 'pn532_com') and self.pn532_com:
            try:
                self.pn532_com.close()
            except Exception:
                pass
        try:
            resource_manager.cleanup_resources()
        except Exception:
            pass
        app_logger.info("应用程序已关闭")
        event.accept()










def main():
    app = QApplication(sys.argv)
    # 强制使用Fusion样式 + 亮色调色板，避免跟随系统主题变色
    app.setStyle('Fusion')
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0xF5, 0xF7, 0xFA))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0x33, 0x33, 0x33))
    palette.setColor(QPalette.ColorRole.Base, QColor(0xFF, 0xFF, 0xFF))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(0xF0, 0xF0, 0xF0))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0xFF, 0xFF, 0xFF))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0x33, 0x33, 0x33))
    palette.setColor(QPalette.ColorRole.Text, QColor(0x33, 0x33, 0x33))
    palette.setColor(QPalette.ColorRole.Button, QColor(0xF0, 0xF0, 0xF0))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0x33, 0x33, 0x33))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(0xFF, 0x00, 0x00))
    palette.setColor(QPalette.ColorRole.Link, QColor(0x00, 0x7B, 0xFF))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0x00, 0x7B, 0xFF))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    app.setPalette(palette)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    main()