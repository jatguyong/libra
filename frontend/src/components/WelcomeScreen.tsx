import React from 'react';
import { motion } from 'framer-motion';
import Typewriter from './Typewriter';

const WelcomeScreen = () => {
    return (
        <div className="flex flex-col items-center justify-center text-center select-none mb-14">
            {/* logo */}
            <motion.div
                initial={{ filter: "drop-shadow(0 0 0px rgba(255,255,255,0))" }}
                animate={{
                    filter: [
                        "drop-shadow(0 0 0px rgba(255,255,255,0))",
                        "drop-shadow(0 0 20px rgba(255,255,255,0.8))",
                        "drop-shadow(0 0 0px rgba(255,255,255,0))"
                    ]
                }}
                transition={{ duration: 2, ease: "easeInOut" }}
                className="mb-0"
            >
                <img
                    src="/libra_logo.png"
                    alt="Libra Logo"
                    className="w-24 h-24 object-contain"
                />
            </motion.div>

            {/* welcome to libra */}
            <motion.h2
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5, duration: 1 }}
                className="font-space text-2xl font-light tracking-wide text-white/90 mb-3"
            >
                Welcome to LIBRA
            </motion.h2>

            {/* how can i help? */}
            <div className="font-space text-6xl text-white font-light tracking-tight h-16">
                <Typewriter text="How can I help?" delay={2} />
            </div>

        </div>
    );
};

export default WelcomeScreen;