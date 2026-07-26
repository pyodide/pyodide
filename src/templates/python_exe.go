package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "syscall"
)

/*
This program acts as a launcher for a Python batch file (python.bat).
It retrieves its own executable path, constructs the path to python.bat,
and forwards all command line arguments to it.

uv expects python.exe to exist to create a virtual environment, while we have
most of the logics in python.bat. This launcher is a thin wrapper around
python.bat to satisfy uv's requirement.
*/

// escapeArg quotes an argument for the Windows command line parser. cmd.exe
// reads the line on the way to python.bat, so quote unconditionally to keep it
// from acting on & | < > ( ) ^.
func escapeArg(s string) string {
    var quoted strings.Builder

    quoted.WriteByte('"')
    backslashes := 0
    for i := 0; i < len(s); i++ {
        switch c := s[i]; c {
        case '\\':
            backslashes++
        case '"':
            // Double the backslashes in front so they stay literal.
            for ; backslashes > 0; backslashes-- {
                quoted.WriteString(`\\`)
            }
            quoted.WriteString(`\"`)
        default:
            for ; backslashes > 0; backslashes-- {
                quoted.WriteByte('\\')
            }
            quoted.WriteByte(c)
        }
    }
    // Trailing backslashes would escape the closing quote.
    for ; backslashes > 0; backslashes-- {
        quoted.WriteString(`\\`)
    }
    quoted.WriteByte('"')

    return quoted.String()
}

func main() {
    // Get the path to the currently running executable (python.exe)
    exePath, err := os.Executable()
    if err != nil {
        os.Stderr.WriteString("Failed to get executable path: " + err.Error() + "\n")
        os.Exit(1)
    }

    // Resolve any symlinks to get the actual location of the executable
    // This ensures we find python.bat in the correct directory
    exePath, err = filepath.EvalSymlinks(exePath)
    if err != nil {
        os.Stderr.WriteString("Failed to resolve symlinks: " + err.Error() + "\n")
        os.Exit(1)
    }

    // Extract the directory containing python.exe and construct the path to python.bat
    exeDir := filepath.Dir(exePath)
    batPath := filepath.Join(exeDir, "python.bat")

    // Rebuild the command line for python.bat out of our own arguments
    parts := make([]string, 0, len(os.Args))
    parts = append(parts, escapeArg(batPath))
    for _, arg := range os.Args[1:] {
        parts = append(parts, escapeArg(arg))
    }

    // Call cmd.exe rather than letting CreateProcess dispatch the .bat itself.
    // cmd drops the outer pair of quotes unless the line holds exactly two, so
    // one quoted argument was enough to unquote batPath and split it at a
    // space. /s makes cmd strip only the pair added here.
    comSpec := os.Getenv("ComSpec")
    if comSpec == "" {
        comSpec = "cmd.exe"
    }

    cmd := exec.Command(comSpec)
    cmd.SysProcAttr = &syscall.SysProcAttr{
        CmdLine: escapeArg(comSpec) + ` /s /c "` + strings.Join(parts, " ") + `"`,
    }

    // Wire up stdin, stdout, and stderr so the batch file can interact with the terminal
    cmd.Stdin = os.Stdin
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    // Execute the command and wait for it to complete
    err = cmd.Run()
    if err != nil {
        // If the batch file executed but returned a non-zero exit code,
        // propagate that exit code to our caller
        if exitError, ok := err.(*exec.ExitError); ok {
            if status, ok := exitError.Sys().(syscall.WaitStatus); ok {
                os.Exit(status.ExitStatus())
            }
            os.Exit(1)
        }
        // If we couldn't even launch the batch file, report the error
        os.Stderr.WriteString("Failed to launch batch file: " + err.Error() + "\n")
        os.Exit(1)
    }

    os.Exit(0)
}
