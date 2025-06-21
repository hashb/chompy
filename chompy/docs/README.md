# CHM Viewer - Online CHM File Reader

A modern, browser-based CHM (Compiled HTML Help) file viewer that runs entirely in your browser using Pyodide. No installation required!

## Features

🔍 **Browser-Based**: View CHM files directly in your browser without installing any software
📁 **Drag & Drop**: Simply drag and drop CHM files to start viewing
📋 **Table of Contents**: Navigate through CHM content with a clean sidebar interface
🔗 **Direct Links**: Click TOC items to jump directly to content
💻 **Cross-Platform**: Works on any device with a modern web browser
🚀 **Fast**: Powered by Pyodide for efficient Python execution in the browser

## How to Use

1. **Visit the Website**: Go to the deployed GitHub Pages URL
2. **Upload CHM File**: Click the upload area or drag & drop your CHM file
3. **Browse Content**: Use the table of contents sidebar to navigate
4. **View Pages**: Click any item to view its content in the main area

## Supported Features

- ✅ Uncompressed CHM files
- ✅ Table of contents (HHC) parsing
- ✅ HTML content display
- ✅ CSS styling preservation
- ✅ File navigation
- ⚠️ LZX compressed files (limited support)

## Technical Details

This viewer is built with:
- **Pyodide**: Python in the browser via WebAssembly
- **Pure JavaScript**: No server required, runs entirely client-side
- **Modern Web APIs**: File API for drag & drop functionality
- **Responsive Design**: Clean, mobile-friendly interface

## Privacy

All CHM files are processed locally in your browser. No files are uploaded to any server, ensuring complete privacy and security.

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 14+
- Edge 80+

## Local Development

To run locally:

1. Clone the repository
2. Start a local web server in the `docs` directory:
   ```bash
   cd docs
   python -m http.server 8000
   ```
3. Open `http://localhost:8000` in your browser

## License

Licensed under the Apache License 2.0. See LICENSE file for details.