# Shader attribution

- **Work:** Path to the colorful infinity
- **Author:** Benoit Marini (benoitM), 2020
- **Source:** https://www.shadertoy.com/view/WtjyzR
- **Licence:** https://creativecommons.org/licenses/by-nc-sa/3.0/
- **Licence text:** https://creativecommons.org/licenses/by-nc-sa/3.0/legalcode

The author's source and licence header were verified on the original Shadertoy page on
7 October 2026. The title retains its original spelling.

`app/web/src/discovery/colourful-infinity.ts` contains the adapted fragment shader and remains
under CC BY-NC-SA 3.0, separately from the repository's general licence. Retain this attribution
and licence when redistributing it. The opening screen shows visible author, source and licence
links, and the file's `/*! ... */` licence comment is kept in the minified release bundle.
`THIRD_PARTY_NOTICES.md` lists the work alongside FirstRoll's other third-party material.

## Changes

- Shadertoy uniforms `iTime` and `iResolution` become `time` and `resolution`.
- `mainImage` becomes the WebGL `main` entry point; output alpha is opaque for the canvas.
- The inner loop uses ordinary WebGL-compatible loop syntax with the same 23 iterations.
- Fractal maths, 16-layer setting (including the original inclusive endpoint), RGB multipliers
  and time multipliers are unchanged. No greyscale, theme tint, blur or opacity filter is added.
- FirstRoll's separate controller caps rendering resolution/frame rate, pauses elapsed time
  when inactive, and supplies pause/reduced-motion/failure handling. Exact pixels can vary with
  viewport dimensions, elapsed time, resolution and GPU implementation.

## Release boundary

On 18 October 2026 the owner decided to ship the shader on FirstRoll's free, non-commercial
public beta. That release depends on these conditions:

- **Attribution:** the shader appears only on the opening screen, which shows visible links to the
  author and Shadertoy source and to the CC BY-NC-SA 3.0 licence whenever it is displayed. This
  file and the source comment record the changes.
- **Non-commercial:** FirstRoll stays free, with no advertising, sponsorship, paid tiers or other
  monetisation while the shader is in use.
- **Share-alike:** the adapted shader, and any further adaptation of it, is distributed only under
  CC BY-NC-SA 3.0, regardless of the repository's general licence.

Before any commercial use, including monetisation, sponsorship or paid tiers, replace the shader
or obtain the author's written permission. Do not assume the wider repository's licence permits
commercial release of this file. No endorsement by the artist is implied. The licence includes a
disclaimer of warranties.
