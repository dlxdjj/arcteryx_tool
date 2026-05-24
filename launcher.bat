@echo off
chcp 65001 >nul
title Arbitrage Tool
cd /d "%~dp0"

:MENU
cls
echo ================================================
echo   Multi-Brand x Mendao  Arbitrage Tool
echo ================================================
echo.
echo   [1] Auto Query (Mendao Miniprogram)
echo   [2] Calculate Profit (use cached data)
echo   [3] Open Dashboard (Browser)
echo   [4] Show Profit Ranking (Console)
echo   [5] Manual Add SKU Price
echo   [6] Start SOCKS5 Server
echo   [7] Clear Cache (Start Fresh)
echo   [8] Exit
echo.
set /p choice=Choose (1-8): 

if "%choice%"=="1" goto MENDAO
if "%choice%"=="2" goto AUTO
if "%choice%"=="3" goto DASHBOARD
if "%choice%"=="4" goto RESULTS
if "%choice%"=="5" goto MANUAL
if "%choice%"=="6" goto SOCKS
if "%choice%"=="7" goto CLEAR
if "%choice%"=="8" exit
goto MENU

:MENDAO
cls
echo === Auto Query via Mendao Miniprogram ===
echo.
echo Before starting:
echo   1. Open Fiddler - start capturing
echo   2. Open WeChat - Mendao miniprogram search page
echo   3. Confirm Fiddler CustomRules.js has spu-index save script
echo.
pause
python auto_click_mendao.py
echo.
pause
goto MENU

:AUTO
cls
echo === Calculate Profit ===
echo.
python rebuild_results.py
echo.
pause
goto MENU

:DASHBOARD
cls
echo === Opening Dashboard ===
echo.
python open_dashboard.py
goto MENU

:RESULTS
cls
echo === Profit Ranking ===
echo.
python -c "import json,os; d=json.load(open('results.json',encoding='utf-8')) if os.path.exists('results.json') else {}; rs=sorted([r for r in d.get('results',[]) if r.get('profit') is not None],key=lambda x:x['profit'],reverse=True); print('Updated:',d.get('timestamp','-'),'  Matched:',str(d.get('matched',0))+'/'+str(d.get('total',0))); print(); [print(r.get('sku','-')[:20].ljust(20), str(r.get('buy_display','-')).rjust(8), ('Y'+str(round(r.get('dewu_price',0)))).rjust(8), ('+Y'+str(r.get('profit',0)) if r.get('profit',0)>=0 else 'Y'+str(r.get('profit',0))).rjust(10), str(r.get('rate',0))+'%', r.get('name',r.get('dewu_title','-'))[:25]) for r in rs[:25]]" 2>nul || echo No results yet. Run option 2 first.
echo.
pause
goto MENU

:MANUAL
cls
echo === Manual Add SKU Price ===
echo.
python manual_add.py
echo.
pause
goto MENU

:SOCKS
cls
echo === SOCKS5 Server ===
echo.
echo Configure SocksDroid:
echo   Server IP:   192.168.1.3
echo   Server Port: 7890
echo.
echo Press Ctrl+C to stop
echo.
python socks5_server.py
echo.
pause
goto MENU

:CLEAR
cls
echo === Clear Cache - Start Fresh ===
echo.
echo This will delete all cached data:
echo   mendao_db.json     - all price data
echo   sku_spu_map.json   - SKU mappings
echo   dewu_prices.json   - price cache
echo   missing_skus.json  - missing SKU list
echo   results.json       - profit results
echo   fiddler_latest.txt - last capture
echo.
set /p confirm=Type YES to confirm: 
if /i not "%confirm%"=="YES" goto MENU
echo.
python -c "import json,os; [open(f,'w',encoding='utf-8').write(e) for f,e in [('mendao_db.json','{}'),('sku_spu_map.json','{}'),('dewu_prices.json','[]'),('missing_skus.json','[]'),('results.json','{}')] if True]; [os.remove(f) for f in ['fiddler_latest.txt'] if os.path.exists(f)]; print('All cache cleared! Ready to start fresh.')"
echo.
pause
goto MENU
