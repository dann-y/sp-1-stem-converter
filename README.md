# SP-1 Stem Converter

Convert a song into an 8-channel, 24-bit, 48 kHz WAV for preparing stems to import to the Teenage Engineering SP-1. Import can be done with Solderless Stemloader: https://solderless.engineering/stemloader

The tool uses Demucs to split an input song into four stereo stems, then writes them into one 8-channel WAV:

- Channels 1-2: drums
- Channels 3-4: bass
- Channels 5-6: other
- Channels 7-8: vocals

## Setup

```bash
bash setup.sh
```

## Usage

Convert one file:

```bash
bash run.sh "song.wav"
```

Choose an output path:

```bash
bash run.sh "song.wav" --output "song_sp1.wav"
```

Set BPM manually:

```bash
bash run.sh "song.wav" --bpm 120
```

Use another Demucs model:

```bash
bash run.sh "song.wav" --model htdemucs_ft
```

Convert a whole folder:

```bash
bash batch_convert.sh "./songs" "./converted"
```

If no BPM is supplied, the script estimates BPM and embeds it in the output filename so Stemloader can detect it.

## Notes

- Input can be WAV, MP3, FLAC, or another audio format supported by the installed audio stack.
- Demucs can take several minutes per song, depending on track length and machine speed.
- Use Solderless Stemloader to import the generated SP-1 WAV: https://solderless.engineering/stemloader
- Generated audio files, virtual environments, and local conversion outputs are ignored by Git.
- Only convert and share audio you have the rights to use.
