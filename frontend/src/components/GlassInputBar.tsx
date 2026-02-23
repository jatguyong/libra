import React, { useState, KeyboardEvent } from 'react';
import { Plus, ChevronDown, Send } from 'lucide-react';

// PROPS: This allows the InputBar to send the message up to your main App
interface GlassInputBarProps {
    onSendMessage: (message: string) => void;
    isLoading?: boolean;
}

const GlassInputBar = ({ onSendMessage, isLoading = false }: GlassInputBarProps) => {
    // STATE: Tracks the text currently in the box
    const [inputText, setInputText] = useState('');

    // HANDLER: Triggers when you click send or press enter
    const handleSend = () => {
        if (inputText.trim() && !isLoading) {
            onSendMessage(inputText);
            setInputText(''); // Clears the box after sending
        }
    };

    // HANDLER: Listens for the "Enter" key
    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Prevents it from just dropping to a new line
            handleSend();
        }
    };

    return (
        <div className="relative w-full max-w-3xl mt-8 rounded-[2rem] shadow-2xl group">

            <div
                className="absolute inset-0 rounded-[2rem] backdrop-blur-md"
                style={{
                    background: `
            radial-gradient(circle at 50% 50%, rgba(165, 239, 255, 0.2) 0%, rgba(110, 191, 244, 0.2) 77%, rgba(70, 144, 212, 0.2) 100%), 
            linear-gradient(rgba(6, 0, 16, 0.65), rgba(6, 0, 16, 0.65))
          `
                }}
            />

            <div
                className="absolute inset-0 rounded-[2rem] pointer-events-none"
                style={{
                    padding: '1px',
                    background: 'linear-gradient(to right, #98F9FF, #FFFFFF, #725584, #654B76)',
                    WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                    WebkitMaskComposite: 'xor',
                    maskComposite: 'exclude'
                }}
            />

            <div className="relative flex flex-col justify-between w-full min-h-[140px] px-6 py-5">

                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 h-[2px] w-[0%] opacity-0 group-hover:w-[40%] group-hover:opacity-100 bg-gradient-to-r from-transparent via-[#A278AE] to-transparent shadow-[0_0_12px_#A278AE] transition-all duration-500 ease-out" />
                <textarea
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isLoading}
                    placeholder="Ask me any educational questions..."
                    className="w-full bg-transparent border-none outline-none text-white font-sans text-sm placeholder:text-white/40 resize-none h-12"
                    style={{ whiteSpace: 'pre-wrap' }}
                />

                <div className="flex justify-between items-center w-full mt-2">

                    <div className="flex items-center gap-3">
                        <button className="flex items-center justify-center w-8 h-8 rounded-full border border-white/20 text-white/70 hover:text-white hover:bg-white/10 transition">
                            <Plus size={16} />
                        </button>

                        <button className="flex items-center gap-2 px-4 py-1.5 rounded-full border border-white/20 text-white/70 text-xs font-sans hover:bg-white/10 transition">
                            Symbolic Engine
                            <ChevronDown size={14} />
                        </button>
                    </div>

                    <button
                        onClick={handleSend}
                        disabled={!inputText.trim() || isLoading}
                        className={`flex items-center justify-center w-9 h-9 rounded-full transition-all ${inputText.trim()
                            ? 'bg-white/20 text-white hover:bg-white/30 hover:scale-105'
                            : 'bg-white/5 text-white/30 cursor-not-allowed'
                            }`}
                    >
                        <Send size={14} className="ml-[-2px]" />
                    </button>

                </div>

            </div>
        </div>
    );
};

export default GlassInputBar;