//go:build !windows

package main

import (
	"os"
	"syscall"
)

func lockInstall(path string) (func(), error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, err
	}
	if err = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		f.Close()
		return nil, err
	}
	return func() { f.Close() }, nil
}
func commitFile(source, target string, replace bool) error {
	if replace {
		return os.Rename(source, target)
	}
	// No-clobber install: a concurrently created target is never overwritten.
	return os.Link(source, target)
}
