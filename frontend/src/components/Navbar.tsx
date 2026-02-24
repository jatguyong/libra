import React from 'react';

interface NavbarProps {
    isSidebarOpen: boolean;
    toggleSidebar: () => void;
}

const Navbar = ({ isSidebarOpen, toggleSidebar }: NavbarProps) => {
    return (
        <nav className="w-full h-[72px] flex items-center justify-between px-6 bg-transparent text-white pointer-events-auto shrink-0">

            <div
                className={`flex items-center gap-3 cursor-pointer group transition-opacity duration-200 ${isSidebarOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'
                    }`}
                onClick={toggleSidebar}
            >
                <img
                    src="/libra_logo.png"
                    alt="Libra Logo"
                    className="w-10 h-10 object-contain"
                />
                <span className="font-space text-lg font-normal tracking-widest mt-[2px] group-hover:text-white/80 transition-colors">
                    LIBRA
                </span>
            </div>

            {/* light mode toggle */}
            <div className="flex items-center gap-3 text-sm text-white/70 hover:text-white transition cursor-pointer">
                <span>Light Mode</span>
                <div className="w-8 h-4 bg-white/20 rounded-full relative flex items-center px-0.5">
                    <div className="w-3 h-3 bg-white rounded-full"></div>
                </div>
            </div>

        </nav>
    );
};

export default Navbar;