import { useState, useRef, useEffect } from 'react'; // Added useRef and useEffect
import Editor from '@monaco-editor/react';

export default function CodeEditor({ code, onChange, onVisualize, loading, currentStep, trace }) { // Added currentStep and trace props
  const [editorLoading, setEditorLoading] = useState(true);
  
  // NEW: Refs to track the editor and the current decorations
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const decorationsRef = useRef([]);

  const handleEditorChange = (value) => {
    onChange(value || '');
  };

  // NEW: Capture the editor instance on mount
  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    setEditorLoading(false);
  };

  // NEW: Effect to highlight the current executing line
  useEffect(() => {
    if (!editorRef.current || !monacoRef.current || !trace?.steps) return;

    const step = trace.steps[currentStep];
    if (!step) return;

    const lineNumber = step.line;

    // deltaDecorations(oldDecorationIds, newDecorations)
    // Passing the old IDs clears the previous highlight automatically
    decorationsRef.current = editorRef.current.deltaDecorations(
      decorationsRef.current,
      [
        {
          range: new monacoRef.current.Range(lineNumber, 1, lineNumber, 1),
          options: {
            isWholeLine: true,
            className: 'executing-line-highlight', // Matches class in index.css
            glyphMarginClassName: 'executing-line-glyph', // Matches class in index.css
          },
        },
      ]
    );

    // Keep the executing line in view
    editorRef.current.revealLineInCenterIfOutsideViewport(lineNumber);
  }, [currentStep, trace]);

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Code Editor</h2>
        <button
          onClick={onVisualize}
          disabled={loading || !code.trim()}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            loading || !code.trim()
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {loading ? 'Generating...' : 'Visualize'}
        </button>
      </div>

      <div className="h-96 relative">
        {editorLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            <p className="text-gray-600">Loading editor...</p>
          </div>
        )}
        <Editor
          height="100%"
          defaultLanguage="python"
          value={code}
          onChange={handleEditorChange}
          onMount={handleEditorDidMount} // Updated to use the new handler
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            glyphMargin: true, // MUST be true for the green side indicator to show
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            readOnly: loading // Prevent editing during visualization
          }}
        />
      </div>

      <div className="border-t px-4 py-2 bg-gray-50 rounded-b-lg">
        <p className="text-xs text-gray-600">
          💡 Tip: The green highlight shows exactly which line is running in the flowchart.
        </p>
      </div>
    </div>
  );
}