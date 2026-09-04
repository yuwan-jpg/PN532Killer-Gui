# Linux 环境设置指南

本指南将帮助您在 Linux 环境下设置 PN532 Python 应用程序所需的依赖工具。

## 系统要求

- Linux 发行版（推荐 Ubuntu 18.04+ 或 Kali Linux）
- Python 3.7+
- 编译工具链（gcc, make, cmake）

## 1. 安装基础依赖

```bash
# Ubuntu/Debian 系统
sudo apt-get update
sudo apt-get install -y build-essential cmake git pkg-config

# CentOS/RHEL 系统
sudo yum groupinstall "Development Tools"
sudo yum install cmake git pkgconfig
```

## 2. 安装 libnfc 工具

### 方法一：使用包管理器（推荐）

```bash
# Ubuntu/Debian
sudo apt-get install -y libnfc-bin libnfc-dev

# Kali Linux（通常已预装）
sudo apt-get install -y libnfc-bin

# CentOS/RHEL
sudo yum install libnfc libnfc-devel
```

### 方法二：从源码编译

```bash
# 下载 libnfc 源码
git clone https://github.com/nfc-tools/libnfc.git
cd libnfc

# 安装依赖
sudo apt-get install -y libusb-dev libpcsclite-dev

# 编译安装
autoreconf -vis
./configure --with-drivers=all
make
sudo make install
sudo ldconfig
```

## 3. 编译 mfkey 工具

### mfkey64

```bash
# 下载源码
git clone https://github.com/zhovner/mfkey64.git
cd mfkey64

# 编译
gcc -O3 -o mfkey64 mfkey64.c

# 复制到应用程序目录
cp mfkey64 /path/to/pn532-python-main/script/
```

### mfkey32v2

```bash
# 下载源码
git clone https://github.com/aczid/crypto1_bs.git
cd crypto1_bs

# 编译
make

# 或者使用单独的 mfkey32v2 实现
git clone https://github.com/nfc-tools/mfkey32v2.git
cd mfkey32v2
gcc -O3 -o mfkey32v2 mfkey32v2.c

# 复制到应用程序目录
cp mfkey32v2 /path/to/pn532-python-main/script/
```

## 4. 安装 mfoc 工具

```bash
# Ubuntu/Debian
sudo apt-get install -y mfoc

# 或从源码编译
git clone https://github.com/nfc-tools/mfoc.git
cd mfoc
autoreconf -vis
./configure
make
sudo make install
```

## 5. 验证安装

运行以下命令验证工具是否正确安装：

```bash
# 检查 libnfc 工具
nfc-list --version
nfc-mfclassic --help

# 检查 mfkey 工具
./mfkey64 --help
./mfkey32v2 --help

# 检查 mfoc
mfoc --help
```

## 6. 配置 libnfc

创建 libnfc 配置文件：

```bash
sudo mkdir -p /etc/nfc
sudo tee /etc/nfc/libnfc.conf << EOF
# Allow device auto-detection (default: true)
allow_autoscan = true

# Allow intrusive auto-detection (default: false)
allow_intrusive_scan = false

# Set log level (default: error)
log_level = 1

# Set default device
device.name = "PN532_UART"
device.connstring = "pn532_uart:/dev/ttyUSB0"
EOF
```

## 7. 用户权限设置

为了访问 USB 设备，需要设置适当的权限：

```bash
# 添加用户到 dialout 组
sudo usermod -a -G dialout $USER

# 创建 udev 规则
sudo tee /etc/udev/rules.d/99-pn532.rules << EOF
# PN532 NFC Reader
SUBSYSTEM=="usb", ATTRS{idVendor}=="072f", ATTRS{idProduct}=="2200", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="072f", ATTRS{idProduct}=="2200", MODE="0666"
EOF

# 重新加载 udev 规则
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## 8. 测试应用程序

```bash
cd /path/to/pn532-python-main/script
python3 pn532_gui.py
```

## 故障排除

### 常见问题

1. **找不到 NFC 设备**
   - 检查设备连接
   - 确认用户权限
   - 查看 `dmesg` 输出

2. **libnfc 工具无法运行**
   - 检查 libnfc 配置文件
   - 确认设备驱动正确加载

3. **mfkey 工具编译失败**
   - 安装缺失的开发库
   - 检查编译器版本

### 调试命令

```bash
# 检查 USB 设备
lsusb | grep -i nfc

# 检查串口设备
ls -la /dev/ttyUSB*

# 测试 libnfc
nfc-scan-device -v

# 检查应用程序日志
tail -f ~/.local/share/pn532-python/logs/app.log
```

## 注意事项

1. 某些 Linux 发行版可能需要额外的驱动程序
2. 确保 PN532 设备固件版本兼容
3. 在虚拟机中使用时，需要正确配置 USB 透传
4. 部分功能可能需要 root 权限

## 支持的 Linux 发行版

- ✅ Ubuntu 18.04+
- ✅ Debian 10+
- ✅ Kali Linux 2020.1+
- ✅ CentOS 7+
- ✅ Fedora 30+
- ⚠️ Arch Linux（需要手动编译部分工具）
- ⚠️ Alpine Linux（需要额外配置）