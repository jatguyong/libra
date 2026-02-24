import React, { useState } from 'react';
import { motion } from 'framer-motion';
import Galaxy from './components/Backgrounds/Galaxy';
import Navbar from './components/Navbar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatBox from './components/ChatBox';
import Sidebar from './components/Sidebar';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
}


function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const isChatting = messages.length > 0;

  const [isVoid, setIsVoid] = useState(false);
  const [hasStartedChat, setHasStartedChat] = useState(false);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);


  const handleSendMessage = (text: string) => {
    if (!hasStartedChat) {
      setIsVoid(true);

      setTimeout(() => {

        setHasStartedChat(true);
        const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
        setMessages([newUserMsg]);
        setIsLoading(true);

        // sync with the browser's GPU paint cycle
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            setIsVoid(false);

            setTimeout(() => {
              const newBotMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'ai',
                content: "I am the Libra UI. Everything is working perfectly on the frontend!"
              };
              setMessages((prev) => [...prev, newBotMsg]);
              setIsLoading(false);
            }, 1200);
          });
        });

      }, 100);

    } else {
      const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
      setMessages((prev) => [...prev, newUserMsg]);
      setIsLoading(true);

      setTimeout(() => {
        const newBotMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'ai',
          content: "I am receiving your messages clearly!"
        };
        setMessages((prev) => [...prev, newBotMsg]);
        setIsLoading(false);
      }, 1500);
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

        <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />

        <div className="flex-1 flex flex-col h-full relative overflow-hidden transition-all duration-300">

          <div className="pointer-events-auto w-full shrink-0 relative z-50">
            <Navbar isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
          </div>

          {!hasStartedChat ? (

            <main className="flex-1 flex flex-col items-center justify-center pointer-events-none px-6 mt-[-10%]">
              <WelcomeScreen />
              <div className="w-full flex justify-center pointer-events-auto">
                <ChatBox onSendMessage={handleSendMessage} isLoading={isLoading} />
              </div>
            </main>

          ) : (

            <main className="flex-1 flex flex-col pointer-events-auto px-6 pb-8 overflow-hidden w-full max-w-4xl mx-auto">

              <div className="flex-1 overflow-y-auto w-full pt-4 flex flex-col gap-6 scrollbar-hide">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-2xl px-5 py-4 font-sans text-[15px] leading-relaxed ${msg.role === 'user'
                      ? 'bg-white/10 text-white border border-white/10 backdrop-blur-md'
                      : 'bg-transparent text-white/90'
                      }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="flex w-full justify-start">
                    <div className="bg-transparent text-white/50 font-sans px-5 py-4 animate-pulse">
                      Libra is thinking...
                    </div>
                  </div>
                )}
              </div>

              <div className="w-full flex justify-center shrink-0 pt-4">
                <ChatBox onSendMessage={handleSendMessage} isLoading={isLoading} />
              </div>

            </main>

          )}
        </div>

      </div>
    </div>
  );
}

export default App;




