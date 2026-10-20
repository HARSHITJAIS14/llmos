/**
 * Anthropic Provider
 * Implements LLMProvider interface for Anthropic's Claude models
 */

import { LLMProvider, LLMResponse, StreamCallbacks, ToolDefinition } from '../llm-provider';
import { Logger } from '../logger';

export class AnthropicProvider implements LLMProvider {
    readonly name = 'Anthropic';
    private modelName: string;
    private apiKey: string;
    private baseUrl = 'https://api.anthropic.com/v1/messages';

    constructor(apiKey: string, modelName: string = 'claude-haiku-4-5-20251001') {
        this.apiKey = apiKey;
        this.modelName = modelName;
        Logger.info(`🧠 [AnthropicProvider] Initialized with model: ${modelName}`);
    }

    supportsToolCalling(): boolean {
        return true;
    }

    private getHeaders() {
        return {
            'x-api-key': this.apiKey,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
            'anthropic-dangerous-direct-browser-access': 'true' // Required for web apps/Electron
        };
    }

    async generateText(
        prompt: string,
        systemPrompt?: string,
        callbacks?: StreamCallbacks
    ): Promise<string> {
        try {
            const body: any = {
                model: this.modelName,
                max_tokens: 1024,
                temperature: 0.2,
                messages: [{ role: 'user', content: prompt }]
            };

            if (systemPrompt) {
                body.system = systemPrompt;
            }

            if (callbacks) {
                body.stream = true;
            }

            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Anthropic API error: ${response.status} - ${errText}`);
            }

            if (callbacks && response.body) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullText = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n').filter(line => line.trim());

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') continue;

                            try {
                                const parsed = JSON.parse(data);
                                if (parsed.type === 'content_block_delta' && parsed.delta?.text) {
                                    const token = parsed.delta.text;
                                    fullText += token;
                                    callbacks.onToken?.(token);
                                }
                            } catch (e) {
                                // Skip malformed JSON
                            }
                        }
                    }
                }

                callbacks.onComplete?.(fullText);
                return fullText;
            } else {
                const data = await response.json();
                return data.content?.[0]?.text || '';
            }
        } catch (error) {
            Logger.error('❌ [AnthropicProvider] generateText failed:', error);
            callbacks?.onError?.(error as Error);
            throw error;
        }
    }

    async callWithTools(
        prompt: string,
        tools: ToolDefinition[],
        systemPrompt?: string
    ): Promise<LLMResponse> {
        // Map tools to Anthropic format
        const anthropicTools = tools.map(t => ({
            name: t.name,
            description: t.description,
            input_schema: {
                type: 'object',
                properties: t.parameters.properties,
                required: t.parameters.required || []
            }
        }));

        const body: any = {
            model: this.modelName,
            max_tokens: 2048,
            temperature: 0.1, // Lower temperature for reliable tool calling
            messages: [{ role: 'user', content: prompt }],
            tools: anthropicTools
        };

        if (systemPrompt) {
            body.system = systemPrompt;
        }

        try {
            Logger.debug(`🧠 [AnthropicProvider] Calling with ${tools.length} tools`);

            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Anthropic API error: ${response.status} - ${errText}`);
            }

            const data = await response.json();
            
            // Check if Claude decided to use a tool
            const toolUseBlock = data.content?.find((block: any) => block.type === 'tool_use');
            
            if (toolUseBlock) {
                Logger.info(`🔧 [AnthropicProvider] Tool call: ${toolUseBlock.name}`);
                return {
                    type: 'tool_call',
                    toolCall: {
                        name: toolUseBlock.name,
                        arguments: toolUseBlock.input
                    }
                };
            }

            // Otherwise return text
            const textBlock = data.content?.find((block: any) => block.type === 'text');
            return {
                type: 'text',
                text: textBlock?.text || ''
            };
        } catch (error) {
            Logger.error('❌ [AnthropicProvider] callWithTools failed:', error);
            throw error;
        }
    }
}
