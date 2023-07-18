import os.path
from typing import Tuple, Type, Optional, Any

import mautrix.crypto.attachments
from maubot import Plugin, MessageEvent
from maubot.handlers import command, event, web
from mautrix.client import Client as MatrixClient
from mautrix.types import MessageType, EventType, MediaMessageEventContent, EncryptedFile
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .transcribe_audio import transcribe_audio_whisper, transcribe_audio_vosk

try:
    import whispercpp
    WHISPER_INSTALLED = True
except ModuleNotFoundError:
    whispercpp = type("whispercpp", dict={"Whisper": Any})
    WHISPER_INSTALLED = False

try:
    import vosk
    VOSK_INSTALLED = True
except ModuleNotFoundError:
    vosk = type("vosk", dict={"Model": Any, "KaldiRecognizer": Any})
    VOSK_INSTALLED = False


async def download_encrypted_media(file: EncryptedFile, client: MatrixClient):
    return mautrix.crypto.attachments.decrypt_attachment(await client.download_media(file.url), file.key.key,
                                                         file.hashes['sha256'], file.iv)


async def download_unencrypted_media(url, client: MatrixClient):
    return await client.download_media(url)


class MauLocalSTT(Plugin):
    config: Config

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.whisper_model = None
        self.vosk_model = None
        self.current_backend = None

        self.last_whisper_model_name = None
        self.last_vosk_model_path = None

    allowed_msgtypes: Tuple[MessageType, ...] = (MessageType.AUDIO,)

    def on_config_update(self) -> None:
        if self.config['backend'] == 'whisper':
            if WHISPER_INSTALLED:
                if self.current_backend != 'whisper' or \
                        self.last_whisper_model_name != self.config['whisper']['model_name']:
                    if self.whisper_model is not None:
                        del self.whisper_model
                        self.whisper_model = None
                    if self.vosk_model is not None:
                        del self.vosk_model
                        self.vosk_model = None

                    self.whisper_model = whispercpp.Whisper.from_pretrained(self.config['whisper']["model_name"],
                                                                            basedir='models')

                    self.current_backend = 'whisper'
                    self.last_whisper_model_name = self.config['whisper']['model_name']

                self.whisper_model.params.language = self.config['whisper']['language']
                self.whisper_model.params.translate = self.config['whisper']['translate']
            else:
                self.log.error("Backend is set to 'whisper', but whispercpp is not installed (pip install whispercpp)")

        if self.config['backend'] == 'vosk':
            if VOSK_INSTALLED:
                if self.current_backend != 'vosk' or self.last_vosk_model_path != self.config['vosk']['model_path']:
                    if self.whisper_model is not None:
                        del self.whisper_model
                    if self.vosk_model is not None:
                        del self.vosk_model

                    self.vosk_model = vosk.Model(self.config['vosk']['model_path'])

                    self.current_backend = 'vosk'
                    self.last_vosk_model_path = self.config['vosk']['model_path']
            else:
                self.log.error("Backend is set to 'vosk', but vosk is not installed (pip install vosk)")

    async def pre_start(self) -> None:
        self.config.set_on_update(self.on_config_update)
        self.config.load_and_update()

    async def stop(self) -> None:
        if self.whisper_model:
            del self.whisper_model
            self.whisper_model = None
        if self.vosk_model:
            del self.vosk_model
            self.vosk_model = None
        self.current_backend = None

    @command.passive("", msgtypes=(MessageType.AUDIO,))
    async def hello_world(self, evt: MessageEvent, match: Tuple[str]) -> None:
        if evt.content.msgtype != MessageType.AUDIO:
            return
        content: MediaMessageEventContent = evt.content
        self.log.debug(F"Message received. MimeType: {content.info.mimetype}")
        if content.url:
            data = await download_unencrypted_media(content.url, evt.client)
        elif content.file:
            data = await download_encrypted_media(content.file, evt.client)
        else:
            return

        if self.config['backend'] == 'whisper' and WHISPER_INSTALLED:
            transc = await transcribe_audio_whisper(data, self.whisper_model, content.info.mimetype, self.log)
        elif self.config['backend'] == 'vosk' and VOSK_INSTALLED:
            transc = await transcribe_audio_vosk(data, self.vosk_model, content.info.mimetype, self.log)
        else:
            return

        self.log.debug(F"Message transcribed: {transc}")
        await evt.reply(transc)
        self.log.debug("Reply sent")

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
