import { useState } from 'react';
import { uploadPDF } from '../../services/api';

const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const UPLOAD_TIMEOUT_MS = 20000; // 20 seconds

export default function PDFUpload({ onCodeExtracted }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [extractedData, setExtractedData] = useState(null);
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [noCodeFound, setNoCodeFound] = useState(false);

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Reset state
    setError(null);
    setNoCodeFound(false);
    setExtractedData(null);
    setSelectedBlockId(null);

    if (!file.name.endsWith('.pdf')) {
      setError('Please upload a PDF file.');
      return;
    }

    // ── File size guard ──────────────────────────────────────────────────────
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError(`File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB (yours: ${(file.size / 1024 / 1024).toFixed(1)} MB).`);
      return;
    }

    setUploading(true);

    try {
      // ── Upload with timeout ────────────────────────────────────────────────
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

      let result;
      try {
        result = await uploadPDF(file, controller.signal);
      } catch (fetchErr) {
        if (fetchErr.name === 'AbortError') {
          setError('Processing timed out. The PDF may be too complex. Try a smaller file.');
          return;
        }
        throw fetchErr;
      } finally {
        clearTimeout(timeoutId);
      }

      if (result.success) {
        if (!result.code_blocks || result.code_blocks.length === 0) {
          // ── No code detected ───────────────────────────────────────────────
          setNoCodeFound(true);
        } else {
          setExtractedData(result);
          const first = result.code_blocks[0];
          setSelectedBlockId(first.id);
          onCodeExtracted(first.code);
        }
      } else {
        setError(result.error || 'Failed to extract PDF. Please try again.');
      }
    } catch (err) {
      setError('Upload failed. Make sure the backend is running.');
      console.error(err);
    } finally {
      setUploading(false);
      // Reset the input so the same file can be re-uploaded if needed
      event.target.value = '';
    }
  };

  const handleBlockSelect = (block) => {
    setSelectedBlockId(block.id);
    onCodeExtracted(block.code);
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold mb-4">Upload PDF</h2>

      {/* ── File Input ──────────────────────────────────────────────────────── */}
      <div className="mb-3">
        <label htmlFor="pdf-upload" className="block w-full cursor-pointer group">
          <div className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center group-hover:border-blue-400 group-hover:bg-blue-50/40 transition-all">
            <div className="flex items-center justify-center gap-4">
              <svg
                className={`h-8 w-8 ${uploading ? 'text-blue-500 animate-pulse' : 'text-gray-400'}`}
                stroke="currentColor"
                fill="none"
                viewBox="0 0 48 48"
              >
                <path
                  d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <div className="text-left">
                <p className="text-sm font-semibold text-gray-800">
                  {uploading ? 'Processing…' : 'Click to upload PDF'}
                </p>
                <p className="text-xs text-gray-500 font-medium">
                  Max {MAX_FILE_SIZE_MB} MB · Educational programming files
                </p>
              </div>
            </div>
          </div>
          <input
            id="pdf-upload"
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>

      {/* ── Error Display ──────────────────────────────────────────────────── */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <span className="text-red-500 mt-0.5 shrink-0">⚠️</span>
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* ── No Code Found ─────────────────────────────────────────────────── */}
      {noCodeFound && !error && (
        <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg flex flex-col items-center gap-2 text-center">
          <svg className="h-8 w-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm font-semibold text-amber-800">No code snippets detected</p>
          <p className="text-xs text-amber-700">
            This PDF doesn't appear to contain recognisable Python code blocks.
            Try a lecture slide or textbook with code examples.
          </p>
        </div>
      )}

      {/* ── Extracted Code Blocks ─────────────────────────────────────────── */}
      {extractedData?.code_blocks?.length > 0 && (
        <div className="mt-4 border-t pt-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Extracted Snippets</h3>
          <div className="max-h-48 overflow-y-auto pr-2 custom-scrollbar">
            <div className="grid grid-cols-2 gap-3">
              {extractedData.code_blocks.map((block, idx) => (
                <div
                  key={block.id ?? idx}
                  onClick={() => handleBlockSelect(block)}
                  className={`p-2 border rounded cursor-pointer transition-all group relative ${
                    selectedBlockId === block.id
                      ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                      : 'bg-gray-50 border-gray-200 hover:border-blue-400'
                  }`}
                >
                  <div className="text-[10px] text-gray-400 mb-1">Snippet {idx + 1}</div>
                  <pre className="text-[10px] font-mono truncate text-gray-700">
                    {block.code.slice(0, 40)}…
                  </pre>
                  <div className="absolute inset-0 bg-blue-500/5 opacity-0 group-hover:opacity-100 rounded flex items-center justify-center">
                    <span className="text-[9px] font-bold text-blue-600 bg-white px-2 py-0.5 rounded shadow-sm">
                      LOAD
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}