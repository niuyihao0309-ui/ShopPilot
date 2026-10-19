@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================================
REM  Ecommerce Operation Assistant - 一键启动
REM
REM  双击本文件即可, 依次完成:
REM    [0/4] 检查 Docker, 没运行就自动拉起 Docker Desktop 并等引擎就绪
REM    [1/4] docker compose up -d (MySQL / Redis / Postgres) 并等 healthcheck
REM    [2/4] 启动后端 FastAPI (uvicorn --reload)
REM    [3/4] 启动前端 Next.js (npm run dev)
REM    [4/4] 自动打开浏览器
REM
REM  可选参数:
REM    start.bat nobrowser   不自动打开浏览器
REM    start.bat stop        停止全部 (等同 stop.bat)
REM
REM  端口唯一准绳 = 根目录 .env 的 API_PORT / WEB_PORT
REM ============================================================================

set "HAVE_CURL=1"
where curl >nul 2>&1 || set "HAVE_CURL=0"
set "DOCKER_OK=0"
set "NO_BROWSER="

REM ---- 端口: 从根目录 .env 读取 ----
set "API_PORT="
set "WEB_PORT="
for /f "tokens=2 delims==" %%V in ('findstr /b /c:"API_PORT=" "%~dp0.env" 2^>nul') do set "API_PORT=%%V"
for /f "tokens=2 delims==" %%V in ('findstr /b /c:"WEB_PORT=" "%~dp0.env" 2^>nul') do set "WEB_PORT=%%V"
if not defined API_PORT set "API_PORT=8000"
if not defined WEB_PORT set "WEB_PORT=3000"

if /i "%~1"=="stop"      goto :stop
if /i "%~1"=="nobrowser" set "NO_BROWSER=1"
if /i "%~2"=="nobrowser" set "NO_BROWSER=1"

echo ============================================================
echo    Ecommerce Operation Assistant  -  一键启动
echo ============================================================
echo    后端端口 !API_PORT!    前端端口 !WEB_PORT!
echo.

call :ensure_docker
call :sync_envlocal
call :start_infra
call :start_api
call :wait_api
call :start_web
call :wait_web
call :open_browser

echo.
echo ============================================================
echo    启动完成
echo      前端  http://localhost:!WEB_PORT!
echo      后端  http://127.0.0.1:!API_PORT!/docs
echo.
echo    停止:   双击 stop.bat  或  start.bat stop
echo    后端/前端各在新窗口运行, 关掉窗口即停
echo ============================================================
echo.
pause
exit /b 0

REM ==================== 停止 ====================
:stop
echo 正在停止 后端(!API_PORT!) / 前端(!WEB_PORT!) ...
REM 说明: uv 建的 .venv\Scripts\python.exe 只是转发壳, 真实 worker 在 uv 自己的 python 下,
REM       且 --reload 会另起 worker, 因此按命令行特征整组清理, 而不是只杀 netstat 里的 PID。
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ( $_.CommandLine -like '*set WBDEV=1*' -or ( $_.Name -eq 'python.exe' -and $_.CommandLine -like '*uvicorn app.main:app*' -and $_.CommandLine -like '*--port !API_PORT!*' ) -or ( $_.Name -eq 'node.exe' -and $_.CommandLine -like '*%~dp0web*' ) ) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
REM 兜底: 再按端口清一次
call :killport !API_PORT!
call :killport !WEB_PORT!
REM 停掉数据库容器(数据保留在 volume)
where docker >nul 2>&1
if errorlevel 1 goto :stop_done
docker info >nul 2>&1
if errorlevel 1 goto :stop_done
echo 正在停止数据库容器 ...
docker compose stop
:stop_done
echo 已停止。
pause
exit /b 0

REM ==================== 子过程 ====================

REM ---- [0/4] 确保 Docker 引擎可用 ----
:ensure_docker
set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
where docker >nul 2>&1
if errorlevel 1 (
    echo [0/4] 未检测到 docker 命令, 跳过数据库。
    echo       如需数据库, 请先安装 Docker Desktop。
    exit /b 0
)
docker info >nul 2>&1
if not errorlevel 1 (
    echo [0/4] Docker 引擎已在运行。
    set "DOCKER_OK=1"
    exit /b 0
)
echo [0/4] Docker 未运行, 正在启动 Docker Desktop ...
set "DD="
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DD=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if not defined DD if exist "%LocalAppData%\Docker\Docker Desktop.exe" set "DD=%LocalAppData%\Docker\Docker Desktop.exe"
if not defined DD (
    echo       找不到 Docker Desktop.exe, 请手动打开 Docker Desktop 后重试。
    exit /b 0
)
start "" "%DD%"
echo       等待 Docker 引擎就绪（首次启动 1-3 分钟, 请耐心等） ...
set /a _D=0
:dd_loop
set /a _D+=3
if !_D! GTR 300 (
    echo       等待超时 300s, 跳过数据库, 继续启动后端/前端。
    exit /b 0
)
docker info >nul 2>&1
if !errorlevel! NEQ 0 (
    ping -n 4 127.0.0.1 >nul
    goto :dd_loop
)
echo       Docker 引擎已就绪（耗时约 !_D! 秒）。
set "DOCKER_OK=1"
exit /b 0

REM ---- 同步 web\.env.local 里的 API 地址 ----
:sync_envlocal
set "_EXPECT=NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:!API_PORT!"
set "_F=%~dp0web\.env.local"
set "_CUR="
if not exist "!_F!" goto :sync_write
findstr /x /c:"!_EXPECT!" "!_F!" >nul 2>&1
if not errorlevel 1 exit /b 0
for /f "tokens=* delims=" %%L in ('findstr /b /c:"NEXT_PUBLIC_API_BASE_URL=" "!_F!" 2^>nul') do set "_CUR=%%L"
echo [提示] web\.env.local 与 .env 的 API_PORT 不一致, 已自动同步:
echo        旧: !_CUR!
echo        新: !_EXPECT!
:sync_write
set "_TMP=%~dp0web\.env.local.tmp"
findstr /v /b /c:"NEXT_PUBLIC_API_BASE_URL=" "!_F!" > "!_TMP!" 2>nul
>> "!_TMP!" echo !_EXPECT!
move /y "!_TMP!" "!_F!" >nul
exit /b 0

REM ---- [1/4] 数据库容器 ----
:start_infra
if "%DOCKER_OK%"=="0" (
    echo [1/4] 跳过数据库（Docker 引擎不可用）。
    exit /b 0
)
echo [1/4] 启动数据库容器: MySQL / Redis / Postgres ...
docker compose up -d
echo       等待容器 healthcheck ...
set /a _W=0
:infra_wait
set /a _W+=3
if !_W! GTR 150 (
    echo       等待超时 150s, 继续启动后端, 可能暂时连不上数据库。
    exit /b 0
)
docker compose ps 2>nul | findstr /i "starting" >nul
if !errorlevel! EQU 0 (
    ping -n 4 127.0.0.1 >nul
    goto :infra_wait
)
echo       数据库就绪。
exit /b 0

REM ---- [2/4] 后端 ----
:start_api
call :portbusy !API_PORT!
if not errorlevel 1 (
    echo [2/4] 端口 !API_PORT! 已被占用, 跳过后端启动。
    echo       若要重启后端, 请先运行 stop.bat。
    exit /b 0
)
if not exist "%~dp0api\.venv\Scripts\python.exe" (
    echo [2/4] 找不到后端虚拟环境 api\.venv
    echo       请先在 api 目录执行: uv sync
    exit /b 1
)
echo [2/4] 启动后端 API, 端口 !API_PORT! ...
start "API - uvicorn :!API_PORT!" /D "%~dp0api" cmd /k "set WBDEV=1& .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port !API_PORT!"
exit /b 0

:wait_api
if "%HAVE_CURL%"=="0" exit /b 0
set /a _H=0
:http_loop
set /a _H+=2
if !_H! GTR 60 (
    echo       后端 60s 内未响应, 请看弹出的 API 窗口里的报错。
    exit /b 1
)
curl -s -f --noproxy "*" -o nul http://127.0.0.1:!API_PORT!/health >nul 2>&1
if !errorlevel! NEQ 0 (
    ping -n 3 127.0.0.1 >nul
    goto :http_loop
)
echo       后端已就绪 ^> http://127.0.0.1:!API_PORT!/docs
exit /b 0

REM ---- [3/4] 前端 ----
:start_web
call :portbusy !WEB_PORT!
if not errorlevel 1 (
    echo [3/4] 端口 !WEB_PORT! 已被占用, 跳过前端启动。
    exit /b 0
)
if not exist "%~dp0web\node_modules" (
    echo [3/4] 未找到 web\node_modules, 先执行 npm install ...
    pushd "%~dp0web"
    call npm install
    popd
)
echo [3/4] 启动前端 Web, 端口 !WEB_PORT! ...
start "WEB - next dev :!WEB_PORT!" /D "%~dp0web" cmd /k "set WBDEV=1& npm run dev"
exit /b 0

:wait_web
if "%HAVE_CURL%"=="0" exit /b 0
echo       等待前端就绪 ...
set /a _N=0
:web_loop
set /a _N+=2
if !_N! GTR 60 (
    echo       前端 60s 内未响应, 仍会打开浏览器; 若白屏请看前端窗口里的报错。
    exit /b 1
)
curl -s --noproxy "*" -o nul --max-time 5 http://127.0.0.1:!WEB_PORT!/ >nul 2>&1
if !errorlevel! NEQ 0 (
    ping -n 3 127.0.0.1 >nul
    goto :web_loop
)
echo       前端已就绪。
exit /b 0

REM ---- [4/4] 浏览器 ----
:open_browser
if defined NO_BROWSER (
    echo [4/4] 已跳过自动打开浏览器（nobrowser）。
    exit /b 0
)
echo [4/4] 正在打开浏览器: http://localhost:!WEB_PORT!
start "" "http://localhost:!WEB_PORT!"
exit /b 0

REM ---- 工具 ----
:portbusy
set "_Q=%~1"
netstat -ano | findstr ":%_Q% " | findstr "LISTENING" >nul
exit /b %errorlevel%

:killport
set "_P=%~1"
for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%_P% " ^| findstr "LISTENING"') do taskkill /PID %%A /T /F >nul 2>&1
exit /b 0
