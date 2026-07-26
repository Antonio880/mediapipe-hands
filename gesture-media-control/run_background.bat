@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  Gesture Media Control — Inicializador para Windows
REM  Roda o script em background (sem janela de terminal visível)
REM  Para encerrar: abra o Gerenciador de Tarefas e finalize "pythonw.exe"
REM ──────────────────────────────────────────────────────────────────────────

echo Instalando dependencias (caso necessario)...
pip install -r requirements.txt --quiet

echo Iniciando Gesture Media Control em background...
start "" /B pythonw main.py

echo Rodando! Para encerrar, feche o processo "pythonw.exe" no Gerenciador de Tarefas.
