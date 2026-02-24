import React from 'react';
import { motion } from 'framer-motion';
import { Edit, FileText, ExternalLink } from 'lucide-react';

interface SidebarProps {
    isOpen: boolean;
    toggleSidebar: () => void;
    uploadedFile: File | null;
}

const Sidebar = ({ isOpen, toggleSidebar, uploadedFile }: SidebarProps) => {
    return (
        <motion.div
            initial={false}
            animate={{ width: isOpen ? 260 : 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="h-full shrink-0 bg-[#0E0915] border-r border-white/10 overflow-hidden flex flex-col pointer-events-auto z-20"
        >

            <div className="w-[260px] flex flex-col h-full">
                <div
                    className="h-[72px] flex items-center gap-3 px-6 cursor-pointer shrink-0"
                    onClick={toggleSidebar}
                >
                    <motion.img
                        src="/libra_logo.png"
                        alt="Libra Logo"
                        className="w-10 h-10 object-contain"
                        // rotates -90 when opened
                        animate={{ rotate: isOpen ? -90 : 0 }}
                        transition={{ duration: 0.3, ease: "easeInOut" }}
                    />
                    <span className="font-space text-lg font-normal tracking-widest mt-[2px] text-white">
                        LIBRA
                    </span>
                </div>

                <div className="flex-1 overflow-y-auto px-4 py-2 flex flex-col gap-6 scrollbar-hide">

                    <button className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-[#343039] text-white hover:bg-[#3f3a45] transition-all text-sm font-sans font-medium">
                        <Edit size={18} />
                        New Conversation
                    </button>

                    {uploadedFile && (
                        <div className="flex flex-col gap-3 mt-2">
                            <span className="text-xs font-sans text-white/40 px-2 tracking-wider uppercase font-medium">Uploaded PDF</span>
                            <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/5 pointer-events-none group">
                                <FileText size={20} className="text-[#ff4a4a] shrink-0" />
                                <span className="text-sm font-sans text-white/80 truncate">
                                    {uploadedFile.name}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                <div className="mt-auto flex flex-col gap-4 p-6 shrink-0">
                    <a href="#" className="flex items-center gap-2 text-sm font-sans text-white/70 hover:text-white transition-all">
                        View Documentation
                        <ExternalLink size={14} />
                    </a>
                    <span className="text-xs font-sans text-white/30">
                        Built by your mama
                    </span>
                </div>

            </div>
        </motion.div>
    );
};

export default Sidebar;