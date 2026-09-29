/**
 * Pattern Scanner Module
 * Exports all pattern detection and UI components
 */

export * from './candlestickPatterns';
export { PatternSelector } from './PatternSelector';

// Re-export commonly used types
export type { PatternMatch, CandlestickPattern } from './candlestickPatterns';
