; AutoHotkey скрипт для вставки тексту з буфера обміну
; Використання: paste_text.ahk "текст для вставки"
; При компіляції: Ahk2Exe.exe /in paste_text.ahk /out paste_text.exe

#NoEnv
#SingleInstance Force
SendMode Input
SetWorkingDir %A_ScriptDir%

; Отримати текст з аргументів командного рядка
if (A_Args.Length() > 0)
{
    text := A_Args[1]
    ; Скопіювати текст в буфер обміну
    clipboard := text
    
    ; Зачекати трохи
    Sleep 100
    
    ; Вставити через Ctrl+V
    Send ^v
    
    ; Зачекати завершення вставки
    Sleep 200
}
else
{
    ; Якщо немає аргументів - просто вставити з буфера
    Send ^v
}

ExitApp
