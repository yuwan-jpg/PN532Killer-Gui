# PN532Killer Gui

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/2ec1c34c-a0b8-4882-8596-ffb9556fad0d"
    alt="PN532Killer Gui"
    width="800"
  />
</p>

---

## 简介

**PN532Killer Gui** 是一款面向 **PN532Killer 硬件设备** 的图形化 NFC 工具，需配合对应硬件及官方固件使用。

提供读卡（Reader）、模拟（Emulator）、嗅探（Sniffer）三大工作模式的可视化操作能力，具备完整的 Mifare Classic 卡片读写、破解、数据编辑等功能，适用于 NFC 安全研究、测试分析与教学演示等场景。

---

## 功能

### 读卡模式

- **Mifare Classic 全卡读取** — 字典破解 + 密钥传播 + 失败重试，支持历史密钥与自定义密钥文件
- **修改 UID** — 检测卡片类型，写入新 UID（支持 CUID 卡）
- **手动读写块** — 指定块号和密钥，精确读写单个数据块
- **卡类型检测** — 自动识别 Gen1A/Gen3/Gen4 魔法卡、标准 MIFARE Classic、NTAG 等
- **写卡** — 从 MFD 文件或扇区数据写入卡片，支持写入块 0

### 模拟器模式

- 支持 Mifare Classic 1K、NTAG、15693 卡片模拟
- 8 个独立卡槽，支持预加载多组卡片数据并快速切换
- 实时设置 UID、加载 MFD 文件

### 嗅探模式

- **无标签嗅探** — 捕获读卡器侧通信数据
- **带标签嗅探** — 记录读卡器与卡片之间的完整交互
- 集成 `mfkey64` / `mfkey32v2`，自动分析嗅探数据并计算密钥

### 扇区工具

- 树形结构查看与编辑扇区数据
- 实时十六进制数据验证与修改
- 导入 MFD / 文本文件，自动检测格式
- 从扇区尾块提取密钥保存到历史
- 扇区内容分析（尾块、数据块识别）

---

## 系统要求

- 支持 Windows 和 Linux 64-bit
- 串口驱动（CH340/CH343/CP2102 等）
- 运行 `PN532Killer_GUI_v0.5_win64.exe`

---

## 资源链接

- **官方固件**：https://github.com/NFC-funs/PN532Killer
- **相关网站**：https://www.pn532killer.com

---

## 声明

- 本项目仅用于对 **本人合法拥有或已获得明确授权** 的 NFC 设备或卡片进行研究与测试
- 严禁用于任何未授权或违法用途
- 用户需对其使用行为及产生的后果承担全部责任
