//go:build darwin && arm64

package main

import _ "embed"

//go:embed assets/buzz-backend-hostinger-https-macos-arm64
var provider []byte

//go:embed provider-history-macos-arm64.json
var providerHistory []byte

const providerFilename = "buzz-backend-hostinger-https"
const desktopName = "Mac"

// First release has no approved predecessors. Unknown bytes remain rejected.
const requireProviderHistory = false
