/**
 * UserMessage — renders a single user chat bubble.
 */

import type { Message } from '../../lib/types';

interface UserMessageProps {
  message: Message;
}

export default function UserMessage({ message }: UserMessageProps) {
  return (
    <div className="flex w-full justify-end">
      <div
        className="max-w-[80%] rounded-2xl rounded-tr-[4px] px-5 py-4 font-inter text-[15px] leading-relaxed bg-white/10 text-white border border-white/10 backdrop-blur-md"
        style={{ whiteSpace: 'pre-wrap' }}
      >
        {message.content.replace(/\n{3,}/g, '\n\n')}
      </div>
    </div>
  );
}
