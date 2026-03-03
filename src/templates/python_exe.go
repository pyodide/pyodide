package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "syscall"
	"unsafe"
)

/*
This program acts as a launcher for a Python batch file (python.bat).
It retrieves its own executable path, constructs the path to python.bat,
and forwards all command line arguments to it.

uv expects python.exe to exist to create a virtual environment, while we have
most of the logics in python.bat. This launcher is a thin wrapper around
python.bat to satisfy uv's requirement.
*/

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

    // Build the command line string manually to preserve quoting
    // We need to reconstruct the original command line as closely as possible
    var cmdLine strings.Builder
    cmdLine.WriteString(syscall.EscapeArg(batPath))

    // Get the original command line and extract everything after the first argument (python.exe)
    // This preserves the exact quoting from the original invocation
	// [1 << 29] is used to create a sufficiently large array to hold the command line
    cmdLinePtr := syscall.GetCommandLine()
    cmdLineStr := syscall.UTF16ToString((*[1 << 29]uint16)(unsafe.Pointer(cmdLinePtr))[:])

    // Find where the arguments start (after python.exe and its quotes/spaces)
    // Skip the first argument (python.exe itself)
    inQuote := false
    argCount := 0
    argStart := -1

    for i, c := range cmdLineStr {
        if c == '"' {
            inQuote = !inQuote
        } else if c == ' ' && !inQuote {
            if argStart != -1 {
                argCount++
                if argCount >= 1 {
                    // Found the start of arguments after python.exe
                    argStart = i + 1
                    break
                }
                argStart = -1
            }
        } else if argStart == -1 {
            argStart = i
        }
    }

    // Append the original arguments if any exist
    if argStart > 0 && argStart < len(cmdLineStr) {
        cmdLine.WriteString(" ")
        cmdLine.WriteString(cmdLineStr[argStart:])
    }

    // Execute the batch file with the reconstructed command line
    cmd := exec.Command(batPath)
    cmd.SysProcAttr = &syscall.SysProcAttr{
        CmdLine: cmdLine.String(),
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
