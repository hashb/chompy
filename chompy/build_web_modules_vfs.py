#!/usr/bin/env python3
"""
Build web version with VFS-based asset loading
"""

import os
import json

def read_file(filepath):
    """Read a file and return its content"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def build_chm_viewer_js():
    """Build the chm-viewer.js with VFS asset loading"""
    
    # Read the Python modules
    modules = {
        'pychmlib/chm.py': read_file('pychmlib/chm.py'),
        'pychmlib/lzx.py': read_file('pychmlib/lzx.py'),
        'hhc.py': read_file('hhc.py')
    }
    
    # Create the JavaScript template with proper escaping
    js_template = """// CHM Viewer with VFS Asset Loading
let pyodide = null;
let currentFile = null;
const blobUrlCache = new Map();

// Initialize Pyodide
async function initPyodide() {
    if (pyodide) return pyodide;
    
    updateLoadingStatus("Initializing Pyodide...");
    pyodide = await loadPyodide();
    
    updateLoadingStatus("Setting up environment...");
    
    updateLoadingStatus("Loading CHM parsing code...");
    await setupCHMParser();
    
    return pyodide;
}

// Python modules embedded as strings
const PYTHON_MODULES = """ + json.dumps(modules, indent=4) + """;

// Setup CHM parsing code in Pyodide
async function setupCHMParser() {
    updateLoadingStatus("Setting up Python modules...");
    
    // Create directories and write files in Pyodide's filesystem
    await pyodide.runPython(`
# Create pychmlib directory
import os
os.makedirs('pychmlib', exist_ok=True)

# Write __init__.py
with open('pychmlib/__init__.py', 'w') as f:
    f.write('')
`);
    
    // Write each module file
    for (const [filename, content] of Object.entries(PYTHON_MODULES)) {
        pyodide.FS.writeFile(filename, content);
    }
    
    // Import and setup the CHM functionality with VFS support
    await pyodide.runPython(`
import sys
sys.path.insert(0, '.')

from pychmlib.chm import _CHMFile
from hhc import parse as parse_hhc
import io
import os

class CHMFileWrapper:
    def __init__(self, file_data):
        self.data = bytes(file_data)
        self.pos = 0
        self.length = len(self.data)
    
    def read(self, size=-1):
        if size == -1:
            result = self.data[self.pos:]
            self.pos = self.length
        else:
            result = self.data[self.pos:self.pos + size]
            self.pos += len(result)
        return result
    
    def seek(self, pos):
        self.pos = pos
    
    def close(self):
        pass

class CHMFile(_CHMFile):
    def __init__(self, file_data):
        self.filename = '<memory>'
        self.file = CHMFileWrapper(file_data)
        try:
            self._parse_chm()
        except Exception as e:
            self.file.close()
            raise Exception(f"CHM parsing failed: {e}") from e
    
    def get_hhc_content(self):
        hhc_file = self.get_hhc()
        if hhc_file:
            content = self.retrieve_object(hhc_file)
            if isinstance(content, bytes):
                return content.decode(self.encoding, errors='ignore')
            return content
        return None
    
    def get_file_content(self, filename):
        unit_info = self.resolve_object(filename)
        if unit_info:
            content = self.retrieve_object(unit_info)
            if isinstance(content, bytes) and filename.endswith(('.htm', '.html', '.hhc', '.hhk', '.css', '.js', '.txt')):
                try:
                    return content.decode(self.encoding, errors='ignore')
                except (UnicodeDecodeError, AttributeError):
                    return content
            return content
        return None
    
    def list_files(self):
        return [ui.name for ui in self.all_files()]
    
    def extract_all_to_vfs(self, base_path='/chm'):
        os.makedirs(base_path, exist_ok=True)
        extracted_files = {}
        
        for unit_info in self.all_files():
            if not unit_info.name or unit_info.name in ['/', '']:
                continue
            
            # Skip directories (they end with / or have length 0)    
            if unit_info.name.endswith('/') or unit_info.length == 0:
                print(f"Skipping directory or empty entry: {unit_info.name}")
                continue
                
            # Skip system files that start with special characters
            if unit_info.name.startswith('/$') or unit_info.name.startswith('/#'):
                print(f"Skipping system file: {unit_info.name}")
                continue
            
            try:
                content = self.retrieve_object(unit_info)
                if content is None:
                    print(f"No content for: {unit_info.name}")
                    continue
                    
                file_path = unit_info.name
                if file_path.startswith('/'):
                    file_path = file_path[1:]
                
                full_path = os.path.join(base_path, file_path)
                
                # Create directories if needed
                dir_path = os.path.dirname(full_path)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                
                # Write file content
                if isinstance(content, str):
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                else:
                    with open(full_path, 'wb') as f:
                        f.write(content)
                
                extracted_files[unit_info.name] = full_path
                print(f"Extracted: {unit_info.name} -> {full_path}")
                
            except Exception as e:
                print(f"Error extracting {unit_info.name}: {e}")
                # Continue with other files even if this one fails
                continue
        
        print(f"Successfully extracted {len(extracted_files)} files to VFS")
        return extracted_files

# Global variables
chm_file = None
vfs_file_mapping = {}

def load_chm_file(file_data):
    global chm_file, vfs_file_mapping
    print(f"load_chm_file called with data type: {type(file_data)}")
    print(f"Data length: {len(file_data) if hasattr(file_data, '__len__') else 'unknown'}")
    if hasattr(file_data, '__getitem__'):
        header = bytes(file_data[:4])
        print(f"Header bytes: {header}")
    chm_file = CHMFile(file_data)
    print("CHMFile created successfully")
    
    print("Extracting CHM files to VFS...")
    vfs_file_mapping = chm_file.extract_all_to_vfs()
    print(f"Extracted {len(vfs_file_mapping)} files to VFS")
    
    return True

def get_chm_toc():
    global chm_file
    print(f"get_chm_toc called, chm_file: {chm_file}")
    if not chm_file:
        print("No chm_file available")
        return None
    
    print("Getting HHC content...")
    hhc_content = chm_file.get_hhc_content()
    print(f"HHC content type: {type(hhc_content)}")
    print(f"HHC content length: {len(hhc_content) if hhc_content else 0}")
    if not hhc_content:
        print("No HHC content found")
        return None
    
    print("Parsing HHC content...")
    result = parse_hhc(hhc_content)
    print(f"Parsed HHC result: {result}")
    return result

def get_chm_file_content(filename):
    global chm_file
    if not chm_file:
        return None
    return chm_file.get_file_content(filename)

def list_chm_files():
    global chm_file
    if not chm_file:
        return []
    return chm_file.list_files()

def get_vfs_path(chm_path):
    global vfs_file_mapping
    if chm_path in vfs_file_mapping:
        return vfs_file_mapping[chm_path]
    
    if '/' + chm_path in vfs_file_mapping:
        return vfs_file_mapping['/' + chm_path]
    
    for original_path, vfs_path in vfs_file_mapping.items():
        if original_path.lower() == chm_path.lower():
            return vfs_path
        if original_path.lower() == ('/' + chm_path).lower():
            return vfs_path
    
    return None

def create_blob_data_for_file(vfs_path):
    try:
        with open(vfs_path, 'rb') as f:
            data = f.read()
        return data
    except Exception as e:
        print(f"Error reading VFS file {vfs_path}: {e}")
        return None
`);
}

// File handling functions
function setupFileHandling() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const loadBtn = document.getElementById('loadBtn');
    
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            currentFile = e.target.files[0];
            loadBtn.disabled = false;
            updateUploadZone();
        }
    });
    
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.toLowerCase().endsWith('.chm')) {
                currentFile = file;
                fileInput.files = e.dataTransfer.files;
                loadBtn.disabled = false;
                updateUploadZone();
            } else {
                showError('Please select a CHM file');
            }
        }
    });
}

function updateUploadZone() {
    const uploadZone = document.getElementById('uploadZone');
    if (currentFile) {
        uploadZone.innerHTML = `
            <div class="upload-icon">✅</div>
            <div>
                <p><strong>${currentFile.name}</strong></p>
                <p style="color: #666; font-size: 0.9rem;">Size: ${formatFileSize(currentFile.size)}</p>
                <p style="color: #666; font-size: 0.9rem;">Click "Load CHM File" to continue</p>
            </div>
        `;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Create blob URL for CHM file content
async function createBlobUrlForCHMFile(chmPath) {
    if (blobUrlCache.has(chmPath)) {
        return blobUrlCache.get(chmPath);
    }
    
    try {
        pyodide.globals.set("blob_chm_path", chmPath);
        await pyodide.runPython(`
global blob_file_data, blob_success, blob_mime_type
import mimetypes

blob_chm_path_clean = blob_chm_path
if blob_chm_path_clean.startswith('/'):
    blob_chm_path_clean = blob_chm_path_clean[1:]

vfs_path = get_vfs_path(blob_chm_path)
if vfs_path:
    blob_file_data = create_blob_data_for_file(vfs_path)
    if blob_file_data:
        mime_type, _ = mimetypes.guess_type(blob_chm_path_clean)
        if not mime_type:
            if blob_chm_path_clean.lower().endswith(('.htm', '.html')):
                mime_type = 'text/html'
            elif blob_chm_path_clean.lower().endswith('.css'):
                mime_type = 'text/css'
            elif blob_chm_path_clean.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif blob_chm_path_clean.lower().endswith('.png'):
                mime_type = 'image/png'
            elif blob_chm_path_clean.lower().endswith('.gif'):
                mime_type = 'image/gif'
            else:
                mime_type = 'application/octet-stream'
        blob_mime_type = mime_type
        blob_success = True
    else:
        blob_success = False
else:
    blob_success = False
`);
        
        const success = pyodide.globals.get('blob_success');
        if (success) {
            const fileData = pyodide.globals.get('blob_file_data');
            const mimeType = pyodide.globals.get('blob_mime_type');
            
            const uint8Array = new Uint8Array(fileData.toJs());
            const blob = new Blob([uint8Array], { type: mimeType });
            const blobUrl = URL.createObjectURL(blob);
            
            blobUrlCache.set(chmPath, blobUrl);
            console.log(`Created blob URL for ${chmPath}: ${blobUrl}`);
            return blobUrl;
        }
    } catch (error) {
        console.error(`Error creating blob URL for ${chmPath}:`, error);
    }
    
    return null;
}

// Load and parse CHM file
async function loadFile() {
    if (!currentFile) {
        showError('Please select a CHM file first');
        return;
    }
    
    try {
        showLoading(true);
        
        if (!pyodide) {
            await initPyodide();
        }
        
        updateLoadingStatus("Reading CHM file...");
        
        const arrayBuffer = await currentFile.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        updateLoadingStatus("Parsing CHM structure and extracting to VFS...");
        
        pyodide.globals.set("file_data", uint8Array);
        
        await pyodide.runPython(`
global chm_load_success
try:
    result = load_chm_file(file_data.to_py())
    print(f"load_chm_file returned: {result}")
    chm_load_success = result
except Exception as e:
    import traceback
    print(f"Error loading CHM: {e}")
    print("Full traceback:")
    traceback.print_exc()
    chm_load_success = False
`);
        
        const success = pyodide.globals.get('chm_load_success');
        console.log("JavaScript success value:", success, "Type:", typeof success);
        
        if (!success) {
            throw new Error("Failed to parse CHM file");
        }
        
        updateLoadingStatus("Extracting table of contents...");
        
        await pyodide.runPython(`
global toc_json_data, toc_extraction_success
import json

try:
    print("Getting TOC...")
    toc = get_chm_toc()
    print(f"TOC result: {toc}")
    print(f"TOC type: {type(toc)}")
    if toc:
        print(f"TOC has children: {hasattr(toc, 'children')}")
        if hasattr(toc, 'children'):
            print(f"Number of children: {len(toc.children)}")
        
        def convert_toc(node):
            result = {
                'name': node.name,
                'local': getattr(node, 'local', None),
                'children': []
            }
            if hasattr(node, 'children'):
                for child in node.children:
                    if child.name and child.name.strip():
                        result['children'].append(convert_toc(child))
            return result
        converted = convert_toc(toc)
        print(f"Converted TOC: {converted}")
        toc_json_data = json.dumps(converted)
        print(f"JSON length: {len(toc_json_data)}")
        toc_extraction_success = True
    else:
        print("No TOC found")
        toc_extraction_success = False
except Exception as e:
    print(f"Error getting TOC: {e}")
    import traceback
    traceback.print_exc()
    toc_extraction_success = False
`);
        
        const tocSuccess = pyodide.globals.get('toc_extraction_success');
        console.log("TOC extraction success:", tocSuccess);
        
        let tocData = null;
        if (tocSuccess) {
            const tocJsonString = pyodide.globals.get('toc_json_data');
            tocData = JSON.parse(tocJsonString);
            console.log("Parsed TOC data:", tocData);
        }
        
        if (tocData) {
            displayCHMViewer(tocData);
        } else {
            throw new Error("Could not extract table of contents from CHM file");
        }
        
    } catch (error) {
        console.error('Error loading CHM file:', error);
        showError(`Error loading CHM file: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// Display CHM viewer
function displayCHMViewer(tocData) {
    document.getElementById('viewerContainer').style.display = 'block';
    
    const tocContainer = document.getElementById('tocContent');
    tocContainer.innerHTML = buildTOCHTML(tocData);
    
    setupTOCHandlers();
    
    document.getElementById('viewerContainer').scrollIntoView({ behavior: 'smooth' });
}

function buildTOCHTML(node) {
    let html = '<ul>';
    
    if (node.children && node.children.length > 0) {
        for (const child of node.children) {
            html += '<li>';
            
            if (child.local) {
                html += `<a href="#" class="toc-item" data-path="${child.local}">${child.name}</a>`;
            } else if (child.children && child.children.length > 0) {
                html += `<div class="folder" onclick="toggleFolder(this)">${child.name}</div>`;
                html += `<div class="folder-content">${buildTOCHTML(child)}</div>`;
            } else {
                html += `<div class="folder">${child.name}</div>`;
            }
            
            if (child.local && child.children && child.children.length > 0) {
                html += `<div class="folder-content">${buildTOCHTML(child)}</div>`;
            }
            
            html += '</li>';
        }
    }
    
    html += '</ul>';
    return html;
}

function setupTOCHandlers() {
    const tocItems = document.querySelectorAll('.toc-item');
    tocItems.forEach(item => {
        item.addEventListener('click', async (e) => {
            e.preventDefault();
            const path = item.dataset.path;
            if (path) {
                await loadContent(path);
                
                document.querySelectorAll('.toc-item').forEach(i => i.classList.remove('current'));
                item.classList.add('current');
            }
        });
    });
}

function toggleFolder(element) {
    element.classList.toggle('collapsed');
}

// Resolve relative paths
function resolveRelativePath(path) {
    const parts = path.split('/');
    const resolved = [];
    
    for (const part of parts) {
        if (part === '' || part === '.') {
            continue;
        } else if (part === '..') {
            if (resolved.length > 0) {
                resolved.pop();
            }
        } else {
            resolved.push(part);
        }
    }
    
    return resolved.join('/');
}

// Scope CSS to content area - Improved version
function scopeCSSToContentArea(cssContent) {
    console.log("Scoping CSS content, original length:", cssContent.length);
    
    // More robust CSS rule parsing
    const rules = [];
    let currentRule = '';
    let braceCount = 0;
    let inString = false;
    let stringChar = '';
    
    for (let i = 0; i < cssContent.length; i++) {
        const char = cssContent[i];
        const prevChar = i > 0 ? cssContent[i - 1] : '';
        
        if (!inString && (char === '"' || char === "'")) {
            inString = true;
            stringChar = char;
        } else if (inString && char === stringChar && prevChar !== '\\\\') {
            inString = false;
            stringChar = '';
        }
        
        if (!inString) {
            if (char === '{') {
                braceCount++;
            } else if (char === '}') {
                braceCount--;
                if (braceCount === 0) {
                    currentRule += char;
                    rules.push(currentRule.trim());
                    currentRule = '';
                    continue;
                }
            }
        }
        
        currentRule += char;
    }
    
    // Add any remaining rule
    if (currentRule.trim()) {
        rules.push(currentRule.trim());
    }
    
    console.log("Parsed", rules.length, "CSS rules");
    
    const scopedRules = [];
    
    for (let rule of rules) {
        rule = rule.trim();
        if (!rule) continue;
        
        // Handle @-rules (media queries, keyframes, etc.)
        if (rule.startsWith('@')) {
            if (rule.startsWith('@media')) {
                // For media queries, scope the inner rules
                const mediaMatch = rule.match(/@media[^{]+\\{([\\s\\S]*)\\}$/);
                if (mediaMatch) {
                    const mediaQuery = rule.substring(0, rule.indexOf('{') + 1);
                    const innerCSS = mediaMatch[1];
                    const scopedInner = scopeCSSToContentArea(innerCSS);
                    scopedRules.push(mediaQuery + scopedInner + '}');
                } else {
                    scopedRules.push(rule);
                }
            } else {
                // Other @-rules (keyframes, imports, etc.) - keep as-is
                scopedRules.push(rule);
            }
            continue;
        }
        
        const braceIndex = rule.indexOf('{');
        if (braceIndex === -1) continue;
        
        const selector = rule.substring(0, braceIndex).trim();
        const properties = rule.substring(braceIndex);
        
        // Scope each selector
        const scopedSelector = selector.split(',').map(sel => {
            sel = sel.trim();
            
            // Skip if already scoped
            if (sel.includes('.chm-content')) {
                return sel;
            }
            
            // Handle special selectors that should be scoped but not prefixed
            if (sel === 'html' || sel === 'body' || sel === '*') {
                return '.chm-content';
            }
            
            // Handle pseudo-selectors and combinators properly
            if (sel.includes(':') || sel.includes('>') || sel.includes('+') || sel.includes('~')) {
                // For complex selectors, scope the first part
                const parts = sel.split(/(\s*[>+~]\s*)/);
                if (parts.length > 1) {
                    parts[0] = '.chm-content ' + parts[0].trim();
                    return parts.join('');
                } else {
                    // For pseudo-selectors like div:hover
                    return '.chm-content ' + sel;
                }
            }
            
            // Add .chm-content prefix to scope the selector
            return '.chm-content ' + sel;
        }).join(', ');
        
        scopedRules.push(scopedSelector + properties);
    }
    
    const result = scopedRules.join('\\n');
    console.log("Scoped CSS result length:", result.length);
    console.log("Sample scoped CSS (first 200 chars):", result.substring(0, 200));
    
    return result;
}

// Process HTML content with VFS assets - General approach
async function processHTMLContent(htmlContent, basePath) {
    console.log("processHTMLContent called with basePath:", basePath);
    let processedHTML = htmlContent;
    
    const baseDir = basePath.includes('/') ? basePath.substring(0, basePath.lastIndexOf('/')) : '';
    console.log("Base directory:", baseDir);
    
    // **GENERAL APPROACH**: Find all relative file paths and replace them with blob URLs
    // This catches any relative path that looks like a file, regardless of context
    // Matches: ../path/file.ext, ./path/file.ext, path/file.ext, file.ext
    // NOTE: Excludes CSS files as they need special processing for url() references
    const generalFileRegex = /(?:["'=\s>])([^"'\s<>]*[^\/\s<>"']\.(?:jpg|jpeg|png|gif|bmp|js|htm|html|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|tar|gz|mp3|mp4|avi|mov|wmv|flv|swf|ico|svg|woff|woff2|ttf|eot))(?=["'\s<>])/gi;
    const generalMatches = [...htmlContent.matchAll(generalFileRegex)];
    console.log("Found", generalMatches.length, "relative file paths via general approach");
    console.log("General matches:", generalMatches.map(m => `"${m[0]}" -> "${m[1]}"`));
    
    for (const match of generalMatches) {
        const fullMatch = match[0];
        const relativePath = match[1];
        
        console.log(`Processing match: Full="${fullMatch}" | Path="${relativePath}"`);
        
        // Skip if already processed (contains blob:) or is an absolute URL
        if (relativePath.includes('blob:') || relativePath.startsWith('http://') || 
            relativePath.startsWith('https://') || relativePath.startsWith('data:')) {
            console.log(`Skipping already processed or absolute URL: "${relativePath}"`);
            continue;
        }
        
        try {
            let resolvedPath = relativePath;
            if (!relativePath.startsWith('/')) {
                if (baseDir) {
                    resolvedPath = baseDir + '/' + relativePath;
                } else {
                    resolvedPath = relativePath;
                }
                resolvedPath = resolveRelativePath(resolvedPath);
            }
            
            console.log("Loading general file via VFS:", resolvedPath, "from original:", relativePath);
            
            const blobUrl = await createBlobUrlForCHMFile(resolvedPath);
            if (blobUrl) {
                // Replace the relative path with the blob URL, preserving the surrounding context
                const newMatch = fullMatch.replace(relativePath, blobUrl);
                console.log(`Replacing "${fullMatch}" with "${newMatch}"`);
                const oldHTML = processedHTML;
                processedHTML = processedHTML.replace(fullMatch, newMatch);
                if (oldHTML === processedHTML) {
                    console.log(`WARNING: No replacement occurred for "${fullMatch}"`);
                } else {
                    console.log("Successfully loaded general file via blob URL:", resolvedPath);
                }
            } else {
                console.log("Could not create blob URL for general file:", resolvedPath);
            }
        } catch (error) {
            console.error("Error processing general file " + relativePath + ":", error);
        }
    }
    
    // Process external CSS files for scoping and url() processing
    // CSS files are excluded from general regex above to allow proper url() processing
    const cssRegex = /<link([^>]*?)href=["']([^"']+\\.css)["']([^>]*?)>/gi;
    const cssMatches = [...processedHTML.matchAll(cssRegex)];
    console.log("Found", cssMatches.length, "CSS links to process for url() references and scoping");
    
    for (const match of cssMatches) {
        const fullTag = match[0];
        const cssHref = match[2];
        
        console.log(`Processing CSS file: "${cssHref}" from tag: "${fullTag}"`);
        
        if (cssHref.startsWith('http://') || cssHref.startsWith('https://') || cssHref.startsWith('blob:')) {
            console.log(`Skipping external/blob CSS: "${cssHref}"`);
            continue;
        }
        
        try {
            let cssPath = cssHref;
            if (!cssHref.startsWith('/')) {
                if (baseDir) {
                    cssPath = baseDir + '/' + cssHref;
                } else {
                    cssPath = cssHref;
                }
                cssPath = resolveRelativePath(cssPath);
            }
            
            console.log("Loading CSS via VFS for scoping: " + cssPath);
            
            const blobUrl = await createBlobUrlForCHMFile(cssPath);
            if (blobUrl) {
                const response = await fetch(blobUrl);
                if (response.ok) {
                    const cssContent = await response.text();
                    console.log("Processing CSS file for url() references and scoping:", cssPath);
                    
                    // Process url() references in the CSS content (general approach may not catch these inside blobs)
                    let processedCssContent = cssContent;
                    const cssUrlRegex = /url\\(["']?([^"')]+)["']?\\)/gi;
                    const cssUrlMatches = [...cssContent.matchAll(cssUrlRegex)];
                    console.log("Found", cssUrlMatches.length, "url() references in CSS file:", cssPath);
                    
                    for (const urlMatch of cssUrlMatches) {
                        const fullCssUrl = urlMatch[0];
                        const cssImgUrl = urlMatch[1];
                        
                        console.log(`Processing CSS url(): "${fullCssUrl}" -> "${cssImgUrl}"`);
                        
                        if (cssImgUrl.startsWith('http://') || cssImgUrl.startsWith('https://') || 
                            cssImgUrl.startsWith('data:') || cssImgUrl.startsWith('blob:')) {
                            console.log(`Skipping external/blob CSS url(): "${cssImgUrl}"`);
                            continue;
                        }
                        
                        try {
                            // Resolve relative to the CSS file's directory
                            const cssDir = cssPath.includes('/') ? cssPath.substring(0, cssPath.lastIndexOf('/')) : '';
                            let cssImagePath = cssImgUrl;
                            if (!cssImgUrl.startsWith('/')) {
                                if (cssDir) {
                                    cssImagePath = cssDir + '/' + cssImgUrl;
                                } else {
                                    cssImagePath = cssImgUrl;
                                }
                                cssImagePath = resolveRelativePath(cssImagePath);
                            }
                            
                            console.log("Loading CSS image via VFS:", cssImagePath, "from CSS file:", cssPath);
                            
                            const cssImageBlobUrl = await createBlobUrlForCHMFile(cssImagePath);
                            if (cssImageBlobUrl) {
                                const newCssUrl = "url('" + cssImageBlobUrl + "')";
                                processedCssContent = processedCssContent.replace(fullCssUrl, newCssUrl);
                                console.log("Successfully loaded CSS image via blob URL:", cssImagePath);
                            } else {
                                console.log("Could not create blob URL for CSS image:", cssImagePath);
                            }
                        } catch (error) {
                            console.error("Error processing CSS image " + cssImgUrl + ":", error);
                        }
                    }
                    
                    // Scope the CSS content to avoid conflicts
                    const scopedCSS = scopeCSSToContentArea(processedCssContent);
                    const styleTag = "<style>" + scopedCSS + "</style>";
                    processedHTML = processedHTML.replace(fullTag, styleTag);
                    console.log("Successfully embedded scoped CSS with processed images: " + cssPath);
                }
            }
        } catch (error) {
            console.error("Error processing CSS " + cssHref + ":", error);
        }
    }
    
    return processedHTML;
}

// Load content for a specific path
async function loadContent(path) {
    try {
        updateLoadingStatus(`Loading ${path}...`);
        
        pyodide.globals.set("content_path", path);
        await pyodide.runPython(`
global content_data, content_success
try:
    print(f"Loading content for path: {content_path}")
    
    base_path = content_path.split('#')[0] if '#' in content_path else content_path
    anchor = content_path.split('#')[1] if '#' in content_path else None
    
    paths_to_try = [
        base_path,
        '/' + base_path,
        '/' + base_path.lower(),
        base_path.lower()
    ]
    
    all_files = list_chm_files()
    print(f"Total files in CHM: {len(all_files)}")
    
    content = None
    used_path = None
    
    for try_path in paths_to_try:
        print(f"Trying path: {try_path}")
        if try_path in all_files:
            print(f"Found exact match: {try_path}")
            content = get_chm_file_content(try_path)
            used_path = try_path
            if anchor:
                print(f"Note: Will need to scroll to anchor #{anchor}")
            break
    
    if not content:
        print("No exact match found. Searching for similar files...")
        similar = [f for f in all_files if base_path.lower() in f.lower()]
        print(f"Similar files: {similar[:5]}")
        if similar:
            try_path = similar[0]
            print(f"Trying similar file: {try_path}")
            content = get_chm_file_content(try_path)
            used_path = try_path
    
    print(f"Content type: {type(content)}")
    print(f"Content length: {len(content) if content else 0}")
    if content and isinstance(content, str):
        print(f"Content preview: {content[:100]}...")
        print(f"Used path: {used_path}")
    
    content_data = content if content else ""
    content_success = bool(content)
    print(f"Stored content_success: {content_success}")
    
except Exception as e:
    print(f"Error loading content: {e}")
    import traceback
    traceback.print_exc()
    content_data = ""
    content_success = False
`);

        const contentSuccess = pyodide.globals.get('content_success');
        const content = contentSuccess ? pyodide.globals.get('content_data') : null;
        
        const contentArea = document.getElementById('contentArea');
        
        console.log("JavaScript received content:", content);
        console.log("Content type:", typeof content);
        console.log("Content length:", content ? content.length : 0);
        
        if (content) {
            console.log("Processing content for path:", path);
            const isHTML = path.toLowerCase().includes('.htm');
            console.log("Is HTML file:", isHTML);
            if (isHTML) {
                console.log("Calling processHTMLContent...");
                const processedContent = await processHTMLContent(content, path);
                
                contentArea.innerHTML = `
                    <div style="border: 1px solid #ddd; border-radius: 4px; overflow: hidden;">
                        <div style="background: #f8f9fa; padding: 0.5rem; border-bottom: 1px solid #ddd; font-weight: 600;">
                            📄 ${path}
                        </div>
                        <div class="chm-content" style="padding: 1rem; max-height: 60vh; overflow-y: auto;">
                            ${processedContent}
                        </div>
                    </div>
                `;
            } else {
                contentArea.innerHTML = `
                    <div style="border: 1px solid #ddd; border-radius: 4px; overflow: hidden;">
                        <div style="background: #f8f9fa; padding: 0.5rem; border-bottom: 1px solid #ddd; font-weight: 600;">
                            📄 ${path}
                        </div>
                        <pre style="padding: 1rem; margin: 0; max-height: 60vh; overflow-y: auto; background: #f8f9fa;">${content}</pre>
                    </div>
                `;
            }
        } else {
            contentArea.innerHTML = `
                <div class="error">
                    <h3>Content Not Available</h3>
                    <p>Could not load content for "${path}". The file may be compressed or not found.</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error loading content:', error);
        const contentArea = document.getElementById('contentArea');
        contentArea.innerHTML = `
            <div class="error">
                <h3>Error Loading Content</h3>
                <p>Failed to load "${path}": ${error.message}</p>
            </div>
        `;
    }
}

// Utility functions
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

function updateLoadingStatus(message) {
    document.getElementById('loadingStatus').textContent = message;
}

function showError(message) {
    const errorContainer = document.getElementById('errorContainer');
    errorContainer.innerHTML = `
        <div class="error">
            <h3>Error</h3>
            <p>${message}</p>
        </div>
    `;
    setTimeout(() => {
        errorContainer.innerHTML = '';
    }, 5000);
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    setupFileHandling();
});
"""
    
    return js_template

if __name__ == '__main__':
    # Generate the new chm-viewer.js
    js_content = build_chm_viewer_js()
    
    # Write to the docs directory
    with open('docs/chm-viewer.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print("✅ Generated docs/chm-viewer.js with VFS asset loading")
    print("   - Uses existing pychmlib/chm.py")
    print("   - Uses existing pychmlib/lzx.py") 
    print("   - Uses existing hhc.py")
    print("   - Extracts all CHM files to Pyodide VFS")
    print("   - Creates blob URLs for assets")
    print("   - CSS scoping for proper isolation")