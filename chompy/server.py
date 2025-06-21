# Copyright 2009 Wayne See
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pychmlib.chm import chm

import socket
import threading
import hhc
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote
import os

HOST = "127.0.0.1"
PORT = 8081

TYPES = {
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".css": "text/css",
    ".js": "application/javascript",
    ".mht": "multipart/related",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}

ERR_NO_HHC = 1
ERR_INVALID_CHM = 2

server_instance = None


def start(filename, hhc_callback=None):
    global server_instance
    server_instance = CHMHTTPServer((HOST, PORT), filename, hhc_callback)
    thread = threading.Thread(target=server_instance.serve_forever)
    thread.daemon = True
    thread.start()
    return server_instance


def stop():
    global server_instance
    if server_instance:
        server_instance.shutdown()
        server_instance = None


class CHMRequestHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Handle HEAD requests by calling do_GET but not sending content"""
        self._head_request = True
        self.do_GET()
    
    def do_GET(self):
        try:
            # Remove leading slash and decode URL
            path = unquote(self.path.lstrip("/"))

            if not path:
                self.send_index_page()
                return

            # Get file from CHM
            ui = self.server.chm_file.resolve_object("/" + path)
            if ui:
                content = ui.get_content()
                # Determine content type
                extension = os.path.splitext(path)[1].lower()
                content_type = TYPES.get(extension, "text/html")

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()

                # Only send content for GET requests, not HEAD requests
                if not getattr(self, '_head_request', False):
                    if isinstance(content, str):
                        self.wfile.write(content.encode("utf-8"))
                    else:
                        self.wfile.write(content)
            else:
                self.send_error(404, f"File not found: {path}")
        except Exception as e:
            print(f"Error serving request: {e}")
            self.send_error(500, "Internal server error")

    def send_index_page(self):
        """Send a simple index page with CHM table of contents"""
        try:
            hhc_file = self.server.chm_file.get_hhc()
            if hhc_file:
                contents = hhc.parse(hhc_file.get_content())
                html = self.generate_index_html(contents)
            else:
                html = "<html><body><h1>CHM File</h1><p>No table of contents available</p></body></html>"

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            
            # Only send content for GET requests, not HEAD requests
            if not getattr(self, '_head_request', False):
                self.wfile.write(html.encode("utf-8"))
        except Exception as e:
            print(f"Error generating index: {e}")
            self.send_error(500, "Error generating index")

    def generate_index_html(self, hhc_obj):
        """Generate HTML index from HHC object"""
        html = '''<!DOCTYPE html>
<html>
<head>
    <title>CHM Contents</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 300px;
            background-color: #f5f5f5;
            border-right: 1px solid #ccc;
            overflow-y: auto;
            padding: 10px;
            box-sizing: border-box;
        }
        
        .content {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }
        
        .sidebar h2 {
            margin-top: 0;
            color: #333;
            font-size: 16px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        
        .sidebar ul {
            list-style-type: none;
            padding-left: 0;
            margin: 0;
        }
        
        .sidebar li {
            margin: 2px 0;
        }
        
        .sidebar ul ul {
            padding-left: 20px;
            margin-top: 5px;
        }
        
        .sidebar a {
            color: #0066cc;
            text-decoration: none;
            display: block;
            padding: 3px 5px;
            border-radius: 3px;
            font-size: 13px;
        }
        
        .sidebar a:hover {
            background-color: #e6f3ff;
            text-decoration: underline;
        }
        
        .sidebar a.current {
            background-color: #0066cc;
            color: white;
            font-weight: bold;
        }
        
        .sidebar a.current:hover {
            background-color: #0052a3;
            color: white;
        }
        
        .sidebar .folder {
            font-weight: bold;
            color: #333;
            padding: 3px 5px;
            cursor: pointer;
            user-select: none;
        }
        
        .sidebar .folder:hover {
            background-color: #e0e0e0;
            border-radius: 3px;
        }
        
        .sidebar .folder:before {
            content: "▾ ";
            font-size: 10px;
            margin-right: 5px;
            display: inline-block;
            width: 10px;
        }
        
        .sidebar .folder.collapsed:before {
            content: "▸ ";
        }
        
        .sidebar .collapsed + ul {
            display: none;
        }
        
        .welcome-text {
            color: #666;
            line-height: 1.6;
        }
        
        iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        #contentFrame {
            display: none;
        }
        
        .content.with-frame {
            padding: 0;
        }
    </style>
    <script>
        function loadContent(path) {
            const welcomeDiv = document.querySelector('.welcome-text');
            const contentDiv = document.querySelector('.content');
            let iframe = document.getElementById('contentFrame');
            
            if (!iframe) {
                iframe = document.createElement('iframe');
                iframe.id = 'contentFrame';
                iframe.src = path;
                contentDiv.appendChild(iframe);
            } else {
                iframe.src = path;
            }
            
            // Hide welcome text and show iframe
            if (welcomeDiv) {
                welcomeDiv.style.display = 'none';
            }
            iframe.style.display = 'block';
            contentDiv.classList.add('with-frame');
            
            // Update current page highlighting
            updateCurrentPageHighlight(path);
        }
        
        function updateCurrentPageHighlight(currentPath) {
            // Remove current class from all links
            const allLinks = document.querySelectorAll('.sidebar a');
            allLinks.forEach(function(link) {
                link.classList.remove('current');
            });
            
            // Find and highlight the current page
            const currentLink = document.querySelector(`.sidebar a[href="javascript:loadContent('${currentPath}')"]`);
            if (currentLink) {
                currentLink.classList.add('current');
                
                // Ensure parent folders are expanded
                let parent = currentLink.parentElement;
                while (parent) {
                    if (parent.tagName === 'UL') {
                        const folder = parent.previousElementSibling;
                        if (folder && folder.classList.contains('folder')) {
                            folder.classList.remove('collapsed');
                        }
                    }
                    parent = parent.parentElement;
                }
            }
        }
        
        function toggleFolder(element) {
            element.classList.toggle('collapsed');
        }
        
        // Add click handlers to folders when page loads
        document.addEventListener('DOMContentLoaded', function() {
            const folders = document.querySelectorAll('.folder');
            folders.forEach(function(folder) {
                folder.addEventListener('click', function() {
                    toggleFolder(this);
                });
            });
            
            // Optionally load the first page automatically
            const firstLink = document.querySelector('.sidebar a[href*="loadContent"]');
            if (firstLink) {
                // Extract the path from the href
                const href = firstLink.getAttribute('href');
                const match = href.match(/loadContent\('([^']+)'\)/);
                if (match) {
                    const firstPath = match[1];
                    // Uncomment the next line to auto-load the first page
                    // loadContent(firstPath);
                }
            }
        });
    </script>
</head>
<body>
    <div class="sidebar">
        <h2>Table of Contents</h2>
'''
        html += self.generate_toc_html(hhc_obj)
        html += '''
    </div>
    <div class="content">
        <div class="welcome-text">
            <h1>CHM File Viewer</h1>
            <p>Welcome to the CHM file viewer. Use the table of contents on the left to navigate through the documentation.</p>
            <p>Click on any link in the sidebar to view that page's content.</p>
        </div>
    </div>
</body>
</html>'''
        return html

    def generate_toc_html(self, node):
        """Recursively generate TOC HTML"""
        html = "<ul>"
        for child in node.children:
            name = (
                child.name.decode(self.server.chm_file.encoding)
                if hasattr(child.name, "decode")
                else str(child.name)
            )
            
            # Skip items with no name
            if not name or name == "None":
                continue
                
            html += "<li>"
            
            # If it has a local link, make it clickable
            if hasattr(child, "local") and child.local:
                html += f'<a href="javascript:loadContent(\'{child.local}\')">{name}</a>'
            else:
                # If it's a folder (has children but no local link), style as folder
                if hasattr(child, "children") and child.children:
                    html += f'<span class="folder">{name}</span>'
                else:
                    html += f'<span class="folder">{name}</span>'
            
            # Add nested children
            if hasattr(child, "children") and child.children:
                html += self.generate_toc_html(child)
            
            html += "</li>"
        html += "</ul>"
        return html

    def log_message(self, format, *args):
        """Override to reduce console spam"""
        # Uncomment for debugging:
        # print(f"[{self.address_string()}] {format % args}")
        pass


class CHMHTTPServer(HTTPServer):
    def __init__(self, server_address, chm_filename, hhc_callback=None):
        try:
            self.chm_file = chm(chm_filename)
        except Exception as e:
            print(f"Error opening CHM file: {e}")
            if hhc_callback:
                hhc_callback(error=ERR_INVALID_CHM)
            raise

        # Process HHC callback if provided
        if hhc_callback:
            hhc_file = self.chm_file.get_hhc()
            if hhc_file:
                contents = hhc.parse(hhc_file.get_content())
                encoding = self.chm_file.encoding
                hhc_callback(chm_filename, contents, encoding)
            else:
                self.chm_file.close()
                hhc_callback(error=ERR_NO_HHC)
                raise Exception("No HHC file found")

        super().__init__(server_address, CHMRequestHandler)
        print(f"CHM server started on http://{server_address[0]}:{server_address[1]}/")

    def shutdown(self):
        super().shutdown()
        if hasattr(self, "chm_file"):
            self.chm_file.close()
        print("CHM server stopped")


if __name__ == "__main__":
    import sys

    filenames = sys.argv[1:]
    if filenames:
        start(filenames.pop())
        # serve chm files for 30 seconds
        import time

        time.sleep(30)
        stop()
    else:
        print("Please provide a CHM file as parameter")
