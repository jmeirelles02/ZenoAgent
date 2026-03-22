Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")
caminho = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = caminho
objShell.Run "cmd /c " & Chr(34) & "iniciar.bat" & Chr(34), 0, False