import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const PROLOG_STEPS = [
  {
    id: 1,
    title: "Router",
    description: "I'm evaluating the complexity of your question to determine if it requires the full GraphRAG and Prolog system or if a simpler path suffices."
  },
  {
    id: 2,
    title: "Encoder",
    description: "I'm transforming the document context into a structured Knowledge Graph, mapping out relevant entities and their relationships."
  },
  {
    id: 3,
    title: "Retriever",
    description: "I'm using hybrid search to locate relevant nodes and categorizing the context into atomic facts, rules, exceptions, and gaps."
  },
  {
    id: 4,
    title: "Entity Filter",
    description: "I'm passing the localized and global concepts through a strict LLM filter to discard generic or coincidental noise before assembling the final logical ground."
  },
  {
    id: 5,
    title: "Prolog Code Generator",
    description: "I'm translating the categorized context into executable Prolog clauses, rules, and constructing the specific logic queries required."
  },
  {
    id: 6,
    title: "Inference Engine",
    description: "I'm executing the generated Prolog query to derive the direct answer and trace the step-by-step logical reasoning that led to it."
  },
  {
    id: 7,
    title: "Explainer",
    description: "I'm acting as a translator, converting the highly technical Prolog output and logical trace into a plain, easy-to-understand natural language explanation."
  },
  {
    id: 8,
    title: "Prompt Reconstructor",
    description: "I'm organizing your original question, the formulated answer, and the natural language trace into a clean, predefined prompt template."
  },
  {
    id: 9,
    title: "Final LLM",
    description: "I'm synthesizing all the reconstructed components into a natural-sounding, digestible final response tailored to your requested format."
  }
];

const TUNED_LLM_STEPS = [
  {
    id: 1,
    title: "Router",
    description: "I'm evaluating the complexity of your question to determine if it requires the full GraphRAG and Prolog system or if a simpler path suffices."
  },
  {
    id: 2,
    title: "Fallback LLM",
    description: "I'm answering with my parametric memory without verifying through Prolog, as the question is simple or conversational."
  }
];

interface ThinkingProcessProps {
  isFinished: boolean;
  fallback?: string;
  currentStep?: number;
  thoughts?: Record<number, string[]>;
}

const ThinkingProcess: React.FC<ThinkingProcessProps> = ({ isFinished, fallback, currentStep = 1, thoughts = {} }) => {
  const activeSteps = fallback === 'tuned' ? TUNED_LLM_STEPS : PROLOG_STEPS;

  const [isExpanded, setIsExpanded] = useState(false);
  
  const internalStep = isFinished ? activeSteps.length - 1 : Math.min(Math.max(0, currentStep - 1), activeSteps.length - 1);

  useEffect(() => {
    if (isFinished) {
      setIsExpanded(false);
    }
  }, [isFinished]);

  return (
    <div className={`w-full flex justify-start ${!isFinished ? '' : ''}`}>
      <div className={`w-full ${!isFinished ? 'max-w-[80%] rounded-2xl px-5 py-4 bg-transparent' : ''}`}>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`flex items-center gap-2 mb-2 group transition-colors w-auto cursor-pointer ${isFinished ? 'text-white/50 hover:text-white/80' : 'text-white/70 hover:text-white/90 animate-pulse'}`}
        >
          <img src="/libra_logo.png" alt="Libra Logo" className={`w-5 h-5 object-contain ${isFinished ? 'opacity-70 group-hover:opacity-100' : 'opacity-100'}`} />
          <span className="text-sm font-medium">{!isFinished ? "Libra is thinking" : "Libra's Thought Process"}</span>
          <ChevronDown
            size={14}
            className={`transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="font-inter pl-6 mt-4 border-l-2 border-white/10 text-sm text-white/70 space-y-5 mb-2">
                {activeSteps.map((step, index) => {
                  const isVisible = index <= internalStep || isFinished;
                  if (!isVisible) return null;

                  const isCurrentlyThinking = !isFinished && index === internalStep;
                  const stepThoughts = thoughts[step.id] || [];

                  return (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4 }}
                      className={isCurrentlyThinking ? 'opacity-100' : 'opacity-70'}
                    >
                      <h4 className="font-bold mb-2 text-white/90 italic">
                        {step.title}
                      </h4>
                      
                      <p className={`text-[14px] leading-relaxed text-white/60 italic ${isCurrentlyThinking && stepThoughts.length === 0 ? 'animate-pulse' : ''}`}>
                        {step.description}
                      </p>
                      
                      {stepThoughts.length > 0 && (
                        <div className="mt-2 space-y-2">
                          {stepThoughts.map((thought, tIdx) => {
                            const isLastThought = tIdx === stepThoughts.length - 1;
                            const applyPulse = isCurrentlyThinking && isLastThought;
                            return (
                              <motion.div 
                                key={tIdx}
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={`text-[14px] leading-relaxed text-white/60 italic ${applyPulse ? 'animate-pulse' : ''}`}
                              >
                                {thought}
                              </motion.div>
                            );
                          })}
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default ThinkingProcess;
