import { useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';

const THEME = {
  start: { f: '#dcfce7', s: '#22c55e', a: '#4ade80' },
  end: { f: '#fee2e2', s: '#ef4444', a: '#f87171' },
  condition: { f: '#fef3c7', s: '#f59e0b', a: '#fbbf24' },
  loop: { f: '#fef3c7', s: '#f59e0b', a: '#fbbf24' },
  process: { f: '#e0f2fe', s: '#0ea5e9', a: '#38bdf8' },
  io: { f: '#e0e7ff', s: '#6366f1', a: '#818cf8' }
};

// A join node is a structural convergence point — rendered as a small dot.
// The CFG builder sets label='↓' and statements[0].code='join' for these.
function isJoinNode(node) {
  if (!node) return false;
  const lbl = (node.label || '').trim();
  if (lbl === '↓' || lbl === 'join') return true;
  const code = (node.statements?.[0]?.code || '').toLowerCase().trim();
  return code === 'join';
}

export default function Flowchart({ layout, currentStep, trace }) {
  const svgRef       = useRef(null);
  const containerRef = useRef(null);
  const prevActiveRef = useRef(null);
  const offsetXRef   = useRef(0); // tracks the SVG content group's x translation

  // ─── Map: join node id → originating decision/loop node id ──────────────────
  // Used to redirect the explainer bubble to the decision diamond when the
  // tracer lands on a join node (which has no semantic label of its own).
  const decisionForJoin = useCallback(() => {
    if (!layout?.nodes || !layout?.edges) return {};
    const map = {};
    layout.nodes.forEach(join => {
      if (!isJoinNode(join)) return;
      layout.edges
        .filter(e => e.to === join.id)
        .forEach(edge => {
          const src = layout.nodes.find(n => n.id === edge.from);
          if (src && (src.type === 'condition' || src.type === 'loop')) {
            map[join.id] = src.id;
          }
        });
    });
    return map;
  }, [layout]);

  // ─── Derive rich context for a given step index ──────────────────────────────
  const getCtx = useCallback((idx) => {
    const s = trace?.steps?.[idx];
    if (!s || !layout?.nodes) return null;

    const djMap  = decisionForJoin();
    const activeId = s.active_node_id;

    // If landing on a join node, show the explanation on the decision that owns it
    const explanationNodeId = djMap[activeId] ?? activeId;

    const node            = layout.nodes.find(n => n.id === activeId);
    const explanationNode = layout.nodes.find(n => n.id === explanationNodeId);
    const next            = trace.steps[idx + 1];

    let explanation = s.explanation || s.ai_explanation || '';

    if (!explanation && explanationNode) {
      const t    = explanationNode.type;
      const vars = s.variables || {};
      if (t === 'condition' || t === 'loop') {
        const parts   = explanationNode.label.split(/([<>!=]+)/);
        const lhs     = parts[0]?.trim() ?? '';
        const op      = parts[1]?.trim() ?? '?';
        const rhs     = parts[2]?.trim() ?? '?';
        const lhsVal  = vars[lhs] !== undefined ? vars[lhs] : lhs;
        const nextEdge = next
          ? layout.edges.find(e => e.from === explanationNodeId && e.to === next.active_node_id)
          : null;
        const result = nextEdge ? !nextEdge.is_false : null;
        explanation = `Is ${lhsVal} ${op} ${rhs}? → ${result === true ? 'Yes!' : result === false ? 'No.' : ''}`;
      } else if (explanationNode.label.toLowerCase().includes('print')) {
        explanation = 'Outputting result to the console.';
      } else if (explanationNode.label.includes('=')) {
        explanation = `Memory Update: ${explanationNode.label.replace('=', 'is now')}`;
      }
    }

    // Determine branch result for conditional colour
    let res = null;
    if ((explanationNode?.type === 'condition' || explanationNode?.type === 'loop') && next) {
      const nextEdge = layout.edges.find(e => e.from === explanationNodeId && e.to === next.active_node_id);
      if (nextEdge) res = !nextEdge.is_false;
    }

    return { step: s, node, explanationNodeId, explanation, activeId, res };
  }, [trace, layout, decisionForJoin]);

  // ─── Build SVG whenever layout changes ──────────────────────────────────────
  useEffect(() => {
    if (!layout?.nodes?.length || !containerRef.current) return;

    // ── Compute the true bounding box of all content ─────────────────────────
    // Nodes are centred on their (x, y), so their left edge is x - width/2.
    // Branches that go LEFT of the layout origin produce negative x values,
    // which the SVG clips because SVG coordinates start at 0. We fix this by
    // computing the leftmost extent, then translating the entire content group
    // right by that amount (+ padding) so nothing sits at a negative coordinate.
    const PAD = 120;

    const extMinX = Math.min(
      ...layout.nodes.map(n => n.x - n.width  / 2),
      ...layout.edges.flatMap(e => (e.points || []).map(p => p[0]))
    );
    const extMaxX = Math.max(
      ...layout.nodes.map(n => n.x + n.width  / 2),
      ...layout.edges.flatMap(e => (e.points || []).map(p => p[0]))
    );
    const extMaxY = Math.max(
      ...layout.nodes.map(n => n.y + n.height / 2),
      ...layout.edges.flatMap(e => (e.points || []).map(p => p[1]))
    );

    // Amount to shift all content rightward so the leftmost element clears PAD
    const offsetX = extMinX < PAD ? PAD - extMinX : 0;

    const W = Math.max(containerRef.current.clientWidth || 800, extMaxX + offsetX + PAD);
    const H = Math.max(600, extMaxY + PAD);

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', W).attr('height', H);

    // Defs: arrowheads + glow filter
    const defs = svg.append('defs');
    [['normal', '#94a3b8'], ['loop', '#3b82f6'], ['true', '#22c55e'], ['false', '#ef4444']].forEach(([id, c]) =>
      defs.append('marker')
        .attr('id', `arrow-${id}`)
        .attr('viewBox', '0 0 10 10').attr('refX', 10).attr('refY', 5)
        .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
        .append('path').attr('d', 'M0 0L10 5L0 10z').attr('fill', c));

    defs.append('filter').attr('id', 'glow')
      .html('<feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>');

    // Single translate so every node and edge shifts right together
    const g = svg.append('g').attr('transform', `translate(${offsetX}, 0)`);
    offsetXRef.current = offsetX;
    const nodeMap = Object.fromEntries(layout.nodes.map(n => [n.id, n]));

    // ── Edges ────────────────────────────────────────────────────────────────
    layout.edges.forEach(e => {
      const [f, t] = [nodeMap[e.from], nodeMap[e.to]];
      if (!f || !t) return;

      const isBack  = !!e.is_back_edge;
      const isTrue  = !!e.is_true;
      const isFalse = !!e.is_false;
      let pts = e.points ? e.points.map(p => [...p]) : [];

      // ── Fix join-node endpoint: the layout routes edges to y - height/2
      //    but join nodes render as a small circle (r=6). Snap the final
      //    point to the actual circle boundary so the arrowhead touches it.
      const JOIN_R = 6;
      

      // ── Fix join-node exit: edges leaving a join node should start at the
      //    circle boundary, not at the process-node bottom (height/2 below centre).
      if (isJoinNode(f) && pts.length >= 2) {
        const first = pts[0];
        const next  = pts[1];
        const dx = next[0] - first[0];
        const dy = next[1] - first[1];
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
          pts[0] = [f.x + (dx / len) * JOIN_R, f.y + (dy / len) * JOIN_R];
        }
      }

      const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]} ${p[1]}`).join(' ');
      const color   = isBack ? '#3b82f6' : isTrue ? '#22c55e' : isFalse ? '#ef4444' : '#94a3b8';
      const markerId = isBack ? 'loop' : isTrue ? 'true' : isFalse ? 'false' : 'normal';

      const eg = g.append('g').attr('class', 'edge').attr('data-from', e.from).attr('data-to', e.to);

      eg.append('path')
        .attr('class', 'edge-path')
        .attr('d', d)
        .attr('stroke', color)
        .attr('stroke-width', 2.5)
        .attr('fill', 'none')
        .attr('marker-end', `url(#arrow-${markerId})`);

      // Particle that rides the path during step transitions
      eg.append('circle')
        .attr('class', 'pulse-particle')
        .attr('r', 5)
        .attr('fill', color)
        .attr('filter', 'url(#glow)')
        .style('opacity', 0);

      if (e.label) {
        const mid = pts[Math.floor(pts.length / 2)];
        eg.append('text')
          .attr('x', mid[0]).attr('y', mid[1] - 6)
          .attr('text-anchor', 'middle')
          .attr('font-size', '10px').attr('font-family', 'monospace')
          .attr('fill', color).attr('font-weight', 'bold')
          .text(e.label);
      }
    });

    // ── Nodes ────────────────────────────────────────────────────────────────
    layout.nodes.forEach(n => {
      const ng = g.append('g')
        .attr('class', 'node')
        .attr('data-id', n.id)
        .attr('transform', `translate(${n.x},${n.y})`);
        

      // Join nodes → small solid circle; no label, no popup
      if (isJoinNode(n)) {
        const JOIN_R = 6;
        ng.append('circle')
          .attr('class', 'shape join-dot')
          .attr('r', JOIN_R)
          .attr('fill', '#475569')
          .attr('stroke', '#475569')
          .attr('stroke-width', 2)
          .attr('data-join-r', JOIN_R); // expose radius for edge routing
        return;
      }

      const isIO = n.label.toLowerCase().includes('print') || n.label.toLowerCase().includes('input');
      const cfg  = isIO ? THEME.io : (THEME[n.type] || THEME.process);

      let shape;
      if (n.type === 'condition' || n.type === 'loop') {
        shape = ng.append('path')
          .attr('d', `M0,${-n.height / 2} L${n.width / 2},0 L0,${n.height / 2} L${-n.width / 2},0Z`);
      } else if (isIO) {
        const off = 15;
        shape = ng.append('path')
          .attr('d', `M${-n.width / 2 + off},${-n.height / 2} L${n.width / 2 + off},${-n.height / 2} L${n.width / 2 - off},${n.height / 2} L${-n.width / 2 - off},${n.height / 2} Z`);
      } else {
        shape = ng.append('rect')
          .attr('x', -n.width / 2).attr('y', -n.height / 2)
          .attr('width', n.width).attr('height', n.height)
          .attr('rx', n.type.includes('start') ? 20 : 6);
      }

      shape.attr('class', 'shape').attr('fill', cfg.f).attr('stroke', cfg.s).attr('stroke-width', 2.5);

      ng.append('text')
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('font-size', '11px').attr('font-family', 'monospace').attr('font-weight', 'bold')
        .text(n.label.slice(0, 22));

      // Explainer popup
      const pop = ng.append('g')
        .attr('class', 'explainer-popup')
        .style('opacity', 0)
        .attr('transform', `translate(0, ${-n.height / 2 - 25})`);
      pop.append('rect').attr('class', 'explainer-bg').attr('height', 28).attr('rx', 14).attr('fill', '#1e293b');
      pop.append('text').attr('class', 'explainer-text')
        .attr('text-anchor', 'middle').attr('y', 18)
        .attr('fill', '#fff').attr('font-size', '11px').attr('font-weight', '500');
    });
  }, [layout]);

  // ─── Animate on step change ──────────────────────────────────────────────────
  useEffect(() => {
    const ctx = getCtx(currentStep);
    if (!ctx || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const { activeId, explanationNodeId, explanation, res } = ctx;

    // ── Auto-scroll: keep active node in upper-center so the node below is visible ──
    const activeNode = layout?.nodes?.find(n => n.id === activeId);
    if (activeNode && containerRef.current && svgRef.current) {
      const scale = parseFloat(
        svgRef.current.style.transform?.match(/scale\(([^)]+)\)/)?.[1] ?? 1
      );
      // The node's rendered position in the scroll container includes:
      //   • its SVG coordinate (x, y)
      //   • the content group's offsetX translation
      //   • the CSS scale applied to the SVG element (origin: top left)
      const renderedX = (activeNode.x + offsetXRef.current) * scale;
      const renderedY = activeNode.y * scale;
      const nodeW     = activeNode.width  * scale;
      const nodeH     = activeNode.height * scale;

      const viewH = containerRef.current.clientHeight;
      const viewW = containerRef.current.clientWidth;

      // Horizontally: keep node centred
      const scrollLeft = Math.max(0, renderedX + nodeW / 2 - viewW / 2);

      // Vertically: place the node's centre at ~33% from the top of the viewport
      // so roughly 2/3 of the viewport below it remains visible for the next node.
      const scrollTop = Math.max(0, renderedY + nodeH / 2 - viewH * 0.33);

      containerRef.current.scrollTo({
        left: scrollLeft,
        top:  scrollTop,
        behavior: 'smooth',
      });
    }

    // ── D3 particle travelling along the active edge ──────────────────────────
    // getPointAtLength(t * totalLength) gives the exact (x, y) at every frame,
    // interpolating smoothly along the full polyline path.
    if (prevActiveRef.current && prevActiveRef.current !== activeId) {
      const edge = svg.select(`.edge[data-from="${prevActiveRef.current}"][data-to="${activeId}"]`);
      if (!edge.empty()) {
        const pathEl  = edge.select('.edge-path').node();
        const totalLen = pathEl.getTotalLength();

        edge.select('.pulse-particle')
          .style('opacity', 1)
          .transition()
          .duration(550)
          .ease(d3.easeCubicInOut)
          .attrTween('transform', () => (t) => {
            const pt = pathEl.getPointAtLength(t * totalLen);
            return `translate(${pt.x},${pt.y})`;
          })
          .on('end', function () { d3.select(this).style('opacity', 0); });
      }
    }
    prevActiveRef.current = activeId;

    // ── Highlight nodes ───────────────────────────────────────────────────────
    svg.selectAll('.node').each(function () {
      const el   = d3.select(this);
      const nid  = el.attr('data-id');
      const node = layout.nodes.find(n => n.id === nid);
      if (!node) return;

      const isActive  = nid === activeId;
      const isExpNode = nid === explanationNodeId;
      const isIO      = node.label.toLowerCase().includes('print');
      const cfg       = isIO ? THEME.io : (THEME[node.type] || THEME.process);

      el.select('.shape')
        .transition().duration(250)
        .attr('fill', isActive
          ? (res === true ? '#4ade80' : res === false ? '#f87171' : cfg.a)
          : cfg.f)
        .attr('stroke-width', isActive ? 4 : 2.5);

      // Show explainer on the semantic node (decision), not on join pass-through
      const pop = el.select('.explainer-popup');
      if (isExpNode && explanation) {
        const textEl = pop.select('.explainer-text').text(explanation);
        const tw     = textEl.node().getBBox().width;
        const fw     = Math.max(120, tw + 30);
        pop.select('.explainer-bg').attr('x', -fw / 2).attr('width', fw);
        pop.transition().duration(300)
          .style('opacity', 1)
          .attr('transform', `translate(0, ${-node.height / 2 - 35})`);
      } else {
        pop.transition().duration(200)
          .style('opacity', 0)
          .attr('transform', `translate(0, ${-node.height / 2 - 25})`);
      }
    });
  }, [currentStep, getCtx, layout]);

  return (
    <div style={{
      border: '1px solid #e2e8f0', borderRadius: 12,
      overflow: 'hidden', background: '#fff', fontFamily: 'sans-serif',
      position: 'relative', /* terminal + zoom controls anchor to this */
    }}>
      {/* ── Header ── */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid #eee',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fff',
      }}>
        <span style={{ fontWeight: 'bold', color: '#1e293b' }}>Interactive Execution Flow</span>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#64748b' }}>
          <LegendItem color={THEME.io.s}        label="Input / Output" shape="para" />
          <LegendItem color={THEME.condition.s} label="Decision"       shape="diamond" />
          <LegendItem color="#3b82f6"            label="Loop"           dashed />
        </div>
      </div>

      {/* ── Scrollable canvas (both axes) ── */}
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          background: '#f8fafc',
          overflow: 'auto',
          maxHeight: '75vh',
        }}
      >
        {/* SVG sized to content by useEffect */}
        <svg ref={svgRef} style={{ display: 'block' }} />
      </div>

      {/* ── Zoom controls — fixed to bottom-left of the panel, never scrolls ── */}
      <div style={{
        position: 'absolute', bottom: 15, left: 15,
        zIndex: 20, width: 'fit-content',
      }}>
        <ZoomControls svgRef={svgRef} />
      </div>

      {/* ── Terminal — fixed to bottom-right of the panel, never scrolls ── */}
      <div style={{
        position: 'absolute', bottom: 15, right: 15,
        zIndex: 20, width: 280, pointerEvents: 'none',
      }}>
        <div style={{
          background: '#1e293b', borderRadius: 8, overflow: 'hidden',
          boxShadow: '0 10px 15px -3px rgba(0,0,0,0.2)', pointerEvents: 'auto',
        }}>
          <div style={{
            background: '#334155', padding: '4px 12px',
            fontSize: 10, color: '#cbd5e1', fontWeight: 'bold', textTransform: 'uppercase',
          }}>Terminal</div>
          <div style={{
            padding: 10, color: '#4ade80', fontFamily: 'monospace',
            fontSize: 12, minHeight: 50, maxHeight: 100, overflowY: 'auto',
          }}>
            {trace?.steps?.[currentStep]?.output?.length > 0
              ? trace.steps[currentStep].output
                  .filter(l => l.trim())
                  .map((line, idx) => <div key={idx} style={{ marginBottom: 2 }}>{`> ${line}`}</div>)
              : <div style={{ opacity: 0.5 }}>{`> System ready...`}</div>
            }
          </div>
        </div>
      </div>
    </div>
  );
}

function LegendItem({ color, label, shape, dashed }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{
        width: 12, height: 12,
        border: `2px ${dashed ? 'dashed' : 'solid'} ${color}`,
        borderRadius: shape === 'para' ? 0 : 2,
        transform: shape === 'diamond' ? 'rotate(45deg)' : shape === 'para' ? 'skewX(-20deg)' : 'none',
      }} />
      <span>{label}</span>
    </div>
  );
}

// ── Zoom +/- buttons that scale the SVG via CSS transform ─────────────────────
function ZoomControls({ svgRef }) {
  const scaleRef = useRef(0.75);

  // Apply initial zoom once the SVG mounts
  useEffect(() => {
    if (svgRef.current) {
      svgRef.current.style.transform = `scale(${scaleRef.current})`;
      svgRef.current.style.transformOrigin = 'top left';
    }
  }, [svgRef]);

  const applyZoom = (delta) => {
    const next = Math.min(2.5, Math.max(0.3, scaleRef.current + delta));
    scaleRef.current = next;
    if (svgRef.current) {
      svgRef.current.style.transform = `scale(${next})`;
      svgRef.current.style.transformOrigin = 'top left';
    }
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 4,
      background: 'rgba(255,255,255,0.92)', borderRadius: 8,
      boxShadow: '0 2px 8px rgba(0,0,0,0.12)', padding: 4,
      border: '1px solid #e2e8f0',
    }}>
      {[{ label: '+', delta: 0.15 }, { label: '−', delta: -0.15 }].map(({ label, delta }) => (
        <button
          key={label}
          onClick={() => applyZoom(delta)}
          style={{
            width: 28, height: 28, borderRadius: 6, border: 'none',
            background: '#f1f5f9', color: '#1e293b',
            fontSize: 16, fontWeight: 'bold', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            lineHeight: 1,
          }}
          onMouseOver={e => e.currentTarget.style.background = '#e2e8f0'}
          onMouseOut={e => e.currentTarget.style.background = '#f1f5f9'}
        >
          {label}
        </button>
      ))}
    </div>
  );
}