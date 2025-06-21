# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chompy is a modern CHM (Compiled HTML Help) file viewer and HTTP server with a professional web interface. Originally designed for Symbian/PyS60 devices, it has been completely modernized to provide a sidebar-based documentation viewer similar to modern documentation sites. The project provides both command-line tools and a feature-rich web server for viewing CHM files.

## Architecture

### Core Components

- **chm_server.py**: Modern HTTP server with sidebar-based web interface
- **chm_viewer.py**: Command-line tool for viewing and extracting CHM content
- **server.py**: Core HTTP server implementation with advanced features:
  - Sidebar table of contents navigation
  - Current page highlighting
  - Collapsible folder structure
  - Professional CSS styling
  - JavaScript-powered content loading
- **pychmlib/**: CHM file parsing library (Python 3 compatible)
  - `chm.py`: Core CHM file format parser with LZX decompression support
  - `lzx.py`: LZX decompression algorithm implementation (fixed for Python 3)
- **hhc.py**: HTML Help Contents (HHC) file parser for table of contents
- **HTMLParser.py**: Modified HTML parser (fixed regex warnings)
- **markupbase.py**: Base classes for markup parsing

### Legacy Components (Symbian-specific, kept for reference)
- **chom.py**: Original Symbian GUI application (requires appuifw, e32, e32dbm)
- **chm_filebrowser.py**: Original Symbian file browser component

### Key Features

#### Web Interface Features
- **📋 Sidebar Navigation**: Fixed 300px sidebar with complete table of contents
- **🎯 Current Page Highlighting**: Blue highlighting shows active page
- **📁 Collapsible Folders**: Click folder names to expand/collapse sections (▼/▶ arrows)
- **💻 Professional Layout**: Modern CSS with flexbox layout and proper typography
- **⚡ JavaScript Content Loading**: Seamless iframe-based content display
- **🖱️ Interactive Elements**: Hover effects and visual feedback
- **📱 Responsive Design**: Works well on different screen sizes

#### Core Functionality
- **CHM Format Support**: Full CHM file parsing including compressed content (LZX algorithm)
- **Python 3 Compatible**: Fixed byte/string handling and modernized syntax
- **Cross-platform**: Works on any system with Python 3
- **Multiple File Types**: Proper MIME type handling for HTML, CSS, images, JavaScript, PDF
- **HEAD Request Support**: Proper HTTP compliance

## Development Commands

### CHM Server (Primary Interface)
```bash
# Serve a CHM file via HTTP with sidebar interface
python3 chm_server.py path/to/file.chm

# Serve with custom host/port
python3 chm_server.py path/to/file.chm --host 0.0.0.0 --port 8080

# Auto-shutdown after timeout
python3 chm_server.py path/to/file.chm --timeout 30

# Then open http://127.0.0.1:8081/ in your browser
```

### CHM Viewer/Extractor (Command Line)
```bash
# List table of contents
python3 chm_viewer.py path/to/file.chm --list

# Extract specific file
python3 chm_viewer.py path/to/file.chm --extract "path/in/chm.htm"

# Extract to output file
python3 chm_viewer.py path/to/file.chm --extract "path/in/chm.htm" --output extracted.htm
```

### Testing
```bash
# Run unit tests
python3 -m unittest discover pychmlib/tests/ -v

# Test individual modules
python3 -m unittest pychmlib.tests.test_chm
python3 -m unittest pychmlib.tests.test_lzx
```

### Syntax Checking
```bash
# Check Python syntax across all files
find . -name "*.py" -exec python3 -m py_compile {} \;
```

## Web Interface Usage

1. **Start the Server**: `python3 chm_server.py your-file.chm`
2. **Open Browser**: Navigate to `http://127.0.0.1:8081/`
3. **Navigate Content**: Click items in the left sidebar to view pages
4. **Organize View**: Click folder names to expand/collapse sections
5. **Track Location**: Current page is highlighted in blue
6. **Auto-expand**: Parent folders automatically expand when child pages are selected

## Bug Fixes Applied

### Python 3 Compatibility
- Fixed Python 3 compatibility issues in LZX decompression (`pychmlib/lzx.py`)
- Fixed byte/string handling throughout CHM parsing library
- Fixed regex escape sequence warning in `HTMLParser.py`
- Fixed relative import issues in test files

### Server Improvements
- Updated HTTP server to use modern `http.server` instead of raw sockets
- Fixed HHC parser to handle malformed content gracefully
- Added HEAD request support for proper HTTP compliance
- Expanded MIME type detection for various file formats

### UI/UX Enhancements
- Fixed Unicode arrow display issues (▼/▶ symbols)
- Added current page highlighting functionality
- Implemented collapsible folder structure
- Added professional CSS styling and JavaScript interactivity

## File Structure Notes

- CHM test files located in `pychmlib/tests/chm_files/`
- LZX test files in `pychmlib/tests/lzx_files/`
- Both executable scripts (`chm_server.py`, `chm_viewer.py`) are in the root directory
- Web interface CSS and JavaScript embedded in `server.py`

## Dependencies

- **Python 3.6+**: Core requirement
- **Standard library only**: No external dependencies required
- **Legacy Symbian modules**: `appuifw`, `e32`, `e32dbm` (only needed for legacy `chom.py`)

## Visual Layout

The web interface provides a modern documentation viewing experience:

```
┌─────────────────────────────────────────────────┐
│ CHM File Viewer                                 │
├───────────────┬─────────────────────────────────┤
│ TOC Sidebar   │ Content Area                    │
│               │                                 │
│ ▼ Welcome     │ [Page content loads here        │
│ ▼ Garden      │  when clicking sidebar links]  │
│   • Flowers   │                                 │
│   • Trees     │ Current page highlighted        │
│ ▶ Examples    │ in blue in sidebar              │
│ ▼ HTMLHelp    │                                 │
│   • Topic 1   │                                 │
│   • Topic 2   │                                 │
│               │                                 │
└───────────────┴─────────────────────────────────┘
```

## Usage Examples

```bash
# Start server for a CHM file
python3 chm_server.py pychmlib/tests/chm_files/CHM-example.chm

# Then open http://127.0.0.1:8081/ in your web browser
# Features available:
# - Click TOC items in sidebar to navigate
# - Click folder names to expand/collapse sections
# - Current page is highlighted in blue
# - Professional documentation-style interface

# Or use the command-line viewer
python3 chm_viewer.py pychmlib/tests/chm_files/CHM-example.chm --list
```

## Static Web Version (GitHub Pages)

A browser-based version is available that runs entirely client-side using Pyodide (Python in WebAssembly). This version requires no server installation and can be deployed to GitHub Pages.

### Features
- **🌐 Browser-based**: Runs entirely in the browser using Pyodide
- **📁 Drag & Drop**: Upload CHM files directly in the browser
- **🔒 Privacy**: All processing happens locally, no files uploaded to servers
- **📋 Same Interface**: Identical sidebar navigation as the server version
- **🚀 No Installation**: Access from any modern web browser

### GitHub Pages Deployment

1. **Enable GitHub Pages**:
   - Go to your repository Settings → Pages
   - Set Source to "GitHub Actions"
   - The workflow in `.github/workflows/deploy.yml` will handle deployment

2. **Automatic Deployment**:
   - Push changes to `master` or `main` branch
   - GitHub Actions will automatically deploy the `docs/` folder
   - Site will be available at `https://yourusername.github.io/your-repo-name/`

3. **Manual Deployment** (alternative):
   - Go to repository Settings → Pages
   - Set Source to "Deploy from a branch"
   - Select `master` branch and `/docs` folder
   - Click Save

### Local Development of Web Version

```bash
# Serve the static site locally for testing
cd docs
python3 -m http.server 8000

# Open http://localhost:8000 in your browser
```

### Web Version File Structure

- `docs/index.html`: Main web interface with Pyodide integration
- `docs/chm-viewer.js`: JavaScript code with embedded Python CHM parser
- `docs/README.md`: Documentation for the web version
- `docs/_config.yml`: GitHub Pages configuration
- `.github/workflows/deploy.yml`: GitHub Actions deployment workflow

### Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 14+
- Edge 80+

## Server Configuration

The server includes several configurable options:
- Host and port settings via command line
- Timeout for auto-shutdown
- MIME type mappings in `server.py` TYPES dictionary
- CSS styling and JavaScript behavior in `generate_index_html()` method

The web interface provides a complete, modern documentation viewing experience that rivals commercial CHM viewers.