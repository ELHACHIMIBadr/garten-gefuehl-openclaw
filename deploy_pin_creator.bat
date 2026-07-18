@echo off
REM ============================================================
REM DEPLOY pin_creator.py v3.1 → VPS Hetzner
REM Lancer depuis : D:\Blogging\DE\openclaw\garten-gefuehl-openclaw\
REM ============================================================

echo [DEPLOY] Copie pin_creator.py vers le VPS...
scp -o StrictHostKeyChecking=no agents\directeur-artistique\pin_creator.py root@167.233.122.174:/root/garten-gefuehl-openclaw/agents/directeur-artistique/pin_creator.py

if %ERRORLEVEL% NEQ 0 (
    echo [DEPLOY] ERREUR : scp echoue. Verifie ta connexion SSH.
    pause
    exit /b 1
)

echo [DEPLOY] Fichier copie. Lancement test dry-run sur le VPS...
ssh -o StrictHostKeyChecking=no root@167.233.122.174 "cd /root/garten-gefuehl-openclaw && python3 agents/directeur-artistique/main.py --dry-run"

echo.
echo [DEPLOY] ============================================
echo [DEPLOY] Dry-run termine.
echo [DEPLOY] Pour un vrai test avec images :
echo [DEPLOY]   ssh root@167.233.122.174
echo [DEPLOY]   cd /root/garten-gefuehl-openclaw
echo [DEPLOY]   python3 agents/directeur-artistique/main.py
echo [DEPLOY] ============================================
pause
