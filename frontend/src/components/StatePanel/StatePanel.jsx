import { motion } from 'framer-motion';

export default function StatePanel({ trace, currentStep }) {
  if (!trace || !trace.steps || trace.steps.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Program State</h2>
        <p className="text-gray-400 text-sm">No execution trace available</p>
      </div>
    );
  }

  const currentStepData = trace.steps[currentStep];
  
  if (!currentStepData) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Program State</h2>
        <p className="text-gray-400 text-sm">Invalid step</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 space-y-4">
        
        

        {/* Variables */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Variables</h3>
          {Object.keys(currentStepData.variables).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(currentStepData.variables).map(([name, value]) => (
                <motion.div
                  key={name}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center justify-between p-2 bg-blue-50 border border-blue-200 rounded"
                >
                  <span className="font-mono text-sm font-medium text-blue-900">
                    {name}
                  </span>
                  <span className="font-mono text-sm text-blue-700">
                    {typeof value === 'string' ? `"${value}"` : JSON.stringify(value)}
                  </span>
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">No variables yet</p>
          )}
        </div>

      </div>
    </div>
  );
}