"""
mfoc.exe + hardnested 包装层。

⚠ 这是"不自己写密码学"的最实用自动解卡方案:
- mfoc 在本机 PN532Killer 上已验证 (Phase 1 测试)
- mfoc 输出标准 MFD,可被 MFDParser 直接解析
- 完整 Python 移植(Crypto1 + nested attack)工作量大(5-10 天)

后续路线:
- 短期: 此包装器 + GUI 集成 (Phase 2)
- 中期: 把 mfoc 的 mf_enhanced_auth + lfsr_recovery32 移植到 Python
- 长期: 完全摆脱 mfoc.exe 依赖
"""

import os
import platform
import re
import subprocess
import time
from typing import Optional, Dict, List, Tuple
from path_manager import PathManager


class MfocRunner:
    """mfoc.exe / libnfc_hardnested.exe 包装器。

    提供与 DumpReader 相同的接口约定,使得后续若替换为 Python
    原生实现只需替换这一个类即可,GUI 完全无需改动。
    """

    MFOC_TIMEOUT = 180  # 3 分钟足够默认密钥 + nested 攻击

    def __init__(self, ports: List[str] = None, keys: List[bytes] = None,
                 tool_name: str = "mfoc"):
        self.ports = ports or []  # 未用,libnfc 自动用 pn532_uart:COMx
        # 至少 1 个已知密钥 - mfoc 的必需参数
        self.keys_hex = []
        if keys:
            for k in keys:
                if isinstance(k, str):
                    self.keys_hex.append(k.lower())
                else:
                    self.keys_hex.append(k.hex().lower())
        self.tool_name = tool_name
        self.executable_path = PathManager.get_mfoc_tool_path(tool_name)
        self.last_output = ""
        self.sectors_found: Dict[int, dict] = {}

    def is_available(self) -> bool:
        """检查 mfoc.exe 是否可用(用于 GUI 显示状态)。"""
        p = self.executable_path
        # 'mfoc.exe' 字符串(未找到本地)始终 try-exists
        if os.path.sep not in p and '/' not in p:
            import shutil
            return shutil.which(p) is not None
        return os.path.exists(p)

    def run(self, output_path: str, progress_cb=None, cancel_cb=None) -> Tuple[bool, bytes, str]:
        """运行 mfoc 攻击并返回解出的 MFD 数据。

        :param output_path: MFD 输出路径(会被 mfoc.exe 创建)
        :param progress_cb: 进度回调(msg: str)
        :param cancel_cb: 取消回调(返回 True 取消)
        :return: (ok, mfd_bytes, summary_msg)
        """
        def _emit(msg):
            if progress_cb:
                enc = 'gbk' if os.name == 'nt' else 'utf-8'
                safe = msg.encode(enc, errors='replace').decode(enc, errors='replace')
                progress_cb(safe)
        if progress_cb:
            _emit(f"[mfoc] 启动自动解卡 (工具: {self.tool_name})")
            _emit(f"[mfoc] 路径: {self.executable_path}")
        if not self.is_available():
            msg = f"mfoc 工具不可用: {self.executable_path}"
            if progress_cb:
                _emit(f"[mfoc] X {msg}")
            return False, b'', msg

        if not self.keys_hex:
            msg = "mfoc 至少需要 1 个已知密钥"
            if progress_cb:
                _emit(f"[mfoc] X {msg}")
            return False, b'', msg

        # 构造命令行: mfoc -k <key1> -k <key2> ... -O output.mfd
        cmd = [self.executable_path]
        for kh in self.keys_hex:
            cmd.extend(["-k", kh])
        cmd.extend(["-O", output_path])

        if progress_cb:
            _emit(f"[mfoc] 命令: {' '.join(cmd)}")

        try:
            creationflags = 0
            if PathManager.is_windows():
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                text=True,
                encoding='gbk' if os.name == 'nt' else 'utf-8',
                errors='ignore',
            )
            stdout_chunks = []
            start = time.time()
            cancelled = False
            sector_progress = {}  # sector -> found state (A, B, both)
            while True:
                if cancel_cb and cancel_cb():
                    proc.terminate()
                    cancelled = True
                    break
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    safe_line = line.encode('gbk', errors='replace').decode('gbk')
                    stdout_chunks.append(safe_line)
                    self.last_output += safe_line
                    # 解析 mfoc 输出并回调进度
                    msg = safe_line.rstrip()
                    if self._parse_progress(msg, sector_progress):
                        for sector, info in sector_progress.items():
                            _emit(self._fmt_sector_status(sector, info))
                    # 实时回显 mfoc 输出(GUI 进程会显示进度)
                    if progress_cb:
                        _emit(f"[mfoc] {msg}")
                # 超时
                if time.time() - start > self.MFOC_TIMEOUT:
                    proc.terminate()
                    cancelled = True
                    break
            proc.wait(timeout=2)
            self.sectors_found = sector_progress
        except Exception as e:
            msg = f"mfoc 执行失败: {e}"
            if progress_cb:
                _emit(f"[mfoc] X {msg}")
            return False, b'', msg

        # 取消
        if cancelled:
            msg = "mfoc 被取消或超时"
            if progress_cb:
                _emit(f"[mfoc] (timeout) {msg}")
            return False, b'', msg

        # 读取 MFD
        if not os.path.exists(output_path):
            tail = '\n'.join(stdout_chunks[-10:])
            msg = f"mfoc 未生成 MFD 文件:\n{tail}"
            if progress_cb:
                _emit(f"[mfoc] X {msg}")
            return False, b'', msg

        try:
            with open(output_path, 'rb') as f:
                mfd = f.read()
        except Exception as e:
            return False, b'', f"读取 MFD 失败: {e}"

        ok_sectors = len(self.sectors_found)
        summary = f"mfoc 成功: {ok_sectors}/16 扇区"
        if progress_cb:
            _emit(f"[mfoc] OK {summary}, {len(mfd)} 字节")
        return True, mfd, summary

    # --------- 输出解析 ---------
    SECTOR_RE = re.compile(r'扇区\s*(\d+)\s*-\s*找[到到]\s*:\s*Key\s*A\s*:?\s*(\S+)\s*:?\s*Key\s*B\s*:?\s*(\S+)', re.IGNORECASE)
    SECTOR_LINE_RE = re.compile(r'\[扇区\s+(\d+)\]', re.IGNORECASE)
    KEY_FOUND_RE = re.compile(r'\[\s*Key\s*:\s*([0-9a-fA-F]{12})\s*\]\s*->\s*\[([x/\\]+)\]', re.IGNORECASE)

    def _parse_progress(self, line: str, sector_progress: dict) -> bool:
        """解析 mfoc 单行输出,更新扇区进度。返回 True 表示有新信息。"""
        # 扇区命中行
        m = self.SECTOR_RE.search(line)
        if m:
            sector = int(m.group(1))
            ka = m.group(2).strip().lower()
            kb = m.group(3).strip().lower()
            sector_progress[sector] = {'ka': ka, 'kb': kb, 'found': True}
            return True
        return False

    def _fmt_sector_status(self, sector: int, info: dict) -> str:
        ka = info.get('ka', '?')
        kb = info.get('kb', '?')
        return f"[mfoc] 扇区 {sector:02d} ✅ KeyA={ka}  KeyB={kb}"


# ----- 便捷工厂 -----

_global_runner: Optional[MfocRunner] = None


def get_mfoc_runner(keys: List[bytes] = None, tool_name: str = "mfoc") -> MfocRunner:
    """获取全局 mfoc runner(自动重用以节省检测开销)。"""
    global _global_runner
    if _global_runner is None or _global_runner.tool_name != tool_name:
        _global_runner = MfocRunner(keys=keys, tool_name=tool_name)
    return _global_runner


def reset_mfoc_runner():
    global _global_runner
    _global_runner = None
