package main

import (
	"os"
	"os/exec"
	"path/filepath"
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

func main() {
	exePath, err := os.Executable()
	if err != nil {
		os.Stderr.WriteString("Failed to get executable path: " + err.Error() + "\n")
		os.Exit(1)
	}

	exePath, err = filepath.EvalSymlinks(exePath)
	if err != nil {
		os.Stderr.WriteString("Failed to resolve symlinks: " + err.Error() + "\n")
		os.Exit(1)
	}

	exeDir := filepath.Dir(exePath)
	batPath := filepath.Join(exeDir, "python.bat")

	args := []string{"/C", batPath}
	args = append(args, os.Args[1:]...)

	cmd := exec.Command("cmd.exe", args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	err = cmd.Run()
	if err != nil {
		if exitError, ok := err.(*exec.ExitError); ok {
			if status, ok := exitError.Sys().(syscall.WaitStatus); ok {
				os.Exit(status.ExitStatus())
			}
			os.Exit(1)
		}
		os.Stderr.WriteString("Failed to launch batch file: " + err.Error() + "\n")
		os.Exit(1)
	}

	os.Exit(0)
}
