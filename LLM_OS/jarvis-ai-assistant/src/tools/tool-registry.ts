/**
 * Tool Registry
 * Manages tool definitions and execution for the unified agent
 */

import { ToolDefinition } from '../core/llm-provider';
import { Logger } from '../core/logger';
import { LlmOsTool } from './llm-os-tool';

export type ToolExecutor = (args: Record<string, any>) => Promise<string>;

interface RegisteredTool {
    definition: ToolDefinition;
    executor: ToolExecutor;
}

export class ToolRegistry {
    private tools: Map<string, RegisteredTool> = new Map();

    register(
        name: string,
        description: string,
        parameters: ToolDefinition['parameters'],
        executor: ToolExecutor
    ): void {
        this.tools.set(name, {
            definition: { name, description, parameters },
            executor
        });
        Logger.debug(`📦 [ToolRegistry] Registered tool: ${name}`);
    }

    getToolDefinitions(): ToolDefinition[] {
        return Array.from(this.tools.values()).map(t => t.definition);
    }

    async execute(name: string, args: Record<string, any>): Promise<string> {
        const tool = this.tools.get(name);
        if (!tool) {
            Logger.error(`❌ [ToolRegistry] Unknown tool: ${name}`);
            return `Error: Unknown tool "${name}"`;
        }

        try {
            Logger.info(`🔧 [ToolRegistry] Executing tool: ${name}`, args);
            const result = await tool.executor(args);
            Logger.info(`✅ [ToolRegistry] Tool ${name} completed`);
            return result;
        } catch (error) {
            Logger.error(`❌ [ToolRegistry] Tool ${name} failed:`, error);
            return `Error executing ${name}: ${error}`;
        }
    }

    has(name: string): boolean {
        return this.tools.has(name);
    }

    get size(): number {
        return this.tools.size;
    }
}

export function createDefaultToolRegistry(): ToolRegistry {
    const registry = new ToolRegistry();

    // Register ONLY the LLMOS routing tool
    registry.register(
        'llm_os',
        'Execute OS-level automation tasks (opening apps, sending messages, navigating GUI). Use this whenever the user asks for a computer task.',
        {
            type: 'object',
            properties: {
                task: {
                    type: 'string',
                    description: 'The clear, actionable task instruction to execute (e.g. "Open WhatsApp and send message to John")'
                }
            },
            required: ['task']
        },
        async (args) => {
            return await LlmOsTool.execute(args.task);
        }
    );

    Logger.info(`📦 [ToolRegistry] Initialized with ${registry.size} tools (LLMOS Router Mode)`);
    return registry;
}
