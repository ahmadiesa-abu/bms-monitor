/**
 * Instrument-panel needle gauge, rendered as inline SVG.
 * Sweeps 270deg starting at 135deg (bottom-left) through to 405deg (bottom-right),
 * matching a classic speedometer / BMS analog-gauge layout.
 */
(function (global) {
  const START_ANGLE = 135;
  const SWEEP = 270;

  function polar(cx, cy, r, angleDeg) {
    const rad = (angleDeg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function arcPath(cx, cy, r, a0, a1) {
    const p0 = polar(cx, cy, r, a0);
    const p1 = polar(cx, cy, r, a1);
    const largeArc = a1 - a0 > 180 ? 1 : 0;
    return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${r} ${r} 0 ${largeArc} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
  }

  /**
   * Rounds a number up to a "nice" scale ceiling (1/2/5/10 * 10^n).
   */
  function niceCeil(value) {
    if (value <= 0) return 10;
    const exp = Math.floor(Math.log10(value));
    const base = Math.pow(10, exp);
    const frac = value / base;
    let niceFrac;
    if (frac <= 1) niceFrac = 1;
    else if (frac <= 2) niceFrac = 2;
    else if (frac <= 5) niceFrac = 5;
    else niceFrac = 10;
    return niceFrac * base;
  }

  /**
   * opts: { min, max, value, label, unit, decimals, majorStep, size }
   */
  function renderGauge(container, opts) {
    const el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) return;

    const min = opts.min;
    const max = opts.max;
    const value = Math.min(Math.max(opts.value, min), max);
    const decimals = opts.decimals != null ? opts.decimals : 1;
    const size = opts.size || 220;
    const cx = size / 2;
    const cy = size / 2 + 6;
    const r = size * 0.38;
    const tickR = r + 12;
    const labelR = r + 28;

    const frac = (value - min) / (max - min);
    const needleAngle = START_ANGLE + frac * SWEEP;

    // ticks
    const majorStep = opts.majorStep || niceCeil((max - min) / 8);
    const ticks = [];
    for (let v = min; v <= max + 1e-6; v += majorStep) {
      const t = Math.min((v - min) / (max - min), 1);
      const angle = START_ANGLE + t * SWEEP;
      ticks.push({ v, angle });
    }
    const minorPerMajor = 4;
    const minorTicks = [];
    for (let i = 0; i < ticks.length - 1; i++) {
      for (let j = 1; j < minorPerMajor; j++) {
        const t = i / (ticks.length - 1) + (j / minorPerMajor) * (1 / (ticks.length - 1));
        minorTicks.push(START_ANGLE + t * SWEEP);
      }
    }

    const zeroAngle = min < 0 && max > 0 ? START_ANGLE + ((0 - min) / (max - min)) * SWEEP : null;

    let ticksSvg = '';
    minorTicks.forEach((angle) => {
      const p0 = polar(cx, cy, tickR - 3, angle);
      const p1 = polar(cx, cy, tickR + 2, angle);
      ticksSvg += `<line x1="${p0.x.toFixed(2)}" y1="${p0.y.toFixed(2)}" x2="${p1.x.toFixed(2)}" y2="${p1.y.toFixed(2)}" stroke="var(--edge-bright)" stroke-width="1"/>`;
    });

    let majorSvg = '';
    let labelsSvg = '';
    ticks.forEach(({ v, angle }) => {
      const p0 = polar(cx, cy, tickR - 5, angle);
      const p1 = polar(cx, cy, tickR + 6, angle);
      majorSvg += `<line x1="${p0.x.toFixed(2)}" y1="${p0.y.toFixed(2)}" x2="${p1.x.toFixed(2)}" y2="${p1.y.toFixed(2)}" stroke="var(--teal)" stroke-width="2" stroke-linecap="round"/>`;
      const lp = polar(cx, cy, labelR, angle);
      const label = Math.abs(v) >= 100 ? Math.round(v) : (Number.isInteger(v) ? v : v.toFixed(0));
      labelsSvg += `<text x="${lp.x.toFixed(2)}" y="${lp.y.toFixed(2)}" text-anchor="middle" dominant-baseline="middle" font-family="var(--font-mono)" font-size="9" fill="var(--ink-faint)">${label}</text>`;
    });

    const trackPath = arcPath(cx, cy, r, START_ANGLE, START_ANGLE + SWEEP);
    const valuePath = frac > 0.002 ? arcPath(cx, cy, r, START_ANGLE, needleAngle) : '';

    let zeroMark = '';
    if (zeroAngle != null) {
      const p0 = polar(cx, cy, r - 8, zeroAngle);
      const p1 = polar(cx, cy, r + 8, zeroAngle);
      zeroMark = `<line x1="${p0.x.toFixed(2)}" y1="${p0.y.toFixed(2)}" x2="${p1.x.toFixed(2)}" y2="${p1.y.toFixed(2)}" stroke="var(--ink-dim)" stroke-width="1.5"/>`;
    }

    const needleLen = r - 14;
    const needleTip = polar(cx, cy, needleLen, needleAngle);
    const needleBackAngle1 = needleAngle + 90;
    const needleBackAngle2 = needleAngle - 90;
    const backW = 5;
    const b1 = polar(cx, cy, backW, needleBackAngle1);
    const b2 = polar(cx, cy, backW, needleBackAngle2);

    const svg = `
<svg class="gauge-svg" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
  <path d="${trackPath}" fill="none" stroke="var(--edge)" stroke-width="4" stroke-linecap="round"/>
  ${valuePath ? `<path d="${valuePath}" fill="none" stroke="var(--teal)" stroke-width="4" stroke-linecap="round" opacity="0.55"/>` : ''}
  ${ticksSvg}
  ${majorSvg}
  ${labelsSvg}
  ${zeroMark}
  <line x1="${b1.x.toFixed(2)}" y1="${b1.y.toFixed(2)}" x2="${needleTip.x.toFixed(2)}" y2="${needleTip.y.toFixed(2)}" stroke="var(--crimson)" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="${b2.x.toFixed(2)}" y1="${b2.y.toFixed(2)}" x2="${needleTip.x.toFixed(2)}" y2="${needleTip.y.toFixed(2)}" stroke="var(--crimson)" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="${cx}" cy="${cy}" r="6" fill="var(--surface-raised)" stroke="var(--crimson)" stroke-width="2"/>
</svg>`;

    el.innerHTML = `
      <div class="gauge-label">${opts.label || ''}</div>
      ${svg}
      <div class="gauge-readout">${value.toFixed(decimals)}<span style="color:var(--ink-faint);font-size:11px;margin-left:4px;">${opts.unit || ''}</span></div>
    `;
  }

  /**
   * Renders a circular progress ring (used for state-of-charge).
   */
  function renderRing(container, opts) {
    const el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) return;
    const pct = Math.min(Math.max(opts.value, 0), 100);
    const size = opts.size || 130;
    const stroke = 10;
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const offset = c - (pct / 100) * c;
    const color = pct < 20 ? 'var(--crimson)' : pct < 40 ? 'var(--amber)' : 'var(--lime)';

    el.innerHTML = `
      <div class="capacity-ring-wrap" style="width:${size}px;height:${size}px;">
        <svg viewBox="0 0 ${size} ${size}">
          <circle class="capacity-ring-track" cx="${size / 2}" cy="${size / 2}" r="${r}"/>
          <circle class="capacity-ring-fill" cx="${size / 2}" cy="${size / 2}" r="${r}"
            stroke="${color}" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"/>
        </svg>
        <div class="capacity-ring-value">${Math.round(pct)}%</div>
      </div>
    `;
  }

  function niceSymmetric(absMax) {
    return niceCeil(Math.max(absMax, 1) * 1.2);
  }

  global.BmsGauge = { renderGauge, renderRing, niceCeil, niceSymmetric };
})(window);
