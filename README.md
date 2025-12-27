# Medium Reader

A command-line tool to fetch Medium articles, save them locally, and open them in your browser to bypass paywalls.

## Features

- 📖 Fetch Medium articles via command line
- 💾 Save articles as clean, readable HTML files
- 🌐 Automatically open articles in your default browser
- 🔓 Bypass Medium's paywall restrictions
- 📚 Store articles locally for offline reading
- 🎨 Clean, readable formatting with proper styling

## Requirements

- Python 3.10
- Conda (for environment management)
- Internet connection (for fetching articles)

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
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

- `--no-open`: Save the article without opening it in the browser
  ```bash
  medium-read https://medium.com/@author/article-title --no-open
  ```

- `--help`: Show help message
  ```bash
  medium-read --help
  ```

### Viewing Saved Articles

All articles are saved to `~/.medium-reader/articles/` (or `/Users/your-username/.medium-reader/articles/` on macOS).

You can:
- Open them directly in your browser
- Access them from the command line:
  ```bash
  open ~/.medium-reader/articles/article-name.html  # macOS
  xdg-open ~/.medium-reader/articles/article-name.html  # Linux
  ```

## How It Works

1. **Fetching**: The tool uses browser-like headers to fetch the article HTML, avoiding bot detection
2. **Parsing**: It extracts article content from Medium's JSON-LD structured data and HTML
3. **Generation**: Creates a clean, readable HTML file with proper styling
4. **Storage**: Saves articles to `~/.medium-reader/articles/` with sanitized filenames
5. **Display**: Opens the saved HTML file in your default browser

## Article Storage

### Storage Location

Articles are saved to `~/.medium-reader/articles/` with filenames based on the article title. 

**Full path examples:**
- macOS/Linux: `/Users/your-username/.medium-reader/articles/`
- The directory is created automatically on first use

### File Naming

- Filenames are based on the article title (sanitized for filesystem compatibility)
- If a file with the same name already exists, a number suffix is added (e.g., `article-title-1.html`)
- Files are saved as `.html` files that can be opened in any web browser

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
- Some Medium articles are "Member-only" stories that are behind a paywall
- Medium only serves a preview of these articles, so the full content may not be available
- This is a limitation of Medium's paywall system, not the tool itself
- Free/public articles should work completely

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

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

MIT License

