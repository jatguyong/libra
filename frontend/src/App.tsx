import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import Galaxy from './components/Backgrounds/Galaxy';
import Navbar from './components/Navbar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';
import { Brain, ChevronDown, Copy, RefreshCw, ChevronLeft, ChevronRight, X } from 'lucide-react';
interface ExplanationData {
  explainer_output: string;
  prolog_explanation: string;
  database: string;
  query: string;
  contexts: string[] | string;
  condensed_context: string;
  fallback: string;
  prolog_error: string | null;
  logprobs: any[];
}

interface Message {
  id: string;
  role: 'user' | 'llm';
  content: string;
  alternativeContents?: string[];
  explanationData?: ExplanationData;
}

const AiMessage = ({ message, onRedo, isFinished, onExplanationClick }: { message: Message, onRedo: (id: string) => void, isFinished: boolean, onExplanationClick: (data: ExplanationData) => void }) => {
  const [isThoughtExpanded, setIsThoughtExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const variants = message.alternativeContents ? [...message.alternativeContents, message.content] : [message.content];
  const [viewIndex, setViewIndex] = useState(variants.length - 1);

  useEffect(() => {
    setViewIndex(variants.length - 1);
  }, [variants.length]);

  const currentDisplayContent = variants[viewIndex] || '';

  const handleCopy = () => {
    navigator.clipboard.writeText(currentDisplayContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrev = () => {
    if (viewIndex > 0) setViewIndex(viewIndex - 1);
  };

  const handleNext = () => {
    if (viewIndex < variants.length - 1) setViewIndex(viewIndex + 1);
  };

  if (!currentDisplayContent && !isFinished) {
    return null;
  }

  return (
    <div className="flex w-full justify-start">
      <div className="max-w-[80%] rounded-2xl px-5 py-4 font-inter text-[15px] leading-relaxed bg-transparent text-white/90">

        {/* CoT header block */}
        <div className="mb-6">
          <button
            onClick={() => setIsThoughtExpanded(!isThoughtExpanded)}
            className="flex items-center gap-2 mb-2 group text-white/50 hover:text-white/80 transition-colors w-auto cursor-pointer"
          >
            <Brain size={16} className="font-inter text-purple-400 group-hover:text-purple-300 transition-colors" />
            <span className="text-sm font-medium">Libra's Thought Process</span>
            <ChevronDown
              size={14}
              className={`transition-transform duration-300 ${isThoughtExpanded ? 'rotate-180' : ''}`}
            />
          </button>

          {isThoughtExpanded && (
            <div className="font-inter pl-4 mt-2 border-l-2 border-white/10 text-sm text-white/50 space-y-2">
              <p>• Parsing user intent and symbolic parameters...</p>
              <p>• Accessing context...</p>
              <p>• Synthesizing logical constraints for final output...</p>
            </div>
          )}
        </div>

        <div className="font-inter text-[15px] leading-relaxed w-full text-[#DEE1E5]">
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
              ul: ({ children }) => <ul className="list-disc pl-5 mb-4 space-y-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal pl-5 mb-4 space-y-1">{children}</ol>,
              li: ({ children }) => <li className="mb-1">{children}</li>,
              strong: ({ children }) => <strong className="font-bold text-[#DEE1E5]">{children}</strong>,
              em: ({ children }) => <em className="italic text-[#DEE1E5]">{children}</em>,
              h1: ({ children }) => <h1 className="text-2xl font-bold mt-5 mb-3 text-[#DEE1E5]">{children}</h1>,
              h2: ({ children }) => <h2 className="text-xl font-bold mt-5 mb-3 text-[#DEE1E5]">{children}</h2>,
              h3: ({ children }) => <h3 className="text-lg font-bold mt-4 mb-2 text-[#DEE1E5]">{children}</h3>,
            }}
          >
            {currentDisplayContent.replace(/<br\s*\/?>/gi, '\n')}
          </ReactMarkdown>
        </div>

        {/* Action Bar */}
        {isFinished && (
          <div className="mt-6 flex items-center gap-1 text-white/40">
            {variants.length > 1 && (
              <div className="flex items-center gap-1 mr-1 select-none text-xs font-medium">
                <button
                  onClick={handlePrev}
                  disabled={viewIndex === 0}
                  className={`p-1 rounded-md transition-colors ${viewIndex === 0 ? 'opacity-40' : 'hover:bg-white/30 hover:text-white cursor-pointer'}`}
                >
                  <ChevronLeft size={18} />
                </button>
                <span className="w-8 text-sm font-inter font-light text-center">{viewIndex + 1}/{variants.length}</span>
                <button
                  onClick={handleNext}
                  disabled={viewIndex === variants.length - 1}
                  className={`p-1 rounded-md transition-colors ${viewIndex === variants.length - 1 ? 'opacity-40' : 'hover:bg-white/30 hover:text-white cursor-pointer'}`}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}

            <div className="relative group/tooltip flex items-center justify-center">
              <button onClick={handleCopy} className="p-1.5 hover:text-white hover:bg-white/10 rounded-md transition-colors cursor-pointer">
                <Copy size={18} />
              </button>
              <div className="absolute bottom-full mb-2 bg-[#1a1523] text-white/80 text-xs px-2 py-1 rounded border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all whitespace-nowrap z-10 pointer-events-none">
                {copied ? 'Copied!' : 'Copy'}
              </div>
            </div>

            <div className="relative group/tooltip flex items-center justify-center">
              <button onClick={() => onRedo(message.id)} className="p-1.5 hover:text-white hover:bg-white/10 rounded-md transition-colors cursor-pointer">
                <RefreshCw size={18} />
              </button>
              <div className="absolute bottom-full mb-2 bg-[#1a1523] text-white/80 text-xs px-2 py-1 rounded border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all whitespace-nowrap z-10 pointer-events-none">
                Redo response
              </div>
            </div>

            {message.explanationData && (
              <button onClick={() => onExplanationClick(message.explanationData!)} className="text-base font-inter font-light text-white/40 hover:text-white/80 transition-colors ml-1 cursor-pointer">
                Explanation
              </button>
            )}
          </div>
        )}

      </div>
    </div>
  );
};


function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const [hasStartedChat, setHasStartedChat] = useState(false);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  const [isExplanationOpen, setIsExplanationOpen] = useState(false);
  const [selectedExplanation, setSelectedExplanation] = useState<ExplanationData | null>(null);

  const openExplanation = (data: ExplanationData) => {
    setSelectedExplanation(data);
    setIsExplanationOpen(true);
  };

  const handleNewConversation = () => {
    setMessages([]);
    setHasStartedChat(false);
    setUploadedFile(null);
    setIsExplanationOpen(false);
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);


  const handleSendMessage = async (text: string) => {
    if (!hasStartedChat) {
      setHasStartedChat(true);
      const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
      const updatedMessagesArray = [newUserMsg];
      setMessages(updatedMessagesArray);
      setIsLoading(true);
      setIsGenerating(true);

      try {
        const response = await fetch('http://localhost:5000/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ messages: updatedMessagesArray }),
        });

        const data = await response.json();

        if (data.error) {
          throw new Error(data.details || data.error);
        }

        const explanationData: ExplanationData = {
          explainer_output: data.explainer_output || '',
          prolog_explanation: data.prolog_explanation || '',
          database: data.database || '',
          query: data.query || '',
          contexts: data.contexts || [],
          condensed_context: data.condensed_context || '',
          fallback: data.fallback || 'unknown',
          prolog_error: data.prolog_error || null,
          logprobs: data.logprobs || [],
        };

        const llmMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'llm',
          content: data.answer || 'No answer generated.',
          explanationData,
        };
        setMessages((prev) => [...prev, llmMsg]);
      } catch (error) {
        const errorMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'llm',
          content: "Error: Cannot connect to the Libra backend."
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
        setIsGenerating(false);
      }

    } else {
      const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
      const updatedMessagesArray = [...messages, newUserMsg];
      setMessages(updatedMessagesArray);
      setIsLoading(true);
      setIsGenerating(true);

      try {
        const response = await fetch('http://localhost:5000/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ messages: updatedMessagesArray }),
        });

        const data = await response.json();

        if (data.error) {
          throw new Error(data.details || data.error);
        }

        const explanationData: ExplanationData = {
          explainer_output: data.explainer_output || '',
          prolog_explanation: data.prolog_explanation || '',
          database: data.database || '',
          query: data.query || '',
          contexts: data.contexts || [],
          condensed_context: data.condensed_context || '',
          fallback: data.fallback || 'unknown',
          prolog_error: data.prolog_error || null,
          logprobs: data.logprobs || [],
        };

        const llmMsgId = (Date.now() + 1).toString();
        const llmMsg: Message = {
          id: llmMsgId,
          role: 'llm',
          content: data.answer || 'No answer generated.',
          explanationData,
        };
        setMessages((prev) => [...prev, llmMsg]);
      } catch (error) {
        const errorMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'llm',
          content: "Error: Cannot connect to the Libra backend."
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
        setIsGenerating(false);
      }
    }
  };

  const handleRedo = async (llmMsgId: string) => {
    if (isLoading) return;

    const msgIndex = messages.findIndex(m => m.id === llmMsgId);
    if (msgIndex === -1) return;

    // Send context up to the message before the LLM message (the user message)
    const contextMessages = messages.slice(0, msgIndex);

    setMessages(prev => prev.map((msg, i) => {
      if (i === msgIndex) {
        const alt = msg.alternativeContents || [];
        return { ...msg, alternativeContents: [...alt, msg.content], content: '' };
      }
      return msg;
    }));

    setIsLoading(true);
    setIsGenerating(true);

    try {
      const response = await fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages: contextMessages }),
      });

      const data = await response.json();

      if (data.error) {
        throw new Error(data.details || data.error);
      }

      const explanationData: ExplanationData = {
        explainer_output: data.explainer_output || '',
        prolog_explanation: data.prolog_explanation || '',
        database: data.database || '',
        query: data.query || '',
        contexts: data.contexts || [],
        condensed_context: data.condensed_context || '',
        fallback: data.fallback || 'unknown',
        prolog_error: data.prolog_error || null,
          logprobs: data.logprobs || [],
        };

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === llmMsgId ? { ...msg, content: data.answer || 'No answer generated.', explanationData } : msg
        )
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === llmMsgId ? { ...msg, content: "Error: Cannot connect to the Libra backend." } : msg
        )
      );
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
    }
  };


  {/* galaxy bg */ }
  return (
    <div className="relative h-screen w-full flex flex-row overflow-hidden bg-[#060010]">

      <div className="relative z-10 flex flex-row h-full w-full pointer-events-none">

        <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} uploadedFile={uploadedFile} onNewConversation={handleNewConversation} />

        {/* Central Chat Column */}
        <div className="flex-1 flex flex-col h-full relative overflow-hidden transition-all duration-300">

          {/* Constrained Galaxy Background */}
          <div className="absolute inset-0 z-0">
            <Galaxy
              mouseRepulsion={false}
              mouseInteraction={!hasStartedChat}
              density={1}
              glowIntensity={hasStartedChat ? 0.1 : 0.2}
              saturation={0}
              hueShift={140}
              twinkleIntensity={hasStartedChat ? 0.1 : 0.3}
              rotationSpeed={hasStartedChat ? 0.0 : 0.05}
              repulsionStrength={10}
              autoCenterRepulsion={0}
              starSpeed={hasStartedChat ? 0 : 0.2}
              speed={hasStartedChat ? 0.2 : 0.8}
            />
          </div>

          <div className="pointer-events-auto w-full shrink-0 relative z-50">
            <Navbar isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
          </div>

          {!hasStartedChat ? (

            <main className="flex-1 flex flex-col items-center justify-center pointer-events-none px-6 mt-[-10%] z-10">
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
                <WelcomeScreen />
              </motion.div>
              <motion.div layout layoutId="chatbox-container" transition={{ duration: 0.5, ease: 'easeInOut' }} className="w-full max-w-4xl mx-auto mt-8 px-6 flex justify-center pointer-events-auto">
                <ChatBox
                  onSendMessage={handleSendMessage}
                  isLoading={isGenerating}
                  uploadedFile={uploadedFile}
                  setUploadedFile={setUploadedFile}
                />
              </motion.div>
            </main>

          ) : (

            <main className="flex-1 flex flex-col pointer-events-auto overflow-hidden w-full relative z-10">

              <div className="h-full overflow-y-auto w-full max-w-[768px] mx-auto shrink-0 pt-4 pb-40 px-6 flex flex-col gap-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                {messages.map((msg) => (
                  <React.Fragment key={msg.id}>
                    {msg.role === 'user' ? (
                      <div className="flex w-full justify-end">
                        <div
                          className="max-w-[80%] rounded-2xl px-5 py-4 font-inter text-[15px] leading-relaxed bg-white/10 text-white border border-white/10 backdrop-blur-md"
                          style={{ whiteSpace: 'pre-wrap' }}
                        >
                          {msg.content.replace(/\n{3,}/g, '\n\n')}
                        </div>
                      </div>
                    ) : (
                      <AiMessage
                        message={msg}
                        onRedo={handleRedo}
                        isFinished={!isGenerating || msg.id !== messages[messages.length - 1].id}
                        onExplanationClick={openExplanation}
                      />
                    )}
                  </React.Fragment>
                ))}

                {isLoading && (
                  <div className="flex w-full justify-start">
                    <div className="bg-transparent text-white/50 font-inter px-5 py-4 animate-pulse">
                      Libra is thinking...
                    </div>
                  </div>
                )}

                {/* Auto-scroll target */}
                <div ref={messagesEndRef} className="h-4 shrink-0" />
              </div>

              <div className="absolute bottom-0 left-0 right-0 z-50 pb-8 pt-12 bg-gradient-to-t from-[#060010] via-[#060010]/80 to-transparent pointer-events-none flex justify-center w-full">
                <motion.div layout layoutId="chatbox-container" transition={{ duration: 0.5, ease: 'easeInOut' }} className="w-full max-w-[768px] mx-auto justify-center shrink-0 px-6 flex pointer-events-auto">
                  <ChatBox
                    onSendMessage={handleSendMessage}
                    isLoading={isGenerating}
                    uploadedFile={uploadedFile}
                    setUploadedFile={setUploadedFile}
                  />
                </motion.div>
              </div>

            </main>

          )}
        </div>

        {/* Explanation Pane */}
        <motion.div
          initial={false}
          animate={{ width: isExplanationOpen ? 384 : 0, opacity: isExplanationOpen ? 1 : 0 }}
          transition={{ duration: 0.3, ease: "easeInOut" }}
          className="h-full shrink-0 pointer-events-auto flex flex-col bg-[#0E0915] border-l border-white/10 overflow-hidden z-20"
        >
          <div className="w-[384px] h-full flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 shrink-0">
              <span className="font-space text-base font-normal tracking-widest mt-[2px] text-white">Explanation</span>
              <button onClick={() => setIsExplanationOpen(false)} className="text-white/50 hover:text-white transition-colors cursor-pointer">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              {selectedExplanation ? (
                <>
                  {/* Pipeline Mode Badge */}
                  <div>
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase ${
                      selectedExplanation.fallback === 'prolog-graphrag' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                      selectedExplanation.fallback === 'graphrag' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                      'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    }`}>
                      {selectedExplanation.fallback === 'prolog-graphrag' ? '⚡ Prolog-GraphRAG' :
                       selectedExplanation.fallback === 'graphrag' ? '🔍 GraphRAG Only' :
                       '🧠 Tuned LLM'}
                    </span>
                  </div>

                  {/* Explainability Section */}
                  {(selectedExplanation.explainer_output || selectedExplanation.prolog_explanation) && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Explainability</h3>
                      {selectedExplanation.explainer_output && (
                        <div className="mb-3">
                          <p className="text-xs text-white/40 mb-2">Explainer Output</p>
                          <div className="text-sm text-white/80 font-inter leading-relaxed">
                            <ReactMarkdown
                              components={{
                                p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                                ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                                ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
                                li: ({ children }) => <li className="mb-1">{children}</li>,
                                strong: ({ children }) => <strong className="font-bold text-white/90">{children}</strong>,
                                em: ({ children }) => <em className="italic">{children}</em>,
                                h1: ({ children }) => <h1 className="text-lg font-bold mt-4 mb-2 text-white/90">{children}</h1>,
                                h2: ({ children }) => <h2 className="text-base font-bold mt-4 mb-2 text-white/90">{children}</h2>,
                                h3: ({ children }) => <h3 className="text-sm font-bold mt-3 mb-1 text-white/90">{children}</h3>,
                              }}
                            >
                              {selectedExplanation.explainer_output}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                      {selectedExplanation.prolog_explanation && (
                        <div>
                          <p className="text-xs text-white/40 mb-1">Prolog Explanation</p>
                          <p className="text-sm text-white/80 font-inter leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5">
                            {selectedExplanation.prolog_explanation}
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Prolog Details Section */}
                  {(selectedExplanation.database || selectedExplanation.query) && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Prolog Details</h3>
                      {selectedExplanation.database && (
                        <div className="mb-3">
                          <p className="text-xs text-white/40 mb-1">Database</p>
                          <pre className="text-xs text-green-300/80 font-mono leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5 max-h-48 overflow-y-auto">
                            {selectedExplanation.database}
                          </pre>
                        </div>
                      )}
                      {selectedExplanation.query && (
                        <div>
                          <p className="text-xs text-white/40 mb-1">Query</p>
                          <pre className="text-xs text-cyan-300/80 font-mono leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5">
                            {selectedExplanation.query}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}

                  {/* GraphRAG Sources Section */}
                  {(selectedExplanation.condensed_context || (Array.isArray(selectedExplanation.contexts) && selectedExplanation.contexts.length > 0)) && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">GraphRAG Sources</h3>
                      {selectedExplanation.condensed_context && (
                        <div className="mb-3">
                          <p className="text-xs text-white/40 mb-1">Condensed Context</p>
                          <p className="text-sm text-white/70 font-inter leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5 max-h-48 overflow-y-auto">
                            {selectedExplanation.condensed_context}
                          </p>
                        </div>
                      )}
                      {Array.isArray(selectedExplanation.contexts) && selectedExplanation.contexts.length > 0 && (
                        <div>
                          <p className="text-xs text-white/40 mb-1">Retrieved Contexts ({selectedExplanation.contexts.length})</p>
                          <div className="space-y-2 max-h-64 overflow-y-auto">
                            {selectedExplanation.contexts.map((ctx, i) => (
                              <div key={i} className="text-xs text-white/60 font-inter leading-relaxed bg-white/5 rounded-lg p-3 border border-white/5">
                                {ctx}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Prolog Error (if any) */}
                  {selectedExplanation.prolog_error && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-red-400/70 mb-2">Prolog Error</h3>
                      <p className="text-sm text-red-300/80 font-inter leading-relaxed whitespace-pre-wrap bg-red-500/5 rounded-lg p-3 border border-red-500/10">
                        {selectedExplanation.prolog_error}
                      </p>
                    </div>
                  )}

                  {/* Logprobs (shown for Tuned fallback) */}
                  {selectedExplanation.fallback === 'tuned' && selectedExplanation.logprobs && selectedExplanation.logprobs.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Token Log Probabilities</h3>
                      <div className="bg-white/5 rounded-lg p-3 border border-white/5 max-h-64 overflow-y-auto">
                        <div className="flex flex-wrap gap-1">
                          {selectedExplanation.logprobs.map((lp: any, i: number) => {
                            const prob = lp.logprob != null ? Math.exp(lp.logprob) : 0;
                            const color = prob > 0.8 ? 'text-green-300' : prob > 0.4 ? 'text-yellow-300' : 'text-red-300';
                            return (
                              <span
                                key={i}
                                className={`${color} text-xs font-mono px-1 py-0.5 rounded bg-white/5 cursor-default`}
                                title={`Token: ${lp.token || '?'}\nLogprob: ${lp.logprob?.toFixed(4) ?? 'N/A'}\nProb: ${(prob * 100).toFixed(1)}%`}
                              >
                                {lp.token || '?'}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-white/40 text-sm font-inter">Click "Explanation" on a response to view pipeline details.</p>
              )}
            </div>
          </div>
        </motion.div>

      </div>
    </div>
  );
}

export default App;
