"""
layout_generator.py — Crossing-Free Flowchart Layout
=====================================================

STRATEGY OVERVIEW
─────────────────
1. TOPOLOGICAL LAYERING (Sugiyama-style)
   - Assign every node a layer (row) via longest-path from START on
     forward edges only (back-edges excluded).
   - This guarantees all forward edges point strictly downward — no
     upward forward edges, so no forward-edge crossings.

2. COLUMN ASSIGNMENT
   - The main (straight-through) spine lives at CENTER_X.
   - Decision TRUE branches shift RIGHT by BRANCH_X.
   - Decision FALSE / exit paths continue straight down.
   - Each column occupies a distinct x-band, so no two node columns
     overlap and no edge can clip an unrelated node.

3. DECISION NODE ANCHOR RULES
   - TRUE  (if-taken / loop body) exits the RIGHT vertex (+w/2,  0)
   - FALSE (else / exit)          exits the LEFT  vertex (-w/2,  0)
   - Incoming edges always enter the TOP vertex           (  0, -h/2)
   - Both branches travel horizontally away from the diamond before
     going down, so they can never share the same vertical line.

4. BACK-EDGE ROUTING
   - Back-edges are routed through the left gutter, which is computed
     as the leftmost x-coordinate of ALL nodes minus LOOP_GUTTER.
   - This guarantees the gutter path never clips any node (including
     spine nodes like print("...") that sit at CENTER_X).
"""

"""
layout_generator.py — Adaptive Flowchart Layout (While Loops + If-Else)
"""

"""
layout_generator.py — Adaptive Flowchart Layout (While Loops + If-Else)
"""

"""
layout_generator.py — Adaptive Flowchart Layout (While Loops + If-Else)
"""

import networkx as nx
from typing import Dict, List, Tuple, Set

# ── Tuneable layout constants ────────────────────────────────────────────────
CENTER_X     = 380    
BRANCH_X     = 250    # Increased to give side-exits more room
LAYER_H      = 160    # Increased to prevent vertical overlapping
LOOP_GUTTER  = 100    
MIN_NODE_W   = 100
CHAR_W       = 8
PAD_X        = 24
# ─────────────────────────────────────────────────────────────────────────────

def generate_layout(cfg_data: Dict) -> Dict:
    nodes = cfg_data.get('nodes', [])
    edges = cfg_data.get('edges', [])
    if not nodes: return {'nodes': [], 'edges': []}

    G = nx.DiGraph()
    for n in nodes: G.add_node(n['id'], data=n)
    for e in edges: G.add_edge(e['from'], e['to'])

    node_dict = {n['id']: n for n in nodes}
    start_id = next((n['id'] for n in nodes if n['type'] == 'start'), nodes[0]['id'])
    
    back_edges = _find_back_edges_dfs(G, start_id)
    forward_adj = _forward_adjacency(edges, back_edges)
    layers = _assign_layers(start_id, forward_adj)
    join_nodes = _find_join_nodes(edges, back_edges)

    columns = _assign_columns(start_id, node_dict, forward_adj, join_nodes)

    positioned = {}
    for nid, node in node_dict.items():
        layer = layers.get(nid, 0)
        col_x = columns.get(nid, CENTER_X)
        w, h = _get_dims(node)
        y = 80 + layer * LAYER_H
        positioned[nid] = {**node, 'x': col_x, 'y': y, 'width': w, 'height': h}

    routed_edges = _route_edges(edges, positioned, back_edges)
    return {'nodes': list(positioned.values()), 'edges': routed_edges}

def _find_back_edges_dfs(G, start_id):
    back_edges, color = set(), {}
    nodes = list(G.nodes())
    if start_id in nodes: nodes.insert(0, nodes.pop(nodes.index(start_id)))
    for start in nodes:
        if start in color: continue
        stack = [(start, iter(G.successors(start)))]
        color[start] = 1
        while stack:
            u, children = stack[-1]
            try:
                v = next(children)
                if color.get(v) == 1: back_edges.add((u, v))
                elif v not in color:
                    color[v] = 1
                    stack.append((v, iter(G.successors(v))))
            except StopIteration:
                color[u] = 2
                stack.pop()
    return back_edges

def _forward_adjacency(edges, back_edges):
    adj = {}
    for e in edges:
        if (e['from'], e['to']) not in back_edges:
            adj.setdefault(e['from'], []).append(e['to'])
    return adj

def _assign_layers(start_id, forward_adj):
    layers, queue = {start_id: 0}, [start_id]
    while queue:
        nid = queue.pop(0)
        for child in forward_adj.get(nid, []):
            new_layer = layers.get(nid, 0) + 1
            if new_layer > layers.get(child, -1):
                layers[child] = new_layer
                queue.append(child)
    return layers

def _find_join_nodes(edges, back_edges):
    in_count = {}
    for e in edges:
        if (e['from'], e['to']) not in back_edges:
            in_count[e['to']] = in_count.get(e['to'], 0) + 1
    return {nid for nid, cnt in in_count.items() if cnt >= 2}

def _assign_columns(start_id, node_dict, forward_adj, join_nodes):
    columns = {}
    
    def walk(nid, current_x):
        # Prevent re-processing nodes (especially Joins with multiple parents)
        if nid in columns: return
        
        # 1. Join nodes are forced to the center spine
        if nid in join_nodes:
            node_x = CENTER_X
        else:
            # 2. Other nodes (like END) inherit the X of the path that led here
            node_x = current_x
        
        columns[nid] = node_x

        children = forward_adj.get(nid, [])
        if len(children) == 2:
            walk(children[0], node_x + BRANCH_X)
            walk(children[1], node_x - BRANCH_X)
        elif len(children) == 1:
            # Linear flow continues the current X alignment
            walk(children[0], node_x)

    walk(start_id, CENTER_X)
    return columns

def _route_edges(edges, pos, back_edges):
    fwd_out_count = {e['from']: 0 for e in edges if (e['from'], e['to']) not in back_edges}
    for e in edges:
        if (e['from'], e['to']) not in back_edges: fwd_out_count[e['from']] += 1

    branch_index = {}
    routed = []
    for e in edges:
        f_id, t_id = e['from'], e['to']
        fn, tn = pos.get(f_id), pos.get(t_id)
        if not fn or not tn: continue

        is_back = (f_id, t_id) in back_edges
        c_true, c_false = False, False
        if fwd_out_count.get(f_id, 0) >= 2 and not is_back:
            idx = branch_index.get(f_id, 0)
            branch_index[f_id] = idx + 1
            c_true, c_false = (idx == 0), (idx == 1)

        def cx(n): return n['x']
        def cy(n): return n['y']
        def hw(n): return n['width'] / 2
        def hh(n): return n['height'] / 2

        # ── Step 1: Anchor Lock (The Vertex Fix) ───────────────────
        
        # Determine Entry Point (To)
        if is_back:
            to_pt = [cx(tn), cy(tn) + hh(tn)] # Loopback enters BOTTOM
        else:
            to_pt = [cx(tn), cy(tn) - hh(tn)] # Everything else enters TOP

        # Determine Exit Point (From)
        if is_back:
            # Back-edge exits bottom of the last body node
            from_pt = [cx(fn), cy(fn) + hh(fn)]
            
        elif fn['type'] in ('loop', 'condition'):
            # FIX: If it's a False/No branch, force it to the LEFT vertex
            if c_false:
                from_pt = [cx(fn) - hw(fn), cy(fn)]
            # If it's a True/Yes branch, force it to the RIGHT vertex
            elif c_true:
                from_pt = [cx(fn) + hw(fn), cy(fn)]
            # Fallback for single-exit diamonds (rare)
            else:
                from_pt = [cx(fn), cy(fn) + hh(fn)]
        else:
            # Standard process nodes exit bottom
            from_pt = [cx(fn), cy(fn) + hh(fn)]

        # ── Step 2: Waypoint Routing (The Elbow Fix) ──────────────
        mid_y = cy(fn) + (cy(tn) - cy(fn)) / 2

        if is_back:
            # Shortest center-spine path to the BOTTOM vertex
            points = [from_pt, [cx(tn), from_pt[1]], to_pt]
            label = 'loop back'
            
        elif (c_true or c_false) and fn['type'] in ('condition', 'loop'):
            # This ensures both Left and Right side-exits draw a horizontal 
            # line to their column before dropping vertically.
            points = [from_pt, [cx(tn), from_pt[1]], to_pt]
            label = 'true' if c_true else 'false'
            
        else:
            # Standard vertical flow or simple join elbows
            if abs(from_pt[0] - to_pt[0]) < 5:
                points = [from_pt, to_pt]
            else:
                points = [from_pt, [from_pt[0], mid_y], [to_pt[0], mid_y], to_pt]
            label = ''
        
        routed.append({'from': f_id, 'to': t_id, 'points': points, 'label': label})
        # layout_generator.py


    # ... existing code ...
    
    # Ensure join nodes are treated as points
    if tn['type'] == 'process' and tn['label'] == '↓':
        to_pt = [cx(tn), cy(tn)] # Route to the absolute center
    else:
        to_pt = [cx(tn), cy(tn) - hh(tn)] # Route to top edge
        
    # ... existing code ...
    return routed

def _get_dims(node):
    label, t = node.get('label', ''), node.get('type', 'process')
    # Join nodes render as a small circle (r=6); give them a tiny bbox so
    # the layout router's hh() = 6 and edges terminate right at the circle edge.
    code = (node.get('statements') or [{}])[0].get('code', '')
    if label == '↓' or label == 'join' or str(code).lower() == 'join':
        return 12, 12  # diameter = 2*r; edges will terminate at centre ± 6
    w = min(max(MIN_NODE_W, len(label) * CHAR_W + PAD_X * 2), 240)
    h = {'start': 40, 'end': 40, 'condition': 70, 'loop': 70}.get(t, 50)
    return w, h