export interface TtsModel {
    id: string;
    name: string;
    description: string;
    tarballUrl: string;
}

export const PIPER_MODELS: TtsModel[] = [
    {
        id: 'vits-piper-en_US-amy-low',
        name: 'Piper Amy (Low)',
        description: 'Extremely fast, natural-sounding English voice.',
        tarballUrl: 'https://github.com/csukuangfj/vits-piper-en_US-amy-low/releases/download/v1.0.0/vits-piper-en_US-amy-low.tar.bz2'
    }
];

export const DEFAULT_TTS_MODEL = 'vits-piper-en_US-amy-low';
