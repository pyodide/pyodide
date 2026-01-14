#include <windows.h>
#include <stdio.h>

int main() {
    char exePath[MAX_PATH];
    char batPath[MAX_PATH];
    
    // 1. Get the absolute path of this .exe
    GetModuleFileNameA(NULL, exePath, MAX_PATH);

    // 2. Determine the path to python.bat
    strcpy(batPath, exePath);
    char *last_slash = strrchr(batPath, '\\');
    if (last_slash != NULL) {
        *(last_slash + 1) = '\0';
    }
    strcat(batPath, "python.bat");

    // 3. Get the original, raw command line string
    // Example: my_app.exe "hello world" --flag
    char *rawArgs = GetCommandLineA();

    // 4. Skip the first argument (our own exe name)
    // We handle cases where the exe name itself is quoted
    BOOL inQuotes = FALSE;
    char *p = rawArgs;
    while (*p != '\0') {
        if (*p == '\"') inQuotes = !inQuotes;
        else if (*p == ' ' && !inQuotes) break;
        p++;
    }
    // 'p' now points to the space after the exe name
    while (*p == ' ') p++; // Skip extra spaces

    // 5. Build the final command: "python.bat" [rawArgs]
    char fullCommand[32768]; // Max command line length
    sprintf(fullCommand, "\"%s\" %s", batPath, p);

    // 6. Execute using CreateProcess
    STARTUPINFOA si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    
    if (CreateProcessA(NULL, fullCommand, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD exitCode;
        GetExitCodeProcess(pi.hProcess, &exitCode);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return exitCode;
    } else {
        fprintf(stderr, "Failed to launch batch file. Error: %lu\n", GetLastError());
        return 1;
    }
}