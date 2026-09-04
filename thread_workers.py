import os
import time
from PyQt6.QtCore import QThread, pyqtSignal
from path_manager import PathManager

try:
    from mfd_parser import (
        decode_mifare_access_bits,
        access_condition_for_block,
        get_data_block_permission,
    )
except Exception:
    decode_mifare_access_bits = None
    access_condition_for_block = None
    get_data_block_permission = None


class FormatCardThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, cmd, uid, key, extra_keys=None):
        super().__init__()
        self.cmd = cmd
        self.uid = uid
        self.key = key
        self.extra_keys = extra_keys or []
        self._fmt = None

    def run(self):
        from card_operations import CardFormatter
        self._fmt = CardFormatter(self.cmd)
        self._fmt.format_card(
            self.uid, self.key,
            lambda m: self.progress.emit(m),
            lambda ok, msg: self.finished.emit(ok, msg),
            extra_keys=self.extra_keys
        )

    def cancel(self):
        if self._fmt:
            self._fmt.cancel()


class OneClickWriteThread(QThread):
    progress_updated = pyqtSignal(str)
    write_finished = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, write_mode, mfd_path, parent_gui):
        super().__init__()
        self.write_mode = write_mode
        self.mfd_path = mfd_path
        self.parent_gui = parent_gui
        self.is_cancelled = False
        self.uid_hex = None
        try:
            if hasattr(self.parent_gui, 'uid_input') and self.parent_gui.uid_input:
                text = self.parent_gui.uid_input.text().strip()
                clean = ''.join(text.split()).upper()
                if clean and len(clean) == 8:
                    self.uid_hex = clean
        except Exception:
            self.uid_hex = None

    def run(self):
        try:
            if self.write_mode == "format":
                success = self._format_card_serial()
            else:
                success = self._write_card_serial()
            self.write_finished.emit(success)
        except Exception as e:
            self.error_occurred.emit(f"写卡过程中出错: {str(e)}")
            self.write_finished.emit(False)

    def cancel(self):
        self.is_cancelled = True

    def _get_cmd_and_uid(self):
        cmd = getattr(self.parent_gui, 'cmd', None)
        if not cmd:
            self.progress_updated.emit("错误: 设备未连接或未初始化")
            return None, None
        if self.uid_hex and len(self.uid_hex) == 8:
            return cmd, bytes.fromhex(self.uid_hex)
        try:
            scan = cmd.hf_14a_scan()
            if not scan:
                self.progress_updated.emit("未检测到卡片")
                return None, None
            uid = scan[0]['uid']
            self.uid_hex = uid.hex().upper()
            return cmd, uid
        except Exception as e:
            self.progress_updated.emit(f"检测卡片失败: {e}")
            return None, None

    def _read_mfd_data(self):
        try:
            with open(self.mfd_path, 'rb') as f:
                return f.read()
        except Exception as e:
            self.progress_updated.emit(f"读取MFD文件失败: {e}")
            return None

    def _format_card_serial(self):
        cmd, uid = self._get_cmd_and_uid()
        if not cmd or not uid:
            return False
        self.progress_updated.emit("开始格式化卡片...")
        try:
            from card_operations import CardFormatter
            fmt = CardFormatter(cmd)
            success = [False]
            def done(ok, msg):
                success[0] = ok
                self.progress_updated.emit(msg)
            fmt.format_card(uid, "FFFFFFFFFFFF", lambda m: self.progress_updated.emit(m), done)
            return success[0]
        except Exception as e:
            self.progress_updated.emit(f"格式化出错: {e}")
            return False

    def _write_card_serial(self):
        cmd, uid = self._get_cmd_and_uid()
        if not cmd or not uid:
            return False
        mfd_data = self._read_mfd_data()
        if not mfd_data:
            return False
        self.progress_updated.emit(f"开始写入 (UID: {uid.hex().upper()})...")
        try:
            key_text = "FFFFFFFFFFFF"
            try:
                if hasattr(self.parent_gui, 'write_key_input') and self.parent_gui.write_key_input:
                    k = self.parent_gui.write_key_input.text().strip()
                    if k and len(k) >= 6:
                        key_text = k
            except Exception:
                pass
            default_key = bytes.fromhex(key_text)
            write_block0 = False
            try:
                if hasattr(self.parent_gui, 'write_block0_checkbox') and self.parent_gui.write_block0_checkbox:
                    write_block0 = self.parent_gui.write_block0_checkbox.isChecked()
            except Exception:
                pass
            helper = SerialWriteHelper(cmd, mfd_data, uid, default_key, write_block0)
            success = [False]
            def progress(m):
                self.progress_updated.emit(m)
            def done(ok, msg):
                success[0] = ok
            helper.run(progress, done)
            return success[0]
        except Exception as e:
            self.progress_updated.emit(f"写入出错: {e}")
            return False


class SerialWriteHelper:
    def __init__(self, cmd, mfd_data, uid, default_key_bytes, write_block0=True,
                 verify_trailer=True, verify_block0=True, max_block_retries=2,
                 card_keys=None, force_write_block0=False):
        """写卡辅助。

        :param card_keys: dict{sector: key_bytes},可选。来自读卡解出的卡真实密钥,
          优先于 MFD trailer 中的密钥用于认证。
        :param force_write_block0: 强制写入块0(跳过卡类型检测)。
          用于用户明确知道是 CUID/UID 卡但自动检测误判为 Standard 的场景。
        """
        self.cmd = cmd
        self.mfd_data = mfd_data
        self.uid = uid
        self.default_key_bytes = default_key_bytes
        self.write_block0 = write_block0
        self.is_cancelled = False
        self.written_count = 0
        self.total_blocks = 0
        self.verify_trailer = verify_trailer
        self.verify_block0 = verify_block0
        self.max_block_retries = max(1, int(max_block_retries))
        self.gen_detected = None
        self.card_keys = card_keys or {}
        self.force_write_block0 = force_write_block0

    def cancel(self):
        self.is_cancelled = True

    def detect_card_gen(self):
        if self.gen_detected is not None:
            return self.gen_detected
        try:
            self.cmd.mf1_authenticated_sector = -1
            if self.cmd.isGen1a():
                self.gen_detected = "Gen1A"
                return self.gen_detected
            if self.cmd.isGen3():
                self.gen_detected = "Gen3"
                return self.gen_detected
            try:
                if self.cmd.isGen4():
                    self.gen_detected = "Gen4"
                    return self.gen_detected
            except Exception:
                pass
            self.gen_detected = "Standard"
        except Exception:
            self.gen_detected = "Standard"
        return self.gen_detected

    def try_write_block(self, block_num, block_data, keys_to_try):
        for try_key in keys_to_try:
            if self.is_cancelled:
                break
            try:
                self.cmd.hf_14a_scan()
                self.cmd.mf1_authenticated_sector = -1
                if self.cmd.mf1_write_block(self.uid, block_num, try_key, block_data):
                    return True
            except Exception:
                pass
        return False

    def try_write_block_with_verify(self, block_num, block_data, keys_to_try, do_verify):
        """带写后读回校验的写入。重试 max_block_retries 次。

        Returns:
          ('ok', key_used) 写入并校验成功
          ('mismatch', key_used) 写入成功但读回不匹配
          ('fail', None) 写入失败
          ('cancelled', None) 已取消
        """
        for attempt in range(self.max_block_retries):
            if self.is_cancelled:
                return ('cancelled', None)
            self.cmd.hf_14a_scan()
            self.cmd.mf1_authenticated_sector = -1
            for try_key in keys_to_try:
                if self.is_cancelled:
                    return ('cancelled', None)
                try:
                    ok, write_resp, verify_match = self.cmd.mf1_write_block_verify(
                        self.uid, block_num, try_key, block_data)
                except Exception:
                    ok = False
                    verify_match = False
                if ok and (not do_verify or verify_match):
                    return ('ok', try_key)
                if ok and do_verify and not verify_match:
                    continue
            self.reset_card()
        return ('fail', None)

    def reset_card(self):
        try:
            self.cmd.device.halt()
            time.sleep(0.05)
            self.cmd.hf_14a_scan()
        except Exception:
            pass

    def _trailer_write_safe(self, sector, block_num, block_data):
        """写尾块前的安全检查：拒绝会永久锁死扇区的尾块配置。

        MIFARE Classic 的尾块写入 access 控制位后立即生效。若写入的
        access 配置使数据块对 KeyA 和 KeyB 都不可读（brick 配置），
        该扇区将永久无法再被读取/改写。写卡前强制校验，杜绝误写损坏卡片。

        Returns (safe, reason):
          safe: True 表示可安全写入；False 表示应跳过该尾块。
        """
        if decode_mifare_access_bits is None or len(block_data) < 16:
            return True, ""
        trailer_block = block_num
        try:
            ab = decode_mifare_access_bits(bytes(block_data[:16]))
            if not ab.get("valid"):
                return False, f"尾块 access 反码校验失败(损坏)"
            normal = ab["normal"]
        except ValueError:
            return False, f"尾块 access 反码校验失败(损坏)"
        # 计算数据块(本扇区第0块)对应的访问条件
        block0 = (block_num // 4) * 4
        cond_a = access_condition_for_block(block0, trailer_block, normal)
        ca = get_data_block_permission(cond_a, "A")
        cb = get_data_block_permission(cond_a, "B")
        read_a = ca.get("R", False)
        read_b = cb.get("R", False)
        if not read_a and not read_b:
            return False, "写入后数据块对 KeyA/KeyB 都不可读(会锁死扇区)"
        return True, ""

    def run(self, progress_cb, finished_cb):
        try:
            mfd_size = len(self.mfd_data)
            if mfd_size == 1024:
                total_sectors = 16
            elif mfd_size == 4096:
                total_sectors = 40
            else:
                progress_cb(f"不支持的MFD大小: {mfd_size} bytes")
                finished_cb(False, "不支持的MFD大小")
                return

            total_blocks = total_sectors * 4
            self.total_blocks = total_blocks
            self.written_count = 0
            total_skipped = 0
            total_verify_failed = 0
            default_key_bytes = self.default_key_bytes

            gen = self.detect_card_gen()
            progress_cb(f"检测到卡类型: {gen}")

            for sector in range(total_sectors):
                # 每扇区开头重新选卡(修复多块写入时标签选中丢失)
                try:
                    self.cmd.hf_14a_scan()
                except Exception:
                    pass

                for block_in_sector in range(4):
                    if self.is_cancelled:
                        progress_cb("写入已取消")
                        finished_cb(False, "已取消")
                        return

                    block_num = sector * 4 + block_in_sector
                    if block_num > 0 and block_num % 16 == 0:
                        self.reset_card()

                    offset = sector * 64 + block_in_sector * 16
                    block_data = self.mfd_data[offset:offset+16]
                    if len(block_data) < 16:
                        block_data = block_data.ljust(16, b'\x00')

                    trailer_offset = sector * 64 + 48
                    key_a = self.mfd_data[trailer_offset:trailer_offset+6]
                    key_b = self.mfd_data[trailer_offset+10:trailer_offset+16]

                    hex_str = ' '.join(f'{b:02X}' for b in block_data)
                    progress_cb(f"[{self.written_count+1}/{self.total_blocks}] 扇区{sector} 块{block_num}: {hex_str}")

                    keys_to_try = []
                    # 卡的真实密钥优先(读卡解出的)
                    card_key = self.card_keys.get(sector)
                    if card_key and card_key not in keys_to_try:
                        keys_to_try.append(card_key)
                    for k in (key_a, key_b, default_key_bytes):
                        if k not in keys_to_try:
                            keys_to_try.append(k)

                    if block_num == 0:
                        if not self.write_block0:
                            progress_cb("  -> 跳过(未勾选写入块0)")
                            total_skipped += 1
                            continue

                        # 标准写入尝试(适用于 CUID/Gen3/Gen4)
                        write_ok = self.try_write_block(0, block_data, keys_to_try)

                        # 标准写入失败时,尝试 Gen1A 后门解锁写入(适用于 UID/FUID/UFUID)
                        # 解锁序列: isGen1a() 内部发 0x40 + 0x43 后门命令解锁,
                        # 解锁成功后立刻写块0 (中间不能 hf_14a_scan,会重置解锁状态)
                        gen1a_unlock_attempted = False
                        if not write_ok and (gen == "Gen1A" or self.force_write_block0):
                            progress_cb("  标准写入失败,尝试Gen1A后门解锁写入...")
                            gen1a_unlock_attempted = True
                            try:
                                # isGen1a() 发后门命令并返回 True/False
                                unlocked = False
                                try:
                                    unlocked = bool(self.cmd.isGen1a())
                                except Exception as e:
                                    progress_cb(f"  -> isGen1a调用异常: {e}")
                                if unlocked:
                                    progress_cb("  -> Gen1A后门解锁成功,立刻写块0...")
                                    # 解锁后直接写,不 scan,不复位认证缓存
                                    self.cmd.mf1_authenticated_sector = -1
                                    for try_key in keys_to_try:
                                        try:
                                            if self.cmd.mf1_write_block(self.uid, 0, try_key, block_data):
                                                write_ok = True
                                                progress_cb("  -> Gen1A后门解锁写入成功")
                                                break
                                        except Exception:
                                            pass
                                    if not write_ok:
                                        progress_cb("  -> 解锁成功但写入仍失败")
                                else:
                                    progress_cb("  -> Gen1A后门解锁失败(卡不支持后门命令)")
                            except Exception as e:
                                progress_cb(f"  -> Gen1A解锁异常: {e}")

                        # block0 失败后,如果尝试过 Gen1A 解锁,必须 halt + 重新选号
                        # 恢复卡到正常状态,否则后续块的认证会失败
                        if gen1a_unlock_attempted and not write_ok:
                            try:
                                self.cmd.device.halt()
                                import time as _time
                                _time.sleep(0.05)
                                self.cmd.hf_14a_scan()
                                self.cmd.mf1_authenticated_sector = -1
                            except Exception:
                                pass

                        if write_ok:
                            if self.verify_block0:
                                self.cmd.mf1_authenticated_sector = -1
                                self.cmd.hf_14a_scan()
                                _, _, vm = self.cmd.mf1_write_block_verify(
                                    self.uid, 0, default_key_bytes, block_data)
                                if not vm:
                                    total_verify_failed += 1
                                    progress_cb("  -> 块0写入但读回校验失败(UID可能未生效)")
                                    continue
                            self.written_count += 1
                            progress_cb("  -> 块0写入成功(已校验)")
                        else:
                            total_skipped += 1
                            if self.force_write_block0:
                                progress_cb("  -> 块0写入失败(强制写入也未成功,可能是标准卡不可写块0)")
                            else:
                                progress_cb("  -> 块0写入失败(非CUID/UID/FUID或已锁定)")
                        continue

                    is_trailer = (block_in_sector == 3)
                    do_verify = is_trailer and self.verify_trailer

                    if is_trailer:
                        tsafe, treason = self._trailer_write_safe(sector, block_num, block_data)
                        if not tsafe:
                            progress_cb(f"  -> 禁止写入 {treason}(已跳过,保护该扇区)")
                            total_skipped += 1
                            continue

                    result, used_key = self.try_write_block_with_verify(
                        block_num, block_data, keys_to_try, do_verify)
                    if result == 'ok':
                        if do_verify:
                            progress_cb(f"  -> 写入成功(已校验) 密钥 {used_key.hex().upper()}")
                        else:
                            progress_cb("  -> 写入成功")
                        self.written_count += 1
                    elif result == 'mismatch':
                        total_verify_failed += 1
                        total_skipped += 1
                        progress_cb(f"  -> 写入成功但读回不匹配(尝试 {self.max_block_retries} 次)")
                    elif result == 'cancelled':
                        progress_cb("写入已取消")
                        finished_cb(False, "已取消")
                        return
                    else:
                        progress_cb("  -> 写入失败")
                        total_skipped += 1

            progress_cb(f"===== 写卡完成 =====")
            progress_cb(f"成功: {self.written_count}/{self.total_blocks} 块")
            if total_skipped > 0:
                progress_cb(f"跳过/失败: {total_skipped} 块")
            if total_verify_failed > 0:
                progress_cb(f"写后校验失败: {total_verify_failed} 块")

            if self.written_count == self.total_blocks:
                finished_cb(True, "所有块写入成功")
            elif self.written_count > 0:
                finished_cb(True, f"部分写入成功 ({self.written_count}/{self.total_blocks})")
            else:
                finished_cb(False, "所有块写入失败")

        except Exception as e:
            progress_cb(f"写卡出错: {str(e)}")
            finished_cb(False, str(e))


class EmulatorThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self, cmd, op_name, slot, data=None, uid_hex=None, card_type=1):
        super().__init__()
        self.cmd = cmd
        self.op_name = op_name
        self.slot = slot
        self.data = data
        self.uid_hex = uid_hex
        self.card_type = card_type
        self.result = None

    def run(self):
        from card_operations import EmulatorOperator
        op = EmulatorOperator(self.cmd)
        if self.op_name == "read":
            self.result = op.read_slot(self.slot, self.card_type, lambda m: self.progress.emit(m))
        elif self.op_name == "load":
            self.result = op.load_mfd(self.data, self.slot, lambda m: self.progress.emit(m))
        elif self.op_name == "setuid":
            self.result = op.set_uid(self.slot, self.uid_hex, lambda m: self.progress.emit(m))
        self.finished.emit(self.result)


class DumpReadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object, object, object)

    def __init__(self, cmd, key_bytes, history_keys, custom_keys=None, custom_only=False):
        super().__init__()
        self.cmd = cmd
        self.key_bytes = key_bytes
        self.history_keys = history_keys
        self.custom_keys = custom_keys
        self.custom_only = custom_only
        self._reader = None

    def run(self):
        from card_operations import DumpReader
        self._reader = DumpReader(self.cmd, self.key_bytes, self.history_keys, self.custom_keys, self.custom_only)
        self._reader.read_card(
            progress_cb=lambda m: self.progress.emit(m),
            finished_cb=lambda *a: self.finished.emit(*a)
        )

    def cancel(self):
        if self._reader:
            self._reader.cancel()


class WriteCardThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, cmd, mfd_data, uid, default_key_bytes, write_block0, card_keys=None,
                 force_write_block0=False):
        super().__init__()
        self.cmd = cmd
        self.mfd_data = mfd_data
        self.uid = uid
        self.default_key_bytes = default_key_bytes
        self.write_block0 = write_block0
        self.card_keys = card_keys or {}
        self.force_write_block0 = force_write_block0
        self._helper = None

    def run(self):
        self._helper = SerialWriteHelper(self.cmd, self.mfd_data, self.uid,
                                         self.default_key_bytes, self.write_block0,
                                         card_keys=self.card_keys,
                                         force_write_block0=self.force_write_block0)
        self._helper.run(
            lambda m: self.progress.emit(m),
            lambda ok, msg: self.finished.emit(ok, msg)
        )

    def cancel(self):
        if self._helper:
            self._helper.cancel()
