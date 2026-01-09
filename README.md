# PN532Killer Gui

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/2ec1c34c-a0b8-4882-8596-ffb9556fad0d"
    alt="PN532Killer Gui Screenshot"
    width="800"
  />
</p>

---

## Overview / 项目简介

**PN532Killer Gui** is a graphical NFC tool designed for the **PN532Killer hardware device**.  
**PN532Killer Gui** 是一款面向 **PN532Killer 硬件设备** 的图形化 NFC 工具。

It must be used together with the corresponding hardware and **official firmware**, providing visualized workflows for **Reader**, **Emulator**, and **Sniffer** modes.  
本软件需配合对应硬件及 **官方固件** 使用，提供 **读卡（Reader）**、**模拟（Emulator）**、**嗅探（Sniffer）** 等可视化操作能力。

The project focuses on improving usability and automation for NFC security research, testing, and educational demonstrations.  
本项目侧重提升易用性与自动化程度，适用于 NFC 安全研究、测试分析与教学演示等场景。

---

## Resources / 相关资源

- **Official PN532Killer Firmware (Firmware / Changelog / Flashing Guide)**  
  **PN532Killer 官方固件（固件 / 更新日志 / 刷写说明）**  
  https://github.com/NFC-funs/PN532Killer

- **PN532Killer Related Website (Docs / Community / Support)**  
  **PN532Killer 相关网站（文档 / 社区 / 支持）**  
  https://www.pn532killer.com  

  > This website is not affiliated with PN532Killer Gui.  
  > 该网站不隶属于 PN532Killer Gui 项目，仅作为相关资料与社区入口引用。

---

## Features / 功能概览

### Device & Mode Management / 设备与模式管理

- **One-click mode switching (Reader / Emulator / Sniffer)**  
  **一键切换 Reader / Emulator / Sniffer 工作模式**  
  Designed for common workflows such as card reading, emulation, and protocol analysis.  
  适用于读卡、模拟与通信分析等常见使用流程。

---

### NFC Toolbox / NFC 工具箱（持续完善）

- **Mifare Classic 1K automated workflow (via `mfoc`)**  
  **基于 `mfoc` 的 Mifare Classic 1K 自动化流程**  

  Intended for cards that are **legally owned or explicitly authorized** by the user.  
  仅适用于 **用户合法持有或已获得明确授权** 的卡片。  

  Actual capabilities depend on card type, environment, and firmware support.  
  实际效果取决于卡片类型、使用环境及固件支持情况。

---

### Emulator / 模拟器

- **Multiple NFC card type support**  
  **支持多种 NFC 卡类型模拟**  
  (e.g., Mifare Classic, Mifare Ultralight; subject to firmware capabilities)  
  （如 Mifare Classic、Mifare Ultralight，具体以固件能力为准）

- **8-slot card profile management**  
  **8 个独立卡槽管理**  
  Allows preloading multiple card data files and switching quickly via UI or shortcuts.  
  支持预加载多组卡片数据，并通过界面或快捷方式快速切换。

---

### Sniffer & Analysis / 嗅探与数据分析

#### Sniffing Modes / 嗅探模式

- **Without Tag**  
  Capture reader-side communication without a physical card.  
  无需连接实体卡片，捕获读卡器侧通信数据。

- **With Tag**  
  Record full reader–card communication, including authentication and data exchange.  
  记录读卡器与卡片之间的完整交互过程，包括认证与数据传输。

#### Assisted Analysis / 辅助分析

- **Integrated analysis tools (`mfkey32v2`, `mfkey64`)**  
  **集成 `mfkey32v2`、`mfkey64` 等分析工具**  

  Used to analyze captured sniffing data and extract key parameters, reducing manual analysis effort and repetitive computation.  
  用于对嗅探到的通信数据进行分析和关键参数提取，减少人工分析过程中的重复计算和工作量。

---

## Legal & Compliance Notice / 合规与使用声明（通用）

- **Authorized use only**  
  This project is intended solely for NFC devices or cards that you **legally own** or are **explicitly authorized** to test.  
  本项目仅用于对 **本人合法拥有或已获得明确授权** 的 NFC 设备或卡片进行研究与测试。

- **Prohibited activities**  
  Unauthorized reading, emulation, sniffing, data recovery, or any illegal use is strictly prohibited.  
  严禁用于任何未授权或违法用途，包括但不限于非法读取、模拟、嗅探或数据恢复。

- **Responsibility & liability**  
  Users are solely responsible for their actions and any resulting consequences.  
  用户需对其使用行为及产生的后果承担全部责任。  

  Developers and contributors disclaim liability to the maximum extent permitted by law.  
  在法律允许的最大范围内，开发者与贡献者不对相关损失承担责任。

- **Risk notice**  
  NFC and RF testing may involve legal, privacy, and security risks.  
  NFC 与射频测试可能涉及法律、隐私及安全风险，请在合规且可控的环境中使用。

---
