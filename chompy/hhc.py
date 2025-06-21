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

from html.parser import HTMLParser

import re

_ESCAPE_PARAM_VALUE = re.compile(r'\s<param name=".*" value="(.*"+.*)">\s')


class HHCParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self._contexts = []

    def handle_starttag(self, tag, attrs):
        if tag == "object":
            self._object = HHCObject()
            self._object.__dict__.update(dict(attrs))
        elif tag == "param":
            if hasattr(self, '_object'):
                param = dict(attrs)
                self._object.__dict__[param["name"].lower()] = param["value"]
        elif tag == "ul":
            # For UL tags, we need to set the last sitemap object as an inner node
            # Look for the most recent sitemap object that could be a parent
            if self._contexts:
                # Use the current context
                pass  # Already handled
            elif hasattr(self, '_last_sitemap_object'):
                # Make the last sitemap object a container
                self._last_sitemap_object._set_as_inner_node()
                self._contexts.append(self._last_sitemap_object)

    def handle_endtag(self, tag):
        if tag == "object":
            if hasattr(self, '_object'):
                # Ignore site properties objects, only process sitemap objects
                if getattr(self._object, 'type', None) == 'text/sitemap':
                    # Remember this as the last sitemap object
                    self._last_sitemap_object = self._object
                    
                    if not self._contexts:
                        # Create a root context if this is the first sitemap object
                        if not hasattr(self, 'root_context'):
                            root = HHCObject()
                            root.is_root = True
                            root._set_as_inner_node()
                            root.name = "Table of Contents"
                            self.root_context = root
                        self.root_context.add_child(self._object)
                    else:
                        # add the object to the top of the stack's HHCObject
                        if hasattr(self._contexts[-1], 'children'):
                            self._contexts[-1].add_child(self._object)
        elif tag == "ul":
            if self._contexts:
                self._contexts.pop()


class HHCObject:

    def __init__(self):
        self.type = None
        self.is_inner_node = False  # means this node has leaves
        self.is_root = False
        self.parent = None
        self.name = None
        self.local = None

    def _set_as_inner_node(self):
        self.is_inner_node = True
        self.children = []

    def add_child(self, obj):
        self.children.append(obj)
        obj.parent = self


def _sanitize(html):
    return re.sub(_ESCAPE_PARAM_VALUE, _replace_param, html)


def _replace_param(match_obj):
    param = match_obj.group(0)
    value = match_obj.group(1)
    return param.replace(value, value.replace('"', "&quot;"))


def parse(html):
    # Handle both bytes and string input
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")
    html = _sanitize(html)
    parser = HHCParser()
    parser.feed(html)
    parser.close()
    # Ensure root context has children attribute
    if hasattr(parser, 'root_context') and parser.root_context:
        if not hasattr(parser.root_context, 'children'):
            parser.root_context._set_as_inner_node()
        return parser.root_context
    else:
        # Create a dummy root if no content was parsed
        root = HHCObject()
        root.is_root = True
        root._set_as_inner_node()
        root.name = "Root"
        return root


if __name__ == "__main__":
    import sys
    from pychmlib.chm import chm

    filenames = sys.argv[1:]
    if filenames:
        chm_file = chm(filenames.pop())
        hhc_file_contents = chm_file.get_hhc().get_content()
        contents = parse(hhc_file_contents)

        def recur_print(content, spaces=0):
            if spaces > 0:
                tab = " " * spaces
                print(tab + content.name)
                if content.local:
                    print(tab + "(" + content.local + ")")
            if content.is_inner_node:
                for i in content.children:
                    recur_print(i, spaces + 2)

        recur_print(contents)
        chm_file.close()
    else:
        print("Please provide a CHM file as parameter")
