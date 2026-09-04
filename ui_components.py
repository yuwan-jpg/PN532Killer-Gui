from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QComboBox, QListWidget, QListWidgetItem, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QCursor
import serial.tools.list_ports
import platform
from i18n import i18n

def _font(name, size, weight=None):
    if name == 'Microsoft YaHei' and platform.system() != 'Windows':
        name = 'sans-serif'
    f = QFont(name, size)
    if weight is not None:
        f.setWeight(weight)
    return f


class ConfigDialog(QWidget):
    def __init__(self, comm_type):
        super().__init__()
        self.comm_type = comm_type
        self.result = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.setWindowTitle(i18n.get_text('select_serial_device'))
        self.setMinimumSize(450, 350)
        self.resize(450, 350)
        
        title_label = QLabel(i18n.get_text('available_ports'))
        title_label.setFont(_font('Microsoft YaHei', 14, QFont.Weight.Bold))
        title_label.setStyleSheet('color: #28a745;')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        self.refresh_label = QLabel(i18n.get_text('refresh_hint'))
        self.refresh_label.setStyleSheet('color: #666; font-size: 12px;')
        self.refresh_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.refresh_label)
        
        self.port_list = QListWidget()
        self.port_list.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.port_list.setStyleSheet('''
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #007bff;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
        ''')
        self.port_list.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.port_list)

        baud_row = QHBoxLayout()
        baud_row.addWidget(QLabel(i18n.get_text('baud_rate')))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "9600", "19200", "38400", "57600", "230400", "460800", "921600", "1000000", "1500000", "2000000", "3000000", "4000000", "6000000", "12000000"])
        self.baud_combo.setCurrentIndex(0)
        self.baud_combo.setStyleSheet("font-size:12px;padding:4px;")
        baud_row.addWidget(self.baud_combo)
        baud_row.addStretch()
        layout.addLayout(baud_row)

        self.refresh_btn = QPushButton(i18n.get_text('refresh_ports'))
        self.refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_btn.setStyleSheet('''
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        ''')
        self.refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(self.refresh_btn)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        ok_btn = QPushButton(i18n.get_text('confirm'))
        ok_btn.setFixedSize(100, 40)
        ok_btn.setStyleSheet('''
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        ''')
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton(i18n.get_text('cancel'))
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.setStyleSheet('''
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        ''')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self.refresh_ports()
        
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_ports)
        self.auto_refresh_timer.start(2000)

    def refresh_ports(self):
        ports = list(serial.tools.list_ports.comports())
        current_item = self.port_list.currentItem()
        current_device = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        
        existing_devices = set()
        for i in range(self.port_list.count()):
            item = self.port_list.item(i)
            device = item.data(Qt.ItemDataRole.UserRole)
            if device:
                existing_devices.add(device)
        
        new_devices = []
        for port in ports:
            device = port.device
            if device not in existing_devices:
                new_devices.append((device, port))
        
        if not new_devices and self.port_list.count() > 0:
            return
        
        self.port_list.clear()
        
        if not ports:
            item = QListWidgetItem(i18n.get_text('no_port'))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.port_list.addItem(item)
            return
            
        for port in ports:
            device = port.device
            description = port.description or i18n.get_text('unknown_device')
            manufacturer = port.manufacturer or ''
            
            if manufacturer:
                display_text = f"{device} - {description} ({manufacturer})"
            else:
                display_text = f"{device} - {description}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.port_list.addItem(item)
        
        if current_device:
            for i in range(self.port_list.count()):
                item = self.port_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == current_device:
                    self.port_list.setCurrentRow(i)
                    break
            else:
                self.port_list.setCurrentRow(0)
        else:
            self.port_list.setCurrentRow(0)

    def accept(self):
        current_item = self.port_list.currentItem()
        if current_item:
            device = current_item.data(Qt.ItemDataRole.UserRole)
            if device:
                if self.comm_type == 'UART':
                    baud_text = self.baud_combo.currentText().strip()
                    try:
                        baud = int(baud_text)
                    except ValueError:
                        baud = 115200
                    self.result = (device, baud)
                else:
                    host = self.host_input.text()
                    port = self.port_input.text()
                    self.result = f'{host}:{port}'
                self.auto_refresh_timer.stop()
                self.close()
                return
        self.result = None

    def reject(self):
        self.result = None
        self.auto_refresh_timer.stop()
        self.close()

    def closeEvent(self, event):
        self.auto_refresh_timer.stop()
        super().closeEvent(event)