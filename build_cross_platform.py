#!/usr/bin/env python3
"""
跨平台构建脚本
支持 Windows 和 Linux 平台的自动化构建
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

class CrossPlatformBuilder:
    def __init__(self):
        self.system = platform.system().lower()
        self.script_dir = Path(__file__).parent
        self.build_dir = self.script_dir / "build"
        self.dist_dir = self.script_dir / "dist"
        
    def detect_platform(self):
        """检测当前平台"""
        print(f"检测到平台: {self.system}")
        return self.system
        
    def check_dependencies(self):
        """检查构建依赖"""
        print("检查构建依赖...")
        
        # 检查 Python
        try:
            python_version = sys.version_info
            if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
                raise Exception("需要 Python 3.7 或更高版本")
            print(f"✓ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        except Exception as e:
            print(f"✗ Python 检查失败: {e}")
            return False
            
        # 检查 PyInstaller
        try:
            result = subprocess.run(['pyinstaller', '--version'], 
                                  capture_output=True, text=True, check=True)
            print(f"✓ PyInstaller {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("✗ PyInstaller 未安装，正在安装...")
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
                print("✓ PyInstaller 安装成功")
            except subprocess.CalledProcessError:
                print("✗ PyInstaller 安装失败")
                return False
                
        # 检查平台特定依赖
        if self.system == "linux":
            return self.check_linux_dependencies()
        elif self.system == "windows":
            return self.check_windows_dependencies()
            
        return True
        
    def check_linux_dependencies(self):
        """检查 Linux 特定依赖"""
        print("检查 Linux 依赖...")
        
        # 检查 libnfc 工具
        tools = ['nfc-list', 'nfc-mfclassic', 'mfoc']
        missing_tools = []
        
        for tool in tools:
            if not shutil.which(tool):
                missing_tools.append(tool)
            else:
                print(f"✓ {tool}")
                
        if missing_tools:
            print(f"✗ 缺少工具: {', '.join(missing_tools)}")
            print("请参考 LINUX_SETUP.md 安装缺少的工具")
            return False
            
        # 检查 mfkey 工具
        mfkey_tools = ['mfkey64', 'mfkey32v2']
        for tool in mfkey_tools:
            tool_path = self.script_dir / tool
            if not tool_path.exists():
                print(f"✗ {tool} 不存在，请编译后放置在脚本目录")
                return False
            else:
                print(f"✓ {tool}")
                
        return True
        
    def check_windows_dependencies(self):
        """检查 Windows 特定依赖"""
        print("检查 Windows 依赖...")
        
        # 检查 nfc-bin 目录
        nfc_bin_dir = self.script_dir / "nfc-bin"
        if not nfc_bin_dir.exists():
            print("✗ nfc-bin 目录不存在")
            return False
            
        # 检查关键工具
        tools = ['nfc-list.exe', 'nfc-mfclassic.exe', 'libnfc_hardnested.exe', 'mfoc.exe']
        for tool in tools:
            tool_path = nfc_bin_dir / tool
            if not tool_path.exists():
                print(f"✗ {tool} 不存在")
                return False
            else:
                print(f"✓ {tool}")
                
        # 检查 mfkey 工具
        mfkey_tools = ['mfkey64.exe', 'mfkey32v2.exe']
        for tool in mfkey_tools:
            tool_path = self.script_dir / tool
            if not tool_path.exists():
                print(f"✗ {tool} 不存在")
                return False
            else:
                print(f"✓ {tool}")
                
        return True
        
    def clean_build(self):
        """清理构建目录"""
        print("清理构建目录...")
        
        for dir_path in [self.build_dir, self.dist_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"✓ 清理 {dir_path}")
                
    def get_spec_file(self):
        """获取平台特定的 spec 文件"""
        if self.system == "linux":
            return self.script_dir / "pyinstaller_linux.spec"
        elif self.system == "windows":
            return self.script_dir / "pn532_gui.spec"
        else:
            return self.script_dir / "pyinstaller.spec"
            
    def build_application(self):
        """构建应用程序"""
        print("开始构建应用程序...")
        
        spec_file = self.get_spec_file()
        if not spec_file.exists():
            print(f"✗ Spec 文件不存在: {spec_file}")
            return False
            
        try:
            cmd = ['pyinstaller', '--clean', str(spec_file)]
            print(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, cwd=self.script_dir, check=True)
            print("✓ 构建成功")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"✗ 构建失败: {e}")
            return False
            
    def package_distribution(self):
        """打包分发文件"""
        print("打包分发文件...")
        
        if not self.dist_dir.exists():
            print("✗ 分发目录不存在")
            return False
            
        # 创建版本信息
        version_info = {
            'platform': self.system,
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'build_date': subprocess.run(['date'], capture_output=True, text=True).stdout.strip()
        }
        
        # 复制必要文件
        files_to_copy = ['README.md', 'requirements.txt']
        if self.system == "linux":
            files_to_copy.append('LINUX_SETUP.md')
            
        for file_name in files_to_copy:
            src_file = self.script_dir / file_name
            if src_file.exists():
                dst_file = self.dist_dir / file_name
                shutil.copy2(src_file, dst_file)
                print(f"✓ 复制 {file_name}")
                
        print("✓ 打包完成")
        return True
        
    def run_tests(self):
        """运行基本测试"""
        print("运行基本测试...")
        
        # 测试 Python 语法
        test_files = [
            'path_manager.py',
            'pn532_gui.py', 
            'thread_workers.py',
            'pn532_cmd.py'
        ]
        
        for test_file in test_files:
            file_path = self.script_dir / test_file
            if file_path.exists():
                try:
                    subprocess.run([sys.executable, '-m', 'py_compile', str(file_path)], 
                                 check=True, capture_output=True)
                    print(f"✓ {test_file} 语法检查通过")
                except subprocess.CalledProcessError:
                    print(f"✗ {test_file} 语法检查失败")
                    return False
            else:
                print(f"⚠ {test_file} 不存在，跳过测试")
                
        return True
        
    def build(self):
        """执行完整构建流程"""
        print("=" * 50)
        print("PN532 Python 跨平台构建脚本")
        print("=" * 50)
        
        # 检测平台
        self.detect_platform()
        
        # 检查依赖
        if not self.check_dependencies():
            print("✗ 依赖检查失败，构建终止")
            return False
            
        # 运行测试
        if not self.run_tests():
            print("✗ 测试失败，构建终止")
            return False
            
        # 清理构建目录
        self.clean_build()
        
        # 构建应用程序
        if not self.build_application():
            print("✗ 应用程序构建失败")
            return False
            
        # 打包分发文件
        if not self.package_distribution():
            print("✗ 分发打包失败")
            return False
            
        print("=" * 50)
        print("✓ 构建完成！")
        print(f"分发文件位于: {self.dist_dir}")
        print("=" * 50)
        
        return True

def main():
    """主函数"""
    builder = CrossPlatformBuilder()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "clean":
            builder.clean_build()
        elif command == "check":
            builder.check_dependencies()
        elif command == "test":
            builder.run_tests()
        elif command == "build":
            builder.build()
        else:
            print("用法: python build_cross_platform.py [clean|check|test|build]")
            print("  clean - 清理构建目录")
            print("  check - 检查依赖")
            print("  test  - 运行测试")
            print("  build - 完整构建")
    else:
        # 默认执行完整构建
        builder.build()

if __name__ == "__main__":
    main()