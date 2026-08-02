# Paper Evidence Search updates

This public repository is the deliberately unlisted distribution channel for the Paper Evidence Search Firefox extension. It contains Mozilla-signed XPI inputs, immutable GitHub Releases, and the Firefox update manifest deployed through GitHub Pages.

- Update manifest: https://c5t8fbt-wy.github.io/paper-evidence-search-updates/updates.json
- Signed releases: https://github.com/C5T8fBt-WY/paper-evidence-search-updates/releases

The application source and research-paper index are not published here. The private source repository signs a version through Mozilla and pushes one `incoming/<version>` directory plus a matching `firefox-v<version>` tag using a repository-scoped write deploy key. This repository then verifies the hash, creates the Release, confirms the anonymous download, and deploys `updates.json` last.

The channel is unlisted, not access-controlled: anyone with these URLs can download the signed extension.
