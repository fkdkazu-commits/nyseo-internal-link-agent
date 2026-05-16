Dim objShell, objFSO, strDir
Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strDir
objShell.Run "cmd /c py -m streamlit run app.py --server.headless true 2>nul || python -m streamlit run app.py --server.headless true", 0, False
