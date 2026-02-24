import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import Galaxy from './components/Backgrounds/Galaxy';
import Navbar from './components/Navbar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';
import { Brain, ChevronDown } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
}

const BotMessage = ({ message }: { message: Message }) => {
  const [isThoughtExpanded, setIsThoughtExpanded] = useState(false);

  return (
    <div className="flex w-full justify-start">
      <div className="max-w-[80%] rounded-2xl px-5 py-4 font-sans text-[15px] leading-relaxed bg-transparent text-white/90">

        {/* CoT header */}
        <button
          onClick={() => setIsThoughtExpanded(!isThoughtExpanded)}
          className="flex items-center gap-2 mb-2 group text-white/50 hover:text-white/80 transition-colors w-auto"
        >
          <Brain size={16} className="text-purple-400 group-hover:text-purple-300 transition-colors" />
          <span className="text-sm font-medium">Libra's Thought Process</span>
          <ChevronDown
            size={14}
            className={`transition-transform duration-300 ${isThoughtExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        {isThoughtExpanded && (
          <div className="pl-4 mt-2 border-l-2 border-white/10 text-sm text-white/50 space-y-2 mb-3">
            <p>• Parsing user intent and symbolic parameters...</p>
            <p>• Accessing context...</p>
            <p>• Synthesizing logical constraints for final output...</p>
          </div>
        )}

        <div style={{ whiteSpace: 'pre-wrap' }}>
          {message.content.replace(/<br\s*\/?>/gi, '\n').replace(/\n{3,}/g, '\n\n')}
        </div>

      </div>
    </div>
  );
};


function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const isChatting = messages.length > 0;

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const [isVoid, setIsVoid] = useState(false);
  const [hasStartedChat, setHasStartedChat] = useState(false);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

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
              const response = await fetch('http://127.0.0.1:5000/api/chat', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({ messages: updatedMessagesArray }),
              });

              const data = await response.json();

              const newBotMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'ai',
                content: data.response
              };
              setMessages((prev) => [...prev, newBotMsg]);
            } catch (error) {
              const errorMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'ai',
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
        const response = await fetch('http://127.0.0.1:5000/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ messages: updatedMessagesArray }),
        });

        const data = await response.json();

        const newBotMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'ai',
          content: data.response
        };
        setMessages((prev) => [...prev, newBotMsg]);
      } catch (error) {
        const errorMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'ai',
          content: "Error: Cannot connect to the Libra backend."
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    }
  };


  return (
    // ROOT is now a flex-row
    <div className="relative h-screen w-full flex flex-row overflow-hidden bg-[#060010]">

      {isVoid && (
        <div className="absolute inset-0 bg-[#060010] z-[100] pointer-events-auto" />
      )}

      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 z-0">
          <Galaxy
            mouseRepulsion={false}
            mouseInteraction={!isChatting}
            density={1}
            glowIntensity={isChatting ? 0.05 : 0.2}
            saturation={0}
            hueShift={140}
            twinkleIntensity={isChatting ? 0.05 : 0.3}
            rotationSpeed={isChatting ? 0.0 : 0.05}
            repulsionStrength={10}
            autoCenterRepulsion={0}
            starSpeed={isChatting ? 0 : 0.2}
            speed={isChatting ? 0.2 : 0.8}
          />
        </div>
      </div>

      <div className="relative z-10 flex flex-row h-full w-full pointer-events-none">

        <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} uploadedFile={uploadedFile} />

        <div className="flex-1 flex flex-col h-full relative overflow-hidden transition-all duration-300">

          <div className="pointer-events-auto w-full shrink-0 relative z-50">
            <Navbar isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
          </div>

          {!hasStartedChat ? (

            <main className="flex-1 flex flex-col items-center justify-center pointer-events-none px-6 mt-[-10%]">
              <WelcomeScreen />
              <div className="w-full flex justify-center pointer-events-auto">
                <ChatBox onSendMessage={handleSendMessage} isLoading={isLoading} uploadedFile={uploadedFile} setUploadedFile={setUploadedFile} />
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
                          className="max-w-[80%] rounded-2xl px-5 py-4 font-sans text-[15px] leading-relaxed bg-white/10 text-white border border-white/10 backdrop-blur-md"
                          style={{ whiteSpace: 'pre-wrap' }}
                        >
                          {msg.content.replace(/\n{3,}/g, '\n\n')}
                        </div>
                      </div>
                    ) : (
                      <BotMessage message={msg} />
                    )}
                  </React.Fragment>
                ))}

                {isLoading && (
                  <div className="flex w-full justify-start">
                    <div className="bg-transparent text-white/50 font-sans px-5 py-4 animate-pulse">
                      Libra is thinking...
                    </div>
                  </div>
                )}

                {/* Auto-scroll target */}
                <div ref={messagesEndRef} />
              </div>

              <div className="w-full flex justify-center shrink-0 pt-4">
                <ChatBox onSendMessage={handleSendMessage} isLoading={isLoading} uploadedFile={uploadedFile} setUploadedFile={setUploadedFile} />
              </div>

            </main>

          )}
        </div>

      </div>
    </div>
  );
}

export default App;




