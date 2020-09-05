package core

import (
	"bufio"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/pkg/sftp"
	"golang.org/x/crypto/ssh"
)

//SSHClient struct
type SSHClient struct {
	addr       string
	BufferSize int
	sshClient  *ssh.Client
	sftpClient *sftp.Client
	sshSession *ssh.Session
	output     io.Reader
	input      io.Writer
}

//NewSSHClient returns new Client struct
func NewSSHClient(addr string) SSHClient {
	return SSHClient{addr, 1024, nil, nil, nil, nil, nil}
}

//Login to remote server
func (c *SSHClient) Login(user, pass string) error {
	config := &ssh.ClientConfig{
		User: user,
		Auth: []ssh.AuthMethod{ssh.Password(pass)},
	}
	config.HostKeyCallback = ssh.InsecureIgnoreHostKey()

	var (
		sshClient *ssh.Client
		err       error
	)
	for {
		sshClient, err = ssh.Dial("tcp", c.addr, config)
		if err != nil {
			println("An error occurred while connecting to the server: \"" + err.Error() + "\" Retrying...")
			time.Sleep(time.Second * 3)
			continue
		}
		break
	}

	sshSession, err := sshClient.NewSession()
	if err != nil {
		return err
	}

	sftpClient, err := sftp.NewClient(sshClient)
	if err != nil {
		panic(err)
	}

	c.output, _ = sshSession.StdoutPipe()
	c.input, _ = sshSession.StdinPipe()
	c.sshSession = sshSession

	c.sshClient = sshClient
	c.sftpClient = sftpClient

	return nil
}

//Read data from remote server
func (c SSHClient) Read() ([]byte, error) {
	buf := make([]byte, c.BufferSize)
	n, err := c.output.Read(buf)
	if err != nil {
		return nil, err
	}

	return buf[:n], nil
}

//Write data to remote server
func (c SSHClient) Write(data []byte) error {
	_, err := c.input.Write(data)
	return err
}

//SFTPOpenFile opens a file on remote server
func (c SSHClient) SFTPOpenFile(path string) (*sftp.File, error) {
	file, err := c.sftpClient.Open(path)
	if err != nil {
		return nil, err
	}

	return file, nil
}

//DownloadRemote downloads a file from remote server
func (c SSHClient) DownloadRemote(remoteFilePath string) error {

	remoteFile, err := c.SFTPOpenFile(remoteFilePath)
	if err != nil {
		return err
	}
	defer remoteFile.Close()

	localFilePath := filepath.Base(remoteFilePath)

	os.Create(localFilePath)

	localFile, err := os.OpenFile(localFilePath, os.O_WRONLY, os.ModeAppend)
	if err != nil {
		return err
	}
	defer localFile.Close()

	buf := make([]byte, 262144)

	for {

		n, err := remoteFile.Read(buf)

		if _, err := localFile.Write(buf[:n]); err != nil {
			return err
		}

		if err != nil {
			if strings.HasSuffix(err.Error(), "EOF") {
				break
			}
			return err
		}
	}

	return nil
}

//UploadLocal uploads local file to the remote server
func (c SSHClient) UploadLocal(localFilePath string) error {

	if _, err := os.Stat(localFilePath); os.IsNotExist(err) {
		return errors.New("File does not exist")
	}

	localFile, err := os.Open(localFilePath)
	if err != nil {
		return err
	}
	defer localFile.Close()

	localFileInfo, err := os.Stat(localFilePath)
	if err != nil {
		return err
	}

	if localFileInfo.IsDir() {
		return errors.New("Not a file")
	}

	go func() {
		time.Sleep(time.Second * 3)
		c.Write([]byte(strconv.Itoa(int(localFileInfo.Size()))))
	}()

	remoteFile, err := c.SFTPOpenFile(localFilePath)
	if err != nil {
		return err
	}
	defer remoteFile.Close()

	r := bufio.NewReader(localFile)
	buf := make([]byte, 262144)

	for {

		n, err := r.Read(buf)

		if err != nil {
			if strings.HasSuffix(err.Error(), "EOF") {
				break
			}
			return err
		}

		if _, err := remoteFile.Write(buf[:n]); err != nil {
			return err
		}

	}

	return nil
}

//Listener listens for incoming data
func (c SSHClient) Listener(handleData func([]byte)) error {
	for {
		data, err := c.Read()
		if err != nil {
			if strings.HasSuffix(err.Error(), "EOF") {
				break
			}
		}
		go handleData(data)
	}

	return nil
}
