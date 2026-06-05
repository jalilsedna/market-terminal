"""obb_layer — the ONLY place in this repo that imports OpenBB.

All OpenBB access funnels through here (SPEC.md §2). Views/services never
`import openbb` directly. This isolates the rest of the codebase from OpenBB's
API churn (endpoints get deprecated/renamed across minor releases) and gives a
single place to cache, retry, and normalize provider responses.
"""
