import { motion } from 'framer-motion';
import { Edit, FileText, ExternalLink, X, Loader2, CheckCircle2, AlertCircle, Trash2 } from 'lucide-react';

interface SidebarProps {
    isOpen: boolean;
    toggleSidebar: () => void;
    uploadedFiles: File[];
    fileStatuses: Record<string, { status: string; duration_s?: number; error?: string }>;
    onNewConversation: () => void;
    onRemoveFile: (filename: string) => void;
    onClearAllFiles: () => void;
}

const FileStatusIcon = ({ status }: { status: string }) => {
    switch (status) {
        case 'processing':
            return <Loader2 size={14} className="text-purple-400 animate-spin shrink-0" />;
        case 'done':
            return <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />;
        case 'error':
            return <AlertCircle size={14} className="text-red-400 shrink-0" />;
        default:
            return null;
    }
};

const Sidebar = ({ isOpen, toggleSidebar, uploadedFiles, fileStatuses, onNewConversation, onRemoveFile, onClearAllFiles }: SidebarProps) => {
    return (
        <motion.div
            initial={false}
            animate={{ width: isOpen ? 260 : 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="h-full shrink-0 flex flex-col pointer-events-auto z-20 relative"
        >

            {/* Background and Clipped Content Layer */}
            <div className="absolute inset-0 bg-[#0E0915] border-r border-white/10 overflow-hidden">
                {/* The inner container is fixed 260px so elements inside don't squish or wrap. They get cleanly clipped by the parent's shrinking width. */}
                <div className="w-[260px] flex flex-col h-full pt-[72px]">

                    {/* Menu Items Area - Fades out gracefully */}
                    <div className={`flex-1 overflow-y-auto px-4 py-2 flex flex-col gap-6 scrollbar-hide ${!isOpen ? 'pointer-events-none' : ''}`}>

                        {/* the explicit fading and width-shrinking container requested by user */}
                        <motion.div
                            initial={false}
                            animate={{ width: isOpen ? "100%" : 0, opacity: isOpen ? 1 : 0 }}
                            transition={{ duration: 0.3, ease: "easeInOut" }}
                            style={{ overflow: 'hidden' }}
                        >
                            <button
                                onClick={onNewConversation}
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-[#343039] text-white hover:bg-[#3f3a45] transition-colors text-sm font-sans font-medium whitespace-nowrap"
                            >
                                <Edit size={18} className="shrink-0" />
                                <span>New Conversation</span>
                            </button>
                        </motion.div>

                        <motion.div
                            initial={false}
                            animate={{ opacity: isOpen ? 1 : 0 }}
                            transition={{ duration: 0.3, ease: "easeInOut" }}
                        >
                            {uploadedFiles.length > 0 && (
                                <div className="flex flex-col gap-3 mt-2">
                                    <div className="flex items-center justify-between px-2">
                                        <span className="text-xs font-sans text-white/40 tracking-wider uppercase font-medium whitespace-nowrap">Uploaded PDFs</span>
                                        <button 
                                            onClick={onClearAllFiles}
                                            className="text-white/30 hover:text-red-400 transition-colors p-1 rounded-md hover:bg-white/5"
                                            title="Clear all documents from knowledge graph"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        {uploadedFiles.map((file, index) => {
                                            const fileStatus = fileStatuses[file.name];
                                            const status = fileStatus?.status || 'processing';
                                            const durationInfo = fileStatus?.duration_s ? `${fileStatus.duration_s}s` : '';

                                            return (
                                                <div key={index} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 group whitespace-nowrap">
                                                    <FileText size={18} className="text-[#ff4a4a] shrink-0" />
                                                    <span className="text-sm font-sans text-white/80 truncate flex-1 min-w-0">
                                                        {file.name}
                                                    </span>
                                                    <div className="flex items-center gap-1.5 shrink-0">
                                                        {durationInfo && status === 'done' && (
                                                            <span className="text-[10px] text-white/30 font-mono">{durationInfo}</span>
                                                        )}
                                                        <FileStatusIcon status={status} />
                                                        <button
                                                            onClick={() => onRemoveFile(file.name)}
                                                            className="p-0.5 text-white/30 hover:text-red-400 transition-colors cursor-pointer opacity-0 group-hover:opacity-100"
                                                            title="Remove from knowledge graph"
                                                        >
                                                            <X size={14} />
                                                        </button>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    </div>

                    {/* Footer Area */}
                    <motion.div
                        initial={false}
                        animate={{ opacity: isOpen ? 1 : 0 }}
                        transition={{ duration: 0.3, ease: "easeInOut" }}
                        className={`mt-auto flex flex-col gap-4 p-6 shrink-0 ${!isOpen ? 'pointer-events-none' : ''}`}
                    >
                        <a href="#" className="flex items-center gap-2 text-sm font-sans text-white/70 hover:text-white transition-all whitespace-nowrap">
                            View Documentation
                            <ExternalLink size={14} className="shrink-0" />
                        </a>
                        <span className="text-xs font-sans text-white/30 whitespace-nowrap">
                            Prototype for CCS10: Thesis Writing 2
                        </span>
                    </motion.div>
                </div>
            </div>

            {/* Header / Logo section - placed absolutely so it always stays visibly sticking out to the right when closed */}
            <div className="absolute top-0 left-0 w-[260px] h-[72px] z-50 pointer-events-none">
                <div
                    className="h-[72px] flex items-center gap-3 px-6 cursor-pointer pointer-events-auto w-fit select-none"
                    onClick={toggleSidebar}
                >
                    <motion.img
                        src="/libra_logo.png"
                        alt="Libra Logo"
                        className="w-10 h-10 object-contain pointer-events-none"
                        animate={{ rotate: isOpen ? -90 : 0 }}
                        transition={{ duration: 0.3, ease: "easeInOut" }}
                    />
                    <span className="font-space text-lg font-normal tracking-widest mt-[2px] text-white">
                        LIBRA
                    </span>
                </div>
            </div>

        </motion.div>
    );
};

export default Sidebar;