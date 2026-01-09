# PN532Killer Gui

![PN532Killer Gui Screenshot](https://github.com/user-attachments/assets/2ec1c34c-a0b8-4882-8596-ffb9556fad0d)

## 一、项目简介

**PN532Killer Gui** 是一款面向 **PN532Killer 硬件设备** 的 NFC 工具图形界面（GUI）。本软件需配合对应硬件与**官方固件**使用，提供读卡（Reader）、模拟（Emulator）、嗅探（Sniffer）与相关数据分析能力，旨在降低 NFC 安全研究与教学演示的操作门槛，提升常用流程的可视化与自动化程度。

## 二、关键资源

- **PN532Killer 官方固件仓库（固件 / 更新日志 / 刷写说明）**  
  https://github.com/NFC-funs/PN532Killer

- **PN532Killer 相关网站（文档 / 社区 / 支持）**  
  https://www.pn532killer.com  
  注：该网站不隶属于本项目（PN532Killer Gui）。本项目仅引用其作为 PN532Killer 相关资料与交流入口。

## 三、功能概览

### 1) 设备连接与模式管理

- **一键切换工作模式**：支持在 **Reader / Emulator / Sniffer** 间快速切换，以适配读取、模拟与通信分析等不同场景。

### 2) NFC 工具箱（持续完善）

- **Mifare Classic 1K 自动化流程**：集成开源工具 `mfoc`，用于对 *用户合法持有或已获授权* 的 Mifare Classic 1K 卡片执行自动化流程，减少手动指令操作与参数配置成本。（具体能力取决于卡片类型、现场条件与固件支持情况）

### 3) Emulator（模拟器）

- **多卡类型支持**：支持模拟常见 NFC 卡片类型（例如 Mifare Classic、Mifare Ultralight 等，具体以固件能力为准）。
- **8 个卡槽管理**：提供 **8 个独立存储槽位**，支持预加载不同卡片数据文件，并通过界面/快捷方式快速切换，便于多场景复用与对比测试。

### 4) Sniffer（嗅探）与数据分析

#### 4.1 双模式嗅探

- **Without Tag**：无需连接实体卡片，捕获读卡器侧通信与指令数据。
- **With Tag**：连接实体卡片后，记录读卡器与卡片之间的完整交互过程（如认证与数据传输等）。

#### 4.2 自动化分析能力

- 集成 `mfkey32v2`、`mfkey64` 等工具，用于对嗅探到的交互数据进行分析与辅助推导，以降低人工计算与复核成本。（结果与成功率受卡片类型、交互质量与环境条件影响）

## 四、合规与使用声明（通用版）

1. **用途限制**：本工具仅用于对**本人合法拥有**或已获得**明确授权**的 NFC 设备/卡片开展安全研究、互操作性测试、技术学习与教育演示。用户应确保其使用场景、对象与方式符合其所在地及适用司法辖区的法律法规与行业规范。

2. **禁止用途**：严禁将本工具用于任何未经授权或违法用途，包括但不限于：对他人 NFC 设备/卡片进行未授权的读取、模拟、嗅探、数据恢复；获取、篡改或泄露受法律保护的数据（如个人信息、商业秘密、访问凭证）；以及任何可能危害公共安全、破坏系统可用性或侵犯他人合法权益的行为。

3. **责任划分**：用户对其使用行为及由此产生的后果承担全部责任。开发者与贡献者在法律允许的最大范围内，不对因滥用、违规使用或第三方行为导致的任何直接、间接、附带、特殊或后果性损失承担责任。

4. **风险提示**：NFC 与射频相关测试可能引发法律、隐私、合规与安全风险。请在获得必要授权并满足合规要求的前提下使用，并在可控环境中进行测试。

---

# PN532Killer Gui (English)

![PN532Killer Gui Screenshot](https://github.com/user-attachments/assets/2ec1c34c-a0b8-4882-8596-ffb9556fad0d)

## 1. Overview

**PN532Killer Gui** is a graphical NFC toolkit built for the **PN532Killer hardware device**. It must be used with the matching hardware and **official firmware**. The GUI provides Reader, Emulator, and Sniffer workflows, plus related data analysis utilities, aiming to reduce operational friction for NFC research and educational demonstrations through visualization and automation.

## 2. Key Resources

- **Official firmware repository (firmware / changelog / flashing guide)**  
  https://github.com/NFC-funs/PN532Killer

- **PN532Killer-related website (docs / community / support)**  
  https://www.pn532killer.com  
  Note: This website is not owned by this project (PN532Killer Gui). It is referenced as an external entry point for PN532Killer-related materials.

## 3. Features

### 1) Device & Mode Management

- **One-click mode switching** among **Reader / Emulator / Sniffer** for common workflows such as reading, emulation, and protocol analysis.

### 2) NFC Toolbox (Work in Progress)

- **Mifare Classic 1K automated workflow** via `mfoc` for *legally owned or explicitly authorized* cards, reducing manual command execution and parameter tuning. (Capabilities depend on card type, environment, and firmware support.)

### 3) Emulator

- **Multi-card type support** (e.g., Mifare Classic, Mifare Ultralight; subject to firmware capabilities).
- **8-slot profile management** for preloading multiple card dumps and switching quickly via UI/shortcuts.

### 4) Sniffer & Analysis

#### 4.1 Dual sniffing modes

- **Without Tag**: capture reader-side traffic without a physical tag.
- **With Tag**: record full reader–tag exchanges, including authentication and data transfer.

#### 4.2 Assisted analysis

- Integration of tools such as `mfkey32v2` and `mfkey64` to analyze captured exchanges and assist in key/material derivation, reducing manual computation. (Success rate depends on card type and capture quality.)

## 4. Legal & Compliance Notice (Universal)

1. **Permitted use**: This tool is intended solely for security research, interoperability testing, learning, and educational demonstrations on NFC devices/cards that you **legally own** or for which you have **explicit authorization**. You are responsible for ensuring that your use complies with all **applicable laws, regulations, and industry policies** in your jurisdiction(s).

2. **Prohibited use**: You must not use this tool for any unauthorized or unlawful activity, including but not limited to: reading, emulating, sniffing, or recovering data from NFC devices/cards without permission; obtaining, altering, or disclosing legally protected data (e.g., personal data, confidential information, credentials); or any activity that may endanger public safety, disrupt services, or infringe the rights of others.

3. **Responsibility & liability**: You assume all responsibility for your use of this tool and any consequences arising from it. To the maximum extent permitted by law, the developers and contributors disclaim liability for any direct, indirect, incidental, special, or consequential damages resulting from misuse, non-compliant use, or third-party actions.

4. **Risk notice**: NFC/RF testing may involve legal, privacy, compliance, and security risks. Use only with proper authorization, in a controlled environment, and in accordance with applicable requirements.
