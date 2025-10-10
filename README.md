# PN532Killer Gui



![PN532Killer Gui 界面截图](https://github.com/user-attachments/assets/a172df0d-bed2-4ee6-8a4d-6c59076ad022)

## 一、软件简介

PN532Killer Gui 是一款基于 **PN532Killer 硬件设备**开发的 NFC 工具图形界面，需搭配对应硬件及官方固件使用，可一站式实现 NFC 卡片的读取、模拟、通信嗅探与数据解密等核心操作，降低 NFC 技术研究的操作门槛。

## 二、关键资源链接



1. **官方固件下载**

   [PN5](https://github.com/NFC-funs/PN532Killer)[32Kil](https://github.com/NFC-funs/PN532Killer)[ler 固](https://github.com/NFC-funs/PN532Killer)[件仓库](https://github.com/NFC-funs/PN532Killer)

   （含最新固件安装包、更新日志及固件刷写说明，确保软件与硬件功能完全匹配）

2. **PN532Killer 相关官网**

   [ht](https://www.pn532killer.com)[tps:/](https://www.pn532killer.com)[/www.](https://www.pn532killer.com)[pn532](https://www.pn532killer.com)[kille](https://www.pn532killer.com)[r.com](https://www.pn532killer.com)

   （注：此官网非本项目（PN532Killer Gui）官方所属，可在该网站获取 PN532Killer 相关详细技术文档、用户社区交流及技术支持）

## 三、核心功能模块

### 3.1 设备连接与管理



* **多模式灵活切换**：支持在读卡器（Reader）模式、模拟器（Emulator）模式、嗅探（Sniffer）模式之间一键切换，适配不同使用场景（如卡片读取、多卡模拟、通信分析）。

### 3.2 NFC 工具箱（持续优化中）



* **Mifare Classic (1k) 一键破解**：集成 `mfoc` 开源工具，对标准 Mifare Classic 1K 卡片自动执行破解流程，无需手动输入指令，可直接获取卡片全部密钥与数据文件。

### 3.3 模拟器（Emulator）功能



* **多卡类型兼容**：支持模拟主流 NFC 卡片类型（如 Mifare Classic、Mifare Ultralight 等），覆盖门禁、考勤、消费等常见应用场景。

* **8 个独立卡槽存储**：内置 8 个独立存储空间，可预先加载不同卡片的数据文件，通过快捷键或界面按钮快速切换模拟卡片，满足多场景复用需求。

### 3.4 嗅探与解密（Sniffer）功能

#### 3.4.1 双模式嗅探



* **无标签嗅探（Without Tag）**：无需连接实体 NFC 卡片，即可捕获读卡器发出的通信信号与指令数据。

* **带标签嗅探（With Tag）**：连接实体 NFC 卡片后，精准记录读卡器与卡片之间的完整交互过程，包括认证指令、数据传输等细节。

#### 3.4.2 自动化数据解密



* 集成 `mfkey32v2` 与 `mfkey64` 工具，可自动分析嗅探到的 Mifare Classic 卡片认证流程数据，智能尝试破解并恢复卡片密钥，减少人工计算成本。

## 四、法律声明



1. **使用范围界定**：本工具（PN532Killer Gui）仅授权用于 **合法拥有所有权或已获得明确书面授权的 NFC 设备 / 卡片的安全研究、技术学习与教育演示场景**，使用者需确保操作对象的合法性及操作行为符合《中华人民共和国网络安全法》《中华人民共和国数据安全法》等相关法律法规要求。

2. **禁止行为声明**：严禁将本工具用于以下非法或侵权行为：

* 对未经授权的他人 NFC 设备、卡片进行读取、模拟、嗅探或数据破解；

* 窃取、篡改、泄露他人隐私信息、商业秘密或其他受法律保护的数据；

* 用于破坏公共安全、扰乱社会秩序或侵犯他人合法权益的任何活动。

1. **责任划分说明**：使用者应自行承担因使用本工具产生的全部法律责任。若因违反本声明及相关法律法规、未经授权使用本工具等行为，导致自身或第三方遭受法律处罚、财产损失、名誉损害等后果，本工具开发者及相关贡献者不承担任何直接、间接或连带责任。

2. **风险提示**：使用者需充分知晓，不当使用 NFC 相关工具可能存在的法律风险、技术风险及安全风险，建议在使用前充分了解并遵守当地法律法规及行业规范。



***

# PN532Killer Gui




## 1. Software Introduction

PN532Killer Gui is a graphical user interface (GUI) for NFC tools developed based on the **PN532Killer hardware device**. It must be used with the corresponding hardware and official firmware, enabling one-stop core operations including NFC card reading, emulation, communication sniffing, and data decryption—thus lowering the operational barrier for NFC technology research.

## 2. Key Resource Links



1. **Official Firmware Download**

   [PN](https://github.com/NFC-funs/PN532Killer)[532Ki](https://github.com/NFC-funs/PN532Killer)[ller](https://github.com/NFC-funs/PN532Killer)[ Firmw](https://github.com/NFC-funs/PN532Killer)[are R](https://github.com/NFC-funs/PN532Killer)[eposi](https://github.com/NFC-funs/PN532Killer)[tory](https://github.com/NFC-funs/PN532Killer)

   (Includes the latest firmware installation package, release notes, and firmware flashing instructions to ensure full functional compatibility between software and hardware)

2. **PN532Killer-Related Official Website**

   [https](https://www.pn532killer.com)[://ww](https://www.pn532killer.com)[w.pn5](https://www.pn532killer.com)[32kil](https://www.pn532killer.com)[ler.c](https://www.pn532killer.com)[om](https://www.pn532killer.com)

   (Note: This website is not officially owned by this project (PN532Killer Gui). You can access detailed PN532Killer-related technical documents, user community discussions, and technical support on this site)

## 3. Core Function Modules

### 3.1 Device Connection and Management



* **Flexible Mode Switching**: Supports one-click switching between Reader Mode, Emulator Mode, and Sniffer Mode, adapting to diverse usage scenarios (e.g., card reading, multi-card emulation, communication analysis).

### 3.2 NFC Toolbox (Under Continuous Optimization)



* **One-Click Cracking for Mifare Classic (1K)**: Integrates the open-source `mfoc` tool to automatically execute the cracking process for standard Mifare Classic 1K cards. No manual command input is required, and all card keys and data files can be retrieved directly.

### 3.3 Emulator Function



* **Multi-Card Type Compatibility**: Supports emulation of mainstream NFC card types (e.g., Mifare Classic, Mifare Ultralight) to cover common application scenarios such as access control, time attendance, and payment systems.

* **8 Independent Card Slot Storage**: Features 8 built-in independent storage slots, allowing preloading of data files for different cards. Quick switching between emulated cards can be done via shortcut keys or interface buttons to meet multi-scenario reuse needs.

### 3.4 Sniffing and Decryption (Sniffer) Function

#### 3.4.1 Dual-Mode Sniffing



* **Sniffing Without Tag**: Captures communication signals and command data transmitted by the card reader without connecting a physical NFC card.

* **Sniffing With Tag**: After connecting a physical NFC card, accurately records the complete interaction process between the card reader and the card—including details like authentication commands and data transmission.

#### 3.4.2 Automated Data Decryption



* Integrates `mfkey32v2` and `mfkey64` tools, which can automatically analyze the sniffed authentication process data of Mifare Classic cards, intelligently attempt to crack and recover card keys, and reduce manual computation costs.

## 4. Legal Disclaimer



1. **Definition of Usage Scope**: This tool (PN532Killer Gui) is only authorized for use in **security research, technical learning, and educational demonstration scenarios involving NFC devices/cards for which you legally hold ownership or have obtained explicit written authorization**. Users must ensure the legality of the target of operation and that their actions comply with the requirements of relevant laws and regulations, such as the Cybersecurity Law of the People's Republic of China and the Data Security Law of the People's Republic of China.

2. **Prohibited Behaviors**: It is strictly prohibited to use this tool for the following illegal or infringing activities:

* Reading, emulating, sniffing, or cracking data from others' unauthorized NFC devices or cards;

* Stealing, tampering with, or disclosing others' private information, trade secrets, or other legally protected data;

* Any activities that undermine public security, disrupt social order, or infringe upon others' legitimate rights and interests.

1. **Responsibility Allocation**: Users shall bear full legal responsibility for all consequences arising from the use of this tool. If violations of this disclaimer, relevant laws and regulations, or unauthorized use of this tool result in legal penalties, property losses, reputation damage, or other consequences for yourself or third parties, the developers and relevant contributors of this tool shall not bear any direct, indirect, or joint liability.

2. **Risk Warning**: Users must fully understand the legal risks, technical risks, and security risks that may arise from the improper use of NFC-related tools. It is recommended to fully understand and comply with local laws, regulations, and industry standards before use.

