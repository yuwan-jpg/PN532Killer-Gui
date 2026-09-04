"""
Card operations module - serial-based card operations for PN532
All operations run synchronously with progress callbacks (not QThread)
"""
import os
import time
import struct
from pn532_enum import MifareCommand, Command, Status


DEFAULT_KEYS = [
    b'\xff\xff\xff\xff\xff\xff',
    b'\xa0\xa1\xa2\xa3\xa4\xa5',
    b'\xb0\xb1\xb2\xb3\xb4\xb5',
    b'\x4d\x3a\x99\xc3\x51\xdd',
    b'\x1a\x98\x2c\x7e\x45\x9a',
    b'\xd3\xf7\xd3\xf7\xd3\xf7',
    b'\xaa\xbb\xcc\xdd\xee\xff',
    b'\x00\x00\x00\x00\x00\x00',
    b'\x11\x11\x11\x11\x11\x11',
    b'\x22\x22\x22\x22\x22\x22',
    b'\x33\x33\x33\x33\x33\x33',
    b'\x44\x44\x44\x44\x44\x44',
    b'\x55\x55\x55\x55\x55\x55',
    b'\x66\x66\x66\x66\x66\x66',
    b'\x77\x77\x77\x77\x77\x77',
    b'\x88\x88\x88\x88\x88\x88',
    b'\x99\x99\x99\x99\x99\x99',
    b'\xaa\xaa\xaa\xaa\xaa\xaa',
    b'\xbb\xbb\xbb\xbb\xbb\xbb',
    b'\xcc\xcc\xcc\xcc\xcc\xcc',
    b'\xdd\xdd\xdd\xdd\xdd\xdd',
    b'\xee\xee\xee\xee\xee\xee',
    b'\x01\x02\x03\x04\x05\x06',
    b'\x12\x34\x56\x78\x9a\xbc',
    b'\xab\xcd\xef\xab\xcd\xef',
    b'\x0a\x0b\x0c\x0d\x0e\x0f',
    b'\xa1\xb2\xc3\xd4\xe5\xf6',
    b'\x14\x72\x64\xa3\x89\xb0',
    b'\x50\x6f\x63\x6b\x65\x74',
    b'\x00\x01\x02\x03\x04\x05',
    b'\x1a\x2b\x3c\x4d\x5e\x6f',
    b'\x0f\x0e\x0d\x0c\x0b\x0a',
    b'\xc0\xc1\xc2\xc3\xc4\xc5',
    b'\xde\xad\xbe\xef\xde\xad',
    b'\xca\xfe\xba\xbe\xca\xfe',
    b'\x0d\x0e\x0a\x0d\x0e\x0a',
    b'\x66\x6f\x6f\x62\x61\x72',
    b'\xba\xdc\x0f\xfe\xba\xdc',
    b'\xfe\xed\xde\xad\xbe\xef',
    b'\xde\xad\xc0\xde\xde\xad',
    b'\x0a\x00\x00\x00\x00\x00',
    b'\x10\x00\x00\x00\x00\x00',
    b'\x05\x00\x00\x00\x00\x00',
    b'\x00\x00\x00\x00\x00\x01',
    b'\x00\x00\x00\x00\x00\x02',
    b'\x00\x00\x00\x00\x00\x03',
    b'\x00\x00\x00\x00\x00\x04',
    b'\x00\x00\x00\x00\x00\x05',
    b'\x00\x00\x00\x00\x00\x10',
    b'\x00\x00\x00\x00\x00\xa0',
    b'\xff\xff\xff\xff\xff\xfe',
]


def collect_progress(cb, msg):
    if cb:
        cb(msg)


class DumpReader:
    def __init__(self, cmd, default_key_bytes, history_keys=None, custom_keys=None, custom_only=False):
        self.cmd = cmd
        self.default_key_bytes = default_key_bytes
        self.history_keys = history_keys or []
        self.custom_keys = custom_keys
        self.custom_only = custom_only
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def _read_sector_blocks(self, uid, sector, key, mfd_data):
        """Read all 4 blocks of a sector using the given key. Returns True if any block read.

        Optimization: MIFARE Classic authenticates an entire sector with one auth.
        We reset the auth state once on entry (to handle key-switching cleanly),
        let the first read trigger authentication, and reuse the authenticated
        session for the remaining 3 blocks. On auth failure we bail out immediately
        instead of wasting 3 more scan+auth cycles.
        """
        self.cmd.mf1_authenticated_sector = -1
        block0 = sector * 4
        resp = self.cmd.mf1_read_block(block0, key)
        if not (resp and resp.parsed and len(resp.parsed) >= 16):
            return False
        offset_base = sector * 64
        mfd_data[offset_base:offset_base + 16] = resp.parsed[:16]
        for bi in range(1, 4):
            block = sector * 4 + bi
            resp = self.cmd.mf1_read_block(block, key)
            if resp and resp.parsed and len(resp.parsed) >= 16:
                offset = offset_base + bi * 16
                mfd_data[offset:offset + 16] = resp.parsed[:16]
        return True

    def _extract_keys_from_trailer(self, sector, mfd_data):
        """从 trailer 提取 Key A 和 Key B"""
        offset = sector * 64 + 48
        trailer = mfd_data[offset:offset+16]
        if len(trailer) >= 16:
            return trailer[0:6], trailer[10:16]
        return None, None

    def _diffuse_trailer_keys(self, progress_cb, sector, mfd_data, key_pool):
        """从成功读取的扇区尾块提取 KeyA/KeyB,加入密钥池横向传播。"""
        ka, kb = self._extract_keys_from_trailer(sector, mfd_data)
        new_keys = []
        for nk in (ka, kb):
            if nk and nk not in key_pool:
                key_pool.append(nk)
                new_keys.append(nk.hex().upper())
        if new_keys:
            collect_progress(progress_cb, f"  从尾块提取新密钥: {', '.join(new_keys)}")

    def _fmt_elapsed(self, start):
        dt = time.time() - start
        if dt < 60:
            return f"{dt:.1f}s"
        return f"{int(dt//60)}m{int(dt%60)}s"

    def read_card(self, progress_cb=None, finished_cb=None):
        _t0 = time.time()
        try:
            collect_progress(progress_cb, "正在检测卡片...")
            scan = self.cmd.hf_14a_scan()
            if not scan:
                collect_progress(progress_cb, "未检测到卡片")
                if finished_cb: finished_cb(False, "未检测到卡片")
                return
            uid = scan[0]['uid']
            sak = scan[0]['sak']
            collect_progress(progress_cb, f"UID: {uid.hex().upper()}  SAK: {sak.hex()}")

            mfd_data = bytearray(1024)
            sectors_ok = [False] * 16

            key_pool = []
            if self.custom_only:
                for k in (self.history_keys or []):
                    kb = bytes.fromhex(k) if isinstance(k, str) else k
                    if kb not in key_pool:
                        key_pool.append(kb)
                if self.default_key_bytes not in key_pool:
                    key_pool.insert(0, self.default_key_bytes)
            else:
                if self.default_key_bytes not in key_pool:
                    key_pool.append(self.default_key_bytes)
                if self.custom_keys:
                    for k in self.custom_keys:
                        kb = bytes.fromhex(k) if isinstance(k, str) else k
                        if kb not in key_pool:
                            key_pool.append(kb)
                for k in self.history_keys:
                    kb = bytes.fromhex(k) if isinstance(k, str) else k
                    if kb not in key_pool:
                        key_pool.append(kb)
                for k in DEFAULT_KEYS:
                    if k not in key_pool:
                        key_pool.append(k)

            collect_progress(progress_cb, f"内置 {len(key_pool)} 个弱口令密钥，开始批量扫描...")

            # 批次检测：用 mf1_check_keys_of_sectors 快速找出可用密钥
            mask = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
            batch_sector_keys = {}
            try:
                self.cmd.mf1_authenticated_sector = -1
                batch = self.cmd.mf1_check_keys_of_sectors(mask, key_pool)
                if isinstance(batch, dict):
                    batch_sector_keys = batch.get('sectorKeys', {})
                    if batch_sector_keys:
                        collect_progress(progress_cb, f"批量检测到 {len(batch_sector_keys)} 个扇区有匹配密钥")
                        for sk, skey in batch_sector_keys.items():
                            if 0 <= sk < 16 and skey not in key_pool:
                                key_pool.append(skey)
                                collect_progress(progress_cb, f"  扇区{sk} 发现密钥: {skey.hex().upper()}")
                    else:
                        collect_progress(progress_cb, "批量检测未发现匹配密钥")
                else:
                    collect_progress(progress_cb, "批量检测未返回有效结果")
            except Exception as e:
                collect_progress(progress_cb, f"批量检测失败({e})")

            # 快照第一轮的 key 集合,第二轮只尝试新发现的 key
            first_pass_keys = set(key_pool)

            def _read_known_sector(sector, key):
                """用已知 key 读取扇区并提取尾块新密钥扩散。成功返回 True。"""
                if self._read_sector_blocks(uid, sector, key, mfd_data):
                    sectors_ok[sector] = True
                    self._diffuse_trailer_keys(progress_cb, sector, mfd_data, key_pool)
                    return True
                return False

            # ---- 第一轮: 0x3A 已匹配的扇区直接定向读取,跳过逐 key 遍历 ----
            collect_progress(progress_cb, "定向读取批量检测命中的扇区...")
            for sk, skey in batch_sector_keys.items():
                if not (0 <= sk < 16):
                    continue
                if self.is_cancelled:
                    collect_progress(progress_cb, "已取消")
                    if finished_cb: finished_cb(False, None, "已取消")
                    return
                collect_progress(progress_cb, f"---- 扇区 {sk} [批量命中 密钥 {skey.hex().upper()}] ----")
                if _read_known_sector(sk, skey):
                    collect_progress(progress_cb, f"  扇区{sk} 读取成功 [OK]")

            # ---- 第一轮(补):未命中扇区逐 key 试探 ----
            collect_progress(progress_cb, "开始逐扇区读取剩余扇区...")
            for sector in range(16):
                if self.is_cancelled:
                    collect_progress(progress_cb, "已取消")
                    if finished_cb: finished_cb(False, None, "已取消")
                    return
                if sectors_ok[sector]:
                    continue
                collect_progress(progress_cb, f"---- 扇区 {sector} ----")
                found = False
                for kidx, key in enumerate(key_pool):
                    if self.is_cancelled:
                        return
                    if _read_known_sector(sector, key):
                        collect_progress(progress_cb, f"  密钥 [{kidx+1}/{len(key_pool)}] {key.hex().upper()} [OK]")
                        found = True
                        break
                if not found:
                    collect_progress(progress_cb, "  所有密钥失败")

            # ---- 第二轮: 只尝试第一轮新发现的 key ----
            failed = [s for s in range(16) if not sectors_ok[s]]
            if failed:
                new_keys = [k for k in key_pool if k not in first_pass_keys]
                if new_keys:
                    collect_progress(progress_cb, f"\n===== 第二轮: 用 {len(new_keys)} 个新发现密钥重试 {len(failed)} 个扇区 =====")
                    for sector in failed:
                        if self.is_cancelled:
                            return
                        for key in new_keys:
                            if _read_known_sector(sector, key):
                                collect_progress(progress_cb, f"  扇区{sector} [OK] 密钥 {key.hex().upper()}")
                                break
                else:
                    collect_progress(progress_cb, f"\n===== 无新密钥可重试,失败 {len(failed)} 个扇区 =====")

            total_ok = sum(1 for s in sectors_ok if s)
            elapsed = self._fmt_elapsed(_t0)
            ok_text = f"成功: {total_ok}/16 个扇区"
            collect_progress(progress_cb, f"\n{'='*30}")
            collect_progress(progress_cb, ok_text)
            collect_progress(progress_cb, f"本次读取耗时: {elapsed}")

            if total_ok > 0:
                collect_progress(progress_cb, "数据已就绪")
            if finished_cb:
                finished_cb(total_ok > 0, mfd_data, f"{ok_text} ({elapsed})")
        except Exception as e:
            collect_progress(progress_cb, f"读取出错: {str(e)}")
            if finished_cb: finished_cb(False, None, str(e))




class SingleBlockOperator:
    def __init__(self, cmd):
        self.cmd = cmd

    def read_block(self, uid, block_num, key_hex, progress_cb=None, key_type="auto"):
        """key_type: 'auto' (A→B), 'A', 'B'"""
        try:
            key = bytes.fromhex(key_hex.replace(' ', ''))
            if key_type == "A":
                self.cmd.mf1_authenticated_useKeyA = True
            elif key_type == "B":
                self.cmd.mf1_authenticated_useKeyA = False
            self.cmd.mf1_authenticated_sector = -1
            resp = self.cmd.mf1_read_block(block_num, key)
            if key_type == "A" and resp and resp.parsed and len(resp.parsed) >= 16:
                # 强制 Key A:若 mf1_read_block 内部已切到 Key B,这里会因为响应失败
                # 真实硬件会立即返回错误 status,我们判断返回的 hf_tag_ok 状态
                if resp.status and resp.status.value != 0:
                    collect_progress(progress_cb, f"块{block_num} Key A 认证失败")
                    return None
            if resp and resp.parsed and len(resp.parsed) >= 16:
                data = resp.parsed[:16]
                hex_str = ' '.join(f'{b:02X}' for b in data)
                collect_progress(progress_cb, f"块{block_num} 读取成功: {hex_str}")
                return data
            else:
                collect_progress(progress_cb, f"块{block_num} 读取失败(认证错误)")
                return None
        except Exception as e:
            collect_progress(progress_cb, f"读取错误: {str(e)}")
            return None

    def write_block(self, uid, block_num, key_hex, data_hex, progress_cb=None, key_type="auto"):
        try:
            key = bytes.fromhex(key_hex.replace(' ', ''))
            data = bytes.fromhex(data_hex.replace(' ', ''))
            if len(data) != 16:
                collect_progress(progress_cb, "数据必须为32位十六进制(16字节)")
                return False
            self.cmd.mf1_authenticated_sector = -1
            self.cmd.hf_14a_scan()  # 写前选卡
            # 用 mf1_write_block_verify(读回验证为准)替代直接 mf1_write_block
            # 解决 @expect_response 装饰器偶发误报 write_ok=False 但实际写入成功的问题
            ok, write_resp, verify_match = self.cmd.mf1_write_block_verify(uid, block_num, key, data)
            # ok 以读回结果为准(verify_match=True 则 ok=True)
            if ok and verify_match:
                collect_progress(progress_cb, f"块{block_num} 写入成功(已校验)")
                return True
            elif ok and not verify_match:
                collect_progress(progress_cb, f"块{block_num} 写入成功但读回不匹配")
                return True
            else:
                collect_progress(progress_cb, f"块{block_num} 写入失败")
                return False
        except Exception as e:
            collect_progress(progress_cb, f"写入错误: {str(e)}")
            return False


class CardFormatter:
    def __init__(self, cmd):
        self.cmd = cmd
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def _build_key_pool(self, key_hex, extra_keys=None):
        pool = [bytes.fromhex(key_hex.replace(' ', ''))]
        if extra_keys:
            for k in extra_keys:
                if isinstance(k, (bytes, bytearray)) and len(k) == 6 and k not in pool:
                    pool.append(k)
        return pool

    def _try_write(self, uid, block, block_data, keys):
        for key in keys:
            if self.is_cancelled:
                return False
            try:
                if block % 4 == 3:
                    ok, _, _ = self.cmd.mf1_write_block_verify(uid, block, key, block_data)
                else:
                    ok = self.cmd.mf1_write_block(uid, block, key, block_data)
                if ok:
                    return True
            except Exception:
                pass
        return False

    def format_card(self, uid, key_hex="FFFFFFFFFFFF", progress_cb=None, finished_cb=None, extra_keys=None):
        try:
            keys = self._build_key_pool(key_hex, extra_keys)
            collect_progress(progress_cb, "开始格式化卡片...")
            total = 64
            written = 0
            written_all = True
            for block in range(1, total):
                if self.is_cancelled:
                    collect_progress(progress_cb, "格式化已取消")
                    if finished_cb: finished_cb(False, "已取消")
                    return
                # 每块写入前重新选卡并复位认证状态,避免 PN532 标签选中丢失
                # 导致后续块连续认证失败(多块写入不稳定)。
                self.cmd.mf1_authenticated_sector = -1
                try:
                    self.cmd.hf_14a_scan()
                except Exception:
                    pass
                if block % 4 == 3:
                    block_data = b'\xff' * 6 + b'\xff\x07\x80\x69' + b'\xff' * 6
                else:
                    block_data = b'\x00' * 16
                ok = self._try_write(uid, block, block_data, keys)
                if ok:
                    written += 1
                    collect_progress(progress_cb, f"[{block}/{total-1}] 块{block}: OK")
                else:
                    written_all = False
                    collect_progress(progress_cb, f"[{block}/{total-1}] 块{block}: FAIL")
            collect_progress(progress_cb, f"格式化完成: {written}/{total-1} (跳过块0 UID)")
            if written_all:
                if finished_cb: finished_cb(True, "格式化成功")
            elif written > 0:
                if finished_cb: finished_cb(True, f"部分成功 ({written}/{total-1})")
            else:
                if finished_cb: finished_cb(False, "格式化失败: 所有块均写入失败，密钥可能不正确")
        except Exception as e:
            collect_progress(progress_cb, f"格式化出错: {str(e)}")
            if finished_cb: finished_cb(False, str(e))


class UidOperator:
    def __init__(self, cmd):
        self.cmd = cmd

    def _detect_gen(self, scan):
        """根据 SAK/ATQA + 试探 Gen1A/3/4 返回卡类型字符串。"""
        if not scan:
            return "Unknown"
        try:
            self.cmd.mf1_authenticated_sector = -1
            if self.cmd.isGen1a():
                return "Gen1A"
            try:
                if self.cmd.isGen3():
                    return "Gen3"
            except Exception:
                pass
            try:
                if self.cmd.isGen4():
                    return "Gen4"
            except Exception:
                pass
        except Exception:
            pass
        return "Standard"

    def _build_block0(self, new_uid, sak=b'\x08', atqa=b'\x04\x00'):
        """构造块 0: UID + BCC + SAK + ATQA + 8 字节填充。"""
        if len(new_uid) == 4:
            bcc = new_uid[0] ^ new_uid[1] ^ new_uid[2] ^ new_uid[3]
            return new_uid + bytes([bcc]) + sak + atqa + b'\x00' * 8
        if len(new_uid) == 7:
            return new_uid + b'\x7B' + b'\x00' * 8
        raise ValueError(f"UID 长度必须是 4 或 7 字节,当前 {len(new_uid)} 字节")

    def set_uid(self, uid_hex, progress_cb=None, finished_cb=None):
        try:
            new_uid = bytes.fromhex(uid_hex.replace(' ', ''))
            if len(new_uid) not in (4, 7):
                collect_progress(progress_cb, "UID必须为4字节(8位)或7字节(14位)十六进制")
                if finished_cb: finished_cb(False, "UID长度错误")
                return

            collect_progress(progress_cb, "检测卡片类型...")
            scan = self.cmd.hf_14a_scan()
            if not scan:
                collect_progress(progress_cb, "未检测到卡片")
                if finished_cb: finished_cb(False, "未检测到卡片")
                return

            current_uid = scan[0]['uid']
            collect_progress(progress_cb, f"当前UID: {current_uid.hex().upper()}")
            gen = self._detect_gen(scan)
            collect_progress(progress_cb, f"卡类型: {gen}")

            block0 = self._build_block0(new_uid)
            key = b'\xff\xff\xff\xff\xff\xff'
            write_ok = False
            method_used = None

            collect_progress(progress_cb, "尝试标准 MIFARE 写块 0...")
            self.cmd.mf1_authenticated_sector = -1
            self.cmd.hf_14a_scan()
            write_ok = bool(self.cmd.mf1_write_block(current_uid, 0, key, block0))
            if write_ok:
                method_used = "Standard"

            # 标准写入失败时,尝试 Gen1A 后门解锁写入(适用于 UID/FUID/UFUID)
            # 解锁序列: isGen1a() 内部发 0x40 + 0x43 后门命令解锁
            if not write_ok and gen in ("Gen1A", "Standard"):
                collect_progress(progress_cb, "标准写入失败,尝试 Gen1A 后门解锁...")
                gen1a_unlock_attempted = True
                try:
                    unlocked = bool(self.cmd.isGen1a())
                    if unlocked:
                        collect_progress(progress_cb, "Gen1A 后门解锁成功,写块0...")
                        self.cmd.mf1_authenticated_sector = -1
                        write_ok = bool(self.cmd.mf1_write_block(current_uid, 0, key, block0))
                        if write_ok:
                            method_used = "Gen1A"
                except Exception as e:
                    collect_progress(progress_cb, f"Gen1A 解锁异常: {e}")

                # Gen1A 解锁尝试后如果写入仍失败,恢复卡到正常状态
                if not write_ok and gen1a_unlock_attempted:
                    try:
                        self.cmd.device.halt()
                        import time as _t; _t.sleep(0.05)
                        self.cmd.hf_14a_scan()
                        self.cmd.mf1_authenticated_sector = -1
                    except Exception:
                        pass

            if write_ok:
                collect_progress(progress_cb, "写后读回校验...")
                self.cmd.mf1_authenticated_sector = -1
                self.cmd.hf_14a_scan()
                verify = self.cmd.mf1_read_block(0, key)
                if verify and verify.parsed and len(verify.parsed) >= 4:
                    read_uid = bytes(verify.parsed[:len(new_uid)])
                    if read_uid != new_uid:
                        collect_progress(progress_cb,
                                        f"读回 UID 不一致: 期望 {new_uid.hex().upper()} 实际 {read_uid.hex().upper()}")
                        write_ok = False

            if write_ok:
                msg = f"UID 设置成功 ({method_used}): {uid_hex}"
                collect_progress(progress_cb, msg)
                if finished_cb: finished_cb(True, msg)
            else:
                collect_progress(progress_cb, "UID 设置失败(卡片不支持或已锁定)")
                if finished_cb: finished_cb(False, "UID设置失败")
        except Exception as e:
            collect_progress(progress_cb, f"UID修改出错: {str(e)}")
            if finished_cb: finished_cb(False, str(e))


class CardDetector:
    def __init__(self, cmd):
        self.cmd = cmd

    def detect(self, progress_cb=None):
        info = {"uid": "", "sak": "", "atqa": "", "type": "未知", "size": "", "gen": ""}
        try:
            scan = self.cmd.hf_14a_scan()
            if not scan:
                collect_progress(progress_cb, "未检测到卡片")
                return info
            tag = scan[0]
            info["uid"] = tag['uid'].hex().upper()
            info["sak"] = tag['sak'].hex().upper()
            info["atqa"] = tag['atqa'].hex().upper()

            sak = tag['sak'][0]
            if sak == 0x08:
                info["size"] = "MIFARE Classic 1K (SAK=08)"
            elif sak == 0x18:
                info["size"] = "MIFARE Classic 4K (SAK=18)"
            elif sak == 0x09:
                info["size"] = "MIFARE Mini (SAK=09)"
            elif sak == 0x00:
                info["size"] = "MIFARE Ultralight (SAK=00)"
            else:
                info["size"] = f"未知 (SAK={sak:02X})"

            if sak == 0x00:
                info["type"] = "NTAG/Ultralight"
                info["gen"] = "N/A"
            else:
                try:
                    if self.cmd.isGen1a():
                        info["type"] = "UID/FUID/UFUID (Gen1A魔法卡)"
                        info["gen"] = "Gen1A"
                        collect_progress(progress_cb, "检测到Gen1A魔法卡特征")
                    elif self.cmd.isGen3():
                        info["type"] = "Gen3魔法卡"
                        info["gen"] = "Gen3"
                        collect_progress(progress_cb, "检测到Gen3魔法卡特征")
                    elif self.cmd.isGen4():
                        info["type"] = "Gen4魔法卡"
                        info["gen"] = "Gen4"
                        collect_progress(progress_cb, "检测到Gen4魔法卡特征")
                    else:
                        info["type"] = "标准MIFARE Classic (可能为CUID)"
                        info["gen"] = "标准/CUID"
                        collect_progress(progress_cb, "标准MIFARE Classic卡片")
                except Exception:
                    info["type"] = "标准MIFARE Classic"
                    info["gen"] = "标准"

            collect_progress(progress_cb, f"UID: {info['uid']}")
            collect_progress(progress_cb, f"类型: {info['type']}")
            collect_progress(progress_cb, f"容量: {info['size']}")
            return info
        except Exception as e:
            collect_progress(progress_cb, f"检测错误: {str(e)}")
            return info


class NtagHelper:
    def __init__(self, cmd):
        self.cmd = cmd
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def read_ntag(self, progress_cb=None, finished_cb=None):
        try:
            collect_progress(progress_cb, "检测NTAG卡片...")
            scan = self.cmd.hf_14a_scan()
            if not scan:
                collect_progress(progress_cb, "未检测到卡片")
                if finished_cb: finished_cb(False, None, "未检测到卡片")
                return
            uid = scan[0]['uid'].hex().upper()
            collect_progress(progress_cb, f"NTAG UID: {uid}")

            block0 = self.cmd.mf0_read_one_block(0)
            if not block0 or not block0.parsed or len(block0.parsed) < 16:
                collect_progress(progress_cb, "读取块0失败")
                if finished_cb: finished_cb(False, "读取失败", None)
                return

            max_block = block0.parsed[14] * 2 + 9 if len(block0.parsed) > 14 else 135
            collect_progress(progress_cb, f"最大页数: {max_block}")

            data = bytearray()
            for block in range(0, max_block, 4):
                if self.is_cancelled:
                    if finished_cb: finished_cb(False, "已取消", None)
                    return
                resp = self.cmd.mf0_read_one_block(block)
                if resp and resp.parsed and len(resp.parsed) >= 16:
                    data.extend(resp.parsed[:16])
                elif resp and resp.parsed and len(resp.parsed) >= 4:
                    data.extend(resp.parsed[:4])
                collect_progress(progress_cb, f"读取页面 {block//4}/{(max_block+3)//4}")
                time.sleep(0.02)

            collect_progress(progress_cb, f"NTAG读取完成,共{len(data)}字节")
            if finished_cb: finished_cb(True, "读取成功", bytes(data))
        except Exception as e:
            collect_progress(progress_cb, f"NTAG读取错误: {str(e)}")
            if finished_cb: finished_cb(False, str(e), None)

    def write_ndef_url(self, url, progress_cb=None, finished_cb=None):
        try:
            import ndef
            collect_progress(progress_cb, f"写入NDEF网址: {url}")
            uri_record = ndef.UriRecord(url)
            ndef_msg = ndef.message_encoder([uri_record])
            ndef_bytes = b''.join(ndef_msg)
            collect_progress(progress_cb, f"NDEF数据: {ndef_bytes.hex().upper()}")

            data_len = len(ndef_bytes) + 4
            cap_container = bytes([
                0x00, 0x0F, 0x20,
                0x00, 0x54, 0x00,
                0xFF, 0x04, 0x06,
                0xE1, 0x04,
                (data_len >> 8) & 0xFF, data_len & 0xFF,
                0x00, 0x00, 0x00
            ])

            for i in range(3):
                page_data = cap_container[i*4:(i+1)*4]
                if len(page_data) < 4:
                    page_data = page_data.ljust(4, b'\x00')
                self.cmd.mf0_write_one_block(i, page_data)
                collect_progress(progress_cb, f"写入能力容器页面{i}")

            for i in range(0, len(ndef_bytes), 4):
                chunk = ndef_bytes[i:i+4]
                if len(chunk) < 4:
                    chunk = chunk.ljust(4, b'\x00')
                self.cmd.mf0_write_one_block(4 + i//4, chunk)
                collect_progress(progress_cb, f"写入NDEF页面 {4 + i//4}")
                time.sleep(0.02)

            collect_progress(progress_cb, "NDEF写入完成!")
            if finished_cb: finished_cb(True, f"NDEF网址写入成功: {url}")
        except Exception as e:
            collect_progress(progress_cb, f"NDEF写入错误: {str(e)}")
            if finished_cb: finished_cb(False, str(e))


class Iso15693Operator:
    def __init__(self, cmd):
        self.cmd = cmd

    def scan(self, progress_cb=None):
        try:
            scan = self.cmd.hf_15_scan()
            if scan:
                for tag in scan:
                    collect_progress(progress_cb, f"ISO15693 UID: {tag['uid']}")
                return scan
            else:
                collect_progress(progress_cb, "未检测到ISO15693标签")
                return None
        except Exception as e:
            collect_progress(progress_cb, f"扫描错误: {str(e)}")
            return None

    def info(self, progress_cb=None):
        try:
            info = self.cmd.hf_15_info()
            if info:
                collect_progress(progress_cb, f"UID: {info['uid'].hex().upper()}")
                collect_progress(progress_cb, f"DSFID: {info.get('dsfid', b'00').hex()} AFI: {info.get('afi', b'00').hex()}")
                collect_progress(progress_cb, f"块大小: {info.get('block_size', 0)}")
                return info
            return None
        except Exception as e:
            collect_progress(progress_cb, f"信息读取错误: {str(e)}")
            return None

    def read_block(self, block, progress_cb=None):
        try:
            data = self.cmd.hf_15_read_block(block)
            if data:
                collect_progress(progress_cb, f"块{block}: {data.hex().upper()}")
                return data
            collect_progress(progress_cb, f"块{block} 读取失败")
            return None
        except Exception as e:
            collect_progress(progress_cb, f"读取错误: {str(e)}")
            return None

    def write_block(self, block, data_hex, progress_cb=None):
        try:
            data = bytes.fromhex(data_hex.replace(' ', ''))
            if self.cmd.hf_15_write_block(block, data):
                collect_progress(progress_cb, f"块{block} 写入成功")
                return True
            collect_progress(progress_cb, f"块{block} 写入失败")
            return False
        except Exception as e:
            collect_progress(progress_cb, f"写入错误: {str(e)}")
            return False


class Em4100Operator:
    def __init__(self, cmd):
        self.cmd = cmd

    def scan(self, progress_cb=None):
        try:
            scan = self.cmd.lf_scan()
            if scan:
                for tag in scan:
                    collect_progress(progress_cb, f"EM4100 ID: {tag['id']} DEC: {tag['dec']}")
                return scan
            collect_progress(progress_cb, "未检测到EM4100标签")
            return None
        except Exception as e:
            collect_progress(progress_cb, f"扫描错误: {str(e)}")
            return None


class EmulatorOperator:
    # Mifare Classic 1K 模拟器槽位容量定义
    MFC_SLOT_BYTES = 1024
    # 1K 槽位总块数
    MFC_SLOT_BLOCKS = 64

    def __init__(self, cmd):
        self.cmd = cmd

    def _check_slot_conflict(self, slot, card_type, progress_cb):
        """检查槽位是否已经被其他卡类型占用。
        返回 True 表示冲突,False 表示空槽位或同类型。
        """
        try:
            # 读 1 字节以了解槽位当前状态(type=0x01 头)
            pkt = struct.pack("!BBBB", card_type, slot, 0xFF, 0xFF)
            resp = self.cmd.device.send_cmd_sync(
                Pn532KillerCommand.ReadEmulator, pkt, timeout=2)
            if resp and resp.data and len(resp.data) >= 5:
                existing_type = resp.data[0]
                if existing_type != 0 and existing_type != card_type:
                    type_names = {1: "MFC", 2: "MFU", 3: "ISO15693", 4: "EM4100",
                                  5: "T5557"}
                    cur_name = type_names.get(existing_type, f"type 0x{existing_type:02X}")
                    new_name = type_names.get(card_type, f"type 0x{card_type:02X}")
                    collect_progress(progress_cb,
                                     f"[WARN] 槽位 {slot + 1} 已存在 {cur_name} 数据,将被 {new_name} 覆盖")
                    return True
            return False
        except Exception:
            return False

    def load_mfd(self, mfd_data, slot=0, progress_cb=None, card_type=1):
        """加载 MFD 到模拟器槽位。

        :param mfd_data: MFD 字节(1024 / 4096)
        :param slot: 0-based 槽位
        :param progress_cb: 进度回调
        :param card_type: 1=MFC, 2=MFU, 3=ISO15693
        :return: bool
        """
        try:
            # 容量校验
            expected_size = 1024 if card_type == 1 else (256 if card_type == 2 else None)
            if expected_size and len(mfd_data) != expected_size:
                collect_progress(progress_cb,
                    f"[WARN] MFD 大小不匹配: 模拟器类型 {card_type} 期望 {expected_size} 字节,"
                    f" 实际 {len(mfd_data)} 字节 (将截断/出错)")
            if card_type == 1 and len(mfd_data) not in (1024, 4096):
                collect_progress(progress_cb, f"不支持的MFC MFD大小: {len(mfd_data)} bytes")
                return False
            if card_type == 1:
                total_blocks = 64 if len(mfd_data) == 1024 else 256
            elif card_type == 2:
                if len(mfd_data) > 256:
                    collect_progress(progress_cb,
                        f"NTAG 模拟器最大 256 字节,你的 MFD 是 {len(mfd_data)} 字节 (截断到 256)")
                    mfd_data = mfd_data[:256]
                total_blocks = len(mfd_data) // 16
            else:
                total_blocks = 64  # ISO15693 默认 64 块

            # 槽位冲突检测
            self._check_slot_conflict(int(slot), card_type, progress_cb)

            dump_map = {}
            for block in range(total_blocks):
                offset = (block // 4) * 64 + (block % 4) * 16
                dump_map[str(block)] = mfd_data[offset:offset+16].hex()

            collect_progress(progress_cb, f"加载{total_blocks}块到模拟器槽位{slot}...")
            self.cmd.hf_mf_load(dump_map, slot)
            collect_progress(progress_cb, "模拟器加载完成!")
            return True
        except Exception as e:
            collect_progress(progress_cb, f"加载错误: {str(e)}")
            return False

    def set_uid(self, slot, uid_hex, progress_cb=None):
        try:
            uid = bytes.fromhex(uid_hex.replace(' ', ''))
            if len(uid) not in (4, 7):
                collect_progress(progress_cb, "UID必须为4或7字节")
                return False
            self.cmd.hf_mf_esetuid(slot, uid)
            collect_progress(progress_cb, f"模拟器槽位{slot} UID设置为 {uid_hex}")
            return True
        except Exception as e:
            collect_progress(progress_cb, f"设置UID错误: {str(e)}")
            return False

    def read_slot(self, slot=0, card_type=1, progress_cb=None):
        try:
            slot_idx = int(slot) - 1
            if card_type == 1:
                collect_progress(progress_cb, f"读取Mifare 1K模拟器槽位{slot}...")
                self.cmd.prepare_get_emulator_data(type=1, slot=slot_idx)
                time.sleep(0.05)
                data = bytearray(1024)
                for bn in range(64):
                    sector = bn // 4
                    blk = bn % 4
                    pkt = struct.pack("!BBBB", 1, slot_idx, sector, blk)
                    resp = self.cmd.device.send_cmd_sync(0x1C, pkt)
                    raw = resp.data[4:] if len(resp.data) > 4 else b''
                    if len(raw) >= 16:
                        data[bn * 16:(bn + 1) * 16] = raw[:16]
                collect_progress(progress_cb, f"读取完成, {len(data)} 字节")
                return bytes(data)
            elif card_type == 2:
                collect_progress(progress_cb, f"读取NTAG模拟器槽位{slot}...")
                self.cmd.prepare_get_emulator_data(type=2, slot=slot_idx)
                time.sleep(0.05)
                data = bytearray(256)
                for page in range(64):
                    pkt = struct.pack("!BBBB", 2, slot_idx, page, 0)
                    resp = self.cmd.device.send_cmd_sync(0x1C, pkt)
                    raw = resp.data[4:] if len(resp.data) > 4 else b''
                    if len(raw) >= 4:
                        data[page * 4:(page + 1) * 4] = raw[:4]
                collect_progress(progress_cb, f"读取完成, {len(data)} 字节")
                return bytes(data)
            elif card_type == 3:
                collect_progress(progress_cb, f"读取15693模拟器槽位{slot}...")
                self.cmd.prepare_get_emulator_data(type=3, slot=slot_idx)
                time.sleep(0.05)
                data = bytearray(1024)
                for bn in range(256):
                    pkt = struct.pack("!BBBB", 3, slot_idx, bn, 0)
                    resp = self.cmd.device.send_cmd_sync(0x1C, pkt)
                    raw = resp.data[4:] if len(resp.data) > 4 else b''
                    if len(raw) >= 4:
                        data[bn * 4:(bn + 1) * 4] = raw[:4]
                collect_progress(progress_cb, f"读取完成, {len(data)} 字节")
                return bytes(data)
            else:
                collect_progress(progress_cb, f"卡类型{card_type}(EM4100/T5557)为低频卡，PN532硬件不支持模拟")
                return None
        except Exception as e:
            collect_progress(progress_cb, f"读取错误: {str(e)}")
            return None


class MfdTools:
    """离线 MFD 处理工具集 (不需要 NFC 硬件)。

    - clone_sector: 扇区克隆(从一个 MFD 复制扇区到另一个)
    - replace_keys_batch: 批量替换所有扇区的 KeyA/KeyB
    - diff: 比较两个 MFD 的差异
    """

    @staticmethod
    def clone_sector(src_mfd: bytes, dst_mfd: bytearray, src_sector: int,
                     dst_sector: int, total_sectors_src: int = 16,
                     total_sectors_dst: int = 16) -> bool:
        """把 src 的扇区 src_sector 数据复制到 dst 的扇区 dst_sector。

        自动处理 1K (4 blocks/sector) 和 4K (后 8 扇区 16 blocks/sector) 的差异。
        """
        try:
            if total_sectors_src not in (16, 40) or total_sectors_dst not in (16, 40):
                return False
            src_blk = MfdTools._sector_blocks(src_sector)
            dst_blk = MfdTools._sector_blocks(dst_sector)
            data = src_mfd[src_blk[0]*16:src_blk[-1]*16 + 16]
            for i, blk in enumerate(dst_blk):
                if i < len(data) // 16:
                    dst_mfd[blk*16:blk*16 + 16] = data[i*16:(i+1)*16]
            return True
        except Exception:
            return False

    @staticmethod
    def replace_keys_batch(mfd: bytearray, old_key: bytes, new_key: bytes,
                           sectors: int = 16) -> int:
        """把所有尾块中等于 old_key 的 KeyA 和/或 KeyB 替换为 new_key。

        :return: 替换次数
        """
        if len(old_key) != 6 or len(new_key) != 6:
            return 0
        count = 0
        for sector in range(sectors):
            trailer_off = MfdTools._sector_blocks(sector)[-1] * 16
            ka_off = trailer_off
            kb_off = trailer_off + 10
            if mfd[ka_off:ka_off+6] == old_key:
                mfd[ka_off:ka_off+6] = new_key
                count += 1
            if mfd[kb_off:kb_off+6] == old_key:
                mfd[kb_off:kb_off+6] = new_key
                count += 1
        return count

    @staticmethod
    def diff(mfd1: bytes, mfd2: bytes) -> list:
        """比较两个 MFD 的差异。

        :return: [(sector_num, block_num, hex1, hex2), ...]
        """
        n_blocks = min(len(mfd1), len(mfd2)) // 16
        diffs = []
        for blk in range(n_blocks):
            b1 = mfd1[blk*16:(blk+1)*16]
            b2 = mfd2[blk*16:(blk+1)*16]
            if b1 != b2:
                sector = MfdTools._block_to_sector(blk)
                diffs.append((sector, blk, b1.hex().upper(), b2.hex().upper()))
        return diffs

    @staticmethod
    def _sector_blocks(sector: int):
        """返回扇区包含的 block 列表。1K 4块/扇区,4K 后 8 扇区 16 块/扇区。"""
        if sector < 32:
            return [sector*4 + i for i in range(4)]
        # 4K 后 8 扇区:128..255,每扇区 16 块
        return [128 + (sector - 32)*16 + i for i in range(16)]

    @staticmethod
    def _block_to_sector(block: int) -> int:
        """block -> sector (1K 与 4K 通用)。"""
        if block < 128:
            return block // 4
        return 32 + (block - 128) // 16
