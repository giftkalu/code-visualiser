from code_analyzer import analyze_code
from execution_tracer import trace_execution
from layout_generator import generate_layout
from typing import Dict


def generate_visualization(code: str) -> Dict:
    """
    Complete pipeline: Code → CFG → Trace → Layout → Visualization
    
    Input: Python code string
    
    Output:
    {
        'success': True/False,
        'code': "...",
        'cfg': {nodes, edges},
        'layout': {positioned nodes and edges},
        'trace': {steps with variables and output},
        'metadata': {total_steps, total_nodes, variables}
    }
    """
    
    # Step 1: Analyze code structure (AST + CFG)
    cfg_result = analyze_code(code)
    
    if not cfg_result['success']:
        return {
            'success': False,
            'error': 'analysis_failed',
            'message': cfg_result.get('error', 'Code analysis failed')
        }
    
    # Step 2: Generate layout positions
    try:
        layout = generate_layout(cfg_result['cfg'])
    except Exception as e:
        return {
            'success': False,
            'error': 'layout_failed',
            'message': f'Layout generation failed: {str(e)}'
        }
    
    # Step 3: Trace execution
    trace_result = trace_execution(code)
    
    # Note: We don't fail if trace has errors - we still return partial results
    # This allows visualization of code structure even if execution fails
    
    # Step 4: Map trace steps to CFG nodes
    mapped_trace = _map_trace_to_nodes(trace_result, cfg_result['cfg'])
    
    # Step 5: Extract metadata
    metadata = _extract_metadata(cfg_result, trace_result)
    
    return {
        'success': True,
        'code': code,
        'cfg': cfg_result['cfg'],
        'layout': layout,
        'trace': mapped_trace,
        'metadata': metadata,
        'execution_success': trace_result.get('success', False),
        'execution_error': trace_result.get('message', None) if not trace_result.get('success') else None
    }


def _map_trace_to_nodes(trace_result: Dict, cfg: Dict) -> Dict:
    """
    Map execution trace steps to CFG nodes for synchronized animation.
    
    Adds 'active_node_id' to each trace step showing which flowchart node
    to highlight during animation.
    """
    if not trace_result.get('success'):
        # Return trace with error info
        return trace_result
    
    steps = trace_result.get('steps', [])
    nodes = cfg.get('nodes', [])
    
    # Build line-to-node mapping
    # For condition/loop nodes, also register the node's own line number
    # (stored in the first statement) so the tracer can highlight them.
    line_to_node = {}
    for node in nodes:
        for stmt in node.get('statements', []):
            line_no = stmt.get('line')
            if line_no:
                # Prefer condition/loop nodes over process nodes for the same line
                existing = line_to_node.get(line_no)
                if existing is None:
                    line_to_node[line_no] = node['id']
                else:
                    existing_node = next((n for n in nodes if n['id'] == existing), None)
                    if existing_node and existing_node['type'] not in ('condition', 'loop') \
                            and node['type'] in ('condition', 'loop'):
                        line_to_node[line_no] = node['id']
    
    # Add active_node_id to each step
    enhanced_steps = []
    for step in steps:
        enhanced_step = step.copy()
        line_no = step.get('line')
        
        # Find which CFG node contains this line
        active_node = line_to_node.get(line_no)
        enhanced_step['active_node_id'] = active_node
        # Ensure ai_explanation is carried over
        enhanced_step['explanation'] = step.get('ai_explanation', "")
        enhanced_steps.append(enhanced_step)
        
    if enhanced_steps:
        # Find the node with type 'end'
        end_node = next((n for n in nodes if n['type'] == 'end'), None)
        if end_node:
            last_step = enhanced_steps[-1].copy()
            last_step['active_node_id'] = end_node['id']
            last_step['explanation'] = "Program execution complete."
            enhanced_steps.append(last_step)
    
    return {
        'success': True,
        'steps': enhanced_steps,
        'total_steps': len(enhanced_steps)
    }


def _extract_metadata(cfg_result: Dict, trace_result: Dict) -> Dict:
    """
    Extract useful metadata about the visualization.
    """
    cfg = cfg_result.get('cfg', {})
    variables = cfg_result.get('variables', [])
    
    # Count control structures
    nodes = cfg.get('nodes', [])
    control_structure_counts = {
        'conditions': sum(1 for n in nodes if n['type'] == 'condition'),
        'loops': sum(1 for n in nodes if n['type'] == 'loop'),
        'process_blocks': sum(1 for n in nodes if n['type'] == 'process')
    }
    
    # Get trace info
    trace_steps = trace_result.get('steps', []) if trace_result.get('success') else []
    
    return {
        'total_nodes': len(nodes),
        'total_edges': len(cfg.get('edges', [])),
        'total_steps': len(trace_steps),
        'variables': variables,
        'control_structures': control_structure_counts,
        'has_loops': control_structure_counts['loops'] > 0,
        'has_conditionals': control_structure_counts['conditions'] > 0
    }


# Convenience function
def visualize_code(code: str) -> Dict:
    """Shorthand for generate_visualization."""
    return generate_visualization(code)


# Tes