'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

export interface UseVirtualWindowOptions {
  itemCount: number;
  itemHeight: number;
  overscan?: number;
  enabled?: boolean;
}

export interface VirtualItem {
  index: number;
  offsetTop: number;
  height: number;
}

export interface VirtualWindowResult<T extends HTMLElement = HTMLDivElement> {
  containerRef: React.RefObject<T | null>;
  virtualItems: VirtualItem[];
  totalHeight: number;
  paddingTop: number;
  paddingBottom: number;
  startIndex: number;
  endIndex: number;
  isVirtualized: boolean;
  scrollToIndex: (index: number) => void;
}

/**
 * High-performance virtual windowing hook for React 19 / Next.js 15.
 * Guarantees constant O(1) DOM nodes regardless of whether total items
 * are 50, 500, or 10,000+, keeping 60 FPS smooth scrolling.
 */
export function useVirtualWindow<T extends HTMLElement = HTMLDivElement>({
  itemCount,
  itemHeight,
  overscan = 5,
  enabled = true,
}: UseVirtualWindowOptions): VirtualWindowResult<T> {
  const containerRef = useRef<T | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(600);
  const rafIdRef = useRef<number | null>(null);

  // Measure container height on mount and resize
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const measure = () => {
      if (el) {
        setViewportHeight(el.clientHeight || 600);
      }
    };

    measure();

    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => measure());
      ro.observe(el);
      return () => ro.disconnect();
    } else {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }
  }, []);

  // Passive scroll listener with requestAnimationFrame throttling
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !enabled) return;

    const onScroll = () => {
      if (rafIdRef.current !== null) return;
      rafIdRef.current = requestAnimationFrame(() => {
        if (el) {
          setScrollTop(el.scrollTop);
        }
        rafIdRef.current = null;
      });
    };

    el.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      el.removeEventListener('scroll', onScroll);
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [enabled]);

  const totalHeight = itemCount * itemHeight;

  const { startIndex, endIndex, virtualItems, paddingTop, paddingBottom } = useMemo(() => {
    if (!enabled || itemCount === 0) {
      const items: VirtualItem[] = Array.from({ length: itemCount }, (_, i) => ({
        index: i,
        offsetTop: i * itemHeight,
        height: itemHeight,
      }));
      return {
        startIndex: 0,
        endIndex: itemCount - 1,
        virtualItems: items,
        paddingTop: 0,
        paddingBottom: 0,
      };
    }

    const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const visibleCount = Math.ceil(viewportHeight / itemHeight);
    const end = Math.min(itemCount - 1, Math.floor(scrollTop / itemHeight) + visibleCount + overscan);

    const items: VirtualItem[] = [];
    for (let i = start; i <= end; i++) {
      items.push({
        index: i,
        offsetTop: i * itemHeight,
        height: itemHeight,
      });
    }

    const topPad = start * itemHeight;
    const bottomPad = Math.max(0, (itemCount - 1 - end) * itemHeight);

    return {
      startIndex: start,
      endIndex: end,
      virtualItems: items,
      paddingTop: topPad,
      paddingBottom: bottomPad,
    };
  }, [itemCount, itemHeight, overscan, enabled, scrollTop, viewportHeight]);

  const scrollToIndex = useCallback((index: number) => {
    const el = containerRef.current;
    if (!el) return;
    const targetTop = Math.max(0, Math.min(index * itemHeight, totalHeight - viewportHeight));
    el.scrollTo({ top: targetTop, behavior: 'smooth' });
  }, [itemHeight, totalHeight, viewportHeight]);

  return {
    containerRef,
    virtualItems,
    totalHeight,
    paddingTop,
    paddingBottom,
    startIndex,
    endIndex,
    isVirtualized: enabled && itemCount > 15,
    scrollToIndex,
  };
}
