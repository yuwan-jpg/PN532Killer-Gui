@echo off
REM PN532 Python Windows 构建脚本

setlocal enabledelayedexpansion

echo ========================================
echo PN532 Python Windows 构建脚本
echo ========================================

REM 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Python 未安装或不在 PATH 中
    pause
    exit /b 1
)

REM 解析命令行参数
set "COMMAND=%1"
if "%COMMAND%"=="" set "COMMAND=build"

if /i "%COMMAND%"=="help" goto :show_help
if /i "%COMMAND%"=="check" goto :check_deps
if /i "%COMMAND%"=="test" goto :run_tests
if /i "%COMMAND%"=="clean" goto :clean_build
if /i "%COMMAND%"=="build" goto :build_app
if /i "%COMMAND%"=="install" goto :install_deps

echo 未知命令: %COMMAND%
goto :show_help

:show_help
echo 用法: build.bat [命令]
echo.
echo 可用命令:
echo   help     - 显示此帮助信息
echo   check    - 检查构建依赖
echo   test     - 运行测试
echo   clean    - 清理构建目录
echo   build    - 构建应用程序 (默认)
echo   install  - 安装依赖
echo.
goto :end

:check_deps
echo 检查构建依赖...
python build_cross_platform.py check
if errorlevel 1 (
    echo 依赖检查失败
    pause
    exit /b 1
)
goto :end

:run_tests
echo 运行测试...
python build_cross_platform.py test
if errorlevel 1 (
    echo 测试失败
    pause
    exit /b 1
)
goto :end

:clean_build
echo 清理构建目录...
python build_cross_platform.py clean
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"
for /r %%i in (*.pyc) do del "%%i" 2>nul
for /r %%i in (*.pyo) do del "%%i" 2>nul
echo 清理完成
goto :end

:install_deps
echo 安装依赖...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
if errorlevel 1 (
    echo 依赖安装失败
    pause
    exit /b 1
)
echo 依赖安装完成
goto :end

:build_app
echo 开始构建应用程序...
python build_cross_platform.py build
if errorlevel 1 (
    echo 构建失败
    pause
    exit /b 1
)
echo 构建完成！
echo 可执行文件位于 dist 目录中
goto :end

:end
if "%COMMAND%"=="build" pause
endlocal