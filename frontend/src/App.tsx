import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import Galaxy from './components/Backgrounds/Galaxy';
import Navbar from './components/Navbar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';
import { Brain, ChevronDown } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'llm';
  content: string;
}

const AiMessage = ({ message }: { message: Message }) => {
  const [isThoughtExpanded, setIsThoughtExpanded] = useState(false);

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
            {message.content.replace(/<br\s*\/?>/gi, '\n')}
          </ReactMarkdown>
        </div>

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
            glowIntensity={hasStartedChat ? 0.05 : 0.2}
            saturation={0}
            hueShift={140}
            twinkleIntensity={hasStartedChat ? 0.05 : 0.3}
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
              <div className="w-full flex justify-center pointer-events-auto">
                <ChatBox
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading}
                  uploadedFile={uploadedFile}
                  setUploadedFile={setUploadedFile}
                  isChatActive={hasStartedChat}
                />
              </div>
            </main>

          ) : (

            <main className="flex-1 flex flex-col pointer-events-auto px-6 pb-8 overflow-hidden w-full max-w-4xl mx-auto">

              <div className="flex-1 overflow-y-auto w-full pt-4 flex flex-col gap-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
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
                      <AiMessage message={msg} />
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
                <div ref={messagesEndRef} />
              </div>

              <div className="w-full flex justify-center shrink-0 pt-4">
                <ChatBox
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading}
                  uploadedFile={uploadedFile}
                  setUploadedFile={setUploadedFile}
                  isChatActive={hasStartedChat}
                />
              </div>

            </main>

          )}
        </div>

      </div>
    </div>
  );
}

export default App;




