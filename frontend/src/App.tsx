import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import Galaxy from './components/Backgrounds/Galaxy';
import Navbar from './components/Navbar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';
import { Brain, ChevronDown, Copy, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
interface Message {
  id: string;
  role: 'user' | 'llm';
  content: string;
  alternativeContents?: string[];
}

const AiMessage = ({ message, onRedo, isFinished }: { message: Message, onRedo: (id: string) => void, isFinished: boolean }) => {
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

        {/* CoT header */}
        <button
          onClick={() => setIsThoughtExpanded(!isThoughtExpanded)}
          className="flex items-center gap-2 mb-2 group text-white/50 hover:text-white/80 transition-colors w-auto"
        >
          <Brain size={16} className="font-inter text-purple-400 group-hover:text-purple-300 transition-colors" />
          <span className="text-sm font-medium">Libra's Thought Process</span>
          <ChevronDown
            size={14}
            className={`transition-transform duration-300 ${isThoughtExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        {isThoughtExpanded && (
          <div className="font-inter pl-4 mt-2 border-l-2 border-white/10 text-sm text-white/50 space-y-2 mb-3">
            <p>• Parsing user intent and symbolic parameters...</p>
            <p>• Accessing context...</p>
            <p>• Synthesizing logical constraints for final output...</p>
          </div>
        )}

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
          <div className="mt-2 flex items-center gap-1 text-white/40">
            <div className="relative group/tooltip flex items-center justify-center">
              <button onClick={handleCopy} className="p-1.5 hover:text-white hover:bg-white/10 rounded-md transition-colors">
                <Copy size={16} />
              </button>
              <div className="absolute bottom-full mb-2 bg-[#1a1523] text-white/80 text-xs px-2 py-1 rounded border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all whitespace-nowrap z-10 pointer-events-none">
                {copied ? 'Copied!' : 'Copy'}
              </div>
            </div>

            <div className="relative group/tooltip flex items-center justify-center">
              <button onClick={() => onRedo(message.id)} className="p-1.5 hover:text-white hover:bg-white/10 rounded-md transition-colors">
                <RefreshCw size={16} />
              </button>
              <div className="absolute bottom-full mb-2 bg-[#1a1523] text-white/80 text-xs px-2 py-1 rounded border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all whitespace-nowrap z-10 pointer-events-none">
                Redo response
              </div>
            </div>

            {variants.length > 1 && (
              <div className="flex items-center gap-1 ml-1 select-none text-xs font-medium">
                <button
                  onClick={handlePrev}
                  disabled={viewIndex === 0}
                  className={`p-1 rounded-md transition-colors ${viewIndex === 0 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/10 hover:text-white'}`}
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="w-8 text-center">{viewIndex + 1}/{variants.length}</span>
                <button
                  onClick={handleNext}
                  disabled={viewIndex === variants.length - 1}
                  className={`p-1 rounded-md transition-colors ${viewIndex === variants.length - 1 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/10 hover:text-white'}`}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
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

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const [isVoid, setIsVoid] = useState(false);
  const [hasStartedChat, setHasStartedChat] = useState(false);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  const handleNewConversation = () => {
    setMessages([]);
    setHasStartedChat(false);
    setUploadedFile(null);
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);


  const handleSendMessage = async (text: string) => {
    if (!hasStartedChat) {
      setIsVoid(true);

      setTimeout(() => {

        setHasStartedChat(true);
        const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
        const updatedMessagesArray = [newUserMsg];
        setMessages(updatedMessagesArray);
        setIsLoading(true);

        // sync with the browser's GPU paint cycle
        requestAnimationFrame(() => {
          requestAnimationFrame(async () => {
            setIsVoid(false);

            try {
              const response = await fetch('http://localhost:5000/api/chat', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({ messages: updatedMessagesArray }),
              });

              if (!response.body) throw new Error('No response body');

              setMessages((prev) => [...prev, { id: (Date.now() + 1).toString(), role: 'llm', content: '' }]);

              const reader = response.body.getReader();
              const decoder = new TextDecoder('utf-8');

              while (true) {
                const { done, value } = await reader.read();
                if (done) {
                  setIsLoading(false); // final cleanup when stream finishes
                  break;
                }

                setIsLoading(false); // remove indicator once text starts arriving
                const chunkText = decoder.decode(value, { stream: true });

                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === (Date.now() + 1).toString() ? { ...msg, content: msg.content + chunkText } : msg
                  )
                );
              }
            } catch (error) {
              const errorMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'llm',
                content: "Error: Cannot connect to the Libra backend."
              };
              setMessages((prev) => [...prev, errorMsg]);
            } finally {
              setIsLoading(false);
            }
          });
        });

      }, 100);

    } else {
      const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
      const updatedMessagesArray = [...messages, newUserMsg];
      setMessages(updatedMessagesArray);
      setIsLoading(true);

      try {
        const response = await fetch('http://localhost:5000/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ messages: updatedMessagesArray }),
        });

        if (!response.body) throw new Error('No response body');

        const llmMsgId = (Date.now() + 1).toString();
        setMessages((prev) => [...prev, { id: llmMsgId, role: 'llm', content: '' }]);

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            setIsLoading(false); // final cleanup when stream finishes
            break;
          }

          setIsLoading(false); // remove indicator once text starts arriving
          const chunkText = decoder.decode(value, { stream: true });

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === llmMsgId ? { ...msg, content: msg.content + chunkText } : msg
            )
          );
        }
      } catch (error) {
        const errorMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'llm',
          content: "Error: Cannot connect to the Libra backend."
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
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

    try {
      const response = await fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages: contextMessages }),
      });

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          setIsLoading(false);
          break;
        }

        setIsLoading(false);
        const chunkText = decoder.decode(value, { stream: true });

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === llmMsgId ? { ...msg, content: msg.content + chunkText } : msg
          )
        );
      }
    } catch (error) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === llmMsgId ? { ...msg, content: "Error: Cannot connect to the Libra backend." } : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="relative h-screen w-full flex flex-row overflow-hidden bg-[#060010]">

      {isVoid && (
        <div className="absolute inset-0 bg-[#060010] z-[100] pointer-events-auto" />
      )}

      <div className="absolute inset-0 z-0">
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
      </div>

      <div className="relative z-10 flex flex-row h-full w-full pointer-events-none">

        <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} uploadedFile={uploadedFile} onNewConversation={handleNewConversation} />

        <div className="flex-1 flex flex-col h-full relative overflow-hidden transition-all duration-300">

          <div className="pointer-events-auto w-full shrink-0 relative z-50">
            <Navbar isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
          </div>

          {!hasStartedChat ? (

            <main className="flex-1 flex flex-col items-center justify-center pointer-events-none px-6 mt-[-10%]">
              <WelcomeScreen />
              <div className="w-full max-w-4xl mx-auto mt-8 px-6 flex justify-center pointer-events-auto">
                <ChatBox
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading}
                  uploadedFile={uploadedFile}
                  setUploadedFile={setUploadedFile}
                />
              </div>
            </main>

          ) : (

            <main className="flex-1 flex flex-col pointer-events-auto overflow-hidden w-full relative">

              <div className="h-full overflow-y-auto w-full max-w-4xl mx-auto pt-4 pb-40 px-6 flex flex-col gap-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
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
                        isFinished={!isLoading || msg.id !== messages[messages.length - 1].id}
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
                <div className="w-full max-w-4xl mx-auto px-6 flex justify-center pointer-events-auto">
                  <ChatBox
                    onSendMessage={handleSendMessage}
                    isLoading={isLoading}
                    uploadedFile={uploadedFile}
                    setUploadedFile={setUploadedFile}
                  />
                </div>
              </div>

            </main>

          )}
        </div>

      </div>
    </div>
  );
}

export default App;




