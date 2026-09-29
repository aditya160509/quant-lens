/**
 * Indicator Confluence Engine
 * 
 * Multi-condition signal detection system per tradefeature.md §12:
 * - AND/OR/NOT logical operators
 * - Cross events detection
 * - Visual signal markers
 * - Template save/load
 */

import type { OHLCVBar, IndicatorOutput } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export type OperandType = 
    | 'price' 
    | 'indicator' 
    | 'constant';

export type Operator = 
    | 'greater_than'
    | 'less_than'
    | 'crosses_above'
    | 'crosses_below'
    | 'equals'
    | 'between';

export type LogicalOperator = 'AND' | 'OR' | 'NOT';

export interface ConditionOperand {
    type: OperandType;
    priceField?: 'open' | 'high' | 'low' | 'close';
    indicatorId?: string;
    indicatorLine?: string; // For multi-line indicators like MACD
    constant?: number;
}

export interface ConfluenceCondition {
    id: string;
    leftOperand: ConditionOperand;
    operator: Operator;
    rightOperand: ConditionOperand;
    lowerBound?: number; // For 'between' operator
    upperBound?: number;
}

export interface ConfluenceRule {
    id: string;
    name: string;
    description?: string;
    conditions: ConfluenceCondition[];
    logicalOperators: LogicalOperator[]; // Between conditions
    signalType: 'bullish' | 'bearish' | 'neutral';
    enabled: boolean;
    createdAt: number;
}

export interface ConfluenceSignal {
    ruleId: string;
    ruleName: string;
    timestamp: number;
    barIndex: number;
    signalType: 'bullish' | 'bearish' | 'neutral';
    triggeredConditions: string[];
    price: number;
}

export interface ConfluenceTemplate {
    id: string;
    name: string;
    description: string;
    rule: Omit<ConfluenceRule, 'id' | 'createdAt'>;
    isBuiltIn: boolean;
}

// =============================================================================
// BUILT-IN TEMPLATES
// =============================================================================

export const CONFLUENCE_TEMPLATES: ConfluenceTemplate[] = [
    {
        id: 'oversold_bounce',
        name: 'Oversold Bounce',
        description: 'RSI crosses above 30 with price above 20 EMA',
        isBuiltIn: true,
        rule: {
            name: 'Oversold Bounce',
            conditions: [
                {
                    id: 'c1',
                    leftOperand: { type: 'indicator', indicatorId: 'rsi' },
                    operator: 'crosses_above',
                    rightOperand: { type: 'constant', constant: 30 },
                },
                {
                    id: 'c2',
                    leftOperand: { type: 'price', priceField: 'close' },
                    operator: 'greater_than',
                    rightOperand: { type: 'indicator', indicatorId: 'ema_20' },
                },
            ],
            logicalOperators: ['AND'],
            signalType: 'bullish',
            enabled: true,
        },
    },
    {
        id: 'breakout_confirmation',
        name: 'Breakout Confirmation',
        description: 'Price breaks above 50 SMA with volume > 1.5x average',
        isBuiltIn: true,
        rule: {
            name: 'Breakout Confirmation',
            conditions: [
                {
                    id: 'c1',
                    leftOperand: { type: 'price', priceField: 'close' },
                    operator: 'crosses_above',
                    rightOperand: { type: 'indicator', indicatorId: 'sma_50' },
                },
                {
                    id: 'c2',
                    leftOperand: { type: 'indicator', indicatorId: 'volumeRatio' },
                    operator: 'greater_than',
                    rightOperand: { type: 'constant', constant: 1.5 },
                },
            ],
            logicalOperators: ['AND'],
            signalType: 'bullish',
            enabled: true,
        },
    },
    {
        id: 'macd_momentum',
        name: 'MACD Momentum',
        description: 'MACD crosses above signal line with positive histogram',
        isBuiltIn: true,
        rule: {
            name: 'MACD Momentum',
            conditions: [
                {
                    id: 'c1',
                    leftOperand: { type: 'indicator', indicatorId: 'macd', indicatorLine: 'macd' },
                    operator: 'crosses_above',
                    rightOperand: { type: 'indicator', indicatorId: 'macd', indicatorLine: 'signal' },
                },
                {
                    id: 'c2',
                    leftOperand: { type: 'indicator', indicatorId: 'macd', indicatorLine: 'histogram' },
                    operator: 'greater_than',
                    rightOperand: { type: 'constant', constant: 0 },
                },
            ],
            logicalOperators: ['AND'],
            signalType: 'bullish',
            enabled: true,
        },
    },
    {
        id: 'overbought_reversal',
        name: 'Overbought Reversal',
        description: 'RSI crosses below 70 with bearish engulfing pattern',
        isBuiltIn: true,
        rule: {
            name: 'Overbought Reversal',
            conditions: [
                {
                    id: 'c1',
                    leftOperand: { type: 'indicator', indicatorId: 'rsi' },
                    operator: 'crosses_below',
                    rightOperand: { type: 'constant', constant: 70 },
                },
            ],
            logicalOperators: [],
            signalType: 'bearish',
            enabled: true,
        },
    },
];

// =============================================================================
// EVALUATOR
// =============================================================================

export class ConfluenceEvaluator {
    private rules: ConfluenceRule[] = [];
    private signals: ConfluenceSignal[] = [];

    constructor(rules?: ConfluenceRule[]) {
        if (rules) this.rules = rules;
    }

    setRules(rules: ConfluenceRule[]): void {
        this.rules = rules;
    }

    addRule(rule: ConfluenceRule): void {
        this.rules.push(rule);
    }

    removeRule(ruleId: string): void {
        this.rules = this.rules.filter(r => r.id !== ruleId);
    }

    /**
     * Evaluate all rules against current bar data
     */
    evaluate(
        bars: OHLCVBar[],
        indicatorOutputs: Map<string, IndicatorOutput>,
        barIndex?: number
    ): ConfluenceSignal[] {
        const idx = barIndex ?? bars.length - 1;
        if (idx < 1 || idx >= bars.length) return [];

        const currentBar = bars[idx];
        const previousBar = bars[idx - 1];
        const newSignals: ConfluenceSignal[] = [];

        for (const rule of this.rules) {
            if (!rule.enabled) continue;

            const result = this.evaluateRule(
                rule,
                currentBar,
                previousBar,
                indicatorOutputs,
                idx
            );

            if (result.triggered) {
                const signal: ConfluenceSignal = {
                    ruleId: rule.id,
                    ruleName: rule.name,
                    timestamp: currentBar.timestamp,
                    barIndex: idx,
                    signalType: rule.signalType,
                    triggeredConditions: result.conditions,
                    price: currentBar.close,
                };
                newSignals.push(signal);
                this.signals.push(signal);
            }
        }

        return newSignals;
    }

    /**
     * Evaluate a single rule
     */
    private evaluateRule(
        rule: ConfluenceRule,
        currentBar: OHLCVBar,
        previousBar: OHLCVBar,
        indicatorOutputs: Map<string, IndicatorOutput>,
        barIndex: number
    ): { triggered: boolean; conditions: string[] } {
        const conditionResults: boolean[] = [];
        const triggeredConditions: string[] = [];

        for (const condition of rule.conditions) {
            const result = this.evaluateCondition(
                condition,
                currentBar,
                previousBar,
                indicatorOutputs,
                barIndex
            );
            conditionResults.push(result);
            if (result) triggeredConditions.push(condition.id);
        }

        // Apply logical operators
        let finalResult = conditionResults[0] ?? false;

        for (let i = 0; i < rule.logicalOperators.length; i++) {
            const op = rule.logicalOperators[i];
            const nextResult = conditionResults[i + 1] ?? false;

            switch (op) {
                case 'AND':
                    finalResult = finalResult && nextResult;
                    break;
                case 'OR':
                    finalResult = finalResult || nextResult;
                    break;
                case 'NOT':
                    finalResult = finalResult && !nextResult;
                    break;
            }
        }

        return { triggered: finalResult, conditions: triggeredConditions };
    }

    /**
     * Evaluate a single condition
     */
    private evaluateCondition(
        condition: ConfluenceCondition,
        currentBar: OHLCVBar,
        previousBar: OHLCVBar,
        indicatorOutputs: Map<string, IndicatorOutput>,
        barIndex: number
    ): boolean {
        const leftCurrent = this.getOperandValue(condition.leftOperand, currentBar, indicatorOutputs, barIndex);
        const leftPrev = this.getOperandValue(condition.leftOperand, previousBar, indicatorOutputs, barIndex - 1);
        const rightCurrent = this.getOperandValue(condition.rightOperand, currentBar, indicatorOutputs, barIndex);
        const rightPrev = this.getOperandValue(condition.rightOperand, previousBar, indicatorOutputs, barIndex - 1);

        if (leftCurrent === null || rightCurrent === null) return false;

        switch (condition.operator) {
            case 'greater_than':
                return leftCurrent > rightCurrent;
            
            case 'less_than':
                return leftCurrent < rightCurrent;
            
            case 'equals':
                return Math.abs(leftCurrent - rightCurrent) < 0.0001;
            
            case 'crosses_above':
                if (leftPrev === null || rightPrev === null) return false;
                return leftPrev <= rightPrev && leftCurrent > rightCurrent;
            
            case 'crosses_below':
                if (leftPrev === null || rightPrev === null) return false;
                return leftPrev >= rightPrev && leftCurrent < rightCurrent;
            
            case 'between':
                const lower = condition.lowerBound ?? 0;
                const upper = condition.upperBound ?? 100;
                return leftCurrent >= lower && leftCurrent <= upper;
            
            default:
                return false;
        }
    }

    /**
     * Get the numeric value of an operand
     */
    private getOperandValue(
        operand: ConditionOperand,
        bar: OHLCVBar,
        indicatorOutputs: Map<string, IndicatorOutput>,
        barIndex: number
    ): number | null {
        switch (operand.type) {
            case 'price':
                switch (operand.priceField) {
                    case 'open': return bar.open;
                    case 'high': return bar.high;
                    case 'low': return bar.low;
                    case 'close': return bar.close;
                    default: return bar.close;
                }
            
            case 'constant':
                return operand.constant ?? 0;
            
            case 'indicator':
                const output = indicatorOutputs.get(operand.indicatorId ?? '');
                if (!output || !output.series || barIndex < 0 || barIndex >= output.series.length) {
                    return null;
                }
                return output.series[barIndex]?.value ?? null;
            
            default:
                return null;
        }
    }

    /**
     * Get all signals
     */
    getSignals(): ConfluenceSignal[] {
        return [...this.signals];
    }

    /**
     * Clear all signals
     */
    clearSignals(): void {
        this.signals = [];
    }

    /**
     * Export signals to CSV
     */
    exportSignalsCSV(): string {
        const headers = ['Timestamp', 'Rule', 'Signal Type', 'Price', 'Conditions'];
        const rows = this.signals.map(s => [
            new Date(s.timestamp).toISOString(),
            s.ruleName,
            s.signalType,
            s.price.toFixed(2),
            s.triggeredConditions.join('; '),
        ]);
        return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    }
}

// =============================================================================
// RULE FACTORY
// =============================================================================

export function createRule(
    name: string,
    conditions: ConfluenceCondition[],
    logicalOperators: LogicalOperator[],
    signalType: 'bullish' | 'bearish' | 'neutral'
): ConfluenceRule {
    return {
        id: `rule_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        name,
        conditions,
        logicalOperators,
        signalType,
        enabled: true,
        createdAt: Date.now(),
    };
}

export function createCondition(
    leftOperand: ConditionOperand,
    operator: Operator,
    rightOperand: ConditionOperand
): ConfluenceCondition {
    return {
        id: `cond_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        leftOperand,
        operator,
        rightOperand,
    };
}

// =============================================================================
// SINGLETON INSTANCE
// =============================================================================

let confluenceInstance: ConfluenceEvaluator | null = null;

export function getConfluenceEngine(): ConfluenceEvaluator {
    if (!confluenceInstance) {
        confluenceInstance = new ConfluenceEvaluator();
    }
    return confluenceInstance;
}
