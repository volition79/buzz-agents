package main

import (
	"os"
	"syscall"
	"unsafe"
)

var kernel32 = syscall.NewLazyDLL("kernel32.dll")
var lockFileEx = kernel32.NewProc("LockFileEx")
var moveFileEx = kernel32.NewProc("MoveFileExW")

func lockInstall(path string) (func(), error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, err
	}
	overlap := new(syscall.Overlapped)
	ok, _, callErr := lockFileEx.Call(f.Fd(), 3, 0, 1, 0, uintptr(unsafe.Pointer(overlap)))
	if ok == 0 {
		f.Close()
		return nil, callErr
	}
	return func() { f.Close() }, nil
}
func commitFile(source, target string, replace bool) error {
	from, err := syscall.UTF16PtrFromString(source)
	if err != nil {
		return err
	}
	to, err := syscall.UTF16PtrFromString(target)
	if err != nil {
		return err
	}
	flags := uintptr(8) // MOVEFILE_WRITE_THROUGH, same directory/volume.
	if replace {
		flags |= 1
	} // MOVEFILE_REPLACE_EXISTING only after explicit reconnect.
	ok, _, callErr := moveFileEx.Call(uintptr(unsafe.Pointer(from)), uintptr(unsafe.Pointer(to)), flags)
	if ok == 0 {
		return callErr
	}
	return nil
}
