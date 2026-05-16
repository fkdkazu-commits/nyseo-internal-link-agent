Dim objShell, objFSO, strDir
Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strDir
' --server.headless true でブラウザ自動起動を抑制（スタートアップ起動時用）
objShell.Run "cmd /c streamlit run app.py --server.headless true", 0, False
