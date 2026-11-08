//go:build !darwin

package main

import _ "embed"

//go:embed assets/buzz-backend-hostinger-https.exe
var provider []byte

//go:embed provider-history.json
var providerHistory []byte

const providerFilename = "buzz-backend-hostinger-https.exe"
const desktopName = "Windows"
const requireProviderHistory = true
