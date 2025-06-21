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
        html = "<html><head><title>CHM Contents</title></head><body><h1>Table of Contents</h1>"
        html += self.generate_toc_html(hhc_obj)
        html += "</body></html>"
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
            html += f"<li>{name}"
            if hasattr(child, "local") and child.local:
                html = html[: -len(name)] + f'<a href="{child.local}">{name}</a>'
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
