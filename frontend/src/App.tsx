import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import Galaxy from './components/Backgrounds/Galaxy';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';
import { Copy, RefreshCw, ChevronLeft, ChevronRight, X, AlertTriangle } from 'lucide-react';
import ThinkingProcess from './components/ThinkingProcess';
interface ExplanationData {
  explainer_output: string;
  prolog_explanation: string;
  database: string;
  query: string;
  prolog_query?: string;
  contexts: string[] | string;
  condensed_context: string;
  fallback: string;
  prolog_error: string | null;
  logprobs: any[];
  semantic_entropy?: number;
  hallucination_flag?: string;
}

interface Message {
  id: string;
  role: 'user' | 'llm';
  content: string;
  alternativeContents?: string[];
  explanationData?: ExplanationData;
}

const AiMessage = ({ message, onRedo, isFinished, onExplanationClick }: { message: Message, onRedo: (id: string) => void, isFinished: boolean, onExplanationClick: (data: ExplanationData) => void }) => {
  const [copied, setCopied] = useState(false);

  const variants = message.alternativeContents ? [...message.alternativeContents, message.content] : [message.content];
  const [viewIndex, setViewIndex] = useState(variants.length - 1);

  useEffect(() => {
    setViewIndex(variants.length - 1);
  }, [variants.length]);

  const currentDisplayContent = variants[viewIndex] || '';

  // ── Typewriter effect ────────────────────────────────────────────
  const hasAnimated = useRef(false);
  const [revealedWordCount, setRevealedWordCount] = useState<number | null>(null);

  useEffect(() => {
    // Skip animation if already animated, or content is empty, or viewing an older variant
    if (hasAnimated.current || !currentDisplayContent || viewIndex !== variants.length - 1) {
      setRevealedWordCount(null); // show full
      return;
    }

    const words = currentDisplayContent.split(/(\s+)/); // preserve whitespace tokens
    const totalTokens = words.length;
    setRevealedWordCount(0);

    // Reveal ~8 words per tick at 30ms intervals → ~250 words/sec
    const WORDS_PER_TICK = 2;
    const INTERVAL_MS = 30;

    const timer = setInterval(() => {
      setRevealedWordCount(prev => {
        const next = (prev ?? 0) + WORDS_PER_TICK;
        if (next >= totalTokens) {
          clearInterval(timer);
          hasAnimated.current = true;
          return null; // null = show full content
        }
        return next;
      });
    }, INTERVAL_MS);

    return () => clearInterval(timer);
  }, [currentDisplayContent, viewIndex, variants.length]);

  // Build the text to render
  const textToRender = (() => {
    if (revealedWordCount === null) return currentDisplayContent;
    const words = currentDisplayContent.split(/(\s+)/);
    return words.slice(0, revealedWordCount).join('');
  })();

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
      <div className="w-full rounded-2xl px-5 py-4 font-inter text-[15px] leading-relaxed bg-transparent text-white/90">

        {/* CoT header block */}
        <div className="mb-6 -ml-5">
          <ThinkingProcess isFinished={true} fallback={message.explanationData?.fallback} />
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
            {textToRender.replace(/<br\s*\/?>/gi, '\n')}
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

            {message.explanationData?.fallback === 'tuned' && (
              <div className="relative group/tooltip flex items-center justify-center ml-1">
                <div className="p-1.5 text-amber-500/80 hover:text-amber-400 group-hover/tooltip:bg-amber-500/10 rounded-md transition-colors cursor-help">
                  <AlertTriangle size={18} />
                </div>
                <div className="absolute bottom-full mb-2 bg-[#1a1523] text-white/90 text-xs px-3 py-2 rounded-lg border border-amber-500/30 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all w-56 text-center shadow-xl shadow-amber-900/20 z-10 pointer-events-none">
                  This response is not Prolog verified and relies solely on the LLM's parametric memory.
                </div>
              </div>
            )}

            {message.explanationData && (
              <button
                onClick={() => onExplanationClick(message.explanationData!)}
                className="text-base font-inter font-light text-white/40 hover:text-white/80 transition-colors ml-1 cursor-pointer"
              >
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
  const [currentStep, setCurrentStep] = useState(1);
  const [currentFallback, setCurrentFallback] = useState<string | undefined>(undefined);

  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [fileStatuses, setFileStatuses] = useState<Record<string, { status: string; duration_s?: number; error?: string }>>({});

  const [hasStartedChat, sethasStartedChat] = useState(false);
  const [isChatLayoutSettled, setIsChatLayoutSettled] = useState(false);
  const [useGlobalKG, setUseGlobalKG] = useState(false);

  useEffect(() => {
    if (hasStartedChat) {
      const timer = setTimeout(() => setIsChatLayoutSettled(true), 500);
      return () => clearTimeout(timer);
    } else {
      setIsChatLayoutSettled(false);
    }
  }, [hasStartedChat]);

  // Poll ingestion status while any file is "processing"
  useEffect(() => {
    const hasProcessing = Object.values(fileStatuses).some(s => s.status === 'processing');
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:5000/api/ingest/status');
        if (res.ok) {
          const data = await res.json();
          setFileStatuses(data);
        }
      } catch (err) {
        console.error('Error polling ingestion status:', err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [fileStatuses]);

  // Mark files as "processing" when they are uploaded
  const handleFilesUploaded = (files: File[]) => {
    setUploadedFiles(prev => [...prev, ...files]);
    const newStatuses: Record<string, { status: string }> = {};
    files.forEach(f => { newStatuses[f.name] = { status: 'processing' }; });
    setFileStatuses(prev => ({ ...prev, ...newStatuses }));
  };

  const handleRemoveFile = async (filename: string) => {
    // Optimistically remove from UI immediately
    setUploadedFiles(prev => prev.filter(f => f.name !== filename));
    setFileStatuses(prev => {
      const next = { ...prev };
      delete next[filename];
      return next;
    });

    const isProcessing = fileStatuses[filename]?.status === 'processing';
    const endpoint = isProcessing ? '/api/ingest/cancel' : '/api/ingest/remove';
    try {
      await fetch(`http://localhost:5000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      });
    } catch (err) {
      console.error(`Error calling ${endpoint} for ${filename}:`, err);
    }
  };

  // True while any file is still being ingested — used to disable the send button
  const hasProcessing = Object.values(fileStatuses).some(s => s.status === 'processing');


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
    sethasStartedChat(false);
    setUploadedFiles([]);
    setFileStatuses({});
    setIsExplanationOpen(false);
  };


  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);


  // ── Shared SSE utilities ──────────────────────────────────────────

  const parseExplanationData = (data: any): ExplanationData => ({
    explainer_output: data.explainer_output || '',
    prolog_explanation: data.prolog_explanation || '',
    database: data.database || '',
    query: data.query || '',
    prolog_query: data.prolog_query || '',
    contexts: data.contexts || [],
    condensed_context: data.condensed_context || '',
    fallback: data.fallback || 'unknown',
    prolog_error: data.prolog_error || null,
    logprobs: data.logprobs || [],
    semantic_entropy: data.semantic_entropy,
    hallucination_flag: data.hallucination_flag,
  });

  const streamChat = async (
    payload: object,
    onResult: (data: any, explanationData: ExplanationData) => void,
  ) => {
    const response = await fetch('http://localhost:5000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (part.startsWith('data: ')) {
          try {
            const eventData = JSON.parse(part.slice(6));

            if (eventData.type === 'step') {
              setCurrentStep(eventData.step);
              if (eventData.fallback) {
                setCurrentFallback(eventData.fallback);
              }
            } else if (eventData.type === 'result') {
              const data = eventData.data;
              if (data.error) throw new Error(data.details || data.error);
              onResult(data, parseExplanationData(data));
            } else if (eventData.type === 'error') {
              throw new Error(eventData.error || "Unknown pipeline error");
            }
          } catch (err) {
            console.error("Error parsing SSE data:", err);
          }
        }
      }
    }
  };

  // ── Handlers ──────────────────────────────────────────────────────

  const handleSendMessage = async (text: string, useGlobalKG: boolean = false) => {
    if (!hasStartedChat) sethasStartedChat(true);

    const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    const updatedMessagesArray = hasStartedChat ? [...messages, newUserMsg] : [newUserMsg];
    setMessages(updatedMessagesArray);
    setIsLoading(true);
    setIsGenerating(true);
    setCurrentStep(1);
    setCurrentFallback(undefined);

    try {
      await streamChat(
        { messages: updatedMessagesArray, useGlobalKG },
        (data, explanationData) => {
          const llmMsg: Message = {
            id: (Date.now() + 1).toString(),
            role: 'llm',
            content: data.answer || 'No answer generated.',
            explanationData,
          };
          setMessages((prev) => [...prev, llmMsg]);
        },
      );
    } catch (error) {
      console.error(error);
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'llm',
        content: "There seems to be an error in the backend. Please try again."
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
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
    setCurrentStep(1);
    setCurrentFallback(undefined);

    try {
      await streamChat(
        { messages: contextMessages },
        (data, explanationData) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === llmMsgId ? { ...msg, content: data.answer || 'No answer generated.', explanationData } : msg
            )
          );
        },
      );
    } catch (error) {
      console.error(error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === llmMsgId ? { ...msg, content: "There seems to be an error in the backend. Please try again." } : msg
        )
      );
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
    }
  };


  {/* galaxy bg */ }
  return (
    <div className="relative h-screen w-full overflow-hidden bg-[#060010]">

      {/* Full-screen Galaxy Background */}
      <div className="absolute inset-0 z-0 pointer-events-auto transition-opacity duration-1000">
        <Galaxy
          mouseRepulsion={false}
          mouseInteraction={false}
          density={1.3}
          glowIntensity={!hasStartedChat ? 0.4 : isGenerating ? 0.2 : 0.2}
          saturation={0}
          hueShift={140}
          twinkleIntensity={!hasStartedChat ? 0.3 : isGenerating ? 0.5 : 0.1}
          rotationSpeed={0}
          repulsionStrength={0}
          autoCenterRepulsion={0}
          starSpeed={!hasStartedChat ? 0.3 : isGenerating ? 10 : 0}
          speed={!hasStartedChat ? 0.5 : isGenerating ? 0.4 : 0.1}
        />
      </div>

      <div className="relative z-10 flex flex-row h-full w-full pointer-events-none">

        {/* Sidebar handles its own pointer events */}
        <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} uploadedFiles={uploadedFiles} fileStatuses={fileStatuses} onNewConversation={handleNewConversation} onRemoveFile={handleRemoveFile} />

        {/* Central Chat Column */}
        <div className="flex-1 flex flex-col h-full relative overflow-hidden transition-all duration-300 pointer-events-auto">

          {/* Reserved space for exactly where the logo sits so the layout doesn't overlap */}
          <div className="w-full shrink-0 relative h-[72px] pointer-events-none">
            {/* The actual Navbar with the logo is removed, we just need the 72px spacing to match the old Navbar height */}
          </div>

          {!hasStartedChat ? (

            <main className="flex-1 flex flex-col items-center justify-center pointer-events-none px-6 mt-[-10vh] z-10">
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
                <WelcomeScreen />
              </motion.div>
              <motion.div layout layoutId="chatbox-container" transition={{ duration: 0, ease: 'easeInOut' }} className="w-full max-w-4xl mx-auto mt-8 px-6 flex flex-col items-center pointer-events-auto">
                <div className="w-full flex justify-center">
                  <ChatBox
                    onSendMessage={handleSendMessage}
                    isLoading={isGenerating}
                    isIngesting={hasProcessing}
                    uploadedFiles={uploadedFiles}
                    setUploadedFiles={setUploadedFiles}
                    onFilesUploaded={handleFilesUploaded}
                    useGlobalKG={useGlobalKG}
                    setUseGlobalKG={setUseGlobalKG}
                  />
                </div>
                <div className="font-normal text-white/70 text-[11px] font-inter tracking-wide text-center mt-4 select-none">
                  Libra is AI and can make mistakes. Check important info.
                </div>
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
                          className="max-w-[80%] rounded-2xl rounded-tr-[4px] px-5 py-4 font-inter text-[15px] leading-relaxed bg-white/10 text-white border border-white/10 backdrop-blur-md"
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
                  <ThinkingProcess isFinished={false} currentStep={currentStep} fallback={currentFallback} />
                )}

                { }
                {isLoading && <div className="h-[42vh] shrink-0" />}

                {/* Auto-scroll target */}
                <div ref={messagesEndRef} className="h-4 shrink-0" />
              </div>

              <div className="absolute bottom-0 left-0 right-0 z-50 pb-4 pt-12 bg-gradient-to-t from-[#060010] via-[#060010]/80 to-transparent pointer-events-none flex justify-center w-full">
                <motion.div layout layoutId="chatbox-container" transition={{ duration: isChatLayoutSettled ? 0 : 0.5, ease: 'easeInOut' }} className="w-full max-w-[768px] mx-auto flex flex-col items-center shrink-0 px-6 pointer-events-auto">
                  <div className="w-full flex justify-center">
                    <ChatBox
                      onSendMessage={handleSendMessage}
                      isLoading={isGenerating}
                      isIngesting={hasProcessing}
                      uploadedFiles={uploadedFiles}
                      setUploadedFiles={setUploadedFiles}
                      onFilesUploaded={handleFilesUploaded}
                      useGlobalKG={useGlobalKG}
                      setUseGlobalKG={setUseGlobalKG}
                    />
                  </div>
                  <div className="font-normal text-white/70 text-[11px] font-inter tracking-wide text-center mt-3 select-none">
                    Libra is AI and can make mistakes. Check important info.
                  </div>
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
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase ${selectedExplanation.fallback === 'prolog-graphrag' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                      selectedExplanation.fallback === 'graphrag' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                        'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      }`}>
                      {selectedExplanation.fallback === 'prolog-graphrag' ? '⚡ Prolog-GraphRAG' :
                        selectedExplanation.fallback === 'graphrag' ? '🔍 GraphRAG Only' :
                          '🧠 Tuned LLM'}
                    </span>
                  </div>

                  {/* Semantic Entropy Section */}
                  {(selectedExplanation.semantic_entropy != null) && (
                    <div className="mb-4 bg-white/5 rounded-lg p-3 border border-white/10 flex flex-col gap-2">
                      <div className="flex justify-between items-center">
                        <span className="text-xs uppercase tracking-wider font-semibold text-white/50">Semantic Entropy</span>
                        <span className="text-sm font-mono text-white/90 bg-black/30 px-2 py-0.5 rounded">
                          {selectedExplanation.semantic_entropy!.toFixed(4)}
                        </span>
                      </div>
                      {selectedExplanation.hallucination_flag && (
                        <div className="flex justify-between items-center">
                          <span className="text-xs uppercase tracking-wider font-semibold text-white/50">Confidence</span>
                          <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${selectedExplanation.hallucination_flag === 'likely_hallucination' ? 'bg-amber-500/20 text-amber-300' : 'bg-green-500/20 text-emerald-300'}`}>
                            {selectedExplanation.hallucination_flag.replace('_', ' ')}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Logprobs Section */}
                  {selectedExplanation.logprobs && selectedExplanation.logprobs.length > 0 && (
                    <div className="mb-4">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Token Log probabilities</h3>
                      <div className="bg-white/5 rounded-lg border border-white/10 max-h-48 overflow-y-auto p-2 space-y-1">
                        {selectedExplanation.logprobs.map((lp: any, i: number) => {
                          const token = lp.token || (typeof lp === 'string' ? lp : JSON.stringify(lp));
                          const prob = typeof lp.logprob === 'number' ? lp.logprob.toFixed(4) : (typeof lp === 'number' ? lp.toFixed(4) : 'N/A');
                          return (
                            <div key={i} className="flex justify-between items-center px-2 py-1 hover:bg-white/5 rounded">
                              <span className="text-xs font-mono text-white/80 truncate max-w-[200px]">{token}</span>
                              <span className="text-xs font-mono text-white/50">{prob}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Mapped Query Section */}
                  {selectedExplanation.query && (
                    <div className="mb-4">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Query</h3>
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
                          {selectedExplanation.query}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}

                  {/* GraphRAG Sources Section */}
                  {(() => {
                    const cc = selectedExplanation.condensed_context;
                    const hasValidContext = cc && !cc.toLowerCase().includes('error during generation');
                    const hasContexts = Array.isArray(selectedExplanation.contexts) && selectedExplanation.contexts.length > 0;
                    return (hasValidContext || hasContexts) ? (
                      <div className="mb-4">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">GraphRAG Sources</h3>
                        {hasValidContext && (() => {
                          // Split the condensed context string into its 4 named sections via regex.
                          const sectionKeys = [
                            'ATOMIC FACTS',
                            'CONDITIONAL RULES',
                            'EXCEPTIONS',
                            'LOGICAL GAPS',
                          ] as const;
                          const pattern = /\*\*(ATOMIC FACTS|CONDITIONAL RULES|EXCEPTIONS|LOGICAL GAPS)\*\*:/g;
                          const sections: Record<string, string> = {};
                          let match: RegExpExecArray | null;
                          const matches: { label: string; contentStart: number; headerStart: number }[] = [];
                          while ((match = pattern.exec(cc)) !== null) {
                            matches.push({ label: match[1], contentStart: match.index + match[0].length, headerStart: match.index });
                          }
                          matches.forEach((m, i) => {
                            const end = i + 1 < matches.length ? matches[i + 1].headerStart : cc.length;
                            sections[m.label] = cc.slice(m.contentStart, end).trim();
                          });

                          const hasSections = matches.length > 0;
                          if (!hasSections) {
                            // Fallback: render as plain markdown if headers aren't found
                            return (
                              <div className="text-sm text-white/80 font-inter leading-relaxed mb-3">
                                <ReactMarkdown>{cc}</ReactMarkdown>
                              </div>
                            );
                          }

                          return (
                            <div className="space-y-2 mb-3">
                              {sectionKeys.map((key) => {
                                const content = sections[key];
                                if (!content || content.toLowerCase() === 'none') return null;
                                return (
                                  <div key={key} className="rounded-lg bg-white/5 px-3 py-2">
                                    <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-1">{key}</p>
                                    <div className="text-sm text-white/80 font-inter leading-relaxed">
                                      <ReactMarkdown
                                        components={{
                                          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                                          ul: ({ children }) => <ul className="list-disc pl-4 space-y-0.5">{children}</ul>,
                                          li: ({ children }) => <li className="mb-0.5">{children}</li>,
                                          strong: ({ children }) => <strong className="font-bold text-white/90">{children}</strong>,
                                        }}
                                      >
                                        {content}
                                      </ReactMarkdown>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          );
                        })()}

                        {Array.isArray(selectedExplanation.contexts) && selectedExplanation.contexts.length > 0 && (
                          <div>
                            <p className="text-xs text-white/40 mb-1">Retrieved Contexts ({selectedExplanation.contexts.length})</p>
                            <div className="space-y-4 max-h-64 overflow-y-auto pr-2 text-sm text-white/80 font-inter leading-relaxed">
                              {selectedExplanation.contexts.map((ctx, i) => (
                                <ReactMarkdown
                                  key={i}
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
                                  {ctx}
                                </ReactMarkdown>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : null;
                  })()}

                  {/* Explainability Section */}
                  {(selectedExplanation.explainer_output || selectedExplanation.prolog_explanation) && (
                    <div className="mb-4">
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
                    <div className="mb-4">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Prolog Details</h3>
                      {selectedExplanation.prolog_query && (
                        <div className="mb-3">
                          <p className="text-xs text-white/40 mb-1">Prolog Query</p>
                          <pre className="text-xs text-cyan-300/80 font-mono leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5">
                            {selectedExplanation.prolog_query}
                          </pre>
                        </div>
                      )}
                      {selectedExplanation.database && (
                        <div>
                          <p className="text-xs text-white/40 mb-1">Database</p>
                          <pre className="text-xs text-green-300/80 font-mono leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5 max-h-48 overflow-y-auto">
                            {selectedExplanation.database}
                          </pre>
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
