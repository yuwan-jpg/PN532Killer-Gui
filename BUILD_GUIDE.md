# PN532 Python 跨平台构建指南

本指南介绍如何在不同平台上构建 PN532 Python 应用程序。

## 目录

- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [详细构建步骤](#详细构建步骤)
- [平台特定说明](#平台特定说明)
- [故障排除](#故障排除)

## 系统要求

### 通用要求
- Python 3.7 或更高版本
- pip 包管理器
- Git（可选，用于克隆仓库）

### Windows 要求
- Windows 10 或更高版本
- PowerShell 5.0 或更高版本
- 预编译的 NFC 工具（已包含在 `nfc-bin` 目录中）

### Linux 要求
- Ubuntu 18.04+ / CentOS 7+ / Fedora 30+ 或其他现代 Linux 发行版
- libnfc 开发库
- 编译工具链（gcc, make）
- 详细要求请参考 [LINUX_SETUP.md](LINUX_SETUP.md)

## 快速开始

### Windows

1. **使用批处理脚本（推荐）**：
   ```cmd
   # 检查依赖
   build.bat check
   
   # 构建应用程序
   build.bat build
   ```

2. **使用 Python 脚本**：
   ```cmd
   python build_cross_platform.py build
   ```

### Linux/macOS

1. **使用 Shell 脚本（推荐）**：
   ```bash
   # 添加执行权限
   chmod +x build.sh
   
   # 设置环境（仅 Linux 首次运行）
   ./build.sh setup
   
   # 检查依赖
   ./build.sh check
   
   # 构建应用程序
   ./build.sh build
   ```

2. **使用 Makefile**：
   ```bash
   # 检查依赖
   make check
   
   # 构建应用程序
   make build
   ```

3. **使用 Python 脚本**：
   ```bash
   python3 build_cross_platform.py build
   ```

## 详细构建步骤

### 1. 环境准备

#### Windows
```cmd
# 克隆仓库（如果需要）
git clone <repository-url>
cd pn532-python-main\script

# 安装 Python 依赖
build.bat install
```

#### Linux
```bash
# 克隆仓库（如果需要）
git clone <repository-url>
cd pn532-python-main/script

# 设置 Linux 环境
./build.sh setup

# 安装依赖
./build.sh install
```

### 2. 依赖检查

在构建之前，建议检查所有依赖是否正确安装：

```bash
# Windows
build.bat check

# Linux/macOS
./build.sh check
# 或
make check
```

### 3. 运行测试

确保代码语法正确：

```bash
# Windows
build.bat test

# Linux/macOS
./build.sh test
# 或
make test
```

### 4. 构建应用程序

```bash
# Windows
build.bat build

# Linux/macOS
./build.sh build
# 或
make build
```

### 5. 清理构建文件

如果需要重新构建：

```bash
# Windows
build.bat clean

# Linux/macOS
./build.sh clean
# 或
make clean
```

## 平台特定说明

### Windows 平台

- **工具位置**：所有 NFC 工具位于 `nfc-bin` 目录
- **可执行文件**：生成的可执行文件位于 `dist\pn532_gui` 目录
- **依赖**：无需额外安装系统依赖，所有工具已预编译

### Linux 平台

- **工具位置**：使用系统安装的 libnfc 工具
- **可执行文件**：生成的可执行文件位于 `dist/pn532_gui` 目录
- **依赖**：需要安装 libnfc、mfoc 等工具，详见 [LINUX_SETUP.md](LINUX_SETUP.md)

## 构建选项

### 可用命令

| 命令 | Windows | Linux/macOS | 描述 |
|------|---------|-------------|------|
| `help` | `build.bat help` | `./build.sh help` | 显示帮助信息 |
| `check` | `build.bat check` | `./build.sh check` | 检查构建依赖 |
| `test` | `build.bat test` | `./build.sh test` | 运行语法测试 |
| `clean` | `build.bat clean` | `./build.sh clean` | 清理构建文件 |
| `build` | `build.bat build` | `./build.sh build` | 构建应用程序 |
| `install` | `build.bat install` | `./build.sh install` | 安装 Python 依赖 |

### Linux 特有命令

| 命令 | 用法 | 描述 |
|------|------|------|
| `setup` | `./build.sh setup` | 显示系统依赖安装指南 |

### Makefile 目标

```bash
make help          # 显示所有可用目标
make check         # 检查依赖
make test          # 运行测试
make clean         # 清理构建文件
make build         # 构建应用程序
make build-fast    # 快速构建（跳过检查）
make install-deps  # 安装 Python 依赖
make dev-setup     # 设置开发环境
make lint          # 语法检查
make run           # 运行应用程序
```

## 构建输出

成功构建后，您将在以下位置找到可执行文件：

- **Windows**: `dist\pn532_gui\pn532_gui.exe`
- **Linux**: `dist/pn532_gui/pn532_gui`

构建还会包含以下文件：
- 配置文件和资源
- 必要的库文件
- 文档文件

## 故障排除

### 常见问题

1. **Python 版本错误**
   ```
   错误: 需要 Python 3.7 或更高版本
   ```
   **解决方案**: 升级 Python 到 3.7 或更高版本

2. **PyInstaller 未安装**
   ```
   错误: PyInstaller 未安装
   ```
   **解决方案**: 运行 `pip install pyinstaller`

3. **Linux 工具缺失**
   ```
   错误: 缺少工具: nfc-list, mfoc
   ```
   **解决方案**: 参考 [LINUX_SETUP.md](LINUX_SETUP.md) 安装缺失工具

4. **Windows 工具缺失**
   ```
   错误: nfc-list.exe 不存在
   ```
   **解决方案**: 确保 `nfc-bin` 目录存在且包含所有必要工具

### 调试构建问题

1. **启用详细输出**：
   ```bash
   python build_cross_platform.py build --verbose
   ```

2. **检查构建日志**：
   构建日志保存在 `build` 目录中

3. **手动运行 PyInstaller**：
   ```bash
   # Windows
   pyinstaller --clean pn532_gui.spec
   
   # Linux
   pyinstaller --clean pyinstaller_linux.spec
   ```

### 获取帮助

如果遇到问题：

1. 检查系统要求是否满足
2. 运行依赖检查：`build.bat check` 或 `./build.sh check`
3. 查看构建日志中的错误信息
4. 参考平台特定的设置指南

## 开发者说明

### 修改构建配置

- **Windows**: 编辑 `pn532_gui.spec`
- **Linux**: 编辑 `pyinstaller_linux.spec`
- **构建脚本**: 编辑 `build_cross_platform.py`

### 添加新的依赖

1. 更新 `requirements.txt`
2. 在相应的 `.spec` 文件中添加 `hiddenimports`
3. 如果是二进制依赖，添加到 `binaries` 列表

### 测试构建

在提交更改前，请在目标平台上测试构建：

```bash
# 完整测试流程
make clean
make check
make test
make build
```

## 许可证

请参考项目根目录的许可证文件。