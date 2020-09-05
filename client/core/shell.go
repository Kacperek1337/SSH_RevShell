package core

import (
	"bufio"
	"os"
	"os/exec"
	"runtime"
	"time"
)

var (
	platform = runtime.GOOS
)

//Shell struct
type Shell struct {
	stop      bool
	isRunning bool
}

//NewShell returns new Shell struct
func NewShell() Shell {
	return Shell{false, false}
}

//Exec executes shell command
func (sh *Shell) Exec(cmdInp string, handleOutput func([]byte) error) error {
	for sh.stop {
	}

	sh.isRunning = true

	defer func() {
		sh.isRunning = false
	}()

	var cmd *exec.Cmd
	if platform == "windows" {
		cmd = exec.Command("cmd.exe", "/c", cmdInp)
	} else {
		cmd = exec.Command(os.Getenv("SHELL"), "-c", cmdInp)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	outScanner := bufio.NewScanner(stdout)
	for outScanner.Scan() {
		if sh.stop {
			sh.stop = false
			return nil
		}
		time.Sleep(time.Millisecond)
		if err := handleOutput(outScanner.Bytes()); err != nil {
			return err
		}
	}

	return outScanner.Err()
}

//IsRunning checks whether command is being currently executed
func (sh Shell) IsRunning() bool {
	return sh.isRunning
}

//Stop currently executed command
func (sh *Shell) Stop() {
	if sh.IsRunning() {
		sh.stop = true
	}
}
