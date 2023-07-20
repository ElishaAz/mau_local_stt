# mau_local_stt

A Maubot to transcribe audio messages in matrix rooms using local open-source libraries

## Installation

1. [FFmpeg](https://ffmpeg.org/) must be in `$PATH`
2. Activate the maubot virtual environment (`source ./bin/activate`), and run
    - `pip install whispercpp numpy` - if you want to use [whisper](https://github.com/ggerganov/whisper.cpp) as the
      backend.
    - `pip install vosk` - if you want to use [vosk](https://alphacephei.com/vosk/) as the backend.
3. Download `maulocalstt` from the [releases](https://github.com/ElishaAz/mau_local_stt/releases) (or download the
   repository and build with `mbc build`), and upload it to maubot.
4. Download a model for your backend:
   - For wisper, download a model from https://huggingface.co/ggerganov/whisper.cpp and place it under `models/whispercpp`
   - For vosk, download a zipped model from https://alphacephei.com/vosk/models and unpack it into `models/vosk`
5. Create an instance of the bot, and update the configuration:
   - For whisper, specify
     - `model_name` - the name of the model you downloaded (the name of the file without the `ggml-` and `.bin`)
     - `language` - the language the audio will be in (you can set it to `auto` for whisper to auto-detect the language)
     - `translate` - if you want wisper to translate the transcription to english (`true` or `false`)
   - For vosk, specify
     - `model_path` - the path to the top directory of the model you downloaded (the one with the folders `am` `conf` `graph` etc.), either absolute or related to maubot's working directory.

## Usage
Simply invite the bot to a room, and it will reply to all audio messages with their transcription