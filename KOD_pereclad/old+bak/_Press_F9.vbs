Set WshShell = WScript.CreateObject("WScript.Shell")
WScript.Sleep 500 ' Затримка 0.5 секунди (може бути корисно, щоб дати час активуватися потрібному вікну)
WshShell.SendKeys "{F9}"
Set WshShell = Nothing