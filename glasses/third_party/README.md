# Third-party code

## rubikscolorresolver

Unmodified copy of [dwalton76/rubiks-color-resolver](https://github.com/dwalton76/rubiks-color-resolver)
at commit `c1a7211dd15a82589fc1454f630450ac26e5b44b` (2022-10-28). MIT licence
(`rubikscolorresolver/LICENSE`).

Vendored because it isn't on PyPI and its package doesn't build with pip.
It is pure Python with no dependencies. We use it as the colour fallback in
`cube/color_detect.py` (`resolver_colors`) when our centre-based rebalance
produces an invalid cube; in our benchmark the combination got 98% of cubes
fully right in normal light vs 96% / 94% for either method alone.

Note: importing it deletes `/tmp/rubiks-color-resolver.html` (its own debug
file); it only writes that file when `write_debug_file` is enabled, which we
never do.
