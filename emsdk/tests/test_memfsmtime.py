import subprocess
from . import common


def test_memfsmtime(tmpdir):
    with tmpdir.as_cwd():
        with open("main.c", "w") as f:
            f.write(
                r"""\
#include <assert.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>

void mysleep(int delta)
{
    time_t end = time(NULL) + delta;

    while (time(NULL)<end);
}

time_t getmtime(char *fname)
{
    struct stat buf;

    stat(fname, &buf);
    return buf.st_mtime;
}

void writefile(char *fname, char *content)
{
    int fd = open(fname, O_CREAT | O_TRUNC | O_WRONLY, 0777);

    write(fd, content, strlen(content));
    close(fd);
}

int main(int argc, char *argv[])
{
    char tmpdir[64] = "/tmp/tmpXXXXXXX";
    char fname[64];
    time_t t0, t1, t2, t3;

    mkdtemp(tmpdir);
    strcpy(fname, tmpdir);
    strcat(fname, "/foo.py");
    t0 = getmtime(tmpdir);
    mysleep(1);
    writefile(fname, "bar = 54\n");
    t1 = getmtime(tmpdir);
    t2 = getmtime(fname);
    assert(t1 > t0);
    assert(t1 == t2);
    mysleep(1);
    unlink(fname);
    t3 = getmtime(tmpdir);
    assert(t3 > t1);
}
"""
            )

        subprocess.run(
            [
                "emcc",
                "-s",
                "MAIN_MODULE=1",
                "main.c",
            ],
            check=True,
            env=common.env,
        )
        out = subprocess.run(
            ["node", "a.out.js"], capture_output=True, check=False, env=common.env
        )
        assert out.returncode == 0
