/*!
 * "Path to the colorful infinity" by Benoit Marini (benoitM), 2020.
 * Source: https://www.shadertoy.com/view/WtjyzR
 * Licence: CC BY-NC-SA 3.0, https://creativecommons.org/licenses/by-nc-sa/3.0/
 * This adapted fragment shader remains under CC BY-NC-SA 3.0, not the repository's general
 * licence. Non-commercial use only; share adaptations under the same licence.
 * Adaptations: WebGL uniforms/entry point, portable loop syntax and opaque canvas alpha.
 * The original fractal, layer count, colour calculation and time multipliers are retained.
 * Full attribution and the list of changes: docs/SHADER_ATTRIBUTION.md in the FirstRoll repository.
 */
export const colourfulInfinityFragment = `
precision highp float;
uniform vec2 resolution;
uniform float time;
#define NUM_LAYERS 16.
#define ITER 23

vec4 tex(vec3 p) {
  float t = time + 78.;
  vec4 o = vec4(p.xyz, 3. * sin(t * .1));
  vec4 dec = vec4(1., .9, .1, .15) + vec4(.06 * cos(t * .1), 0., 0., .14 * cos(t * .23));
  for (int i = 0; i < ITER; i++) o.xzyw = abs(o / dot(o, o) - dec);
  return o;
}

void main() {
  vec2 uv = (gl_FragCoord.xy - resolution.xy * .5) / resolution.y;
  vec3 col = vec3(0.);
  float t = time * .3;
  for (float i = 0.; i <= 1.; i += 1. / NUM_LAYERS) {
    float d = fract(i + t);
    float s = mix(5., .5, d);
    float f = d * smoothstep(1., .9, d);
    col += tex(vec3(uv * s, i * 4.)).xyz * f;
  }
  col /= NUM_LAYERS;
  col *= vec3(2., 1., 2.);
  col = pow(col, vec3(.5));
  gl_FragColor = vec4(col, 1.);
}
`;
