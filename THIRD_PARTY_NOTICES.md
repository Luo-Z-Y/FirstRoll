# Third-party notices

## douban-mcp

- Project: `moria97/douban-mcp`
- Source: <https://github.com/moria97/douban-mcp>
- Pinned revision: `1adc26d39532db893616ceb7ea851733948ae69e`
- Declared licence: MIT (upstream README and package metadata)
- Use in FirstRoll: optional hosted MCP runtime for Douban film search and review summaries

The image build applies exact patched production dependency versions and fails when `npm audit`
reports a high-severity advisory. These compatibility overrides do not alter the connector source.

The connector's software licence does not grant rights to Douban content returned through it.
FirstRoll preserves source links and treats retrieved summaries as attributed secondary criticism.

## Path to the colorful infinity

- Work: "Path to the colorful infinity" by Benoit Marini (benoitM), 2020
- Source: <https://www.shadertoy.com/view/WtjyzR>
- Declared licence: CC BY-NC-SA 3.0 (<https://creativecommons.org/licenses/by-nc-sa/3.0/>)
- Use in FirstRoll: adapted WebGL fragment shader behind the opening screen, in
  `app/web/src/discovery/colourful-infinity.ts`

The adapted shader remains under CC BY-NC-SA 3.0, not the repository's general licence. The opening
screen links to the author, source and licence. `docs/SHADER_ATTRIBUTION.md` lists the adaptations
and the non-commercial release boundary: replace the shader or obtain the author's permission before
any commercial use. No endorsement by the author is implied.

## Pi subagent example

- Project: `earendil-works/pi`
- Source: <https://github.com/earendil-works/pi/tree/main/packages/coding-agent/examples/extensions/subagent>
- Adapted version: `@earendil-works/pi-coding-agent` 0.84.2
- Declared licence: MIT
- Use in FirstRoll: project-local Pi extension, agent discovery and isolated child-process delegation

The FirstRoll copy changes the default scope, agent prompts, model inheritance boundary, working
folder and execution caps, nested usage accounting, and repository safety guidance. The upstream MIT
notice follows.

```text
MIT License

Copyright (c) 2025 Mario Zechner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
