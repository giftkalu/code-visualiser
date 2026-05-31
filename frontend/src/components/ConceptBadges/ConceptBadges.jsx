import { useEffect, useState } from 'react';

const COLORS = {
  for_loop:             { bg: '#dbeafe', text: '#1d4ed8', border: '#93c5fd' },
  while_loop:           { bg: '#dbeafe', text: '#1d4ed8', border: '#93c5fd' },
  conditional:          { bg: '#fef9c3', text: '#854d0e', border: '#fde047' },
  function:             { bg: '#f3e8ff', text: '#7e22ce', border: '#d8b4fe' },
  assignment:           { bg: '#dcfce7', text: '#166534', border: '#86efac' },
  function_call:        { bg: '#e0f2fe', text: '#075985', border: '#7dd3fc' },
  nested_statements:    { bg: '#fce7f3', text: '#9d174d', border: '#f9a8d4' },
  list_comprehension:   { bg: '#ffedd5', text: '#9a3412', border: '#fdba74' },
  return_statement:     { bg: '#f1f5f9', text: '#475569', border: '#cbd5e1' },
  comparison:           { bg: '#ecfeff', text: '#155e75', border: '#67e8f9' },
  arithmetic_operation: { bg: '#faf5ff', text: '#6b21a8', border: '#c4b5fd' },
};

export default function ConceptBadges({ code }) {
  const [concepts, setConcepts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
  if (!code?.trim()) { 
    setConcepts([]); 
    setError(null);
    return; 
  }

  const timer = setTimeout(async () => {
    setLoading(true);

    try {
      const res = await fetch('http://localhost:5000/api/analyze-concepts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });

      const data = await res.json();

      if (data.success) {
        setConcepts(data.concepts || []);
        setError(null);
      } else {
        setConcepts([]);
        setError(data.error || "Something went wrong");
      }

    } catch (err) {
      // network/server error
      setConcepts([]);
      setError("Failed to analyze code. Check connection.");

    } finally {
      setLoading(false);
    }

  }, 600);

  return () => clearTimeout(timer);
}, [code]);

  if (!concepts.length && !loading && !error) return null;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
        Concepts Detected
      </h3>

      {error ? (
      <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3">
        ⚠️ {error}
      </div>
    ) : loading ? (
        <div className="flex gap-2">
          {[1,2,3].map(i => (
            <div key={i} className="h-6 w-20 bg-gray-100 rounded-full animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {concepts.map((c) => {
            const style = COLORS[c.name] || { bg: '#f1f5f9', text: '#475569', border: '#cbd5e1' };
            const isOpen = expanded === c.name;
            return (
              <div key={c.name} className="relative">
                <button
                  onClick={() => setExpanded(isOpen ? null : c.name)}
                  style={{ background: style.bg, color: style.text, borderColor: style.border }}
                  className="border text-xs font-semibold px-3 py-1 rounded-full hover:opacity-80 transition-opacity"
                >
                  {c.name.replace(/_/g, ' ')}
                </button>

                {isOpen && (
                  <div className="absolute z-20 top-8 left-0 w-56 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
                    <p className="text-xs text-gray-700 leading-relaxed">{c.explanation}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}