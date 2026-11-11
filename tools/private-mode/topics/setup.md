# Private mode — setup

Read when: private mode is chosen for a person, or a setup line reports private mode's tools missing.

Private mode masks pages on your own computer, so it needs a few free tools. A session installs them
when private mode is chosen: it asks what language the person's documents are in, and after your yes
runs `bash checks/setup-mac.sh private-mode <language>`. Apart from Python, which every instance needs,
skip them unless someone's records will be kept in private mode. To see what this machine has (the
check changes nothing, and names the install command for anything missing):

```bash
bash tools/private-mode/check-setup.sh
```

`checks/install-instance.sh` runs the same check and reports it in one line: complete, or what is
missing. On an install used only for care, nothing else needs setting up for the number unless its page
says so (README → *Which number*); a number not on the list is covered by hand.

| Tool | What it does | Install ([Homebrew](https://brew.sh)) |
|---|---|---|
| Python 3.9 or newer | every instance needs it, not only private mode: the installer, the checks and private mode's own tools run on it | `xcode-select --install` |
| poppler | turns each PDF page into an image | `brew install poppler` |
| tesseract, with its orientation data and English; for each person in private mode, the language of their documents and of their number's row in the number list | reads each page to find the identifier (a national ID number; `tools/private-mode/id-schemes.tsv` names which) | `brew install tesseract tesseract-lang` |
| ImageMagick | draws the black boxes | `brew install imagemagick` |

On a Mac, install Homebrew first: its installer also brings Apple's command line tools, and Python
with them.
