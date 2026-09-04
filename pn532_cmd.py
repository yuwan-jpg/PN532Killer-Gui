import struct
import ctypes
from typing import Union
import threading

import pn532_com
from unit.calc import crc16A, crc16Ccitt
from pn532_com import Response, DEBUG
from pn532_utils import expect_response
from pn532_enum import Command, MifareCommand, ApduCommand, TagFile, NdefCommand, Status
from pn532_enum import Pn532KillerCommand

from pn532_enum import ButtonPressFunction, ButtonType, MifareClassicDarksideStatus
from pn532_enum import MfcKeyType, MfcValueBlockOperator
from time import sleep
from pn532_utils import CC, CB, CG, C0, CY, CR
from pn532_utils import NdefParser
import os
import subprocess
import ndef
from multiprocessing import Pool, cpu_count
from typing import Union
from pathlib import Path
from platform import uname
import sys
import select
import serial.tools.list_ports
# if system is Windows
if os.name == "nt":
    import msvcrt

class Pn532CMD:
    """
    Pn532 cmd function
    """

    def __init__(self, pn532: pn532_com.Pn532Com):
        """
        :param pn532: pn532 instance, @see pn532_device.Pn532
        """
        self.device = pn532

    @expect_response(Status.SUCCESS)
    def hf_14a_scan(self):
        self.device.set_normal_mode()
        """
        14a tags in the scanning field.

        :return:
        """
        timeout = 1
        if hasattr(self.device, 'connection_type') and self.device.connection_type in ('udp', 'tcp'):
            timeout = 2  # 给网络模式多一点时间
        resp = self.device.send_cmd_sync(Command.InListPassiveTarget, b"\x01\x00", timeout=timeout)
        try:
            if resp.status == Status.SUCCESS and len(resp.data) >= 6 and resp.data[0] > 0:
                offset = 0
                data = []
                while offset < len(resp.data):
                    tagType = resp.data[offset]
                    offset += 1
                    if offset >= len(resp.data):
                        break
                    tagNum = resp.data[offset]
                    offset += 1
                    if offset + 4 > len(resp.data):
                        break
                    atqa, sak, uidlen = struct.unpack_from("!2s1sB", resp.data, offset)
                    offset += struct.calcsize("!2s1sB")
                    if offset + uidlen > len(resp.data):
                        break
                    uid = resp.data[offset : offset + uidlen]
                    ats = resp.data[offset + uidlen :]
                    data.append(
                        {
                            "tagType": tagType,
                            "tagNum": tagNum,
                            "atqa": atqa,
                            "sak": sak,
                            "uid": uid,
                            "ats": ats
                        }
                    )
                    break
                resp.parsed = data if data else None
        except Exception:
            resp.parsed = None
        return resp

    def mf0_read_one_block(self, block):
        """NTAG/Ultralight 单次 READ。Ultralight READ(0x30) 返回 4 页(16 字节),
        单页写入(0xA2)只写 4 字节。返回的 resp.parsed = resp.data,大小由调用方决定。
        """
        data = struct.pack("!BBB", 0x01, MifareCommand.MfReadBlock, block)
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        resp.parsed = resp.data
        return resp

    def mf0_write_one_block(self, block, data):
        data = struct.pack("!BBB4s", 0x01, MifareCommand.MfWrite4Bytes, block, data)
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        if len(resp.data) >= 1:
            resp.parsed = resp.data
        return resp

    @expect_response(Status.SUCCESS)
    def hfmf_cview(self):
        """
        View the Gen1A Tag

        :return:
        """
        self.device.set_normal_mode()

        tag_info = {}
        scan_result = self.hf_14a_scan() 
        
        if scan_result == None or len(scan_result) == 0:
            print("No tag found")
            return Response(Command.InListPassiveTarget, Status.HF_TAG_NO)
        
        tag_info["uid"] = scan_result[0]["uid"].hex()
        tag_info["atqa"] = scan_result[0]["atqa"].hex()
        tag_info["sak"] = scan_result[0]["sak"].hex()
        tag_info["data"] = []
        try:
            if not self.isGen1a():
                print("Not Gen1A tag")
                return Response(Command.InCommunicateThru, Status.HF_TAG_NO)

            options = {
                "activate_rf_field": 0,
                "wait_response": 1,
                "append_crc": 1,
                "auto_select": 0,
                "keep_rf_field": 1,
                "check_response_crc": 1,
            }
            block = 0
            block_data = {}
            while block < 64:
                if block == 63:
                    options["keep_rf_field"] = 0
                resp_data = self.hf14a_raw(
                    options=options,
                    resp_timeout_ms=1000,
                    data=[MifareCommand.MfReadBlock, block],
                )  # 装饰器直接返回 parsed 数据（字节）
                if len(resp_data) > 16:
                    resp_data = resp_data[:16]
                block_data[f"{block}"] = resp_data.hex()
                if block == 0:
                    print(
                        f"{block:02d}: {CY}{resp_data.hex()[0:8].upper()}{CR}{resp_data.hex()[8:10].upper()}{CG}{resp_data.hex()[10:12].upper()}{CY}{resp_data.hex()[12:16].upper()}{C0}{resp_data.hex()[16:].upper()}{C0}"
                    )
                elif block % 4 == 3:
                    print(
                        f"{block:02d}: {CG}{resp_data.hex()[0:12].upper()}{CR}{resp_data.hex()[12:20].upper()}{CG}{resp_data.hex()[20:].upper()}{C0}"
                    )
                else:
                    print(f"{block:02d}: {resp_data.hex().upper()}")
                block += 1
            tag_info["blocks"] = block_data
        except Exception as e:
            print("Error:", e)

        resp = Response(Command.InCommunicateThru, Status.SUCCESS)
        resp.parsed = tag_info
        return resp

    @expect_response(Status.HF_TAG_OK)
    def hf14a_raw(self, options, resp_timeout_ms=100, data=[], bitlen=None) -> Response:
        """
        Send raw cmd to 14a tag.

        :param options:
        :param resp_timeout_ms:
        :param data:
        :param bit_owned_by_the_last_byte:
        :return:
        """

        class CStruct(ctypes.BigEndianStructure):
            _fields_ = [
                ("activate_rf_field", ctypes.c_uint8, 1),
                ("wait_response", ctypes.c_uint8, 1),
                ("append_crc", ctypes.c_uint8, 1),
                ("auto_select", ctypes.c_uint8, 1),
                ("keep_rf_field", ctypes.c_uint8, 1),
                ("check_response_crc", ctypes.c_uint8, 1),
                ("reserved", ctypes.c_uint8, 2),
            ]

        cs = CStruct()
        cs.activate_rf_field = options["activate_rf_field"]
        cs.wait_response = options["wait_response"]
        cs.append_crc = options["append_crc"]
        cs.auto_select = options["auto_select"]
        cs.keep_rf_field = options["keep_rf_field"]
        cs.check_response_crc = options["check_response_crc"]
        
        if cs.auto_select:
            self.hf_14a_scan()

        if cs.activate_rf_field:
            self.device.halt()

        if bitlen is None:
            bitlen = len(data) * 8  # bits = bytes * 8(bit)
        else:
            if len(data) == 0:
                raise ValueError(f"bitlen={bitlen} but missing data")
            if not ((len(data) - 1) * 8 < bitlen <= len(data) * 8):
                raise ValueError(
                    f"bitlen={bitlen} incompatible with provided data ({len(data)} bytes), "
                    f"must be between {((len(data) - 1) * 8 )+1} and {len(data) * 8} included"
                )

        if bitlen == 7:
            self.device.set_register([0x63, 0x3D, 0x07])
            sleep(0.1)

        if cs.append_crc:
            data = bytes(data) + crc16A(bytes(data))
        resp = self.device.send_cmd_sync(Command.InCommunicateThru, data, timeout=1)
        resp.parsed = resp.data
        if cs.keep_rf_field == 0:
            self.device.halt()

        if bitlen == 7:
            self.device.set_register([0x63, 0x3D, 0x00])
            sleep(0.1)

        if DEBUG:
            print(
                f"Send: {bytes(data).hex().upper()} Status: {hex(resp.status)[2:].upper()}, Data: {resp.parsed.hex().upper()}"
            )
        return resp

    def isGen1a(self):
        options = {
            "activate_rf_field": 1,
            "wait_response": 1,
            "append_crc": 0,
            "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        # Unlock 1
        resp_data = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=[0x40], bitlen=7
        )
        if DEBUG:
            print("unlock 1:", resp_data.hex())
        if resp_data[-1] == 0x0A:
            options["activate_rf_field"] = 0
            # Unlock 2
            resp_data = self.hf14a_raw(options=options, resp_timeout_ms=1000, data=[0x43])
            if DEBUG:
                print("unlock 2:", resp_data.hex())
            if resp_data[-1] == 0x0A:
                return True
        return False

    def selectTag(self):
        tag_info = {}
        scan_result = self.hf_14a_scan()
        self.device.halt()
        if scan_result == None or len(scan_result) == 0:
            print("No tag found")
            return Response(Command.InListPassiveTarget, Status.HF_TAG_NO)
        
        tag_info["uid"] = scan_result[0]["uid"].hex()
        uid_length = len(scan_result[0]["uid"])
        if DEBUG:
            print("Found UID:", tag_info["uid"])
        tag_info["atqa"] = scan_result[0]["atqa"].hex()
        tag_info["sak"] = scan_result[0]["sak"].hex()
        tag_info["data"] = []
        options = {
            "activate_rf_field": 0,
            "wait_response": 1,
            "append_crc": 0,
             "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        wupa_result = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=[0x52], bitlen=7
        )
        if DEBUG: 
            print("WUPA:", wupa_result)
        anti_coll_result = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=[0x93, 0x20]
        )
        if DEBUG:
            print("Anticollision CL1:", anti_coll_result.hex())
        if len(anti_coll_result) < 4:
            if DEBUG: 
                print("Anticollision failed")
            return False

        anti_coll_data = anti_coll_result[0:]
        options["append_crc"] = 1
        select_result = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=[0x93, 0x70] + list(anti_coll_data)
        )
        if DEBUG:
            print("Select CL1:", select_result.hex())

        if uid_length == 4:
            return len(select_result) > 1 and select_result[0] == 0x00
        elif uid_length == 7:
            options["append_crc"] = 0
            anti_coll2_result = self.hf14a_raw( options=options, resp_timeout_ms=1000, data=[0x95, 0x20])
            if len(anti_coll2_result) < 4:
                if DEBUG: 
                    print("Anticollision CL2 failed")
                return False
            anti_coll2_data = anti_coll2_result[0:]
            options["append_crc"] = 1
            select2_result = self.hf14a_raw(
                options=options, resp_timeout_ms=1000, data=[0x95, 0x70] + list(anti_coll2_data)
            )
            if DEBUG: 
                print("Select CL2:", select2_result.hex())
            return len(select2_result) > 1 and select2_result[0] == 0x00
        return False

    def isGen3(self):
        selected_tag = self.selectTag()
        if selected_tag is None:
            print(f"{CR}Select tag failed{C0}")
            return False
        options = {
            "activate_rf_field": 0,
            "wait_response": 1,
            "append_crc": 1,
            "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        block0 = self.hf14a_raw(
            options=options,
            resp_timeout_ms=1000,
            data=b"\x30\x00",
        )
        if len(block0) >= 16:
            return True
        return False

    def setGen3Uid(self, uid: bytes):
        selected_tag = self.selectTag()
        if selected_tag is None:
            print(f"{CR}Select tag failed{C0}")
            return
        options = {
            "activate_rf_field": 0,
            "wait_response": 1,
            "append_crc": 1,
            "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        command = "90FBCCCC07" + uid.hex()
        resp = self.hf14a_raw(
            options=options, resp_timeout_ms=2000, data=bytes.fromhex(command)
        )
        if DEBUG:
            print("Set Gen3 UID:", resp.hex())
        if len(resp) >= 2 and resp[0] == 0x90 and resp[1] == 0x00:
            return True
        return False

    def setGen3Block0(self, block0: bytes):
        options = {
            "activate_rf_field": 0,
            "wait_response": 1,
            "append_crc": 1,
            "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        command = "90F0CCCC10" + block0.hex()
        resp = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=bytes.fromhex(command)
        )
        if len(resp) >= 2 and resp[0] == 0x90 and resp[1] == 0x00:
            return True
        return False

    def lockGen3Uid(self):
        options = {
            "activate_rf_field": 0,
            "wait_response": 1,
            "append_crc": 1,
            "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        command = "90FD111100"
        resp = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=bytes.fromhex(command)
        )
        if len(resp) >= 2 and resp[0] == 0x90 and resp[1] == 0x00:
            return True
        return False

    def isGen4(self, pwd="00000000"):
        options = {
            "activate_rf_field": 0,
            "wait_response": 1,
            "append_crc": 1,
            "auto_select": 0,
            "keep_rf_field": 1,
            "check_response_crc": 0,
        }
        command = f"CF{pwd}C6"
        resp = self.hf14a_raw(
            options=options, resp_timeout_ms=1000, data=bytes.fromhex(command)
        )
        if DEBUG:
            try:
                print(f"isGen4: {resp.hex()}")
            except AttributeError:
                print(f"isGen4: <{type(resp).__name__}> {resp}")
        if resp is None:
            return False
        if len(resp) >= 30:
            return True
        return False

    def mf1_auth_one_key_block(self, block, type_value: MfcKeyType, key, uid) -> bool:
        if len(uid) > 4:
            uid = uid[-4:]
        format_str = f"!BBB6s{len(uid)}s"
        data = struct.pack(format_str, 0x01, type_value, block, key, uid)
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        return len(resp.data) > 0 and resp.data[0] == Status.HF_TAG_OK

    mf1_authenticated_sector = -1
    mf1_authenticated_useKeyA = True

    def mf1_read_block(self, block, key):
        current_sector = block // 4 if block < 128 else ((block - 128) // 16 + 32)
        if self.mf1_authenticated_sector != current_sector:
            resp = self.hf_14a_scan()
            if not resp:
                print("No tag found")
                return Response(Command.InListPassiveTarget, Status.HF_TAG_NO)
            uidID1 = bytes(resp[0]["uid"])
            auth_result = self.mf1_auth_one_key_block(block, MfcKeyType.KEY_A, key, uidID1)
            if not auth_result:
                self.mf1_authenticated_useKeyA = False
                resp = self.hf_14a_scan()
                if not resp:
                    print("No tag found")
                    return Response(Command.InListPassiveTarget, Status.HF_TAG_NO)
                uidID1 = bytes(resp[0]["uid"])
                auth_result = self.mf1_auth_one_key_block(block, MfcKeyType.KEY_B, key, uidID1)
            if not auth_result:
                self.mf1_authenticated_useKeyA = True
                return Response(Command.InDataExchange, Status.MF_ERR_AUTH)
            self.mf1_authenticated_sector = current_sector

        data = struct.pack("!BBB", 0x01, MifareCommand.MfReadBlock, block)
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        resp.parsed = resp.data
        if len(resp.data) >= 16:
            if self.is_mf_trailler_block(block):
                if self.mf1_authenticated_useKeyA:
                    resp.parsed = key + resp.parsed[6:]
                else:
                    resp.parsed = resp.parsed[0:10] + key
        return resp

    def mf1_read_one_block(self, block, type_value: MfcKeyType, key):
        resp = self.hf_14a_scan()
        if resp == None:
            print("No tag found")
            return resp
        uidID1 = bytes(resp[0]["uid"])
        auth_result = self.mf1_auth_one_key_block(
            block, type_value, key, uidID1
        )
        if not auth_result:
            return Response(Command.InDataExchange, Status.MF_ERR_AUTH)
        data = struct.pack("!BBB", 0x01, MifareCommand.MfReadBlock, block)
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        if len(resp.data) >= 16:
            resp.parsed = resp.data
            if self.is_mf_trailler_block(block):
                if type_value == MfcKeyType.KEY_A:
                    resp.parsed = key + resp.parsed[6:]
                else:
                    resp.parsed = resp.parsed[0:10] + key
        return resp

    def is_mf_trailler_block(self, block_index) -> bool:
        if block_index < 128:
            return (block_index + 1) % 4 == 0
        else:
            return (block_index + 1 - 128) % 16 == 0

    @expect_response(Status.HF_TAG_OK)
    def mf1_write_block(self, uid, block, key, block_data):
        auth_result = self.mf1_auth_one_key_block(
            block, MfcKeyType.KEY_A, key, uid
        )
        if not auth_result:
            auth_result = self.mf1_auth_one_key_block(block, MfcKeyType.KEY_B, key, uid)
        if not auth_result:
            return Response(Command.InDataExchange, Status.HF_TAG_NO)
        data = struct.pack(
            "!BBB16s", 0x01, MifareCommand.MfWriteBlock, block, block_data
        )
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        resp.parsed = len(resp.data) > 0 and resp.data[0] == Status.HF_TAG_OK
        return resp

    def mf1_write_block_verify(self, uid, block, key, block_data):
        """写后读回校验,防锁卡。对 trailer 块、块 0、NDEF 数据块应强制使用。

        Returns (ok, write_resp, verify_match):
          - ok: 写命令是否成功
          - write_resp: 写结果(bool)
          - verify_match: 读回数据与写入数据是否一致(全部 16 字节)

        ⚠ mf1_write_block 被 @expect_response 装饰,返回 bool 而非 Response。
        ⚠ PN532 写入成功后偶尔返回非 HF_TAG_OK 状态码导致 write_ok=False,
           但实际写入成功。此处即使 write_ok=False 也做读回验证,以读回为准。
        """
        write_ok = self.mf1_write_block(uid, block, key, block_data)
        # 无论 write_ok 如何,都尝试读回验证(PN532 偶尔误报写入失败)
        self.mf1_authenticated_sector = -1
        verify_resp = self.mf1_read_block(block, key)
        if not (verify_resp and verify_resp.parsed and len(verify_resp.parsed) >= 16):
            if not write_ok:
                return False, write_ok, False
            return True, write_ok, False
        written = bytes(block_data[:16])
        read_back = bytes(verify_resp.parsed[:16])
        if self.is_mf_trailler_block(block):
            ka_written = written[0:6]
            kb_written = written[10:16]
            ka_read = read_back[0:6]
            kb_read = read_back[10:16]
            match = (ka_written == ka_read) and (kb_written == kb_read)
            return True, write_ok, match
        match = (written == read_back)
        # 即使 write_ok=False, 如果读回匹配说明实际写入成功
        return (True if match else write_ok), write_ok, match

    @expect_response(Status.HF_TAG_OK)
    def mf1_write_one_block(self, uid, block, type_value: MfcKeyType, key, block_data):
        auth_result = self.mf1_auth_one_key_block(
            block, type_value, key, uid
        )
        if not auth_result:
            return Response(Command.InDataExchange, Status.HF_TAG_NO)
        data = struct.pack(
            "!BBB16s", 0x01, MifareCommand.MfWriteBlock, block, block_data
        )
        resp = self.device.send_cmd_sync(Command.InDataExchange, data)
        resp.parsed = len(resp.data) > 0 and resp.data[0] == Status.HF_TAG_OK
        return resp

    @expect_response([Status.HF_TAG_OK, Status.HF_TAG_NO])
    def mf1_check_keys_of_sectors(self, mask: bytes, keys: list[bytes]):
        """
        Check keys of sectors.
        :return:
        """
        if len(mask) != 10:
            raise ValueError("len(mask) should be 10")
        if len(keys) < 1 or len(keys) > 83:
            raise ValueError("Invalid len(keys)")
        data = struct.pack(f"!10s{6*len(keys)}s", mask, b"".join(keys))

        bitsCnt = 80  # maximum sectorKey_to_be_checked
        for b in mask:
            while b > 0:
                [bitsCnt, b] = [bitsCnt - (b & 0b1), b >> 1]
        if bitsCnt < 1:
            # All sectorKey is masked
            return pn532_com.Response(
                cmd=Command.MF1_CHECK_KEYS_OF_SECTORS,
                status=Status.HF_TAG_OK,
                parsed={"status": Status.HF_TAG_OK},
            )
        # base timeout: 1s
        # auth: len(keys) * sectorKey_to_be_checked * 0.1s
        # read keyB from trailer block: 0.1s
        timeout = 1 + (bitsCnt + 1) * len(keys) * 0.1

        resp = self.device.send_cmd_sync(
            Command.MF1_CHECK_KEYS_OF_SECTORS, data, timeout=timeout
        )
        resp.parsed = {"status": resp.status}
        if len(resp.data) == 490:
            found = "".join([format(i, "08b") for i in resp.data[0:10]])
            # print(f'{found = }')
            resp.parsed.update(
                {
                    "found": resp.data[0:10],
                    "sectorKeys": {
                        k: resp.data[6 * k + 10 : 6 * k + 16]
                        for k, v in enumerate(found)
                        if v == "1"
                    },
                }
            )
        return resp

    @expect_response(Status.SUCCESS)
    def get_firmware_version(self):
        """
        Get firmware version
        """
        resp = self.device.send_cmd_sync(
            Command.GetFirmwareVersion, None, Status.SUCCESS, 1
        )
        resp.parsed = f"Ver.{resp.data.hex()}"
        return resp

    @expect_response(Status.SUCCESS)
    def hf_sniff_set_uid(self, block0: bytes):
        """
        Set block0 for sniffing

        :param block0: 16 bytes
        :return:
        """
        self.upload_data_block(slot = 0x11, data = block0)
        self.upload_data_block_done(slot = 0x11)
        return Response(Pn532KillerCommand.WriteEmulator, Status.SUCCESS)

    def clear_sniffer_log(self, timeout: int = 2) -> bool:
        """
        清除嗅探日志 (Pn532Killer 0x22 命令)。

        包装 Pn532Com.clear_sniffer_log,返回 bool 便于 GUI 判断。
        """
        try:
            resp = self.device.clear_sniffer_log(timeout=timeout)
            return bool(resp and resp.status == Status.SUCCESS)
        except Exception:
            return False

    def staticnested_collect(self, key_known, blkknown, type_known, targetblock,
                             targettype, timeout: int = 5):
        """
        PN532Killer StaticNested 攻击采集 (0x24 命令)。

        按官方协议 PN532Killer Command-V0.1.md 拼装 0x24 StaticNested 请求,
        让固件对目标扇区发起一次基于已知密钥的 nested 认证,并返回
        uid + 两组 (nt, nr) 原始 nonce,供主机离线用 lfsr_recovery32 反推密钥。

        Param format:
          type(1) = 1 (Staticnested)
          data:
            keyknown  (8 bytes, 后 6 字节为已知密钥)
            blkknown  (1 byte)    -- 已知密钥所在块
            typknown  (0x60/0x61) -- 已知密钥类型 KeyA/KeyB
            targetblock(1 byte)   -- 目标块
            targettype(0x60/0x61) -- 目标块密钥类型

        返回: dict
          {
            'uid': bytes(4..7), 'targetType': int,
            'nt0': int, 'nr0': int, 'nt1': int, 'nr1': int,
            'raw': bytes,
          }
          失败返回 None
        """
        try:
            if len(key_known) != 6:
                raise ValueError("已知密钥必须为 6 字节")
            known_field = b'\x00\x00' + key_known  # 8 bytes
            data = bytes([0x01]) + known_field + bytes([
                blkknown & 0xFF, type_known & 0xFF,
                targetblock & 0xFF, targettype & 0xFF,
            ])
            resp = self.device.send_cmd_sync(
                Pn532KillerCommand.ReadUserDefData, data, timeout=timeout)
            if resp is None or not resp.data:
                return None
            blob = resp.data
            # 响应: uid(4) + targetType(1) + nt0(4) + nr0(4) + nt1(4) + nr1(4)
            if len(blob) < 21:
                return None
            uid = blob[0:4]
            target_type = blob[4]
            nt0 = int.from_bytes(blob[5:9], 'little')
            nr0 = int.from_bytes(blob[9:13], 'little')
            nt1 = int.from_bytes(blob[13:17], 'little')
            nr1 = int.from_bytes(blob[17:21], 'little')
            return {
                'uid': uid,
                'targetType': target_type,
                'nt0': nt0,
                'nr0': nr0,
                'nt1': nt1,
                'nr1': nr1,
                'raw': blob,
            }
        except Exception as e:
            print(f"staticnested_collect error: {e}")
            return None
    
    @expect_response(Status.SUCCESS)
    def hf_mf_esetuid(self, slot, uid: bytes):
        """
        Set 4 byte or 7 byte uid for Mifare 1K emulator
        """
        slot = int(slot) - 1
        if len(uid) == 4:
            bcc = 0
            for byte in uid:
                bcc ^= byte
            sak = b"\x08"
            atqa = b"\x04\x00"
            block0 = uid + bytes([bcc]) + sak + atqa + b"\x00" * 8
        elif len(uid) == 7:
            block0 = uid + b"\x7B" + b"\x00" * 8
        else:
            raise ValueError("UID length must be 4 or 7 bytes")
        self.upload_data_block(slot=slot, data=block0)
        self.upload_data_block_done(slot=slot)
        
    @expect_response(Status.SUCCESS)
    def lf_scan(self):
        resp = self.device.send_cmd_sync(Command.InListPassiveTarget, b"\x01\x06")
        if resp.status == Status.SUCCESS:
            # 01011122334455
            # tagType[1]tagNum[1]uid[5]
            offset = 0
            data = []
            if len(resp.data) < 7:
                resp.parsed = None
                return resp
            while offset < len(resp.data):
                tagType = resp.data[offset]
                offset += 1
                tagNum = resp.data[offset]
                offset += 1
                uid = resp.data[offset : offset + 5]
                offset += 5
                uidHex = uid.hex()
                uidDec = int.from_bytes(uid, "big")
                data.append({"tagType": tagType, "tagNum": tagNum, "id": uidHex, "dec": uidDec})
            resp.parsed = data
        return resp

    def lf_em4100_eset_id(self, slot, uid: bytes):
        """
        Set id for EM4100 emulator
        """
        resp_set = self.upload_data_block(type = 0x04, slot = slot + 0x12, data = uid)
        resp_save = self.upload_data_block_done(type = 0x04, slot = slot + 18)
        return resp_set and resp_save

    def lf_em4100_eread(self, slot, length: int = 5):
        """
        读取 EM4100 模拟器槽位数据。

        协议: 复用 ReadEmulator 0x1C 命令,type=0x04。
        返回的 5 字节是 EM4100 ID (40 bit),最右边字节是 ID 的最高位。

        :param slot: 槽位号 (0-based)
        :param length: 读取字节数,默认 5 (完整 ID)
        :return: bytes 或 None
        """
        try:
            slot_idx = int(slot)
            pkt = struct.pack("!BBBB", 0x04, slot_idx, 0xFF, 0xFF)
            resp = self.device.send_cmd_sync(Pn532KillerCommand.ReadEmulator, pkt, timeout=2)
            if resp and resp.data and len(resp.data) >= 4:
                # 返回格式: [type|slot|sector|block|length_byte_data...]
                # 跳过 4 字节头
                payload = resp.data[4:4+length]
                return bytes(payload)
            return None
        except Exception:
            return None

    def lf_t5557_eset_block(self, slot, block: int, data: bytes):
        """
        T5557 模拟器块写入 (框架)。

        T5557 是可写 EM 卡(125 kHz),有 8 个 block × 32 bit。
        当前固件的命令格式需参考最新 PN532Killer 协议,这里只占位,
        避免 silent failure。

        :param slot: 槽位号
        :param block: 块号 (0-7)
        :param data: 4 字节数据
        :return: bool
        """
        if len(data) != 4:
            return False
        try:
            # TODO: 替换为 PN532Killer T5557 真实命令 (需查 update_help.py)
            # 暂用通用 upload 通道
            resp = self.upload_data_block(type=0x05, slot=int(slot) + 0x20,
                                           sector=0, block=int(block), data=data)
            resp_done = self.upload_data_block_done(type=0x05, slot=int(slot) + 0x20)
            return resp and resp_done
        except Exception:
            return False

    def lf_t5557_eread(self, slot, block: int, length: int = 4):
        """T5557 模拟器块读取 (框架)。"""
        try:
            pkt = struct.pack("!BBBB", 0x05, int(slot), 0, int(block))
            resp = self.device.send_cmd_sync(Pn532KillerCommand.ReadEmulator, pkt, timeout=2)
            if resp and resp.data and len(resp.data) >= 4:
                return bytes(resp.data[4:4+length])
            return None
        except Exception:
            return None

    @expect_response(Status.SUCCESS)
    def hf_15_scan(self):
        self.device.set_normal_mode()
        """
        15 tags in the scanning field.

        :return:
        """
        resp = self.device.send_cmd_sync(Command.InListPassiveTarget, b"\x01\x05")
        if resp.status == Status.SUCCESS:
            # 010188888888332211E0
            # tagType[1]tagNum[1]uid[8, reversed]
            offset = 0
            data = []
            if len(resp.data) < 10:
                return resp
            while offset < len(resp.data):
                tagType = resp.data[offset]
                offset += 1
                tagNum = resp.data[offset]
                offset += 1
                uid = resp.data[offset : offset + 8]
                offset += 8
                # reversed uid
                uidHex = uid.hex()
                uidHex = (
                    uidHex[14:16]
                    + uidHex[12:14]
                    + uidHex[10:12]
                    + uidHex[8:10]
                    + uidHex[6:8]
                    + uidHex[4:6]
                    + uidHex[2:4]
                    + uidHex[0:2]
                )
                data.append({"tagType": tagType, "tagNum": tagNum, "uid": uidHex})
            resp.parsed = data
        return resp

    def hf_15_info(self):
        command = b"\x02\x2B"
        resp = self.hf_15_raw(options = {"select_tag": 0, "append_crc": 1, "no_check_response": 0}, data = command)
        # example: 00(status) 0F(flags) 77 66 55 44 33 22 11 E0(uid7 to uid0) 00(Dsfid) 00(Afi) 07(block size) 03 8B(IcReference) F9 4D
        if len(resp.data) > 15:
            return {
                "flags": resp.data[1],
                "uid": resp.data[2:10][::-1],
                "dsfid": resp.data[10],
                "afi": resp.data[11],
                "block_size": resp.data[12] + 1,
                "ic_reference": resp.data[14],
            }
        return None

    def hf_15_read_block(self, block):
        command = b"\x01\x20" + bytes([block])
        resp = self.device.send_cmd_sync(Command.InDataExchange, command)
        if len(resp.data) == 5 and resp.data[0] == 0x00:
            return resp.data[1:]
        return None

    def hf_15_write_block(self, block, data):
        command = b"\x01\x21" + bytes([block]) + data
        resp = self.device.send_cmd_sync(Command.InDataExchange, command)
        return len(resp.data) == 1 and resp.data[0] == 0x00

    def hf_15_raw(self, options, resp_timeout_ms=100, data=[]) -> Response:
        """
        Send raw cmd to 15 tag.

        :param options:
        :param resp_timeout_ms:
        :param data:
        :param bit_owned_by_the_last_byte:
        :return:
        """

        class CStruct(ctypes.BigEndianStructure):
            _fields_ = [
                ("select_tag", ctypes.c_uint8, 1),
                ("append_crc", ctypes.c_uint8, 1),
                ("no_check_response", ctypes.c_uint8, 1)
            ]

        cs = CStruct()
        cs.select_tag = options["select_tag"]
        cs.append_crc = options["append_crc"]
        cs.no_check_response = options["no_check_response"]
        if cs.select_tag:
            self.hf_15_scan()
        if cs.append_crc:
            data = bytes(data) + crc16Ccitt(bytes(data))
        req_ack = 0x80
        if cs.no_check_response:
            req_ack = 0x00
        data = bytes([req_ack, 0x00]) + data  # Insert Tag Num
        resp = self.device.send_cmd_sync(Command.InCommunicateThru, data, timeout=1)
        resp.parsed = resp.data

        if DEBUG:
            print(
                f"Send: {bytes(data).hex().upper()} Status: {hex(resp.status)}, Data: {resp.parsed.hex().upper()}"
            )
        return resp

    def hf_15_set_gen1_uid(self, uid: bytes, block_size: int):
        return self.hf_15_write_block(block_size, uid[4:][::-1]) and self.hf_15_write_block(block_size + 1, uid[:4][::-1])

    def hf_15_set_gen2_uid(self, uid: bytes):
        # 02e0094044556677 44556677 is the last 4 bytes of uid
        command1 = b"\x02\xE0\x09\x40" + uid[4:][::-1]
        resp1 = self.hf_15_raw(options = {"select_tag": 0, "append_crc": 1, "no_check_response": 1}, data = command1)
        # print(f"Set uid1 {uid.hex()}: {resp1.data.hex().upper()}")
        # 02e00941332211E0 332211E0 is the first 4 bytes of uid
        command2 = b"\x02\xE0\x09\x41" + uid[:4][::-1]
        resp2 = self.hf_15_raw(options = {"select_tag": 0, "append_crc": 1, "no_check_response": 1}, data = command2)
        # print(f"Set uid2 {uid.hex()}: {resp2.data.hex().upper()}")
        return True

    def hf_15_set_gen2_config(self, size: int, afi: int, dsfid: int, ic_reference: int):
        # 02e00946 00 00 00 00: last 2 byte is afi and dsfid
        command = b"\x02\xE0\x09\x46\x00\x00" + bytes([afi]) + bytes([dsfid])
        self.hf_15_raw(options = {"select_tag": 0, "append_crc": 1, "no_check_response": 1}, data = command)
        # 02e00947 3f 03 8b 00: 3f is block size, 8b is ic reference
        command = b"\x02\xE0\x09\x47" + bytes([size - 1]) + b"\x03" + bytes([ic_reference]) + b"\x00"
        self.hf_15_raw(options = {"select_tag": 0, "append_crc": 1, "no_check_response": 1}, data = command)
        print(f"Config: Size {size}, AFI 0x{afi:02X}, DSFID 0x{dsfid:02X}, IC Reference 0x{ic_reference:02X}")
        return True

    def hf_15_eset_uid(self, slot, uid: bytes):
        """
        Set uid for 15 emulator
        """
        # data is 0xFE, 0x00 + uid
        resp_set = self.upload_data_block(type = 0x03, slot = slot + 0x1A, index = 0xFE00, data = uid[::-1])
        resp_save = self.hf_15_esave(slot)
        return resp_set and resp_save

    def hf_15_eset_block(self, slot, index,  data: bytes):
        """
        Set block data for 15 emulator on block index
        """
        resp_set = self.upload_data_block(type = 0x03, slot = slot + 0x1A, index = index, data = data)
        resp_save = self.hf_15_esave(slot)
        return resp_set and resp_save
    
    def hf_15_eset_dump(self, slot, bin_data):
        """
        Set the whole dump for 15 emulator
        """
        for block_index in range(0, len(bin_data), 4):
            block_data = bin_data[block_index:block_index + 4]
            resp = self.upload_data_block(type=0x03, slot=slot + 0x1A, index=block_index // 4, data=block_data)
            print(f"Set block {block_index // 4:02d} {block_data.hex()}: {resp}")
        resp_save = self.hf_15_esave(slot)
        return resp_save

    def hf_15_eset_resv_eas_afi_dsfid(self, slot, data):
        """
        Set Resv EAS AFI DSFID for 15 emulator
        """
        resp_set = self.upload_data_block(type = 0x03, slot = slot + 0x1A, index = 0xFC00, data = data)
        resp_save = self.hf_15_esave(slot)
        return resp_set and resp_save

    def hf_15_eset_write_protect(self, slot, data):
        """
        Set write protect for 15 emulator
        """
        resp_set = self.upload_data_block(type = 0x03, slot = slot + 0x1A, index = 0xFB00, data = data)
        resp_save = self.hf_15_esave(slot)
        return resp_set and resp_save

    def hf_15_esave(self, slot):
        """
        Save 15 emulator data
        """
        return self.upload_data_block_done(type = 0x03, slot = slot + 0x1A, extra = b"\x00" * 4)

    @expect_response(Status.SUCCESS)
    def hf_mf_load(self, dump_map, slot=0):
        slot = int(slot) - 1
        for block_index, block_data in dump_map.items():
            bn = int(block_index)
            sector = bn // 4
            blk = bn % 4
            resp = self.upload_data_block(type=1, slot=slot, sector=sector, block=blk, data=bytes.fromhex(block_data))
            print(f"Load block {bn:02d} (sector {sector} block {blk}): {resp}")
        self.upload_data_block_done(slot=slot)
        return Response(Pn532KillerCommand.WriteEmulator, Status.SUCCESS)

    def hf_mf_eread(self, slot):
        slot = slot - 1
        self.prepare_get_emulator_data(type=1, slot=slot)
        sleep(0.02)
        mifare_dump = {}
        for bn in range(64):
            sector = bn // 4
            blk = bn % 4
            resp = self.download_data_block(type=1, slot=slot, sector=sector, block=blk)
            mifare_dump[bn] = resp
        return mifare_dump

    def hf_mfu_eread(self, slot):
        """
        Mifare Ultralight emulator read to dump

        :param slot: slot number
        :return:
        """
        slot = slot - 1
        self.prepare_get_emulator_data(type = 2, slot = slot)
        sleep(0.02)
        mfu_dump = {}
        # Read first 4 pages
        max_page = 64
        for page in range(4):
            resp = self.download_data_block(type = 2, slot = slot, index = page)
            if page == 0:
                print(f"page {page:02d}: {CY}{resp.parsed.hex()[0:6].upper()}{CR}{resp.parsed.hex()[6:8].upper()}{C0}")
            elif page == 1:
                print(f"page {page:02d}: {CY}{resp.parsed.hex().upper()}{C0}")
            elif page == 2:
                print(f"page {page:02d}: {CR}{resp.parsed.hex()[0:2].upper()}{CG}{resp.parsed.hex()[2:].upper()}{C0}")
            elif page == 3:
                print(f"page {page:02d}: {CG}{resp.parsed.hex().upper()}{C0}")
                # page 3 , index 2 is the max page indicator
                if len(resp.parsed) >= 3:
                    max_page = resp.parsed[2] * 2 + 12
            mfu_dump[page] = resp
        # Read remaining pages
        for page in range(4, max_page):
            resp = self.download_data_block(type = 2, slot = slot, index = page)
            print(f"page {page:02d}: {resp.parsed.hex().upper()}")
            mfu_dump[page] = resp
        return mfu_dump

    def upload_data_block(self, type=1, slot=0, sector=0, block=0, data=b""):
        """type(1) + tagindex(1) + sector(1) + block(1) + data(n)"""
        pkt = struct.pack("!BBBB", type, slot, sector, block) + data
        resp = self.device.send_cmd_sync(Pn532KillerCommand.WriteEmulator, pkt)
        resp.parsed = len(resp.data) > 3 and resp.data[-1] == 0x00
        return resp

    def upload_data_block_done(self, type=1, slot=0, extra=b""):
        """sector=0xFF block=0xFF marks write completion"""
        pkt = struct.pack("!BBBB", type, slot, 0xFF, 0xFF) + extra
        resp = self.device.send_cmd_sync(Pn532KillerCommand.WriteEmulator, pkt)
        resp.parsed = resp.data[-1] == 0x00 if resp.data else False
        return resp

    @expect_response(Status.SUCCESS)
    def download_data_block(self, type=1, slot=0, sector=0, block=0):
        """type(1) + tagindex(1) + sector(1) + block(1)"""
        pkt = struct.pack("!BBBB", type, slot, sector, block)
        resp = self.device.send_cmd_sync(Pn532KillerCommand.ReadEmulator, pkt)
        resp.parsed = resp.data[4:] if len(resp.data) > 4 else b''
        return resp

    @expect_response(Status.SUCCESS)
    def prepare_get_emulator_data(self, type=1, slot=0):
        resp = self.download_data_block(type, slot, 0xFF, 0xFF)
        return Response(Pn532KillerCommand.ReadEmulator, Status.SUCCESS)

    @expect_response(Status.SUCCESS)
    def ntag_emulator(self, url: str, debug_callback=None):
        """NDEF 模拟器(可选 debug 回调,用于 APDU 调试器)。

        :param url: NDEF URL 记录
        :param debug_callback: 可选 callable(event_type, raw_bytes),
          event_type ∈ {'RX', 'TX', 'INFO'},raw_bytes 为原始 APDU 字节
        """
        def _emit(event, data):
            if debug_callback:
                try:
                    debug_callback(event, data)
                except Exception:
                    pass
            # 即便没有 callback,也保留 print 行为
            print(f"[{event}] {data.hex().upper() if isinstance(data, bytes) else data}")

        input_thread = threading.Thread(target=self.wait_for_enter)
        input_thread.start()
        resp_tginitastarget = self.device.send_cmd_sync(
            Command.TgInitAsTarget,
            bytes.fromhex(
                "0408001122336001FEA2A3A4A5A6A7C0C1C2C3C4C5C6C7FFFFAA9988776655443322110000"
            ),
        )
        _emit('TX', bytes.fromhex("0408001122336001FEA2A3A4A5A6A7C0C1C2C3C4C5C6C7FFFFAA9988776655443322110000"))
        _emit('RX', resp_tginitastarget.data)
        compatibility_container = [
            0,
            0x0F,
            0x20,
            0,
            0x54,
            0,
            0xFF,
            0x04,
            0x06,
            0xE1,
            0x04,
            ((NdefCommand.NDEF_MAX_LENGTH & 0xFF00) >> 8),
            (NdefCommand.NDEF_MAX_LENGTH & 0xFF),
            0x00,
            0x00,
        ]
        current_file = TagFile.NONE
        while not self.stop_flag:
            resp = self.device.send_cmd_sync(Command.TgGetData)
            _emit('RX', resp.data)
            if len(resp.data) == 0:
                self.device.in_release()
                sleep(0.01)
                continue
            if len(resp.data) > 0:
                if resp.data[0] == 0x29 or resp.data[0] == 0x25:
                    resp_tginitastarget = self.device.send_cmd_sync(
                        Command.TgInitAsTarget,
                        bytes.fromhex(
                            "0408001122336001FEA2A3A4A5A6A7C0C1C2C3C4C5C6C7FFFFAA9988776655443322110000"
                        ),
                    )
                    print(
                        f"TgInitAsTarget restarted = {resp_tginitastarget.data.hex().upper()}"
                    )
                    continue
            if len(resp.data) < 5:
                sleep(0.01)
                continue
            rbuf = resp.data[1:]
            print(f"TgGetData => {rbuf.hex().upper()}")
            if len(rbuf) < 5:
                continue

            ins = rbuf[ApduCommand.C_APDU_INS]
            p1 = rbuf[ApduCommand.C_APDU_P1]
            p2 = rbuf[ApduCommand.C_APDU_P2]
            p1p2_length = (p1 << 8) | p2
            lc = rbuf[ApduCommand.C_APDU_P2 + 1]
            if DEBUG: 
                print(
                    f"ins = {hex(ins)}, p1 = {hex(p1)}, p2 = {hex(p2)}, p1p2_length = {hex(p1p2_length)},  lc = {hex(lc)}"
                )
            if ins == ApduCommand.ISO7816_SELECT_FILE:
                if DEBUG:
                    print("ISO7816_SELECT_FILE")
                if p1 == ApduCommand.C_APDU_P1_SELECT_BY_ID:
                    if DEBUG:
                        print("C_APDU_P1_SELECT_BY_ID")
                    if p2 != 0x0C:
                        if DEBUG:
                            print("C_APDU_P2 != 0x0C")
                        wbuf = [
                            ApduCommand.R_APDU_SW1_COMMAND_COMPLETE,
                            ApduCommand.R_APDU_SW2_COMMAND_COMPLETE,
                        ]
                    elif (
                        lc == 0x02
                        and rbuf[ApduCommand.C_APDU_DATA] == 0xE1
                        and (
                            rbuf[ApduCommand.C_APDU_DATA + 1] == 0x03
                            or rbuf[ApduCommand.C_APDU_DATA + 1] == 0x04
                        )
                    ):
                        if rbuf[ApduCommand.C_APDU_DATA + 1] == 0x03:
                            current_file = TagFile.CC
                        elif rbuf[ApduCommand.C_APDU_DATA + 1] == 0x04:
                            current_file = TagFile.NDEF
                        if DEBUG:
                            print("current_file = ", current_file)

                        wbuf = [
                            ApduCommand.R_APDU_SW1_COMMAND_COMPLETE,
                            ApduCommand.R_APDU_SW2_COMMAND_COMPLETE,
                        ]
                    else:
                        wbuf = [
                            ApduCommand.R_APDU_SW1_NDEF_TAG_NOT_FOUND,
                            ApduCommand.R_APDU_SW2_NDEF_TAG_NOT_FOUND,
                        ]
                        if DEBUG:
                            print("NDEF tag not found")
                if p1 == ApduCommand.C_APDU_P1_SELECT_BY_NAME:
                    if DEBUG:
                        print("C_APDU_P1_SELECT_BY_NAME")
                    if list(rbuf[3:12]) == NdefCommand.APPLICATION_NAME_V2:
                        wbuf = [
                            ApduCommand.R_APDU_SW1_COMMAND_COMPLETE,
                            ApduCommand.R_APDU_SW2_COMMAND_COMPLETE,
                        ]
                        if DEBUG:
                            print(f"application = {rbuf[3:12].hex().upper()}")
                    else:
                        wbuf = [
                            ApduCommand.R_APDU_SW1_FUNCTION_NOT_SUPPORTED,
                            ApduCommand.R_APDU_SW2_FUNCTION_NOT_SUPPORTED,
                        ]
                        if DEBUG:
                            print("function not supported")
            elif ins == ApduCommand.ISO7816_READ_BINARY:
                if current_file == TagFile.NONE:
                    wbuf = [
                        ApduCommand.R_APDU_SW1_NDEF_TAG_NOT_FOUND,
                        ApduCommand.R_APDU_SW2_NDEF_TAG_NOT_FOUND,
                    ]
                    if DEBUG:
                        print("NDEF tag not found")
                elif current_file == TagFile.CC:
                    if p1p2_length > NdefCommand.NDEF_MAX_LENGTH:
                        wbuf = [
                            ApduCommand.R_APDU_SW1_END_OF_FILE_BEFORE_REACHED_LE_BYTES,
                            ApduCommand.R_APDU_SW2_END_OF_FILE_BEFORE_REACHED_LE_BYTES,
                        ]
                        if DEBUG:
                            print("CC: End of file before reached LE bytes")
                    else:
                        # set deny
                        compatibility_container[14] = 0xFF
                        # C: memcpy(rbuf, compatibility_container + p1p2_length, lc)
                        wbuf = compatibility_container[p1p2_length:]
                        data = [
                            ApduCommand.R_APDU_SW1_COMMAND_COMPLETE,
                            ApduCommand.R_APDU_SW2_COMMAND_COMPLETE,
                        ]
                        wbuf += bytes(data)
                        if DEBUG:
                            print("CC data set")
                elif current_file == TagFile.NDEF:
                    if p1p2_length > NdefCommand.NDEF_MAX_LENGTH:
                        wbuf = [
                            ApduCommand.R_APDU_SW1_END_OF_FILE_BEFORE_REACHED_LE_BYTES,
                            ApduCommand.R_APDU_SW2_END_OF_FILE_BEFORE_REACHED_LE_BYTES,
                        ]
                        if DEBUG:
                            print("NDEF: End of file before reached LE bytes")
                    else:
                        payload = ndef.ndef._url_ndef_abbrv(url)
                        uri_record = (
                            ndef.TNF_WELL_KNOWN,
                            ndef.RTD_URI,
                            "".encode("utf-8"),
                            payload,
                        )
                        uri_message = ndef.new_message(uri_record)
                        ndef_bytes = list(uri_message.to_buffer())
                        if lc == 0x02:
                            # turn NdefCommand.NDEF_MAX_LENGTH to 2 bytes then add R_APDU_SW1_COMMAND_COMPLETE R_APDU_SW2_COMMAND_COMPLETE
                            wbuf = list(len(ndef_bytes).to_bytes(2, byteorder="big"))
                            data = [
                                ApduCommand.R_APDU_SW1_COMMAND_COMPLETE,
                                ApduCommand.R_APDU_SW2_COMMAND_COMPLETE,
                            ]
                            wbuf += bytes(data)
                            if DEBUG:
                                print("NDEF_MAX_LENGTH set")
                        else:
                            wbuf = ndef_bytes
                            wbuf += bytes(data)
                            if DEBUG:
                                print("NDEF data set")
                else:
                    if DEBUG:
                        print("Command not supported!")
                    wbuf = [
                        ApduCommand.R_APDU_SW1_FUNCTION_NOT_SUPPORTED,
                        ApduCommand.R_APDU_SW2_FUNCTION_NOT_SUPPORTED,
                    ]
            elif ins == ApduCommand.ISO7816_UPDATE_BINARY:
                wbuf = [
                    ApduCommand.R_APDU_SW1_FUNCTION_NOT_SUPPORTED,
                    ApduCommand.R_APDU_SW2_FUNCTION_NOT_SUPPORTED,
                ]
            resp = self.device.send_cmd_sync(Command.TgSetData, wbuf)
            _emit('TX', bytes(wbuf))
            _emit('RX', resp.data)
            if resp.status != Status.SUCCESS:
                self.device.in_release()
                continue
            if self.stop_flag:
                break
        self.device.set_normal_mode()
        return resp

    def ntag_reader(self):
        import webbrowser
        """
        Read NTAG and parse NDEF data. If the data contains a URI (e.g., link, tel, mailto), open it in the browser.
        """
        try:
            self.device.set_normal_mode()
            self.stop_flag = False
            input_thread = threading.Thread(target=self.wait_for_enter)
            input_thread.start()
            
            while not self.stop_flag:
                resp = self.hf_14a_scan()
                if resp is None:
                    print("No tag found. Waiting for tag...")
                    sleep(0.5)
                    continue

                dump_bin_data = bytearray()
                max_block = 4
                block = 0
                while block < max_block:
                    resp = self.mf0_read_one_block(block)
                    if block == 0 and resp and resp.parsed and len(resp.parsed) == 16:
                        max_block = resp.parsed[14] * 2 + 9
                    if resp and resp.parsed and len(resp.parsed) == 16:
                        dump_bin_data.extend(resp.parsed)
                    else:
                        print(f"Error reading block {block}: {resp}")
                        break
                    block += 4
                print("NTAG Dump:")
                for i in range(0, len(dump_bin_data), 16):
                    print(f"{CG}{' '.join(f'{byte:02X}' for byte in dump_bin_data[i:i + 16])}  {''.join(chr(byte) if 32 <= byte <= 126 else '.' for byte in dump_bin_data[i:i + 16])}{C0}")
                ndef_parser = NdefParser(dump_bin_data)
                urls = ndef_parser.get_urls()
                if urls:
                    print("NDEF URLs:")
                    for url in urls:
                        print(f"{CG}{url}{C0}")
                        
                for url in urls:
                    if "http" in url or "tel" in url or "mailto" in url:
                        webbrowser.open(url)
                
                print("Remove card and place another, or press Enter to stop...")
                sleep(1)
            
            print("Stopped NTAG reading.")
            return []
        except Exception as e:
            print("Error reading NTAG:", e)
            self.stop_flag = True
            return []
        
    stop_flag = False
    def wait_for_enter(self):
        print("Press Enter to stop...")
        while not self.stop_flag:
            while True:
                # if system is Windows
                if os.name == "nt":
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b"\r":  # 检测回车键
                            self.stop_flag = True
                            print("Stopping...")
                            break
                else:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        if key == "\n":  # 检测回车键
                            self.stop_flag = True
                            print("Stopping...")
                            break
            sleep(0.1)

def test_fn():
    # connect to pn532
    dev = pn532_com.Pn532Com()
    platform_name = uname().release
    if "Microsoft" in platform_name:
        path = os.environ["PATH"].split(os.pathsep)
        path.append("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/")
        powershell_path = None
        for prefix in path:
            fn = os.path.join(prefix, "powershell.exe")
            if not os.path.isdir(fn) and os.access(fn, os.X_OK):
                powershell_path = fn
                break
        if powershell_path:
            process = subprocess.Popen(
                [
                    powershell_path,
                    "Get-PnPDevice -Class Ports -PresentOnly |"
                    " where {$_.DeviceID -like '*VID_6868&PID_8686*'} |"
                    " Select-Object -First 1 FriendlyName |"
                    " % FriendlyName |"
                    " select-string COM\\d+ |"
                    "% { $_.matches.value }",
                ],
                stdout=subprocess.PIPE,
            )
            res = process.communicate()[0]
            _comport = res.decode("utf-8").strip()
            if _comport:
                dev.open(_comport.replace("COM", "/dev/ttyS"))
    else:
        # loop through all ports and find pn532
        for port in serial.tools.list_ports.comports():
            if port.vid == 6790:
                dev.open(port.device)
                break
            if "PN532Killer" in port.description:
                dev.open(port.device)
                break
    print(f"Connected to {dev.get_connection_info()}")
    print(f"Device: {dev.device_name}")
    cml = Pn532CMD(dev)

    try:
        resp = cml.hf_14a_scan()
        print("hf_14a_scan:", resp)
        options = {
                "activate_rf_field": 0,
                "wait_response": 1,
                "append_crc": 1,
                "auto_select": 0,
                "keep_rf_field": 1,
                "check_response_crc": 0,
            }
        resp = cml.hf14a_raw(
                options=options,
                resp_timeout_ms=1000,
                data= bytes.fromhex("cf00000000ce00"),
            )
        print("hf14a_raw:", resp.parsed.hex().upper())
    except Exception as e:
        print("Error:", e)
    dev.close()


if __name__ == "__main__":
    test_fn()
