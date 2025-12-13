import { useEffect, useRef, useState } from 'react';

/**
 * Auto-save hook with debounce and state tracking
 *
 * @param {Function} saveFn - Async function to call when saving
 * @param {any} value - Current value to save
 * @param {number} delay - Debounce delay in milliseconds (default 1500)
 * @returns {Object} - { saveState, error }
 *   saveState: 'idle' | 'saving' | 'saved' | 'error'
 *   error: Error message if save failed
 */
export function useAutoSave(saveFn, value, delay = 1500) {
  const [saveState, setSaveState] = useState('idle');
  const [error, setError] = useState(null);
  const timeoutRef = useRef(null);
  const resetTimeoutRef = useRef(null);
  const previousValueRef = useRef(value);
  const unmountSaveRef = useRef(false);
  const currentValueRef = useRef(value);
  const currentSaveFnRef = useRef(saveFn);

  // Keep refs up to date
  useEffect(() => {
    currentValueRef.current = value;
    currentSaveFnRef.current = saveFn;
  }, [value, saveFn]);

  useEffect(() => {
    // Skip if value hasn't changed
    if (value === previousValueRef.current) {
      return;
    }

    previousValueRef.current = value;

    // Clear existing timeouts
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    if (resetTimeoutRef.current) {
      clearTimeout(resetTimeoutRef.current);
    }

    // Set new timeout
    timeoutRef.current = setTimeout(async () => {
      setSaveState('saving');
      setError(null);

      try {
        await saveFn(value);
        setSaveState('saved');

        // Reset to idle after 2 seconds
        resetTimeoutRef.current = setTimeout(() => {
          setSaveState('idle');
        }, 2000);
      } catch (err) {
        setSaveState('error');
        setError(err.message || 'Save failed');
      }
    }, delay);

    // Cleanup
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      if (resetTimeoutRef.current) {
        clearTimeout(resetTimeoutRef.current);
      }
    };
  }, [value, saveFn, delay]);

  // Save on unmount if dirty - FIX: Use refs to avoid stale closure
  useEffect(() => {
    return () => {
      if (currentValueRef.current !== previousValueRef.current && !unmountSaveRef.current) {
        unmountSaveRef.current = true;
        // Fire-and-forget save using latest values from refs
        currentSaveFnRef.current(currentValueRef.current).catch(err => {
          console.error('Unmount save failed:', err);
        });
      }
    };
  }, []); // Empty deps - only runs on unmount

  return { saveState, error };
}
