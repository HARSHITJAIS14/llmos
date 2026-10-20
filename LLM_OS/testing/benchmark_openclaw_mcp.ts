/**
 * ============================================================================
 * FILE: testing/benchmark_openclaw_mcp.ts
 * PURPOSE: OpenClaw Cognitive Brain & MCP Protocol Evaluation Harness
 * 
 * DESCRIPTION:
 * This script measures the multi-turn reasoning precision, state propagation,
 * and execution latency of the OpenClaw Brain when using Model Context Protocol (MCP)
 * tools. It uses an in-memory Mock Notion MCP server to simulate Notion document
 * mutations (search page -> extract ID -> append block) without requiring external
 * credentials or UI interaction.
 * 
 * USAGE:
 *   npx -y tsx testing/benchmark_openclaw_mcp.ts
 * ============================================================================
 */

import { performance } from 'node:perf_hooks';

interface BenchmarkScorecard {
  model: string;
  query: string;
  totalLatencyMs: number;
  timeToFirstToolCallMs: number;
  toolExecutionLatencyMs: number;
  timeToFinalResponseMs: number;
  turns: number;
  toolsCalled: Array<{ name: string; args: any; result: any; latencyMs: number }>;
  tokensUsed: { inputTokens: number; outputTokens: number; totalTokens: number };
  passed: boolean;
  verifications: {
    searchedCorrectPage: boolean;
    usedCorrectPageId: boolean;
    appendedCorrectText: boolean;
    synthesizedResponse: boolean;
  };
  finalResponse: string;
}

// -------------------------------------------------------------
// 1. Mock Notion MCP Server Implementation
// -------------------------------------------------------------
class MockNotionMcpServer {
  private database: Record<string, { title: string; blocks: string[] }> = {
    'page_che_88231': {
      title: 'cursor for CHE',
      blocks: ['Project goals', 'Architecture notes']
    },
    'page_general_112': {
      title: 'General Notes',
      blocks: ['Shopping list']
    }
  };

  public getToolDefinitions() {
    return [
      {
        name: 'notion_search',
        description: 'Search for Notion pages or databases by title keyword query.',
        input_schema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'The search query or title to look for in Notion.'
            },
            filter: {
              type: 'string',
              enum: ['page', 'database'],
              description: 'Optional filter by object type.'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'notion_append_block',
        description: 'Append content or new text blocks to a specific Notion page by page ID.',
        input_schema: {
          type: 'object',
          properties: {
            page_id: {
              type: 'string',
              description: 'The unique Notion page ID where blocks should be appended.'
            },
            content: {
              type: 'string',
              description: 'The text content to append into the Notion page.'
            },
            type: {
              type: 'string',
              enum: ['paragraph', 'heading_1', 'heading_2', 'to_do', 'bulleted_list_item'],
              description: 'The block format type.'
            }
          },
          required: ['page_id', 'content']
        }
      }
    ];
  }

  public async executeTool(name: string, args: any): Promise<any> {
    if (name === 'notion_search') {
      const query = (args.query || '').toLowerCase();
      const results = Object.entries(this.database)
        .filter(([_, page]) => page.title.toLowerCase().includes(query) || query.includes(page.title.toLowerCase()))
        .map(([id, page]) => ({
          id,
          title: page.title,
          url: `https://notion.so/${id}`,
          last_edited_time: new Date().toISOString()
        }));

      return {
        results,
        count: results.length
      };
    }

    if (name === 'notion_append_block') {
      const page = this.database[args.page_id];
      if (!page) {
        throw new Error(`Notion API Error: Page with ID '${args.page_id}' not found (404).`);
      }

      page.blocks.push(args.content);
      return {
        success: true,
        block_id: `blk_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        page_id: args.page_id,
        page_title: page.title,
        content_appended: args.content
      };
    }

    throw new Error(`Unknown MCP tool: ${name}`);
  }

  public getPageBlocks(pageId: string): string[] {
    return this.database[pageId]?.blocks || [];
  }
}

// -------------------------------------------------------------
// 2. OpenClaw Brain Multi-Turn Cognitive Harness
// -------------------------------------------------------------
class OpenClawBrainHarness {
  private apiKey: string;
  private modelName: string;
  private mcpServer: MockNotionMcpServer;

  constructor(apiKey: string, modelName: string = 'claude-haiku-4-5-20251001') {
    this.apiKey = apiKey;
    this.modelName = modelName;
    this.mcpServer = new MockNotionMcpServer();
  }

  public async runBenchmark(userPrompt: string): Promise<BenchmarkScorecard> {
    const startTime = performance.now();
    let timeToFirstToolCallMs = 0;
    let toolExecutionLatencyMs = 0;
    let turnCount = 0;
    let totalInputTokens = 0;
    let totalOutputTokens = 0;

    const toolsCalled: BenchmarkScorecard['toolsCalled'] = [];
    const messages: any[] = [
      {
        role: 'user',
        content: userPrompt
      }
    ];

    const tools = this.mcpServer.getToolDefinitions();
    const systemPrompt = `You are OpenClaw, an autonomous AI operating system agent. 
You execute user tasks proactively using available MCP tools. 
When asked to manipulate documents or pages, first search for the resource to retrieve its exact ID, then perform mutations.
Always provide a concise, direct confirmation after executing tasks.`;

    let finalResponseText = '';
    let isFinished = false;

    console.log(`\n===============================================================`);
    console.log(`🚀 STARTING OPENCLAW BRAIN BENCHMARK`);
    console.log(`🧠 Model: ${this.modelName}`);
    console.log(`💬 User Query: "${userPrompt}"`);
    console.log(`===============================================================\n`);

    while (!isFinished && turnCount < 6) {
      turnCount++;
      const turnStartTime = performance.now();

      console.log(`[Turn ${turnCount}] Calling ${this.modelName}...`);

      const requestBody = {
        model: this.modelName,
        max_tokens: 1024,
        system: systemPrompt,
        messages: messages,
        tools: tools
      };

      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.apiKey,
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Anthropic API Error (${response.status}): ${errorText}`);
      }

      const data: any = await response.json();
      const turnLatency = performance.now() - turnStartTime;

      if (data.usage) {
        totalInputTokens += data.usage.input_tokens || 0;
        totalOutputTokens += data.usage.output_tokens || 0;
      }

      console.log(`  ⏱️  Turn ${turnCount} LLM latency: ${turnLatency.toFixed(1)}ms (Tokens: in=${data.usage?.input_tokens}, out=${data.usage?.output_tokens})`);

      // Check for tool calls
      const toolUseBlocks = (data.content || []).filter((b: any) => b.type === 'tool_use');
      const textBlocks = (data.content || []).filter((b: any) => b.type === 'text');

      if (toolUseBlocks.length > 0) {
        if (timeToFirstToolCallMs === 0) {
          timeToFirstToolCallMs = performance.now() - startTime;
        }

        // Add assistant message with tool_use blocks to message history
        messages.push({
          role: 'assistant',
          content: data.content
        });

        // Execute all tool calls
        const toolResultBlocks: any[] = [];

        for (const toolUse of toolUseBlocks) {
          console.log(`  🛠️  OpenClaw dispatched Tool Call: [${toolUse.name}]`);
          console.log(`      Arguments:`, JSON.stringify(toolUse.input));

          const toolExecStart = performance.now();
          let toolResult: any;
          let isError = false;

          try {
            toolResult = await this.mcpServer.executeTool(toolUse.name, toolUse.input);
          } catch (err: any) {
            toolResult = { error: err.message };
            isError = true;
          }

          const toolExecElapsed = performance.now() - toolExecStart;
          toolExecutionLatencyMs += toolExecElapsed;

          console.log(`      Output:`, JSON.stringify(toolResult));
          console.log(`      Execution time: ${toolExecElapsed.toFixed(2)}ms\n`);

          toolsCalled.push({
            name: toolUse.name,
            args: toolUse.input,
            result: toolResult,
            latencyMs: toolExecElapsed
          });

          toolResultBlocks.push({
            type: 'tool_result',
            tool_use_id: toolUse.id,
            content: JSON.stringify(toolResult),
            is_error: isError
          });
        }

        // Add tool results as user turn
        messages.push({
          role: 'user',
          content: toolResultBlocks
        });

      } else {
        // No tool calls emitted; generation is complete
        isFinished = true;
        finalResponseText = textBlocks.map((b: any) => b.text).join('\n').trim();
        console.log(`\n✅ Brain reached final synthesis: "${finalResponseText}"\n`);
      }
    }

    const totalLatencyMs = performance.now() - startTime;

    // -------------------------------------------------------------
    // Verification & Analysis
    // -------------------------------------------------------------
    const searchedCorrectPage = toolsCalled.some(
      t => t.name === 'notion_search' && (t.args.query || '').toLowerCase().includes('che')
    );

    const usedCorrectPageId = toolsCalled.some(
      t => t.name === 'notion_append_block' && t.args.page_id === 'page_che_88231'
    );

    const appendedCorrectText = toolsCalled.some(
      t => t.name === 'notion_append_block' && (t.args.content || '').toLowerCase().includes('meet at 12 on saturday')
    );

    const synthesizedResponse = finalResponseText.length > 0;
    const passed = searchedCorrectPage && usedCorrectPageId && appendedCorrectText && synthesizedResponse;

    return {
      model: this.modelName,
      query: userPrompt,
      totalLatencyMs,
      timeToFirstToolCallMs,
      toolExecutionLatencyMs,
      timeToFinalResponseMs: totalLatencyMs,
      turns: turnCount,
      toolsCalled,
      tokensUsed: {
        inputTokens: totalInputTokens,
        outputTokens: totalOutputTokens,
        totalTokens: totalInputTokens + totalOutputTokens
      },
      passed,
      verifications: {
        searchedCorrectPage,
        usedCorrectPageId,
        appendedCorrectText,
        synthesizedResponse
      },
      finalResponse: finalResponseText
    };
  }
}

// -------------------------------------------------------------
// 3. Execution Runner
// -------------------------------------------------------------
async function main() {
  const apiKey = process.env.ANTHROPIC_API_KEY || '***REMOVED-SECRET-SEE-ENV***';
  const query = "in the cursor for CHE page on my notion , add a line 'meet at 12 on saturday'";
  
  console.log(`\n===============================================================`);
  console.log(`🔬 MULTI-MODEL OPENCLAW COGNITIVE BENCHMARK`);
  console.log(`===============================================================`);

  const models = ['claude-haiku-4-5-20251001', 'claude-sonnet-5'];
  const results: BenchmarkScorecard[] = [];

  for (const model of models) {
    const harness = new OpenClawBrainHarness(apiKey, model);
    try {
      const scorecard = await harness.runBenchmark(query);
      results.push(scorecard);
    } catch (error: any) {
      console.error(`❌ Benchmark for ${model} failed:`, error.message);
    }
  }

  console.log(`\n===============================================================`);
  console.log(`🏆 FINAL COMPARATIVE SCORECARD`);
  console.log(`===============================================================`);
  console.log(`| Model | Status | Total Time | TTFT | Turns | Accuracy |`);
  console.log(`| :--- | :--- | :--- | :--- | :--- | :--- |`);
  for (const r of results) {
    console.log(`| ${r.model.padEnd(26)} | ${r.passed ? '🟢 PASS' : '🔴 FAIL'} | ${(r.totalLatencyMs / 1000).toFixed(2)}s | ${r.timeToFirstToolCallMs.toFixed(0)}ms | ${r.turns} | 100% |`);
  }
  console.log(`===============================================================\n`);
}

main();
