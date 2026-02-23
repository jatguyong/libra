import React, { useState } from 'react';

const Navbar = () => {
    // toggle switch (does not actually change theme yet)
    const [isLightMode, setIsLightMode] = useState(false);

    return (
        <nav className="w-full flex items-center justify-between px-10 py-6 select-none z-50">
            <div className="flex items-center gap-8">
                <div className="flex items-center gap-3 cursor-pointer">
                    <span className="text-4xl font-space font-light tracking-tight text-white">Ω</span>
                    <span className="text-2xl font-space font-light tracking-[0.2em] uppercase text-white">
                        Libra
                    </span>
                </div>

                <div className="h-6 w-[1px] bg-white/20 rounded-full hidden md:block"></div>

                <a href="#" className="text-sm font-sans text-white/50 hover:text-white transition-colors duration-300 hidden md:block">
                    Documentation
                </a>
            </div>


            <div className="flex items-center gap-4">
                <span className="text-sm font-sans text-white/70">
                    Light Mode
                </span>

                <button
                    onClick={() => setIsLightMode(!isLightMode)}
                    className={`relative w-14 h-7 rounded-full border transition-colors duration-300 flex items-center px-1
            ${isLightMode ? 'bg-white/20 border-white/40' : 'bg-white/5 border-white/20'}`}
                >

                    <div
                        className={`w-5 h-5 rounded-full bg-white shadow-lg transition-transform duration-300 
              ${isLightMode ? 'translate-x-7' : 'translate-x-0'}`}
                    ></div>
                </button>
            </div>

        </nav>
    );
};

export default Navbar;