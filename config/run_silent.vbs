Option Explicit

' Launch a PowerShell wrapper with no console window.
' Scheduled tasks should execute: wscript.exe //B //nologo run_silent.vbs <script> [args]

If WScript.Arguments.Count < 1 Then
    WScript.Quit 1
End If

Dim shell, command, i, arg
Set shell = CreateObject("WScript.Shell")

command = "powershell.exe -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File " & Quote(WScript.Arguments.Item(0))
For i = 1 To WScript.Arguments.Count - 1
    arg = WScript.Arguments.Item(i)
    If Left(arg, 1) = "-" Then
        command = command & " " & arg
    Else
        command = command & " " & Quote(arg)
    End If
Next

shell.Run command, 0, True
WScript.Quit 0

Function Quote(text)
    Quote = """" & Replace(text, """", """""") & """"
End Function
