/**
 * Owned WebGL2 dense renderer — device setup helper only.
 * Product semantics (scales, picking, domain) stay in JS.
 * Falls back to Canvas2D when WebGL2 unavailable.
 */

function compile(gl, type, src) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const log = gl.getShaderInfoLog(shader);
        gl.deleteShader(shader);
        throw new Error(`WebGL shader compile failed: ${log}`);
    }
    return shader;
}

function link(gl, vs, fs) {
    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        const log = gl.getProgramInfoLog(prog);
        gl.deleteProgram(prog);
        throw new Error(`WebGL link failed: ${log}`);
    }
    return prog;
}

export function createWebGLContext(canvas) {
    const gl = canvas.getContext('webgl2', { antialias: true, alpha: false });
    if (!gl) return null;
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    return gl;
}

export function createDenseProgram(gl) {
    const vs = `#version 300 es
    in vec2 a_pos;
    uniform vec2 u_scale;
    uniform vec2 u_translate;
    void main() {
        vec2 p = a_pos * u_scale + u_translate;
        p = p * 2.0 - 1.0;
        p.y = -p.y;
        gl_Position = vec4(p, 0.0, 1.0);
    }`;
    const fs = `#version 300 es
    precision mediump float;
    uniform vec4 u_color;
    out vec4 outColor;
    void main() { outColor = u_color; }`;
    const prog = link(gl, compile(gl, gl.VERTEX_SHADER, vs), compile(gl, gl.FRAGMENT_SHADER, fs));
    const aPos = gl.getAttribLocation(prog, 'a_pos');
    const uScale = gl.getUniformLocation(prog, 'u_scale');
    const uTranslate = gl.getUniformLocation(prog, 'u_translate');
    const uColor = gl.getUniformLocation(prog, 'u_color');
    const buf = gl.createBuffer();
    return { gl, prog, aPos, uScale, uTranslate, uColor, buf };
}

/**
 * Draw dense scatter/paths as line strips on WebGL.
 * Falls back to Canvas2D caller if gl is null.
 * Returns true if WebGL drew, false if fallback needed.
 */
export function drawDensePathsGL(glCtx, { paths, width, height, minV, maxV, color = 'rgba(52,211,153,0.11)' }) {
    if (!glCtx) return false;
    const { gl, prog, aPos, uScale, uTranslate, uColor, buf } = glCtx;
    const c = parseColor(color);
    gl.viewport(0, 0, width * (window.devicePixelRatio || 1), height * (window.devicePixelRatio || 1));
    gl.clearColor(0.02, 0.04, 0.08, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(prog);
    gl.uniform2f(uScale, 1 / width, 1 / height);
    gl.uniform2f(uTranslate, 0, 0);
    gl.uniform4f(uColor, c.r / 255, c.g / 255, c.b / 255, c.a);
    // Draw each path as line strip
    paths.forEach((path) => {
        if (path.length < 2) return;
        const verts = new Float32Array(path.length * 2);
        for (let i = 0; i < path.length; i += 1) {
            const x = (i / (path.length - 1)) * width;
            const y = height - ((path[i] - minV) / (maxV - minV || 1)) * height;
            verts[i * 2] = x;
            verts[i * 2 + 1] = y;
        }
        gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(aPos);
        gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
        gl.drawArrays(gl.LINE_STRIP, 0, path.length);
    });
    return true;
}

function parseColor(c) {
    const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+),?\s*([\d.]+)?\)/);
    if (m) return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] ? Number(m[4]) : 1 };
    const h = c.match(/^#([0-9a-f]{6})$/i);
    if (h) { const n = parseInt(h[1], 16); return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 }; }
    return { r: 52, g: 211, b: 153, a: 0.11 };
}

export function isWebGLAvailable() {
    try {
        const c = document.createElement('canvas');
        return !!c.getContext('webgl2');
    } catch { return false; }
}
