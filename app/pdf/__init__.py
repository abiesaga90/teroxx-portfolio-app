"""PDF helpers: SVG exhibits, narrative generator, brand palette.

The proposal PDF is rendered by WeasyPrint from a Jinja template; this
package owns the pure-Python helpers the template depends on so they can
be unit-tested in isolation and reused by HTML surfaces (Workspace,
Client View) without dragging WeasyPrint along.
"""
