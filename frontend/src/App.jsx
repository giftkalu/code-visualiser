import { useState, useEffect, useCallback } from 'react';
import PDFUpload from './components/PDFUpload/PDFUpload';
import CodeEditor from './components/CodeEditor/CodeEditor';
import ConceptBadges from './components/ConceptBadges/ConceptBadges';
import Flowchart from './components/Flowchart/Flowchart';
import PlaybackControls from './components/PlaybackControls/PlaybackControls';
import StatePanel from './components/StatePanel/StatePanel';
import { visualizeCode } from './services/api';

// ── Toast notification ────────────────────────────────────────────────────────
function Toast({ toast, onDismiss }) {
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(onDismiss, 6000);
    return () => clearTimeout(id);
  }, [toast, onDismiss]);

  if (!toast) return null;

  const styles = {
    runtime_error: {
      bg: 'bg-red-50',
      border: 'border-red-300',
      icon: '🚨',
      title: 'Runtime Error',
      titleColor: 'text-red-700',
      msgColor: 'text-red-800',
    },
    infinite_loop: {
      bg: 'bg-orange-50',
      border: 'border-orange-300',
      icon: '🔁',
      title: 'Infinite Loop Detected',
      titleColor: 'text-orange-700',
      msgColor: 'text-orange-800',
    },
    syntax_error: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-300',
      icon: '✏️',
      title: 'Syntax Error',
      titleColor: 'text-yellow-700',
      msgColor: 'text-yellow-800',
    },
    generic: {
      bg: 'bg-red-50',
      border: 'border-red-300',
      icon: '⚠️',
      title: 'Error',
      titleColor: 'text-red-700',
      msgColor: 'text-red-800',
    },
  };

  const s = styles[toast.type] ?? styles.generic;

  return (
    <div
      className={`fixed top-5 right-5 z-50 max-w-sm w-full ${s.bg} border ${s.border} rounded-xl shadow-lg p-4 flex gap-3 animate-fade-in`}
      role="alert"
    >
      <span className="text-xl shrink-0 mt-0.5">{s.icon}</span>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-bold ${s.titleColor}`}>{s.title}</p>
        <p className={`text-sm mt-0.5 ${s.msgColor} break-words`}>{toast.message}</p>
      </div>
      <button
        onClick={onDismiss}
        className="text-gray-400 hover:text-gray-600 shrink-0 self-start leading-none text-lg"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
function App() {
  const [code, setCode] = useState('');
  const [visualizationData, setVisualizationData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [toast, setToast] = useState(null); // { type, message }

  const showToast = useCallback((type, message) => {
    setToast({ type, message });
  }, []);

  const dismissToast = useCallback(() => setToast(null), []);

  const handleCodeChange = (newCode) => {
    setCode(newCode);
  };

  const handleVisualize = async () => {
    if (!code.trim()) {
      showToast('syntax_error', 'Please enter some code before visualising.');
      return;
    }

    setLoading(true);
    setVisualizationData(null); // clear stale flowchart immediately

    try {
      const result = await visualizeCode(code);

      // ── Execution failed: show toast, do NOT render flowchart ─────────────
      if (!result.success) {
        const errType = result.error ?? 'generic';
        showToast(errType, result.message ?? 'An unexpected error occurred.');
        return;
      }

      // ── Execution succeeded but runtime produced an error mid-run ─────────
      if (!result.execution_success && result.execution_error) {
        // The CFG is valid; we still want the flowchart structure but we warn
        // the user about the runtime problem via toast.
        const errType = result.trace?.steps?.some(s => s.is_infinite_loop)
          ? 'infinite_loop'
          : 'runtime_error';
        showToast(errType, result.execution_error);

        // ── Infinite loop → don't show an empty / misleading flowchart ───────
        return;
      }

      setVisualizationData(result);
      setCurrentStep(0);
      setIsPlaying(false);
    } catch (err) {
      showToast('generic', 'Failed to connect to server. Make sure the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const totalSteps = visualizationData?.trace?.total_steps ?? 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Global toast */}
      <Toast toast={toast} onDismiss={dismissToast} />

      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="w-full px-6 py-4">
          <h1 className="text-2xl font-bold text-gray-900">
            Text-to-Visual Programming Education
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Upload a PDF or write code to generate interactive visualisations
          </p>
        </div>
      </header>

      <div className="max-w-full px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* Column 1-3: Code & Upload */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
              <PDFUpload onCodeExtracted={setCode} />
            </div>
            <ConceptBadges code={code} />
            <CodeEditor
              code={code}
              onChange={handleCodeChange}
              onVisualize={handleVisualize}
              loading={loading}
              currentStep={currentStep}
              trace={visualizationData?.trace}
            />
          </div>

          {/* Column 4-9: Flowchart + Playback */}
          <div className="lg:col-span-6 flex flex-col gap-4">
            {visualizationData ? (
              <>
                <Flowchart
                  layout={visualizationData.layout}
                  currentStep={currentStep}
                  trace={visualizationData.trace}
                />
                <PlaybackControls
                  currentStep={currentStep}
                  totalSteps={totalSteps}
                  isPlaying={isPlaying}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onStepForward={() =>
                    setCurrentStep(prev => Math.min(prev + 1, totalSteps - 1))
                  }
                  onStepBackward={() =>
                    setCurrentStep(prev => Math.max(prev - 1, 0))
                  }
                  onReset={() => setCurrentStep(0)}
                />
              </>
            ) : (
              <div className="bg-white rounded-lg shadow p-8 text-center h-[600px] flex flex-col items-center justify-center border-2 border-dashed border-gray-200 gap-3">
                <svg className="h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7" />
                </svg>
                <p className="text-gray-400 text-sm max-w-xs">
                  Upload a PDF or enter code, then click <strong>"Visualize"</strong> to see the logic flow
                </p>
              </div>
            )}
          </div>

          {/* Column 10-12: State Panel */}
          <div className="lg:col-span-3">
            {visualizationData ? (
              <StatePanel
                trace={visualizationData.trace}
                currentStep={currentStep}
              />
            ) : (
              <div className="bg-gray-50 rounded-lg p-6 border border-gray-200 h-full">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                  Memory Map
                </h3>
                <p className="text-xs text-gray-400 mt-2">
                  Variables will appear here during execution
                </p>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}

export default App;