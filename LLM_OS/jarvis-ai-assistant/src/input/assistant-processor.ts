import { AudioProcessor } from '../audio/processor';
import { Logger } from '../core/logger';
import { AppContext } from '../interfaces/transcription';
import { AgentHandler } from './agent-handler';
import { AppState } from '../services/app-state';

/**
 * Handles all incoming voice queries purely as conversational AI prompts
 */
export class AssistantProcessor {
  private agentHandler: AgentHandler;
  private appState: AppState;

  constructor() {
    this.agentHandler = AgentHandler.getInstance();
    this.appState = AppState.getInstance();
  }

  /**
   * Process transcription as a conversational assistant command
   */
  async processWithAssistantDetection(
    transcriptText: string,
    appContext: AppContext,
    forceAssistant: boolean = false
  ): Promise<{ text: string; isAssistant: boolean }> {
    
    // We are now purely conversational, so dictation mode is always off.
    this.appState.setDictationMode(false);
    Logger.info(`🤖 [ASSISTANT] Processing conversational query: "${transcriptText.substring(0, 50)}..."`);

    try {
      // Bypassed selected text checking as per user request
      const userMessage = transcriptText;

      Logger.info('📞 [Assistant] Sending query to LLM Agent...');
      
      // Send directly to the AI agent
      const responseText = await this.agentHandler.processQuery(userMessage);
      
      Logger.info(`✅ [Assistant] Received Response: "${responseText.substring(0, 50)}..."`);
      
      // Always return as an assistant response to trigger TTS output
      return { text: responseText, isAssistant: true };
    } catch (error) {
      Logger.error('❌ [Assistant] Processing failed:', error);
      // Return a graceful error message to be spoken aloud
      return { text: "I'm sorry, I encountered an error while processing your request.", isAssistant: true };
    }
  }
}
