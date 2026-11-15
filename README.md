# Medium Reader

A command-line tool to fetch Medium articles, save them locally, and open them in your browser to bypass paywalls.

## Features

- 📖 Fetch Medium articles from the command line
- 🔓 Member-only articles are read through freedium proxies (freedium.cfd, then freedium-mirror.cfd)
- 🖼️ Images, captions, code blocks and embeds kept, with image links that work from a local file
- 🎨 A clean reader view with reading settings (theme, font, size, spacing, width), time left,
  resume-where-you-stopped, a table of contents, click-to-zoom images and print styles
- 📚 A library page (`index.html`) listing everything you have saved, with search
- 💾 `--offline` downloads the images too, so articles read without a connection

## Requirements

- Python 3.10
- Conda (for environment management)
- Internet connection (for fetching articles)

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/abdukarimovhm/medium-reader
cd medium-reader
```

Or download and extract the ZIP file, then navigate to the directory.

### Step 2: Create Conda Environment

```bash
conda create -n medium-reader python=3.10 -y
conda activate medium-reader
```

**Note:** If you don't have conda installed, you can install it from [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution).

### Step 3: Install Dependencies

```bash
pip install requests beautifulsoup4 lxml
pip install -e .
```

### Step 4: Set Up Global Access

This step allows you to use `medium-read` from anywhere in your terminal without manually activating the conda environment.

```bash
# Create ~/bin directory if it doesn't exist
mkdir -p ~/bin

# Copy the wrapper script
cp medium-read-wrapper.sh ~/bin/medium-read
chmod +x ~/bin/medium-read

# Add ~/bin to PATH
# For zsh (default on macOS):
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For bash:
# echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
# source ~/.bashrc
```

**Important:** After adding to PATH, you may need to restart your terminal or run `source ~/.zshrc` (or `source ~/.bashrc` for bash) for the changes to take effect.

## Usage

### Basic Usage

After installation, you can use the `medium-read` command from anywhere in your terminal:

```bash
medium-read https://medium.com/@author/article-title
```

**Example:**
```bash
medium-read https://medium.com/python-in-plain-english/7-python-scripts-i-run-every-morning-before-writing-a-single-line-of-code-bacfc43c4739
```

The tool will automatically:
1. Activate the conda environment (via wrapper script)
2. Fetch the article from Medium
3. Parse and extract the content
4. Save it as an HTML file in `~/.medium-reader/articles/`
5. Open it in your default browser

**No need to activate conda manually!** The wrapper script handles it automatically.

### Command Options

| Option | What it does |
| --- | --- |
| `--no-open` | Save without opening the browser |
| `--offline` | Also download the article's images next to it, for reading without a connection |
| `--proxy` | Skip medium.com and go straight to the freedium proxies |
| `--library` | Open the library of saved articles |
| `--repair` | Re-render every saved article with the current reader (see below) |
| `-y`, `--yes` | Don't ask before fetching a URL that isn't on medium.com (custom publication domains) |
| `--debug` | Show every request, redirect and fallback |

### Reading

Each article page has an **Aa** button (top right) for theme (auto, light, sepia, dark), serif or
sans text, text size, line spacing and column width. Your choices apply to every saved article.
The top bar hides while you read down and comes back when you scroll up; it shows the time left.
Reopen an article and it offers to take you back to where you stopped. Click any image to
enlarge it.

### Your Library

Articles are saved to `~/.medium-reader/articles/` (set `MEDIUM_READER_DIR` to use another folder).
`index.html` in that folder lists them all, newest first, with a search box:

```bash
medium-read --library
```

Every article page links back to the library and to the original on Medium.

### Upgrading Articles Saved by Older Versions

Older versions saved member-only articles with image paths like `/img/medium/700/...`, which a
browser can't load from a local file, and sometimes garbled characters (`Donât`). Re-render
everything with:

```bash
medium-read --repair
```

The articles folder is copied to `~/.medium-reader/backup-<timestamp>/` first. Pages that never
held an article (an old save of a member-only preview, for example) are left untouched and listed;
fetch those again.

## How It Works

1. **Fetching**: The article is fetched from Medium first. If Medium marks it member-only
   (`isAccessibleForFree: false`) or blocks the request, each freedium proxy is tried in turn.
   If every proxy fails, the Medium preview is saved and you get a warning.
2. **Parsing**: The article text is taken from whichever page shape came back (Medium,
   freedium-mirror or the older freedium layout) and cleaned into plain HTML: framework classes,
   inline styles and reader UI removed, every image pointed at Medium's public image CDN
   (`miro.medium.com`), captions turned into real `<figcaption>`s.
3. **Generation**: The reader page is built with the title, author, date, read time and cover
   in one header.
4. **Storage**: Saving the same article again replaces the earlier copy; the library page is
   rebuilt after every save.

## Article Storage

- Filenames come from the article title.
- Re-fetching an article overwrites its file (matched by Medium's post id), so there are no
  `-1`, `-2` copies.
- With `--offline`, images go to `~/.medium-reader/articles/assets/<article>/`.

## Troubleshooting

### Common Issues

**Command not found: `medium-read`**
- Make sure you completed Step 4 of installation (setting up global access)
- Verify `~/bin` is in your PATH: `echo $PATH | grep bin`
- Try restarting your terminal or running `source ~/.zshrc`

**Connection errors**
- Make sure you have an active internet connection
- Check if the Medium URL is correct and accessible
- Some networks may block requests - try a different network

**Parse errors**
- Some Medium articles may use different structures
- If parsing fails, the tool will report a specific error message
- Try the article URL in a browser first to verify it's accessible

**Browser doesn't open**
- Use the `--no-open` flag and manually open the file from `~/.medium-reader/articles/`
- Check your system's default browser settings

**Truncated articles**
- Member-only articles are read through the freedium proxies. If both are down, only Medium's
  preview is saved and `medium-read` prints a warning. Try again later, or with `--debug` to see
  which proxy failed.

**Images missing in older saves**
- Run `medium-read --repair` (see above).

**Conda environment issues**
- Make sure conda is properly installed and in your PATH
- Try recreating the environment: `conda env remove -n medium-reader` then reinstall
- Check the wrapper script path in `~/bin/medium-read` matches your conda installation

## Updating

To update the tool to the latest version:

```bash
cd medium-reader
git pull  # if using git
conda activate medium-reader
pip install -e .
```

## Development

```bash
python -m unittest discover -s tests
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

MIT License

