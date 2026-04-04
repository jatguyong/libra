/**
 * App — root component orchestrating layout, chat state, and child components.
 *
 * Heavy logic has been extracted into:
 *   - lib/api.ts          — SSE streaming, API_BASE
 *   - lib/types.ts        — shared TypeScript interfaces
 *   - hooks/useIngestion   — PDF ingestion state and polling
 *   - components/chat/*   — AiMessage, UserMessage, MarkdownRenderer
 *   - components/ExplanationPane — pipeline detail sidebar
 */

import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';

import Galaxy from './components/Backgrounds/Galaxy';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';
import ThinkingProcess from './components/ThinkingProcess';
import AiMessage from './components/chat/AiMessage';
import UserMessage from './components/chat/UserMessage';
import ExplanationPane from './components/ExplanationPane';
import KnowledgeGraphViewer from './components/KnowledgeGraphViewer';

import { streamChat } from './lib/api';
import { useIngestion } from './hooks/useIngestion';
import type { Message, ExplanationData } from './lib/types';


function App() {
  // ── Chat state ──────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [currentFallback, setCurrentFallback] = useState<string | undefined>(undefined);
  const [thoughts, setThoughts] = useState<Record<number, string[]>>({});

  // ── Layout state ────────────────────────────────────────────────
  const [hasStartedChat, setHasStartedChat] = useState(false);
  const [isChatLayoutSettled, setIsChatLayoutSettled] = useState(false);
  const [useGlobalKG, setUseGlobalKG] = useState(true);
  const [forceProlog, setForceProlog] = useState(true);
  const [calculateSemanticEntropy, setCalculateSemanticEntropy] = useState(false);

  const settingsRef = useRef({ useGlobalKG, forceProlog, calculateSemanticEntropy });
  useEffect(() => {
    settingsRef.current = { useGlobalKG, forceProlog, calculateSemanticEntropy };
  }, [useGlobalKG, forceProlog, calculateSemanticEntropy]);

  useEffect(() => {
    if (hasStartedChat) {
      const timer = setTimeout(() => setIsChatLayoutSettled(true), 500);
      return () => clearTimeout(timer);
    } else {
      setIsChatLayoutSettled(false);
    }
  }, [hasStartedChat]);

  // ── Ingestion (custom hook) ─────────────────────────────────────
  const ingestion = useIngestion();

  // ── Sidebar & Explanation pane ──────────────────────────────────
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isExplanationOpen, setIsExplanationOpen] = useState(false);
  const [selectedExplanation, setSelectedExplanation] = useState<ExplanationData | null>(null);

  const openExplanation = (data: ExplanationData) => {
    setSelectedExplanation(data);
    setIsExplanationOpen(true);
  };

  const [isGraphOpen, setIsGraphOpen] = useState(false);
  const [selectedGraphData, setSelectedGraphData] = useState<ExplanationData | null>(null);

  const openGraph = (data: ExplanationData) => {
    setSelectedGraphData(data);
    setIsGraphOpen(true);
  };

  const handleNewConversation = () => {
    setMessages([]);
    setHasStartedChat(false);
    ingestion.reset();
    setIsExplanationOpen(false);
  };

  // ── Auto‑scroll ─────────────────────────────────────────────────
  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // ── Chat handlers ───────────────────────────────────────────────

  const handleSendMessage = async (text: string) => {
    if (!hasStartedChat) setHasStartedChat(true);

    const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    const updatedMessages = hasStartedChat ? [...messages, newUserMsg] : [newUserMsg];
    setMessages(updatedMessages);
    setIsLoading(true);
    setIsGenerating(true);
    setCurrentStep(1);
    setCurrentFallback(undefined);
    setThoughts({});

    let localThoughts: Record<number, string[]> = {};

    try {
      await streamChat(
        {
          messages: updatedMessages,
          useGlobalKG: settingsRef.current.useGlobalKG,
          forceProlog: settingsRef.current.forceProlog,
          calculateSemanticEntropy: settingsRef.current.calculateSemanticEntropy,
        },
        {
          onStep: (step, fallback) => {
            setCurrentStep(step);
            if (fallback) setCurrentFallback(fallback);
          },
          onThought: (step, message) => {
            localThoughts = {
              ...localThoughts,
              [step]: [...(localThoughts[step] || []), message]
            };
            setThoughts(localThoughts);
          },
          onResult: (data, explanationData) => {
            console.log('[App] SSE result received. graph_data:', JSON.stringify(explanationData.graph_data));
            console.log('[App] graph_data nodes:', explanationData.graph_data?.nodes?.length, 'edges:', explanationData.graph_data?.edges?.length);
            const llmMsg: Message = {
              id: (Date.now() + 1).toString(),
              role: 'llm',
              content: (data.answer as string) || 'No answer generated.',
              explanationData,
              thoughts: { ...localThoughts }
            };
            setMessages(prev => [...prev, llmMsg]);
          },
        },
      );
    } catch (error) {
      console.error(error);
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'llm',
        content: 'There seems to be an error in the backend. Please try again.',
        thoughts: { ...localThoughts }
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
    }
  };

  const handleRedo = async (llmMsgId: string) => {
    if (isLoading) return;

    const msgIndex = messages.findIndex(m => m.id === llmMsgId);
    if (msgIndex === -1) return;

    const contextMessages = messages.slice(0, msgIndex);

    // Stash current content as an alternative
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
    setThoughts({});

    let localThoughts: Record<number, string[]> = {};

    try {
      await streamChat(
        {
          messages: contextMessages,
          useGlobalKG: settingsRef.current.useGlobalKG,
          forceProlog: settingsRef.current.forceProlog,
          calculateSemanticEntropy: settingsRef.current.calculateSemanticEntropy,
        },
        {
          onStep: (step, fallback) => {
            setCurrentStep(step);
            if (fallback) setCurrentFallback(fallback);
          },
          onThought: (step, message) => {
            localThoughts = {
              ...localThoughts,
              [step]: [...(localThoughts[step] || []), message]
            };
            setThoughts(localThoughts);
          },
          onResult: (data, explanationData) => {
            setMessages(prev =>
              prev.map(msg =>
                msg.id === llmMsgId
                  ? { ...msg, content: (data.answer as string) || 'No answer generated.', explanationData, thoughts: { ...localThoughts } }
                  : msg,
              ),
            );
          },
        },
      );
    } catch (error) {
      console.error(error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === llmMsgId
            ? { ...msg, content: 'There seems to be an error in the backend. Please try again.', thoughts: { ...localThoughts } }
            : msg,
        ),
      );
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────

  const chatBoxProps = {
    onSendMessage: handleSendMessage,
    isLoading: isGenerating,
    isIngesting: ingestion.hasProcessing,
    uploadedFiles: ingestion.uploadedFiles,
    setUploadedFiles: ingestion.setUploadedFiles,
    onFilesUploaded: ingestion.handleFilesUploaded,
    useGlobalKG,
    setUseGlobalKG,
    forceProlog,
    setForceProlog,
    calculateSemanticEntropy,
    setCalculateSemanticEntropy,
  };

  return (
    <div className="relative h-screen w-full overflow-hidden bg-[#060010]">

      {/* Galaxy background */}
      <div className="absolute inset-0 z-0 pointer-events-auto transition-opacity duration-1000">
        <Galaxy
          mouseRepulsion={false}
          mouseInteraction={false}
          density={1.3}
          glowIntensity={!hasStartedChat ? 0.4 : isGenerating ? 0.2 : 0.1}
          saturation={0}
          hueShift={140}
          twinkleIntensity={!hasStartedChat ? 0.3 : isGenerating ? 0.5 : 0.1}
          rotationSpeed={0}
          repulsionStrength={0}
          autoCenterRepulsion={0}
          starSpeed={!hasStartedChat ? 0.3 : isGenerating ? 5 : 0}
          speed={!hasStartedChat ? 0.5 : isGenerating ? 0.4 : 0.1}
        />
      </div>

      <div className="relative z-10 flex flex-row h-full w-full pointer-events-none">

        {/* Sidebar */}
        <Sidebar
          isOpen={isSidebarOpen}
          toggleSidebar={() => setIsSidebarOpen(prev => !prev)}
          uploadedFiles={ingestion.uploadedFiles}
          fileStatuses={ingestion.fileStatuses}
          onNewConversation={handleNewConversation}
          onRemoveFile={ingestion.handleRemoveFile}
          onClearAllFiles={ingestion.handleClearAll}
        />

        {/* Central column */}
        <div className="flex-1 flex flex-col h-full relative overflow-hidden transition-all duration-300 pointer-events-auto">

          {/* Top spacer (matches old navbar height) */}
          <div className="w-full shrink-0 relative h-[72px] pointer-events-none" />

          {!hasStartedChat ? (
            /* ── Welcome screen ──────────────────────────────── */
            <main className="flex-1 flex flex-col items-center justify-center pointer-events-none px-6 mt-[-10vh] z-10">
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
                <WelcomeScreen />
              </motion.div>
              <motion.div layout layoutId="chatbox-container" transition={{ duration: 0, ease: 'easeInOut' }} className="w-full max-w-4xl mx-auto mt-8 px-6 flex flex-col items-center pointer-events-auto">
                <div className="w-full flex justify-center">
                  <ChatBox {...chatBoxProps} />
                </div>
                <div className="font-normal text-white/70 text-[11px] font-inter tracking-wide text-center mt-4 select-none">
                  Libra is AI and can make mistakes. Check important info.
                </div>
              </motion.div>
            </main>
          ) : (
            /* ── Chat view ───────────────────────────────────── */
            <main className="flex-1 flex flex-col pointer-events-auto overflow-hidden w-full relative z-10">

              {/* Messages list */}
              <div className="h-full overflow-y-auto w-full max-w-[768px] mx-auto shrink-0 pt-4 pb-40 px-6 flex flex-col gap-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                {messages.map(msg => (
                  msg.role === 'user'
                    ? <UserMessage key={msg.id} message={msg} />
                    : <AiMessage
                      key={msg.id}
                      message={msg}
                      onRedo={handleRedo}
                      isFinished={!isGenerating || msg.id !== messages[messages.length - 1].id}
                      onExplanationClick={openExplanation}
                      onGraphClick={openGraph}
                    />
                ))}

                {isLoading && (
                  <ThinkingProcess isFinished={false} currentStep={currentStep} fallback={currentFallback} thoughts={thoughts} />
                )}

                {isLoading && <div className="h-[42vh] shrink-0" />}
                <div ref={messagesEndRef} className="h-4 shrink-0" />
              </div>

              {/* Sticky chat box */}
              <div className="absolute bottom-0 left-0 right-0 z-50 pb-4 pt-12 bg-gradient-to-t from-[#060010] via-[#060010]/80 to-transparent pointer-events-none flex justify-center w-full">
                <motion.div layout layoutId="chatbox-container" transition={{ duration: isChatLayoutSettled ? 0 : 0.5, ease: 'easeInOut' }} className="w-full max-w-[768px] mx-auto flex flex-col items-center shrink-0 px-6 pointer-events-auto">
                  <div className="w-full flex justify-center">
                    <ChatBox {...chatBoxProps} />
                  </div>
                  <div className="font-normal text-white/70 text-[11px] font-inter tracking-wide text-center mt-3 select-none">
                    Libra is AI and can make mistakes. Check important info.
                  </div>
                </motion.div>
              </div>
            </main>
          )}
        </div>

        {/* Explanation pane */}
        <ExplanationPane
          isOpen={isExplanationOpen}
          onClose={() => setIsExplanationOpen(false)}
          data={selectedExplanation}
        />

        {/* Knowledge Graph Viewer overlay */}
        <KnowledgeGraphViewer
          isOpen={isGraphOpen}
          onClose={() => setIsGraphOpen(false)}
          graphData={selectedGraphData?.graph_data || null}
        />
      </div>
    </div>
  );
}

export default App;
