import { exec } from 'child_process';
import * as path from 'path';
import { Logger } from '../core/logger';
import { app } from 'electron';

export class LlmOsTool {
    /**
     * Executes the python LLM_OS engine in the parent directory
     */
    static async execute(task: string): Promise<string> {
        return new Promise((resolve) => {
            Logger.info(`🤖 [LlmOsTool] Executing LLMOS task: "${task}"`);
            
            // Resolve the path to the LLM_OS python project (parent directory of jarvis-ai-assistant)
            const isPackaged = app.isPackaged;
            let llmOsDir = process.cwd();
            
            // In dev mode (not packaged), process.cwd() is likely the jarvis-ai-assistant folder
            // So the llm_os python module is one level up
            if (!isPackaged) {
                if (path.basename(llmOsDir) === 'jarvis-ai-assistant') {
                    llmOsDir = path.dirname(llmOsDir);
                }
            } else {
                // If packaged, we assume the python project is shipped alongside the app
                llmOsDir = path.join(path.dirname(app.getPath('exe')), '..');
            }

            // Command runs the python CLI
            // We escape double quotes to prevent bash injection issues
            const safeTask = task.replace(/"/g, '\\"');
            const command = `python3 -m llm_os "${safeTask}"`;

            Logger.debug(`🤖 [LlmOsTool] Running command in ${llmOsDir}: ${command}`);

            exec(command, { cwd: llmOsDir }, (error, stdout, stderr) => {
                if (error) {
                    Logger.error(`❌ [LlmOsTool] Execution failed:`, error);
                    Logger.error(`Stderr: ${stderr}`);
                    return resolve(`LLMOS failed to complete the task. Error: ${error.message}`);
                }

                Logger.success(`✅ [LlmOsTool] Task completed successfully`);
                // LLM_OS usually prints logs to stdout/stderr.
                // For Jarvis, we just return a success message since the action was performed
                resolve(`LLMOS successfully completed the task: ${task}. It has been executed on the user's system.`);
            });
        });
    }
}
