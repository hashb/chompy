# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chompy is a CHM (Compiled HTML Help) file viewer originally designed for Symbian/PyS60 mobile devices. The project provides both online and offline modes for viewing CHM files, with a built-in HTTP server for online mode and direct file extraction for offline mode.

## Architecture

### Core Components

- **chom.py**: Main application entry point with GUI using appuifw (Symbian UI framework)
  - `Chompy` class: Main application controller with file browser and recent files management
  - `HHCViewer` class: Content viewer for navigating CHM table of contents
- **server.py**: HTTP server for online CHM viewing mode (serves on localhost:8081)
- **pychmlib/**: CHM file parsing library
  - `chm.py`: Core CHM file format parser with LZX decompression support
  - `lzx.py`: LZX decompression algorithm implementation
- **hhc.py**: HTML Help Contents (HHC) file parser for table of contents
- **chm_filebrowser.py**: File browser component for CHM file selection
- **HTMLParser.py**: Modified HTML parser (contains syntax warning with regex escape sequence)
- **markupbase.py**: Base classes for markup parsing

### Key Features

- **Dual Mode Operation**: Online mode (HTTP server) and offline mode (direct extraction)
- **CHM Format Support**: Full CHM file parsing including compressed content (LZX algorithm)
- **Navigation**: Table of contents browsing with hierarchical navigation
- **File Management**: Recent files tracking with persistent storage
- **Mobile Optimized**: Designed for Symbian devices with touch-friendly navigation

## Development Commands

### Testing
```bash
# Run unit tests (requires Python package structure fixes)
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

### Running the Application
```bash
# Main application (requires Symbian/PyS60 environment)
python chom.py

# HTTP server standalone (for testing)
python server.py path/to/file.chm
```

## Known Issues

- HTMLParser.py:46 contains invalid regex escape sequence `\s` that should be `\\s`
- Tests have import issues due to relative imports without proper package structure
- Application is designed for Symbian/PyS60 environment and won't run on standard Python installations without modifications

## File Structure Notes

- Configuration stored in E:\Data\chompy\ (Symbian path)
- Temporary HTML files generated for browser viewing
- CHM test files located in pychmlib/tests/chm_files/
- LZX test files in pychmlib/tests/lzx_files/

## Dependencies

The project uses only Python standard library modules plus:
- Symbian-specific modules: appuifw, e32, e32dbm (not available on standard Python)
- No external package dependencies or requirements.txt file