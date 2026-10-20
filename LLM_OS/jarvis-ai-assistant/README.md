<p align="center">
  <img src="assets/jarvis-logo.svg" alt="Jarvis" width="140"/>
</p>
<h1 align="center">Jarvis AI Assistant</h1>
<p align="center"><strong>Hold one key. Speak. Hear the response or watch the text appear — perfectly.</strong></p>

## How to Run (Mac Only)

Jarvis relies on native macOS C++ bindings for global audio and keyboard hooks. It must be built and run on a macOS machine.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/HARSHITJAIS14/LLM_OS.git
   cd LLM_OS/jarvis-ai-assistant
   ```

2. **Install Dependencies:**
   ```bash
   npm install
   ```
   *(This downloads all Node packages and compiles the native C++ bindings for macOS).*

3. **Run in Development Mode:**
   ```bash
   npm run dev
   ```
   *(This compiles the TypeScript and launches the Electron app).*

Once running, Jarvis will appear in your Mac's top menu bar. Hold the **Fn** key to talk to Jarvis!

---

## How It Works Under The Hood

Jarvis operates an incredibly fast, privacy-first AI pipeline that intercepts your voice and processes it seamlessly. Here is the step-by-step architecture:

### 1. Global Input Hook (C++ Native)
When you hold the **Fn** key on your Mac, a custom native C++ module (`fn_key_monitor.mm`) intercepts the keypress globally, regardless of what application you are currently focused on. This immediately triggers the audio capture module (`audio_capture.mm`) to start recording your microphone.

### 2. Speech-to-Text (STT) 
The raw audio buffer is passed to **Sherpa-ONNX**, a lightning-fast local inference engine. By default, it runs the **NVIDIA Parakeet TDT 0.6B** model (quantized in Int8) locally on your Mac's CPU or Apple Silicon Neural Engine (CoreML). It transforms your voice into raw text instantly.

### 3. Intent & LLM Processing (The Router)
The transcribed text is sent to the `AssistantProcessor`. 
Jarvis acts strictly as a conversational router for **LLM_OS**. The prompt is sent to your configured LLM (either **Ollama** locally or **Gemini** in the cloud). The LLM determines your intent:
- **General Questions:** Answered directly by the LLM using its own knowledge.
- **Computer Use Tasks:** Handed off to the underlying `LLM_OS` execution engine via a background Python script.

### 4. Output Generation (TTS)
Jarvis delivers the final response back to you via Voice:
- **Text-to-Speech (TTS):** Whether it's an answer to a question, or a status report from `LLM_OS` finishing an automation task, the text is fed into a local **Piper VITS** model via `Sherpa-ONNX` and played instantly through your speakers.
