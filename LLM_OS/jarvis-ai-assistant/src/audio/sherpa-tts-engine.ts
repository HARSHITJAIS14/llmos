import { app } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { exec } from 'child_process';
import { Logger } from '../core/logger';
import { AppSettingsService } from '../services/app-settings-service';
import { PIPER_MODELS, DEFAULT_TTS_MODEL } from './tts-models';

let sherpa: any = null;

function getSherpaOnnx(): any {
    if (sherpa) return sherpa;
    const isPackaged = app.isPackaged;
    const appPath = app.getAppPath();
    let baseNodeModules = isPackaged 
        ? path.join(appPath + '.unpacked', 'node_modules')
        : path.join(__dirname, '..', '..', 'node_modules'); // from dist/audio/ to node_modules
    
    // Check if we are running tsx in dev which changes path resolution
    if (!fs.existsSync(baseNodeModules) && !isPackaged) {
        baseNodeModules = path.join(process.cwd(), 'node_modules');
    }

    const arch = process.arch;
    const sherpaLibPath = path.join(baseNodeModules, `sherpa-onnx-darwin-${arch}`);
    
    if (fs.existsSync(sherpaLibPath)) {
        const existingPath = process.env.DYLD_LIBRARY_PATH || '';
        process.env.DYLD_LIBRARY_PATH = sherpaLibPath + (existingPath ? ':' + existingPath : '');
    }

    const Module = require('module');
    const originalPaths = Module._nodeModulePaths;
    Module._nodeModulePaths = function (from: string) {
        return [baseNodeModules].concat(originalPaths.call(this, from));
    };

    try {
        const nodeRequire = typeof __non_webpack_require__ !== 'undefined' ? __non_webpack_require__ : require;
        sherpa = nodeRequire('sherpa-onnx-node');
        Logger.info('🦜 [SherpaTTS] Loaded sherpa-onnx-node');
    } catch (e) {
        Logger.error('🦜 [SherpaTTS] Failed to load sherpa-onnx-node', e);
    } finally {
        Module._nodeModulePaths = originalPaths;
    }
    return sherpa;
}

declare const __non_webpack_require__: NodeRequire | undefined;

export class SherpaTtsEngine {
    private static instance: SherpaTtsEngine;
    private tts: any = null;
    private isDownloading = false;

    public static getInstance(): SherpaTtsEngine {
        if (!SherpaTtsEngine.instance) {
            SherpaTtsEngine.instance = new SherpaTtsEngine();
        }
        return SherpaTtsEngine.instance;
    }

    private getModelsDir(): string {
        return path.join(app.getPath('userData'), 'tts-models');
    }

    public async downloadModelIfNeeded(): Promise<boolean> {
        const modelDef = PIPER_MODELS.find(m => m.id === DEFAULT_TTS_MODEL)!;
        const modelsDir = this.getModelsDir();
        const targetDir = path.join(modelsDir, modelDef.id);
        
        if (fs.existsSync(path.join(targetDir, 'en_US-amy-low.onnx'))) {
            return true;
        }

        if (this.isDownloading) return false;
        this.isDownloading = true;

        if (!fs.existsSync(modelsDir)) {
            fs.mkdirSync(modelsDir, { recursive: true });
        }

        Logger.info(`🦜 [SherpaTTS] Downloading TTS model ${modelDef.id}...`);
        
        return new Promise((resolve) => {
            const tarballPath = path.join(modelsDir, `${modelDef.id}.tar.bz2`);
            const curlCmd = `curl -L "${modelDef.tarballUrl}" -o "${tarballPath}"`;
            
            exec(curlCmd, (error) => {
                if (error) {
                    Logger.error('🦜 [SherpaTTS] Failed to download tarball', error);
                    this.isDownloading = false;
                    return resolve(false);
                }
                
                Logger.info('🦜 [SherpaTTS] Extracting TTS model...');
                const tarCmd = `tar -xf "${tarballPath}" -C "${modelsDir}"`;
                
                exec(tarCmd, (err) => {
                    if (fs.existsSync(tarballPath)) fs.unlinkSync(tarballPath); // cleanup
                    
                    if (err) {
                        Logger.error('🦜 [SherpaTTS] Failed to extract tarball', err);
                        this.isDownloading = false;
                        return resolve(false);
                    }
                    
                    Logger.success('🦜 [SherpaTTS] TTS model ready!');
                    this.isDownloading = false;
                    resolve(true);
                });
            });
        });
    }

    private initTts(): boolean {
        if (this.tts) return true;
        
        const sherpaModule = getSherpaOnnx();
        if (!sherpaModule) return false;

        const modelDef = PIPER_MODELS.find(m => m.id === DEFAULT_TTS_MODEL)!;
        const modelDir = path.join(this.getModelsDir(), modelDef.id);
        
        const onnxPath = path.join(modelDir, 'en_US-amy-low.onnx');
        const tokensPath = path.join(modelDir, 'tokens.txt');
        const dataDir = path.join(modelDir, 'espeak-ng-data');
        
        if (!fs.existsSync(onnxPath)) {
            Logger.warning('🦜 [SherpaTTS] TTS model files missing');
            return false;
        }

        try {
            Logger.info('🦜 [SherpaTTS] Initializing OfflineTTS...');
            this.tts = new sherpaModule.OfflineTts({
                model: {
                    vits: {
                        model: onnxPath,
                        tokens: tokensPath,
                        dataDir: dataDir,
                        noiseScale: 0.667,
                        noiseScaleW: 0.8,
                        lengthScale: 1.0,
                    },
                    numThreads: 2,
                    provider: 'cpu', // Piper runs instantly on CPU, no need for CoreML overhead
                    debug: false,
                },
                maxNumSentences: 1,
            });
            Logger.success('🦜 [SherpaTTS] TTS Initialized');
            return true;
        } catch (error) {
            Logger.error('🦜 [SherpaTTS] Failed to init TTS:', error);
            return false;
        }
    }

    private pcmToWav(samples: Float32Array, sampleRate: number): Buffer {
        // Convert Float32Array to 16-bit PCM Buffer
        const pcm16 = Buffer.alloc(samples.length * 2);
        for (let i = 0; i < samples.length; i++) {
            let s = Math.max(-1, Math.min(1, samples[i]));
            s = s < 0 ? s * 0x8000 : s * 0x7FFF;
            pcm16.writeInt16LE(s, i * 2);
        }

        // Add WAV header
        const numChannels = 1;
        const bitsPerSample = 16;
        const byteRate = sampleRate * numChannels * (bitsPerSample / 8);
        const blockAlign = numChannels * (bitsPerSample / 8);
        const dataSize = pcm16.length;
        const headerSize = 44;
        const fileSize = headerSize + dataSize - 8;

        const wavBuffer = Buffer.alloc(headerSize + dataSize);
        wavBuffer.write('RIFF', 0);
        wavBuffer.writeUInt32LE(fileSize, 4);
        wavBuffer.write('WAVE', 8);
        wavBuffer.write('fmt ', 12);
        wavBuffer.writeUInt32LE(16, 16);
        wavBuffer.writeUInt16LE(1, 20);
        wavBuffer.writeUInt16LE(numChannels, 22);
        wavBuffer.writeUInt32LE(sampleRate, 24);
        wavBuffer.writeUInt32LE(byteRate, 28);
        wavBuffer.writeUInt16LE(blockAlign, 32);
        wavBuffer.writeUInt16LE(bitsPerSample, 34);
        wavBuffer.write('data', 36);
        wavBuffer.writeUInt32LE(dataSize, 40);
        
        pcm16.copy(wavBuffer, 44);
        return wavBuffer;
    }

    public async speak(text: string): Promise<void> {
        const settings = AppSettingsService.getInstance().getSettings();
        if (settings.enableVoiceResponse === false) return; // Note: we'll need to add this to settings

        if (!this.initTts()) {
            // Attempt auto-download and fallback to macOS native 'say' in the meantime
            this.downloadModelIfNeeded();
            Logger.info('🦜 [SherpaTTS] Falling back to native macOS say');
            exec(`say "${text.replace(/"/g, '\\"')}"`);
            return;
        }

        try {
            Logger.info(`🦜 [SherpaTTS] Generating speech for: "${text.substring(0, 30)}..."`);
            const audio = this.tts.generate({ text: text, sid: 0, speed: 1.0 });
            
            if (audio && audio.samples && audio.sampleRate) {
                const wavBuffer = this.pcmToWav(audio.samples, audio.sampleRate);
                const tempFile = path.join(app.getPath('temp'), `jarvis_tts_${Date.now()}.wav`);
                fs.writeFileSync(tempFile, wavBuffer);
                
                // Play and clean up
                exec(`afplay "${tempFile}"`, () => {
                    if (fs.existsSync(tempFile)) fs.unlinkSync(tempFile);
                });
            }
        } catch (error) {
            Logger.error('🦜 [SherpaTTS] Speech generation failed:', error);
            exec(`say "${text.replace(/"/g, '\\"')}"`); // fallback
        }
    }
}
