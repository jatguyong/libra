import React, { useState, type KeyboardEvent, useRef } from 'react';
import { Plus, Send, FileText, X, Info } from 'lucide-react';

interface ChatBoxProps {
    onSendMessage: (message: string, useGlobalKG: boolean) => void;
    isLoading?: boolean;
    isIngesting?: boolean;
    uploadedFiles?: File[];
    setUploadedFiles?: (files: File[]) => void;
    onFilesUploaded?: (files: File[]) => void;
    useGlobalKG?: boolean;
    setUseGlobalKG?: (value: boolean) => void;
}

const ChatBox = ({ onSendMessage, isLoading = false, isIngesting = false, uploadedFiles = [], setUploadedFiles, onFilesUploaded, useGlobalKG = false, setUseGlobalKG }: ChatBoxProps) => {
    const [inputText, setInputText] = useState('');
    const [showBadge, setShowBadge] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const adjustTextareaHeight = () => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    };

    // Reset height when input clears (e.g., after send)
    React.useEffect(() => {
        if (inputText === '') {
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    }, [inputText]);

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const newFiles = Array.from(e.target.files);
            const validFiles = newFiles.filter(file => file.type === 'application/pdf');

            if (validFiles.length > 0) {
                // Upload to backend first — state is added via onFilesUploaded callback on success
                const formData = new FormData();
                validFiles.forEach(file => {
                    formData.append('files', file);
                });

                try {
                    const response = await fetch('http://localhost:5000/api/ingest', {
                        method: 'POST',
                        body: formData,
                    });
                    if (!response.ok) {
                        console.error('Failed to upload files:', await response.text());
                    } else {
                        if (onFilesUploaded) {
                            onFilesUploaded(validFiles);
                        }
                        setShowBadge(true);
                    }
                } catch (error) {
                    console.error('Error uploading files:', error);
                }
            } else {
                alert('Please upload valid PDF files.');
            }
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleSend = () => {
        if (inputText.trim() && !isLoading && !isIngesting) {
            onSendMessage(inputText, useGlobalKG);
            setInputText(''); // clears the box after sending
            setShowBadge(false); // hides badge but keeps uploadedFiles in sidebar
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // prevents it from just dropping to a new line
            handleSend();
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setInputText(e.target.value);
        adjustTextareaHeight();
    };

    return (
        <div className="relative w-full rounded-[2rem] shadow-2xl group">

            <div
                className="absolute inset-0 rounded-[2rem] backdrop-blur-md"
                style={{
                    background: `
            radial-gradient(circle at 50% 50%, rgba(120, 120, 120, 0.2) 0%, rgba(120, 120, 120, 0.05) 100%), 
            linear-gradient(rgba(6, 0, 16, 0.65), rgba(6, 0, 16, 0.65))
          `
                }}
            />

            <div
                className="absolute inset-0 rounded-[2rem] pointer-events-none"
                style={{
                    padding: '1.5px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                    WebkitMaskComposite: 'xor',
                    maskComposite: 'exclude'
                }}
            />

            <div className="relative flex flex-col justify-between w-full min-h-[120px] px-6 py-5">
                <input
                    type="file"
                    accept="application/pdf"
                    multiple
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                />
                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 h-[2px] w-[0%] opacity-0 group-hover:w-[40%] group-hover:opacity-100 bg-gradient-to-r from-transparent via-[#A278AE] to-transparent shadow-[0_0_12px_#A278AE] transition-all duration-500 ease-out" />

                {showBadge && uploadedFiles.length > 0 && setUploadedFiles && (
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                        {uploadedFiles.map((file, index) => (
                            <div key={index} className="flex items-center gap-2 bg-white/10 backdrop-blur-md rounded-lg px-3 py-2 w-max max-w-full">
                                <FileText size={16} className="text-red-500 shrink-0" />
                                <span className="text-sm text-white/90 truncate font-sans">{file.name}</span>
                                <button
                                    onClick={() => {
                                        const newFiles = [...uploadedFiles];
                                        newFiles.splice(index, 1);
                                        setUploadedFiles(newFiles);
                                        if (newFiles.length === 0) setShowBadge(false);
                                    }}
                                    className="text-white/50 hover:text-white transition-colors cursor-pointer"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <textarea
                    ref={textareaRef}
                    value={inputText}
                    onChange={handleChange}
                    onKeyDown={handleKeyDown}
                    disabled={isLoading}
                    rows={1}
                    placeholder="Ask Libra any educational question..."
                    className="w-full bg-transparent border-none outline-none text-white font-inter text-sm placeholder:text-white/40 resize-none overflow-y-auto min-h-[44px] max-h-[200px]"
                    style={{ whiteSpace: 'pre-wrap' }}
                />

                <div className="flex justify-between items-center w-full mt-2">

                    <div className="flex items-center gap-3">
                        <button
                            className={`flex items-center justify-center w-8 h-8 rounded-full border transition cursor-pointer ${
                                isIngesting
                                    ? 'border-white/10 text-white/30 cursor-not-allowed'
                                    : 'border-white/20 text-white/70 hover:text-white hover:bg-white/10'
                            }`}
                            onClick={() => !isIngesting && fileInputRef.current?.click()}
                            disabled={isIngesting}
                            title={isIngesting ? 'Wait for ingestion to finish' : 'Upload PDF'}
                        >
                            <Plus size={16} />
                        </button>

                        <div className="flex items-center gap-2 pl-2">
                            <button
                                onClick={() => setUseGlobalKG && setUseGlobalKG(!useGlobalKG)}
                                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300 ease-in-out focus:outline-none ${useGlobalKG ? 'bg-[#A278AE]' : 'bg-white/20'}`}
                                role="switch"
                                aria-checked={useGlobalKG}
                            >
                                <span
                                    aria-hidden="true"
                                    className={`pointer-events-none inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow ring-0 transition duration-300 ease-in-out ${useGlobalKG ? 'translate-x-[19px]' : 'translate-x-[3px]'}`}
                                />
                            </button>

                            <span className="text-white/70 text-sm font-space select-none tracking-wide">Use Global KG</span>

                            <div className="relative group/tooltip flex items-center">
                                <Info size={17} className="text-white/50 cursor-help hover:text-white/80 transition-colors" />
                                <div className="font-inter absolute bottom-full left-0 mb-3 w-64 p-3 bg-[#1a1523] border border-white/10 rounded-xl shadow-2xl z-50 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all duration-300 origin-bottom-left scale-95 group-hover/tooltip:scale-100 text-xs text-white/80 leading-relaxed pointer-events-none">
                                    Searches the Global Knowledge Graph (including KBPedia and Wikidata) to provide highly accurate, fact-based answers.
                                    <div className="absolute top-full left-1.5 border-4 border-transparent border-t-[#1a1523]" />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        {isIngesting && (
                            <div className="flex items-center gap-1.5" title="Ingesting PDF into knowledge graph...">
                                <span className="inline-block w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                                <span className="text-[11px] text-white/40 font-inter">Ingesting…</span>
                            </div>
                        )}
                        <button
                            onClick={handleSend}
                            disabled={!inputText.trim() || isLoading || isIngesting}
                            className={`flex items-center justify-center w-9 h-9 rounded-full transition-all ${
                                (!inputText.trim() || isLoading || isIngesting)
                                    ? 'bg-white/5 text-white/30 cursor-not-allowed'
                                    : 'bg-white/20 text-white hover:bg-white/30 hover:scale-105'
                            }`}
                            title={isIngesting ? 'Waiting for PDF ingestion to complete…' : 'Send'}
                        >
                            <Send size={14} className="ml-[-2px]" />
                        </button>
                    </div>

                </div>

            </div>
        </div>
    );
};

export default ChatBox;