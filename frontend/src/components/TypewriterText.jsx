import React, { useState, useEffect, useRef } from 'react';

/**
 * TypewriterText — progressively reveals text character-by-character.
 * 
 * Props:
 *   content      – full string to reveal
 *   speed        – interval in ms between ticks (lower = faster)
 *   charsPerTick – characters revealed per tick
 *   onComplete   – callback fired after the full text is shown (with a small pause)
 */
const TypewriterText = ({ content, speed = 18, charsPerTick = 3, onComplete }) => {
  const [charIndex, setCharIndex] = useState(0);
  const timerRef = useRef(null);
  const completedRef = useRef(false);
  const contentRef = useRef(content);

  useEffect(() => {
    // If the content prop changed (new subtask), reset
    contentRef.current = content;
    completedRef.current = false;
    setCharIndex(0);

    if (!content) return;

    timerRef.current = setInterval(() => {
      setCharIndex(prev => {
        const next = Math.min(prev + charsPerTick, contentRef.current.length);
        if (next >= contentRef.current.length && !completedRef.current) {
          completedRef.current = true;
          clearInterval(timerRef.current);
          timerRef.current = null;
          // Brief pause so the user can read the last few chars before the accordion closes
          if (onComplete) setTimeout(onComplete, 600);
        }
        return next;
      });
    }, speed);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [content, speed, charsPerTick]); // re-run when content changes

  const displayedText = content ? content.slice(0, charIndex) : '';
  const isTyping = charIndex < (content?.length || 0);

  return (
    <span className="typewriter-text">
      {displayedText}
      {isTyping && <span className="typewriter-cursor">▋</span>}
    </span>
  );
};

export default TypewriterText;
