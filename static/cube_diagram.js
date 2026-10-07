// Renders a 2D unfolded cube net with the target face highlighted and a
// curved arrow showing which way to turn it.
const FACE_NET_POS = { U: [60, 0], L: [0, 60], F: [60, 60], R: [120, 60], B: [180, 60], D: [60, 120] };
const SVG_NS = 'http://www.w3.org/2000/svg';

function el(tag, attrs) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

function ensureArrowMarker(svg) {
  if (svg.querySelector('#arrowhead')) return;
  const defs = el('defs', {});
  const marker = el('marker', {
    id: 'arrowhead', markerWidth: '8', markerHeight: '8',
    refX: '4', refY: '4', orient: 'auto',
  });
  marker.appendChild(el('path', { d: 'M0,0 L8,4 L0,8 Z', fill: '#ffb454' }));
  defs.appendChild(marker);
  svg.appendChild(defs);
}

function renderCubeDiagram(svg, face, direction) {
  svg.innerHTML = '';
  ensureArrowMarker(svg);

  for (const [f, [fx, fy]] of Object.entries(FACE_NET_POS)) {
    const isTarget = f === face;
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) {
        svg.appendChild(el('rect', {
          x: fx + c * 20, y: fy + r * 20, width: 19, height: 19,
          fill: isTarget ? '#2a3550' : '#22252c', stroke: '#3a3f4a',
        }));
      }
    }
    svg.appendChild(el('rect', {
      x: fx, y: fy, width: 60, height: 60, fill: 'none',
      stroke: isTarget ? '#4f8cff' : '#3a3f4a', 'stroke-width': isTarget ? 3 : 1,
    }));
    const label = el('text', { x: fx + 4, y: fy + 11, fill: '#777', 'font-size': 9 });
    label.textContent = f;
    svg.appendChild(label);
  }

  const [fx, fy] = FACE_NET_POS[face];
  const cx = fx + 30, cy = fy + 30, r = 27;
  const rad = (deg) => (deg * Math.PI) / 180;
  const point = (deg) => [cx + r * Math.cos(rad(deg)), cy + r * Math.sin(rad(deg))];

  if (direction === '180') {
    const [sx, sy] = point(200);
    const [ex, ey] = point(-20);
    svg.appendChild(el('path', {
      d: `M ${sx} ${sy} A ${r} ${r} 0 1 1 ${ex} ${ey}`,
      fill: 'none', stroke: '#ffb454', 'stroke-width': 3, 'marker-end': 'url(#arrowhead)',
    }));
    const [sx2, sy2] = point(20);
    const [ex2, ey2] = point(160);
    svg.appendChild(el('path', {
      d: `M ${sx2} ${sy2} A ${r} ${r} 0 1 1 ${ex2} ${ey2}`,
      fill: 'none', stroke: '#ffb454', 'stroke-width': 3, 'marker-end': 'url(#arrowhead)',
    }));
  } else {
    const sweep = direction === 'CW' ? 1 : 0;
    const startDeg = -30;
    const endDeg = direction === 'CW' ? 230 : -290;
    const [sx, sy] = point(startDeg);
    const [ex, ey] = point(endDeg);
    svg.appendChild(el('path', {
      d: `M ${sx} ${sy} A ${r} ${r} 0 1 ${sweep} ${ex} ${ey}`,
      fill: 'none', stroke: '#ffb454', 'stroke-width': 3, 'marker-end': 'url(#arrowhead)',
    }));
  }
}
