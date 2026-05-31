from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf_extractor import extract_pdf_bytes
from code_analyzer import analyze_code
from concept_analyzer import ConceptDetector
from execution_tracer import trace_execution
from layout_generator import generate_layout
from visualizer import generate_visualization
import os

app = Flask(__name__)
CORS(app)

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB
 
@app.route('/api/extract-pdf', methods=['POST'])
def extract_pdf_endpoint():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
 
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
 
    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400
 
    try:
        pdf_bytes = file.read()
 
        # ── File size guard ────────────────────────────────────────────────
        if len(pdf_bytes) > MAX_PDF_BYTES:
            size_mb = len(pdf_bytes) / 1024 / 1024
            return jsonify({
                'error': f'File too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB.'
            }), 413
 
        result = extract_pdf_bytes(pdf_bytes)
 
        return jsonify({
            'success': True,
            'doc_id': hash(pdf_bytes) % 10000,
            'code_blocks': result['code_blocks']
        })
 
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-code', methods=['POST'])
def analyze_code_endpoint():
    """Analyze Python code structure and generate CFG."""
    data = request.json
    code = data.get('code', '')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        result = analyze_code(code)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': str(e)
        }), 500
@app.route('/api/analyze-concepts', methods=['POST'])
def analyze_concepts_endpoint():
    """Detect concepts in code and return explanations."""
    data = request.json
    code = data.get('code', '')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        detector = ConceptDetector()
        result = detector.detect(code)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/api/trace-execution', methods=['POST'])
def trace_execution_endpoint():
    """Execute code and return step-by-step trace."""
    data = request.json
    code = data.get('code', '')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        result = trace_execution(code)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/generate-layout', methods=['POST'])
def generate_layout_endpoint():
    """Generate flowchart layout from CFG data."""
    data = request.json
    cfg_data = data.get('cfg', {})
    
    if not cfg_data or 'nodes' not in cfg_data:
        return jsonify({'error': 'Invalid CFG data'}), 400
    
    try:
        layout = generate_layout(cfg_data)
        return jsonify(layout)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/visualize', methods=['POST'])
def visualize_endpoint():
    """
    Master endpoint: Generate complete visualization from code.
    
    Request body:
    {
        "code": "count = 0\nwhile count < 3:\n    print(count)\n    count += 1"
    }
    
    Response:
    {
        "success": true,
        "cfg": {...},
        "layout": {...},
        "trace": {...},
        "metadata": {...}
    }
    """
    data = request.json
    code = data.get('code', '')
    
    if not code or not code.strip():
        return jsonify({
            'success': False,
            'error': 'no_code',
            'message': 'No code provided'
        }), 400
    
    try:
        result = generate_visualization(code)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Unexpected error: {str(e)}'
        }), 500
    
@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if API is running."""
    return jsonify({
        'status': 'healthy',
        'message': 'Text-to-Visual API is running'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))