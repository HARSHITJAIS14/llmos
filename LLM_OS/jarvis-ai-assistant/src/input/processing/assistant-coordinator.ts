import { AssistantProcessor } from '../assistant-processor';
import { ContextDetector } from '../../context/context-detector';
import { Logger } from '../../core/logger';
import { AppContext } from '../../interfaces/transcription';
import { SherpaTtsEngine } from '../../audio/sherpa-tts-engine';

export interface AssistantResult {
  text: string;
  isAssistant: boolean;
  processedText?: string;
  context?: AppContext;
  suggestions?: string[];
}

/**
 * Coordinates purely conversational assistant processing
 */
export class AssistantCoordinator {
  private assistantProcessor: AssistantProcessor;
  private contextDetector: ContextDetector;

  constructor() {
    this.assistantProcessor = new AssistantProcessor();
    this.contextDetector = new ContextDetector();
  }

  /**
   * Process transcription through conversational agent
   */
  async processTranscription(transcriptionText: string, sessionId: string): Promise<AssistantResult> {
    try {
      Logger.info(`🤖 [Assistant] Processing transcription: "${transcriptionText}"`);

      // Detect current application context (useful for the LLM to know what you are looking at)
      const context = await this.contextDetector.detectContext();
      Logger.debug(`📱 [Context] Detected context: ${context.activeApp || 'unknown'}`);

      // Process strictly through conversational assistant
      const assistantResult = await this.assistantProcessor.processWithAssistantDetection(
        transcriptionText,
        context
      );

      // Instantly speak the assistant's response aloud
      SherpaTtsEngine.getInstance().speak(assistantResult.text);

      const result: AssistantResult = {
        text: assistantResult.text,
        isAssistant: true,
        processedText: assistantResult.text,
        context,
        suggestions: [] 
      };

      Logger.success(`✅ [Assistant] Processing complete - Replied: "${result.text}"`);

      return result;
    } catch (error) {
      Logger.error('❌ [Assistant] Processing failed:', error);
      return {
        text: transcriptionText,
        isAssistant: true,
        processedText: transcriptionText,
        context: { activeApp: 'unknown', windowTitle: '', type: 'default' },
        suggestions: []
      };
    }
  }

  async getCurrentContext(): Promise<AppContext> {
    return await this.contextDetector.detectContext();
  }

  getContextKeywords(): string[] {
    return [];
  }

  async clearMemory(): Promise<void> {
    Logger.info('🧹 [Assistant] Memory clear requested');
  }
}
