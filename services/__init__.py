"""services — thin domain logic per view.

Each view (SPEC.md §4) gets one service module that composes data from
`obb_layer/` into the shape its router returns. Services never import OpenBB
directly; they call `obb_layer/` functions.
"""
