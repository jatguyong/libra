import React, { useState } from 'react';
import { motion } from 'framer-motion'; //
import Galaxy from './components/Backgrounds/Galaxy';
import Navbar from './components/Navbar';
import WelcomeScreen from './components/WelcomeScreen';
import GlassInputBar from './components/GlassInputBar';

interface Message {
  id: string;
  role: 'user' | 'bot';
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // the function that receives the typed text from GlassInputBar
  const handleSendMessage = (text: string) => {
    // add the user's message to the screen immediately
    const newUserMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    setMessages((prev) => [...prev, newUserMsg]);

    // simulate Libra thinking for 1.5 seconds, then reply
    setIsLoading(true);
    setTimeout(() => {
      const newBotMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: "bobo pa ako sorry"
      };
      setMessages((prev) => [...prev, newBotMsg]);
      setIsLoading(false);
    }, 1500);
  };

  return (
    <div className="relative h-screen w-full flex flex-col overflow-hidden">

      {/* LAYER 0: Galaxy bg */}
      <div className="absolute inset-0 z-0">
        <Galaxy
          mouseRepulsion={false}
          mouseInteraction={true}
          density={1}
          glowIntensity={0.2}
          saturation={0}
          hueShift={140}
          twinkleIntensity={0.3}
          rotationSpeed={0.05}
          repulsionStrength={10}
          autoCenterRepulsion={0}
          starSpeed={0.2}
          speed={0.8}
        />
      </div>

      {/* LAYER 1: UI Overlay */}
      <div className="relative z-10 flex flex-col h-full w-full pointer-events-none">

        <div className="pointer-events-auto">
          <Navbar />
        </div>


        {messages.length === 0 ? (
          <main className="flex-1 flex flex-col items-center justify-center px-6 mt-[-10%]">
            <WelcomeScreen />

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1, duration: 1, ease: "easeOut" }}
              className="w-full flex justify-center pointer-events-auto"
            >
              <GlassInputBar onSendMessage={handleSendMessage} isLoading={isLoading} />
            </motion.div>

          </main>

        ) : (

          /* CHAT STATE: Messages in the middle, Input Bar at the bottom */
          <main className="flex-1 flex flex-col px-6 pb-8 overflow-hidden">

            {/* The scrollable chat area */}
            <div className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto pt-8 flex flex-col gap-6 pointer-events-auto">
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

            {/* The input bar anchored to the bottom */}
            <div className="w-full flex justify-center shrink-0 pointer-events-auto">
              <GlassInputBar onSendMessage={handleSendMessage} isLoading={isLoading} />
            </div>

          </main>

        )}

      </div>
    </div>
  );
}

export default App;