"""
国际化模块 - 管理界面文本和消息
"""
import json
import os
import sys

class I18n:
    """国际化文本管理类"""
    
    def __init__(self):
        # 默认语言
        self.current_language = "zh"
        # 处理PyInstaller打包环境的资源路径
        if hasattr(sys, '_MEIPASS'):
            # 打包后，资源文件在sys._MEIPASS目录下
            self.lang_dir = os.path.join(sys._MEIPASS, "lang")
        else:
            # 开发环境，资源文件在当前目录下的lang文件夹
            self.lang_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
        self.supported_languages = ["zh", "en"]
        
        # 初始化默认文本
        self._init_default_texts()
        
        # 加载语言文件
        self.load_language(self.current_language)
    
    def _init_default_texts(self):
        """初始化默认文本"""
        # 界面文本
        self.UI_TEXTS = {
            'window_title': 'PN532Killer Gui v0.6 Beta',
            'about_title': 'PN532Killer GUI',
            'about_version': '版本: v0.6 Beta',
            'about_author': '作者: 鱼丸',
            'about_description': '基于PN532的NFC工具图形界面\n支持Mifare卡片读写、破解、仿真等功能',
            'project_link': '访问项目主页',
            'feedback_link': '问题反馈',
            
            # 标签页
            'tab_function': '功能',
            'tab_nfc_tools': 'NFC工具',
            'tab_about': '关于',
            
            # 功能选择
            'nfc_function_selection': 'NFC功能选择',
            'crack_card': '一键解卡 (mfoc)',
            'nfc_scan': 'NFC扫描 (nfc-list)',
            'hardnested_attack': 'Hardnested攻击',
            
            # 参数设置
            'parameter_settings': '参数设置',
            'advanced_options': '高级选项',
            'select_keyfile': '选择密钥文件',
            
            # 按钮
            'execute': '执行',
            'save': '保存',
            'stop': '停止',
            'connect': '连接',
            'disconnect': '断开',
            'refresh': '刷新',
            'browse': '浏览',
            'import': '导入',
            'export': '导出',
            'save': '保存',
            'clear': '清空',
            'keys': '密钥',
            'advanced_parameters': '高级参数',
            'device_connection': '设备连接',
            'work_mode': '工作模式',
            'set_work_mode': '设置工作模式',
            'connect_device': '连接设备',
            'not_connected': '未连接',
            'select_mode': '选择模式:',
            'reader_mode': '读卡器模式',
            'emulator_mode': '模拟器模式',
            'sniffer_mode': '嗅探模式',
            'select_file': '选择文件...',
            '12_hex_digits': '12位十六进制',
            'key': '密钥:',
            'key_file': '密钥文件:',
            'probe': '探测:',
            'tolerance': '容错:',
            'verbose_mode': '详细模式',
            'type': '类型:',
            
            # NFC扫描类型
            'nfc_type_all': '全部 (511)',
            'nfc_type_iso14443a': 'ISO14443A (1)',
            'nfc_type_felica212k': 'Felica 212k (2)',
            'nfc_type_felica424k': 'Felica 424k (4)',
            'nfc_type_iso14443b': 'ISO14443B (16)',
            'nfc_type_iso14443b2st': 'ISO14443B-2 ST (32)',
            'nfc_type_iso14443b2ask': 'ISO14443B-2 ASK (64)',
            'nfc_type_jewel': 'Jewel (128)',
            'nfc_type_nfcbarcode': 'NFC Barcode (256)',
            
            # 串口设置
            'serial_settings': '串口设置',
            'select_port': '选择串口:',
            'no_port_detected': '未检测到串口',
            'confirm': '确认',
            'cancel': '取消',
            
            # 状态消息
            'connecting': '正在连接...',
            'connected': '已连接',
            'disconnected': '已断开连接',
            'executing': '正在执行...',
            'completed': '执行完成',
            'failed': '执行失败',
            'cancelled': '已取消',
            
            # 错误消息
            'error_no_port': '未选择串口',
            'error_connection_failed': '连接失败',
            'error_command_failed': '命令执行失败',
            'error_file_not_found': '文件未找到',
            'error_invalid_data': '无效数据',
            
            # 成功消息
            'success_connected': '串口连接成功',
            'success_disconnected': '串口断开成功',
            'success_command_completed': '命令执行成功',
            'success_file_saved': '文件保存成功',
            'success_data_imported': '数据导入成功',
            
            # 扇区数据
            'sector_block': '扇区/块',
            'data': '数据',
            'description': '说明',
            'sector_data': '扇区数据',
            'operation_log': '操作日志',
            'no_card_data_loaded': '未加载卡片数据',
            'save_card': '保存卡片',
            'one_click_cracking_mode': '一键解卡模式',
            'nfc_scanning_mode': 'NFC扫描模式',
            'hardnested_attack_mode': 'Hardnested攻击模式',
            'full_screen_sector_data': '扇区数据 - 全屏查看',
            'sector_data_viewer': '扇区数据查看器',
            'no_sector_data': '暂无扇区数据，请先读取卡片数据',
            'export_data': '导出数据',
            'close': '关闭',
            
            # Hardnested攻击
            'sector': '扇区:',
            'key_a': '密钥A',
            'key_b': '密钥B',
            'known_sector': '已知扇区:',
            
            # 工作模式
            'select_type': '选择类型:',
            'sniffer_mode_label': '嗅探模式:',
            'select_slot': '选择卡槽:',
            'slot_0': '卡槽0',
            'slot_1': '卡槽1',
            'slot_2': '卡槽2',
            'slot_3': '卡槽3',
            'slot_4': '卡槽4',
            'slot_5': '卡槽5',
            'slot_6': '卡槽6',
            'slot_7': '卡槽7',
            
            # 卡片类型
            'card_type_mifare1_4b1k': 'Mifare1-4B1K',
            'card_type_ntag': 'Ntag',
            'card_type_15693': '15693',
            'card_type_em4100': 'EM4100',
            'card_type_t5557': 'T5557',
            
            # 嗅探模式选项
            'sniffer_mode_without_tag': '无标签嗅探',
            'sniffer_mode_with_tag': '带标签嗅探',
            
            # 嗅探按钮
            'sniff_without_tag': '无标签嗅探读取',
            'sniff_with_tag': '带标签嗅探读取',

            # 卡工具 - 读取全卡
            'save_to': '保存到:',
            'dump_placeholder': '默认: dumps/时间戳.mfd',
            'default_key': '默认密钥:',
            'key_file_btn': '密钥文件',
            'use_history': '历史密钥',
            'start_read': '开始读取',
            'stop': '停止',
            'custom_keys_only': '仅自定义密钥',
            'key_format_hint': '支持格式:\n  FFFFFFFFFFFF         一行一个\n  FF FF FF FF FF FF   空格分隔\n  FFFFFFFFFFFF ...    一行多个\n  FF-FF-FF-FF-FF-FF   带横线\n  # 开头              注释行',

            # 卡工具 - 修改UID
            'new_uid': '新UID(8位hex):',
            'uid_placeholder': '输入新UID',
            'detect_card': '检测卡片',
            'write_new_uid': '写入新UID',

            # 卡工具 - 手动读写块
            'block_num': '块号:',
            'key_colon': '密钥:',
            'read': '读取',
            'write': '写入',
            'data_32hex': '数据(32位hex):',
            'data_placeholder': '如: 00112233445566778899AABBCCDDEEFF',

            # 卡工具 - 卡类型检测
            'detect_card_type': '检测卡片类型',

            # 卡工具 - 写卡
            'mfd_file': 'MFD文件:',
            'mfd_placeholder': '选择要写入的MFD文件...',
            'load_from_sector': '从扇区加载',
            'write_block0': '写入块0(UID)',
            'write_block0_tip': '写块0(UID)仅支持可改UID的魔法卡:\n  CUID (Gen3/Gen4)、UID/FUID/UFUID (Gen1A)\n标准 MIFARE Classic 卡无法写块0,写卡时若未检测到上述类型会自动取消勾选并跳过块0。',
            'detect_card_write': '检测卡片',
            'start_write': '开始写卡',
            'no_card': '未检测卡片',
            'write_hint': '提示: 支持CUID/UID(FUID/UFUID)卡，自动选择写入方式。区块密钥优先从MFD尾块提取。FUID卡块0写入后永久锁定！',

            # 卡工具 - 子标签页
            'tab_read_full': '读取全卡',
            'tab_modify_uid': '修改UID',
            'tab_manual_block': '手动读写块',
            'tab_card_detect': '卡类型检测',
            'tab_write_card': '写卡',
            'tab_card_tools': '卡工具',
            'tab_sector_tools': '扇区工具',
            'tab_ntag': 'NTAG',
            'tab_advanced': '高级(ISO15693/EM4100)',

            # 模拟器
            'emu_card_type': '卡类型:',
            'emu_slot': '槽位:',
            'emu_slot_n': '槽位{}',
            'emu_uid': 'UID:',
            'uid_8hex': '8位hex',
            'set_uid': '设置UID',
            'emu_read': '读取',
            'emu_mfd_placeholder': '选择要加载的MFD文件...',
            'load_to_emu': '加载到模拟器',
            'emu_card_mifare': 'Mifare 1K',
            'emu_card_ntag': 'NTAG',
            'emu_card_15693': '15693',

            # ConfigDialog
            'select_serial': '选择串口设备',
            'select_serial_device': '选择串口设备',
            'available_ports': '可用串口设备',
            'refresh_hint': '点击刷新按钮重新扫描串口设备',
            'refresh_ports': '刷新串口列表',
            'baud_rate': '波特率:',
            'no_port': '未检测到串口设备',
            'unknown_device': '未知设备',

            'scan': '扫描',
            'read_info': '读取信息',
            'read_block': '读块',
            'write_block': '写块',

            # 写卡
            'read_keys_before_write': '写卡前读密钥',
            'read_keys_before_write_tip': '写卡前先读卡解出真实密钥,用卡自身的密钥认证写入,提高成功率',
            'read_ntag': '读取NTAG',
            'write_ndef_url': '写入NDEF网址',
            'iso_group': 'ISO15693 (15693)',
            'em_group': 'EM4100 (低频 125kHz)',
            'key_type': 'Key类型:',
            'format_confirm_title': '确认格式化',
            'format_confirm_msg': '⚠️ 格式化将清空卡片所有数据!\n\n所有扇区将被重置为传输配置(密钥FFFFFFFFFFFF)。\n块0(UID)将被保留，不会修改。\n确认继续?',
            'write_block0_title': '确认写入块0',
            'write_block0_msg': '⚠️ 写入块0(UID)为不可逆操作！\n\n• 如果这是 FUID 卡，块0写入后永久锁定，无法再次修改！\n• 如果这是 UID/UFUID/CUID 卡，块0可反复写入。\n\n确认继续？',
            'write_block0_msg_supported': '检测到该卡为[{card_gen}],支持写块0(UID)。\n\n⚠️ 写入块0为不可逆操作!\n• FUID 卡块0写入后永久锁定!\n• UID/UFUID/CUID 卡可反复写入。\n\n确认继续?',
            'write_block0_unsupported': '检测到该卡为[{card_gen}],不支持写块0(UID)。\n\n已自动取消勾选\"写入块0(UID)\",本次写卡将跳过块0。\n\n仅 CUID(Gen3/Gen4)、UID/FUID/UFUID(Gen1A) 支持写块0。',
            'write_block0_force_msg': '检测到该卡为[{card_gen}],自动判定不支持写块0。\n\n但如果这是 CUID/UID/FUID 魔法卡(检测可能不准),你可以选择\"强制写入块0\"。\n\n• 选\"Yes\"强制写入(已知是CUID/UID卡时)\n• 选\"No\"跳过块0(保守做法,推荐)\n\n⚠️ 标准卡强制写入块0会失败(不会损坏卡),可放心尝试。',
            'write_progress_format': '写块 %v / %m',
            'try_connect': '正在尝试连接串口: {port} ({baud} baud)...',
            'open_port_ok': '串口打开成功: {port} ({baud} baud)',
            'open_port_fail': '串口打开失败: {port}',
            'init_cmd': '正在初始化PN532命令接口...',
            'init_cmd_done': 'PN532命令接口初始化完成',
            'error_details': '错误详情: ',
            'already_connected': '设备已连接，无需重连。',
            'reconnecting': '正在重新连接串口: {port}...',
            'cannot_reopen': '无法重新打开串口 {port}',
            'no_fw_version': '重新连接后无法获取设备版本信息',
            'reconnect_ok': '重新连接成功，固件版本: {version}',
            'device_connected': '设备已连接',
            'reconnect_done': '设备已成功重新连接。',
            'reconnect_fail': '重新连接失败: ',
            'format_card': '格式化卡片',
            'format_key': '格式化密钥:',

            # 文件格式
            'format_mfd': 'MFD文件 (*.mfd)',
            'format_all': '所有文件 (*)',
            'format_txt': '文本文件 (*.txt)',
            'format_key': '密钥文件 (*.txt *.key *.mfd *.dic);;所有文件 (*)',
        }
        
        # 日志消息
        self.LOG_MESSAGES = {
            'port_occupied_warning': '检测到串口已连接，NFC工具可能无法正常使用。\n是否先断开串口连接？',
            'port_disconnected_for_nfc': '已断开串口连接，可以正常使用NFC工具',
            'port_still_connected_warning': '警告：串口仍处于连接状态，NFC工具可能无法正常工作',
            'writing_sector': '正在写入扇区 {}...',
            'sector_write_success': '扇区 {} 写入成功',
            'sector_write_failed': '扇区 {} 写入失败',
            'all_write_methods_failed': '所有写入方法都失败了',
            'write_timeout': '写入操作超时',
            'creating_temp_file': '正在创建临时文件...',
            'temp_file_created': '临时文件创建成功: {}',
            'cleaning_temp_files': '正在清理临时文件...',
            'temp_files_cleaned': '临时文件清理完成',
        }
        
        # 命令输出消息
        self.COMMAND_MESSAGES = {
            'command_output': '命令输出: {}',
            'command_error': '命令错误: {}',
            'command_timeout': '命令执行超时',
            'command_cancelled': '命令已取消',
            'method_trying': '尝试 {}...',
            'method_success': '{} 成功: 发现成功指示符 \'{}\'',
            'method_failed': '{} 失败: 发现错误指示符 \'{}\'',
            'method_return_code_success': '{} 可能成功: 返回码为0',
            'method_return_code_failed': '{} 失败: 返回码为 {}',
        }
    
    def load_language(self, language_code):
        """加载指定语言的翻译文件"""
        if language_code not in self.supported_languages:
            language_code = "zh"  # 默认使用中文
        
        lang_file = os.path.join(self.lang_dir, f"{language_code}.json")
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            
            # 重新初始化默认文本，确保从中文开始
            self._init_default_texts()
            
            # 更新UI文本
            for key, value in translations.items():
                # 查找对应的键
                for ui_key, ui_value in self.UI_TEXTS.items():
                    if ui_value == key:
                        self.UI_TEXTS[ui_key] = value
            
            self.current_language = language_code
        except Exception as e:
            print(f"Failed to load language file {lang_file}: {e}")
            # 如果加载失败，重置为中文
            self._init_default_texts()
            self.current_language = "zh"
    
    def switch_language(self, language_code):
        """切换语言"""
        # 直接加载新语言，load_language中已包含初始化逻辑
        self.load_language(language_code)
    
    def get_text(self, key, *args):
        """获取文本，支持格式化参数"""
        text = self.UI_TEXTS.get(key, key)
        if args:
            try:
                return text.format(*args)
            except:
                return text
        return text
    
    def get_log_message(self, key, *args):
        """获取日志消息，支持格式化参数"""
        message = self.LOG_MESSAGES.get(key, key)
        if args:
            try:
                return message.format(*args)
            except:
                return message
        return message
    
    def get_command_message(self, key, *args):
        """获取命令消息，支持格式化参数"""
        message = self.COMMAND_MESSAGES.get(key, key)
        if args:
            try:
                return message.format(*args)
            except:
                return message

    def tr(self, zh_text, fallback=None):
        """Translate a hardcoded Chinese string.
        用法: i18n.tr('保存') -> 当前语言的翻译。
        优先查 self.UI_TEXTS 值与 zh_text 相等的项,再查 lang/{locale}.json。
        都找不到时返回 fallback (默认 zh_text 本身)。
        """
        if not zh_text:
            return fallback or zh_text
        # 当前语言就是中文,直接返回
        if self.current_language == 'zh':
            return zh_text
        # 反向查表: zh_text -> English
        import json as _json
        import os as _os
        try:
            base = _os.path.dirname(_os.path.abspath(__file__))
            lang_file = _os.path.join(base, 'lang', f'{self.current_language}.json')
            if _os.path.exists(lang_file):
                with open(lang_file, encoding='utf-8') as f:
                    mapping = _json.load(f)
                if zh_text in mapping:
                    return mapping[zh_text]
        except Exception:
            pass
        return fallback or zh_text
        return message
    
    def get_current_language(self):
        """获取当前语言"""
        return self.current_language
    
    def get_supported_languages(self):
        """获取支持的语言列表"""
        return self.supported_languages

# 创建全局实例
i18n = I18n()
