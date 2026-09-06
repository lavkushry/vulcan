import { useState, useEffect } from 'react';

export function useKeyboardNavigation(taskCount: number, onApprove: (index: number) => void, onOpenTerminal: (index: number) => void) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA'].includes(target.tagName) || target.isContentEditable) {
        return;
      }

      switch (e.key) {
        case 'j':
          e.preventDefault();
          setSelectedIndex(prev => (prev === null ? 0 : Math.min(prev + 1, taskCount - 1)));
          break;
        case 'k':
          e.preventDefault();
          setSelectedIndex(prev => (prev === null ? Math.max(0, taskCount - 1) : Math.max(0, prev - 1)));
          break;
        case '/':
          e.preventDefault();
          const searchInput = document.querySelector('input[type="search"], input[placeholder*="Search"]') as HTMLInputElement;
          if (searchInput) {
            searchInput.focus();
          }
          break;
        case 'Escape':
          setSelectedIndex(null);
          break;
        case 'Enter':
          if ((e.metaKey || e.ctrlKey)) {
            if (selectedIndex !== null) onApprove(selectedIndex);
          } else {
            if (selectedIndex !== null) onOpenTerminal(selectedIndex);
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [taskCount, selectedIndex, onApprove, onOpenTerminal]);

  return { selectedIndex, setSelectedIndex };
}
