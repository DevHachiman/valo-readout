
Option Explicit

Dim shell, fso, here, pyw, check, msg
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = here

pyw = ""
On Error Resume Next
Dim exec, out
Set exec = shell.Exec("cmd /c python -c ""import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))""")
out = Trim(exec.StdOut.ReadAll())
On Error GoTo 0
If out <> "" And fso.FileExists(out) Then pyw = out

If pyw = "" Then
  If fso.FileExists(shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & _
     "\Programs\Python\Python311\pythonw.exe") Then
    pyw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & _
          "\Programs\Python\Python311\pythonw.exe"
  End If
End If

If pyw = "" Then
  MsgBox "Python non risulta installato, oppure pythonw.exe non si trova." & vbCrLf & vbCrLf & _
         "Prendilo da https://www.python.org/downloads/ e lascia spuntato" & vbCrLf & _
         "'Add Python to PATH' durante l'installazione." & vbCrLf & vbCrLf & _
         "In alternativa avvia valo-readout.bat, che mostra i dettagli.", _
         vbExclamation, "valo-readout"
  WScript.Quit 1
End If

check = shell.Run("cmd /c """"" & pyw & """ -c ""import aiohttp""""", 0, True)
If check <> 0 Then
  msg = MsgBox("Manca la libreria aiohttp." & vbCrLf & vbCrLf & _
               "Vuoi aprire valo-readout.bat per installarla?" & vbCrLf & _
               "Serve solo la prima volta.", vbYesNo + vbQuestion, "valo-readout")
  If msg = vbYes Then shell.Run """" & here & "\valo-readout.bat""", 1, False
  WScript.Quit 1
End If

shell.Run """" & pyw & """ bridge.py", 0, False
