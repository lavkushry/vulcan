'use client';

import { useEffect, useCallback } from 'react';

export interface HotkeyOptions {
  onNextItem?: () => void; // 'j' or 'ArrowDown'
  onPrevItem?: () => void; // 'k' or 'ArrowUp'
  onExecuteOrApprove?: () => void; // 'Cmd+Enter' or 'Ctrl+Enter'
  onFocusSearch?: () => void; // '/'
  onDismiss?: () => void; // 'Escape'
  onToggleHelp?: () => void; // '?'
}

export function useKeyboardHotkeys({
  onNextItem,
  onPrevItem,
  onExecuteOrApprove,
  onFocusSearch,
  onDismiss,
  onToggleHelp,
}: HotkeyOptions) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const activeTag = (document.activeElement?.tagName || '').toLowerCase();
      const isInputActive =
        activeTag === 'input' ||
        activeTag === 'textarea' ||
        document.activeElement?.getAttribute('contenteditable') === 'true';

      // 1. Meta / Ctrl + Enter (Universal Execute / Approve)
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        if (onExecuteOrApprove) {
          e.preventDefault();
          onExecuteOrApprove();
        }
        return;
      }

      // 2. Escape (Universal Dismiss)
      if (e.key === 'Escape') {
        if (onDismiss) {
          e.preventDefault();
          onDismiss();
        }
        return;
      }

      // If typing inside an input field, do not trigger single-key hotkeys
      if (isInputActive) {
        return;
      }

      // 3. '/' Focus Search
      if (e.key === '/') {
        if (onFocusSearch) {
          e.preventDefault();
          onFocusSearch();
        }
        return;
      }

      // 4. 'j' or 'ArrowDown' (Next item in list)
      if (e.key === 'j' || e.key === 'ArrowDown') {
        if (onNextItem) {
          e.preventDefault();
          onNextItem();
        }
        return;
      }

      // 5. 'k' or 'ArrowUp' (Previous item in list)
      if (e.key === 'k' || e.key === 'ArrowUp') {
        if (onPrevItem) {
          e.preventDefault();
          onPrevItem();
        }
        return;
      }

      // 6. '?' (Shift + '/') Help Modal
      if (e.key === '?') {
        if (onToggleHelp) {
          e.preventDefault();
          onToggleHelp();
        }
        return;
      }
    },
    [onNextItem, onPrevItem, onExecuteOrApprove, onFocusSearch, onDismiss, onToggleHelp]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

export default useKeyboardHotkeys;
