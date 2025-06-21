# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chompy is a modern CHM (Compiled HTML Help) file viewer and HTTP server. Originally designed for Symbian/PyS60 devices, it has been modernized to work with standard Python 3 installations. The project provides both command-line tools and an HTTP server for viewing CHM files.

## Architecture

### Core Components

- **chm_server.py**: Modern HTTP server for serving CHM files via web browser
- **chm_viewer.py**: Command-line tool for viewing and extracting CHM content
- **server.py**: Core HTTP server implementation using Python's built-in HTTP server
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

- **HTTP Server**: Serves CHM files via modern HTTP server with table of contents navigation
- **Command-line Viewer**: Extract and view CHM content without GUI dependencies
- **CHM Format Support**: Full CHM file parsing including compressed content (LZX algorithm)
- **Python 3 Compatible**: Fixed byte/string handling and modernized syntax
- **Cross-platform**: Works on any system with Python 3

## Development Commands

### CHM Server
```bash
# Serve a CHM file via HTTP
python3 chm_server.py path/to/file.chm

# Serve with custom host/port
python3 chm_server.py path/to/file.chm --host 0.0.0.0 --port 8080

# Auto-shutdown after timeout
python3 chm_server.py path/to/file.chm --timeout 30
```

### CHM Viewer/Extractor
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

## Bug Fixes Applied

- Fixed Python 3 compatibility issues in LZX decompression (`pychmlib/lzx.py`)
- Fixed byte/string handling throughout CHM parsing library
- Fixed regex escape sequence warning in `HTMLParser.py`
- Fixed relative import issues in test files
- Updated HTTP server to use modern `http.server` instead of raw sockets
- Fixed HHC parser to handle malformed content gracefully

## File Structure Notes

- CHM test files located in `pychmlib/tests/chm_files/`
- LZX test files in `pychmlib/tests/lzx_files/`
- Both executable scripts (`chm_server.py`, `chm_viewer.py`) are in the root directory

## Dependencies

- **Python 3.6+**: Core requirement
- **Standard library only**: No external dependencies required
- **Legacy Symbian modules**: `appuifw`, `e32`, `e32dbm` (only needed for legacy `chom.py`)

## Usage Examples

```bash
# Start server for a CHM file
python3 chm_server.py pychmlib/tests/chm_files/CHM-example.chm

# Then open http://127.0.0.1:8081/ in your web browser

# Or use the command-line viewer
python3 chm_viewer.py pychmlib/tests/chm_files/CHM-example.chm --list
```