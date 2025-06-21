#!/usr/bin/env python3
"""
Script to build the web version with embedded Python modules
"""

import os
import json

def read_file(filepath):
    """Read a file and return its content"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def build_chm_viewer_js():
    """Build the chm-viewer.js with embedded Python modules"""
    
    # Read the Python modules
    modules = {
        'pychmlib/chm.py': read_file('pychmlib/chm.py'),
        'pychmlib/lzx.py': read_file('pychmlib/lzx.py'),
        'hhc.py': read_file('hhc.py')
    }
    
    # Create the JavaScript template
    js_template = '''// CHM Viewer JavaScript - Pyodide Integration
let pyodide = null;
let currentFile = null;
let chmData = null;

// Initialize Pyodide
async function initPyodide() {
    if (pyodide) return pyodide;
    
    updateLoadingStatus("Initializing Pyodide...");
    pyodide = await loadPyodide();
    
    updateLoadingStatus("Setting up environment...");
    
    updateLoadingStatus("Loading CHM parsing code...");
    // Install our CHM parsing code
    await setupCHMParser();
    
    return pyodide;
}

// Python modules embedded as strings
const PYTHON_MODULES = ''' + json.dumps(modules, indent=4) + ''';

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
    
    // Import and setup the CHM functionality
    await pyodide.runPython(`
import sys
sys.path.insert(0, '.')

from pychmlib.chm import _CHMFile
from hhc import parse as parse_hhc
import io

class CHMFileWrapper:
    """Wrapper to make CHM parsing work with in-memory data"""
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
    """Modified CHM file class that works with in-memory data"""
    def __init__(self, file_data):
        self.filename = '<memory>'
        self.file = CHMFileWrapper(file_data)
        try:
            self._parse_chm()
        except Exception as e:
            self.file.close()
            raise Exception(f"CHM parsing failed: {e}") from e
    
    def get_hhc_content(self):
        """Get HHC content as string"""
        hhc_file = self.get_hhc()
        if hhc_file:
            content = self.retrieve_object(hhc_file)
            if isinstance(content, bytes):
                return content.decode(self.encoding, errors='ignore')
            return content
        return None
    
    def get_file_content(self, filename):
        """Get file content by filename"""
        unit_info = self.resolve_object(filename)
        if unit_info:
            content = self.retrieve_object(unit_info)
            # Ensure text files are properly decoded
            if isinstance(content, bytes) and filename.endswith(('.htm', '.html', '.hhc', '.hhk', '.css', '.js', '.txt')):
                try:
                    return content.decode(self.encoding, errors='ignore')
                except (UnicodeDecodeError, AttributeError):
                    return content
            return content
        return None
    
    def list_files(self):
        """List all files in the CHM"""
        return [ui.name for ui in self.all_files()]
    
    def extract_all_to_vfs(self, base_path='/chm'):
        """Extract all CHM files to Pyodide's virtual file system"""
        import os
        
        # Create base directory
        os.makedirs(base_path, exist_ok=True)
        
        extracted_files = {}
        
        for unit_info in self.all_files():
            if not unit_info.name or unit_info.name in ['/', '']:
                continue
                
            content = self.retrieve_object(unit_info)
            if content is None:
                continue
                
            # Clean up the file path
            file_path = unit_info.name
            if file_path.startswith('/'):
                file_path = file_path[1:]
            
            # Create full path in VFS
            full_path = os.path.join(base_path, file_path)
            
            try:
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
                
            except Exception as e:
                print(f"Error extracting {unit_info.name}: {e}")
                continue
        
        return extracted_files

# Global CHM file instance and VFS file mapping
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
    
    # Extract all files to VFS
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
    """Get the VFS path for a CHM file path"""
    global vfs_file_mapping
    # Try exact match first
    if chm_path in vfs_file_mapping:
        return vfs_file_mapping[chm_path]
    
    # Try with leading slash
    if '/' + chm_path in vfs_file_mapping:
        return vfs_file_mapping['/' + chm_path]
    
    # Try case variations
    for original_path, vfs_path in vfs_file_mapping.items():
        if original_path.lower() == chm_path.lower():
            return vfs_path
        if original_path.lower() == ('/' + chm_path).lower():
            return vfs_path
    
    return None

def create_blob_url_for_file(vfs_path):
    """Create a blob URL for a file in the VFS"""
    try:
        with open(vfs_path, 'rb') as f:
            data = f.read()
        return data
    except Exception as e:
        print(f"Error reading VFS file {vfs_path}: {e}")
        return None
`);
}

// File handling
function setupFileHandling() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const loadBtn = document.getElementById('loadBtn');
    
    // Click to select file
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    // File selection
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            currentFile = e.target.files[0];
            loadBtn.disabled = false;
            updateUploadZone();
        }
    });
    
    // Drag and drop
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

// Load and parse CHM file
async function loadFile() {
    if (!currentFile) {
        showError('Please select a CHM file first');
        return;
    }
    
    try {
        showLoading(true);
        
        // Initialize Pyodide if not already done
        if (!pyodide) {
            await initPyodide();
        }
        
        updateLoadingStatus("Reading CHM file...");
        
        // Read file as ArrayBuffer
        const arrayBuffer = await currentFile.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        updateLoadingStatus("Parsing CHM structure...");
        
        // Pass file data to Python
        pyodide.globals.set("file_data", uint8Array);
        
        // Load CHM file in Python
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
        
        // Check the success flag
        const success = pyodide.globals.get('chm_load_success');
        console.log("JavaScript success value:", success, "Type:", typeof success);
        
        if (!success) {
            throw new Error("Failed to parse CHM file");
        }
        
        updateLoadingStatus("Extracting table of contents...");
        
        // Get table of contents
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
        # Convert to JavaScript-friendly format
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
        # Store as JSON string for reliable transfer
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
    
    // Build table of contents
    const tocContainer = document.getElementById('tocContent');
    tocContainer.innerHTML = buildTOCHTML(tocData);
    
    // Add click handlers
    setupTOCHandlers();
    
    // Scroll to top
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
                
                // Update current highlighting
                document.querySelectorAll('.toc-item').forEach(i => i.classList.remove('current'));
                item.classList.add('current');
            }
        });
    });
}

function toggleFolder(element) {
    element.classList.toggle('collapsed');
}

// Global blob URL cache
const blobUrlCache = new Map();

// Create blob URL for CHM file content
async function createBlobUrlForCHMFile(chmPath) {
    // Check cache first
    if (blobUrlCache.has(chmPath)) {
        return blobUrlCache.get(chmPath);
    }
    
    try {
        // Get VFS path and file data from Python
        pyodide.globals.set("blob_chm_path", chmPath);
        await pyodide.runPython(`
global blob_file_data, blob_success, blob_mime_type
import mimetypes

blob_chm_path_clean = blob_chm_path
# Clean up path
if blob_chm_path_clean.startswith('/'):
    blob_chm_path_clean = blob_chm_path_clean[1:]

vfs_path = get_vfs_path(blob_chm_path)
if vfs_path:
    blob_file_data = create_blob_url_for_file(vfs_path)
    if blob_file_data:
        # Determine MIME type
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
            
            // Convert Python bytes to JavaScript Uint8Array
            const uint8Array = new Uint8Array(fileData.toJs());
            
            // Create blob and URL
            const blob = new Blob([uint8Array], { type: mimeType });
            const blobUrl = URL.createObjectURL(blob);
            
            // Cache the URL
            blobUrlCache.set(chmPath, blobUrl);
            
            console.log(`Created blob URL for ${chmPath}: ${blobUrl}`);
            return blobUrl;
        }
    } catch (error) {
        console.error(`Error creating blob URL for ${chmPath}:`, error);
    }
    
    return null;
}

// Resolve relative paths with .. references
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

// Scope CSS to only apply within the content area
function scopeCSSToContentArea(cssContent) {
    // Split CSS into rules
    const rules = cssContent.split('}');
    const scopedRules = [];
    
    for (let rule of rules) {
        rule = rule.trim();
        if (!rule) continue;
        
        // Add closing brace back
        rule += '}';
        
        // Skip @import, @media, and other at-rules - scope them differently
        if (rule.startsWith('@')) {
            // For @media rules, scope the content inside
            if (rule.startsWith('@media')) {
                const mediaMatch = rule.match(/@media[^{]+\{(.*)\}/s);
                if (mediaMatch) {
                    const mediaQuery = rule.substring(0, rule.indexOf('{') + 1);
                    const innerCSS = mediaMatch[1];
                    const scopedInner = scopeCSSToContentArea(innerCSS);
                    scopedRules.push(mediaQuery + scopedInner + '}');
                } else {
                    scopedRules.push(rule);
                }
            } else {
                scopedRules.push(rule);
            }
            continue;
        }
        
        // Extract selector and properties
        const braceIndex = rule.indexOf('{');
        if (braceIndex === -1) continue;
        
        const selector = rule.substring(0, braceIndex).trim();
        const properties = rule.substring(braceIndex);
        
        // Scope the selector to only apply within .chm-content
        const scopedSelector = selector.split(',').map(sel => {
            sel = sel.trim();
            // Skip selectors that already contain our scope or are too broad
            if (sel.includes('.chm-content') || sel === 'html' || sel === 'body') {
                return sel;
            }
            return '.chm-content ' + sel;
        }).join(', ');
        
        scopedRules.push(scopedSelector + properties);
    }
    
    return scopedRules.join('\\n');
}

// Process HTML content to handle embedded images and CSS
async function processHTMLContent(htmlContent, basePath) {
    let processedHTML = htmlContent;
    
    // Get the directory of the current page for resolving relative paths
    const baseDir = basePath.includes('/') ? basePath.substring(0, basePath.lastIndexOf('/')) : '';
    
    // Process CSS links first
    const cssRegex = /<link([^>]*?)href=["']([^"']+\.css)["']([^>]*?)>/gi;
    const cssMatches = [...htmlContent.matchAll(cssRegex)];
    
    for (const match of cssMatches) {
        const fullTag = match[0];
        const beforeHref = match[1];
        const cssHref = match[2];
        const afterHref = match[3];
        
        // Skip absolute URLs
        if (cssHref.startsWith('http://') || cssHref.startsWith('https://')) {
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
            
            console.log("Loading CSS: " + cssPath);
            
            // Get CSS content from CHM
            pyodide.globals.set("css_path", cssPath);
            await pyodide.runPython(`
global css_data, css_found
try:
    paths_to_try = [css_path, '/' + css_path, '/' + css_path.lower(), css_path.lower()]
    css_content = None
    for try_path in paths_to_try:
        if try_path in list_chm_files():
            css_content = get_chm_file_content(try_path)
            break
    if css_content:
        css_data = css_content
        css_found = True
        print(f"CSS loaded, length: {len(css_content)}")
    else:
        css_data = ""
        css_found = False
except Exception as e:
    print(f"Error loading CSS: {e}")
    css_data = ""
    css_found = False
`);
            
            const cssFound = pyodide.globals.get('css_found');
            if (cssFound) {
                const cssContent = pyodide.globals.get('css_data');
                // Scope the CSS to only apply to the content area
                const scopedCSS = scopeCSSToContentArea(cssContent);
                const styleTag = "<style>" + scopedCSS + "</style>";
                processedHTML = processedHTML.replace(fullTag, styleTag);
                console.log("Successfully embedded CSS: " + cssPath);
            }
        } catch (error) {
            console.error("Error processing CSS " + cssHref + ":", error);
        }
    }
    
    // Process image tags
    const imgRegex = /<img([^>]*?)src=["']([^"']+)["']([^>]*?)>/gi;
    const imgMatches = [...processedHTML.matchAll(imgRegex)];
    
    for (const match of imgMatches) {
        const fullTag = match[0];
        const beforeSrc = match[1];
        const imgSrc = match[2];
        const afterSrc = match[3];
        
        // Skip absolute URLs
        if (imgSrc.startsWith('http://') || imgSrc.startsWith('https://') || imgSrc.startsWith('data:')) {
            continue;
        }
        
        try {
            // Resolve relative path
            let imagePath = imgSrc;
            if (!imgSrc.startsWith('/')) {
                // Relative path - combine with base directory and resolve .. references
                if (baseDir) {
                    imagePath = baseDir + '/' + imgSrc;
                } else {
                    imagePath = imgSrc;
                }
                // Resolve .. references properly
                imagePath = resolveRelativePath(imagePath);
            }
            
            console.log("Loading image: " + imagePath);
            
            // Get image data from CHM
            pyodide.globals.set("image_path", imagePath);
            await pyodide.runPython(`
global image_data_b64, image_found
try:
    # Try different path variations for the image
    paths_to_try = [
        image_path,
        '/' + image_path,
        '/' + image_path.lower(),
        image_path.lower()
    ]
    
    all_files = list_chm_files()
    print(f"Looking for image: {image_path}")
    print(f"Trying paths: {paths_to_try}")
    
    # Find image files in CHM for debugging
    image_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp'])]
    print(f"Available image files in CHM: {image_files[:10]}")  # Show first 10
    
    image_data = None
    for try_path in paths_to_try:
        if try_path in all_files:
            print(f"Found image at: {try_path}")
            image_data = get_chm_file_content(try_path)
            break
    
    if image_data:
        import base64
        if isinstance(image_data, str):
            image_data = image_data.encode('latin-1')
        image_data_b64 = base64.b64encode(image_data).decode('ascii')
        image_found = True
        print(f"Image converted to base64, length: {len(image_data_b64)}")
    else:
        image_data_b64 = ""
        image_found = False
        print("No image data found")
except Exception as e:
    print(f"Error loading image {image_path}: {e}")
    image_data_b64 = ""
    image_found = False
`);
            
            const imageFound = pyodide.globals.get('image_found');
            const imageDataBase64 = imageFound ? pyodide.globals.get('image_data_b64') : null;
            
            if (imageDataBase64) {
                // Determine MIME type based on file extension
                let mimeType = 'image/jpeg';
                const ext = imgSrc.toLowerCase().split('.').pop();
                if (ext === 'png') mimeType = 'image/png';
                else if (ext === 'gif') mimeType = 'image/gif';
                else if (ext === 'bmp') mimeType = 'image/bmp';
                
                // Replace with data URL
                const dataUrl = "data:" + mimeType + ";base64," + imageDataBase64;
                const newTag = "<img" + beforeSrc + "src=\\"" + dataUrl + "\\"" + afterSrc + ">";
                processedHTML = processedHTML.replace(fullTag, newTag);
                
                console.log("Successfully loaded image: " + imagePath);
            } else {
                console.log("Image not found in CHM: " + imagePath);
            }
        } catch (error) {
            console.error("Error processing image " + imgSrc + ":", error);
        }
    }
    
    // Also handle CSS background images and other image references
    // Look for style attributes and CSS url() references
    const styleRegex = /url\(["']?([^"')]+)["']?\)/gi;
    const styleMatches = [...processedHTML.matchAll(styleRegex)];
    
    for (const match of styleMatches) {
        const fullUrl = match[0];
        const imgUrl = match[1];
        
        // Skip absolute URLs and data URLs
        if (imgUrl.startsWith('http://') || imgUrl.startsWith('https://') || imgUrl.startsWith('data:')) {
            continue;
        }
        
        try {
            let imagePath = imgUrl;
            if (!imgUrl.startsWith('/')) {
                if (baseDir) {
                    imagePath = baseDir + '/' + imgUrl;
                } else {
                    imagePath = imgUrl;
                }
                imagePath = resolveRelativePath(imagePath);
            }
            
            console.log("Loading CSS background image: " + imagePath);
            
            // Get image data
            pyodide.globals.set("bg_image_path", imagePath);
            await pyodide.runPython(`
global bg_image_data_b64, bg_image_found
try:
    paths_to_try = [bg_image_path, '/' + bg_image_path, '/' + bg_image_path.lower(), bg_image_path.lower()]
    image_data = None
    for try_path in paths_to_try:
        if try_path in list_chm_files():
            image_data = get_chm_file_content(try_path)
            break
    if image_data:
        import base64
        if isinstance(image_data, str):
            image_data = image_data.encode('latin-1')
        bg_image_data_b64 = base64.b64encode(image_data).decode('ascii')
        bg_image_found = True
    else:
        bg_image_data_b64 = ""
        bg_image_found = False
except Exception as e:
    print(f"Error loading background image: {e}")
    bg_image_data_b64 = ""
    bg_image_found = False
`);
            
            const bgImageFound = pyodide.globals.get('bg_image_found');
            if (bgImageFound) {
                const bgImageDataBase64 = pyodide.globals.get('bg_image_data_b64');
                let mimeType = 'image/jpeg';
                const ext = imgUrl.toLowerCase().split('.').pop();
                if (ext === 'png') mimeType = 'image/png';
                else if (ext === 'gif') mimeType = 'image/gif';
                else if (ext === 'bmp') mimeType = 'image/bmp';
                
                const dataUrl = "data:" + mimeType + ";base64," + bgImageDataBase64;
                const newUrl = "url('" + dataUrl + "')";
                processedHTML = processedHTML.replace(fullUrl, newUrl);
                console.log("Successfully loaded CSS background image: " + imagePath);
            }
        } catch (error) {
            console.error("Error processing background image " + imgUrl + ":", error);
        }
    }
    
    return processedHTML;
}

// Load content for a specific path
async function loadContent(path) {
    try {
        updateLoadingStatus(`Loading ${path}...`);
        
        // Get file content from Python
        pyodide.globals.set("content_path", path);
        await pyodide.runPython(`
global content_data, content_success
try:
    print(f"Loading content for path: {content_path}")
    
    # Handle anchor links by removing fragment identifier
    base_path = content_path.split('#')[0] if '#' in content_path else content_path
    anchor = content_path.split('#')[1] if '#' in content_path else None
    
    # Try different path variations
    paths_to_try = [
        base_path,                       # Original path without anchor
        '/' + base_path,                 # With leading slash
        '/' + base_path.lower(),         # Lowercase with slash
        base_path.lower()                # Just lowercase
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
            # Try the first similar file
            try_path = similar[0]
            print(f"Trying similar file: {try_path}")
            content = get_chm_file_content(try_path)
            used_path = try_path
    
    print(f"Content type: {type(content)}")
    print(f"Content length: {len(content) if content else 0}")
    if content and isinstance(content, str):
        print(f"Content preview: {content[:100]}...")
        print(f"Used path: {used_path}")
    
    # Store content for JavaScript retrieval
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

        // Get the content from global variables
        const contentSuccess = pyodide.globals.get('content_success');
        const content = contentSuccess ? pyodide.globals.get('content_data') : null;
        
        const contentArea = document.getElementById('contentArea');
        
        console.log("JavaScript received content:", content);
        console.log("Content type:", typeof content);
        console.log("Content length:", content ? content.length : 0);
        
        if (content) {
            if (path.toLowerCase().endsWith('.htm') || path.toLowerCase().endsWith('.html')) {
                // Process HTML content to handle images
                const processedContent = await processHTMLContent(content, path);
                
                // For HTML content, display in iframe or directly
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
                // For other content types
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
'''
    
    return js_template

if __name__ == '__main__':
    # Generate the new chm-viewer.js
    js_content = build_chm_viewer_js()
    
    # Write to the docs directory
    with open('docs/chm-viewer.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print("✅ Generated docs/chm-viewer.js with embedded Python modules")
    print("   - Uses existing pychmlib/chm.py")
    print("   - Uses existing pychmlib/lzx.py") 
    print("   - Uses existing hhc.py")
    print("   - Removed ~300 lines of duplicate code")