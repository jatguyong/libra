import { motion } from 'framer-motion';


const Typewriter = ({ text, delay = 0 }: { text: string; delay?: number }) => {
    const characters = text.split('');

    return (
        <div className="flex justify-center">
            {characters.map((char, index) => (
                <motion.span
                    key={index}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    // waits for the logo glow to finish
                    transition={{ delay: delay + index * 0.05, duration: 0.1 }}
                    style={{ whiteSpace: 'pre' }}
                >
                    {char}
                </motion.span>
            ))}
        </div>
    );
};

export default Typewriter;