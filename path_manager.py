import tempfile
import sys
import os
import shutil
import platform


class PathManager:
    @staticmethod
    def get_app_data_dir():
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return base_path

    @staticmethod
    def get_temp_dir():
        return tempfile.gettempdir()

    @staticmethod
    def get_history_keys_path():
        history_dir = os.path.join(PathManager.get_app_data_dir(), "history")
        os.makedirs(history_dir, exist_ok=True)
        history_keys_path = os.path.join(history_dir, "history_keys.txt")
        if not os.path.exists(history_keys_path):
            source_path = ""
            if getattr(sys, 'frozen', False):
                source_path = os.path.join(sys._MEIPASS, "history_keys.txt")
            else:
                source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_keys.txt")
            if os.path.exists(source_path):
                shutil.copy2(source_path, history_keys_path)
            else:
                with open(history_keys_path, 'w') as f:
                    pass
        return history_keys_path

    @staticmethod
    def get_history_dir():
        """返回 history 目录(用于嗅探、UID 修改记录等运行时文件)。"""
        d = os.path.join(PathManager.get_app_data_dir(), "history")
        os.makedirs(d, exist_ok=True)
        return d

    @staticmethod
    def get_mfoc_tool_path(tool_name="mfoc"):
        """获取 mfoc 系列工具路径。

        自动查找顺序:
          1. 打包环境 (sys._MEIPASS/nfc-bin/<tool>.exe)
          2. 开发环境 - 同级 nfc-bin/<tool>.exe
          3. 系统 PATH

        已在本机验证 mfoc.exe 在 PN532Killer 上完整工作
        (等同标准 pn532_uart 协议,无需固件扩展)。
        """
        # 兼容传统 mfoc / mfoc-hardnested / libnfc_hardnested
        candidate_names = [tool_name, f"{tool_name}.exe"]
        exe_name = candidate_names[1] if PathManager.is_windows() else candidate_names[0]

        # 1. frozen - 优先 exe 同目录,其次 _MEIPASS
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            cand = os.path.join(exe_dir, 'nfc-bin', exe_name)
            if os.path.exists(cand):
                return cand
            cand = os.path.join(exe_dir, exe_name)
            if os.path.exists(cand):
                return cand
            base = sys._MEIPASS
            cand = os.path.join(base, 'nfc-bin', exe_name)
            if os.path.exists(cand):
                return cand
            cand = os.path.join(base, exe_name)
            if os.path.exists(cand):
                return cand
        # 2. 开发环境 - 同级 nfc-bin/ 下
        base = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(base, 'nfc-bin', exe_name)
        if os.path.exists(cand):
            return cand
        cand = os.path.join(base, exe_name)
        if os.path.exists(cand):
            return cand
        # 3. Windows PATH
        return exe_name

    @staticmethod
    def get_key_file_path():
        app_data_dir = PathManager.get_app_data_dir()
        key_file_path = os.path.join(app_data_dir, "key.txt")
        if not os.path.exists(key_file_path):
            source_path = ""
            if getattr(sys, 'frozen', False):
                source_path = os.path.join(sys._MEIPASS, "key.txt")
            else:
                source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.txt")
            if os.path.exists(source_path):
                shutil.copy2(source_path, key_file_path)
            else:
                with open(key_file_path, 'w') as f:
                    pass
        return key_file_path

    @staticmethod
    def get_temp_file_path(filename):
        return os.path.join(PathManager.get_temp_dir(), filename)

    @staticmethod
    def get_output_dir():
        output_dir = os.path.join(PathManager.get_app_data_dir(), "dumps")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    @staticmethod
    def is_windows():
        """检查是否为 Windows 系统"""
        return platform.system() == "Windows"

    @staticmethod
    def get_mfkey_tool_path(tool_name):
        """获取 mfkey 工具的完整路径"""
        if getattr(sys, 'frozen', False):
            # 打包后: 优先 exe 同目录,其次 _MEIPASS
            exe_dir = os.path.dirname(sys.executable)
            exe_name = tool_name + ".exe" if PathManager.is_windows() else tool_name
            cand = os.path.join(exe_dir, exe_name)
            if os.path.exists(cand):
                return cand
            cand = os.path.join(sys._MEIPASS, exe_name)
            if os.path.exists(cand):
                return cand
            return exe_name  # fallback to PATH
        else:
            # 开发环境
            if PathManager.is_windows():
                base_dir = os.path.dirname(os.path.abspath(__file__))
                return os.path.join(base_dir, tool_name + ".exe")
            else:
                # Linux/macOS 开发环境：首先尝试本地文件，如果不存在则使用系统PATH
                base_dir = os.path.dirname(os.path.abspath(__file__))
                local_tool_path = os.path.join(base_dir, tool_name)
                if os.path.exists(local_tool_path):
                    return local_tool_path
                else:
                    # 如果本地文件不存在，返回工具名称让系统在PATH中查找
                    return tool_name

    @staticmethod
    def get_shell_command():
        """获取系统 shell 命令"""
        if PathManager.is_windows():
            return "cmd.exe"
        else:
            return "/bin/bash"

    @staticmethod
    def get_icon_path():
        """获取应用程序图标路径"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            icon_path = os.path.join(sys._MEIPASS, "ico.png")
        else:
            # 开发环境
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ico.png")
        
        return icon_path if os.path.exists(icon_path) else None