import os.path
import shutil
from typing import Tuple, Type, Optional, Any

import mautrix.crypto.attachments
from maubot import Plugin, MessageEvent
from maubot.handlers import command, event, web
from mautrix.client import Client as MatrixClient
from mautrix.types import MessageType, EventType, MediaMessageEventContent, EncryptedFile
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .transcribe_audio import transcribe_audio_whisper, transcribe_audio_vosk

from .import_backends import vosk, VOSK_INSTALLED, whispercpp, WHISPER_INSTALLED


async def download_encrypted_media(file: EncryptedFile, client: MatrixClient) -> bytes:
    """
    Download an encrypted media file
    :param file: The `EncryptedFile` instance, from MediaMessageEventContent.file.
    :param client: The Matrix client. Can be accessed via MessageEvent.client
    :return: The media file as bytes.
    """
    return mautrix.crypto.attachments.decrypt_attachment(await client.download_media(file.url), file.key.key,
                                                         file.hashes['sha256'], file.iv)


async def download_unencrypted_media(url, client: MatrixClient) -> bytes:
    """
    Download an unencrypted media file
    :param url: The media file mxc url, from MediaMessageEventContent.url.
    :param client: The Matrix client. Can be accessed via MessageEvent.client
    :return: The media file as bytes.
    """
    return await client.download_media(url)


class MauLocalSTT(Plugin):
    config: Config  # Set type for type hinting

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize variables
        self.whisper_model = None
        self.vosk_model = None
        self.current_backend = None

        self.last_whisper_model_name = None
        self.last_vosk_model_path = None

    allowed_msgtypes: Tuple[MessageType, ...] = (MessageType.AUDIO,)

    def on_config_update(self) -> None:
        """
        Called by `Config` when the configuration is updated
        """
        if self.config['backend'] == 'whisper':
            if WHISPER_INSTALLED:
                # if the current backend is not whisper, or the model has changed
                if self.current_backend != 'whisper' or \
                        self.last_whisper_model_name != self.config['whisper']['model_name']:
                    # delete the old model
                    if self.whisper_model is not None:
                        del self.whisper_model
                        self.whisper_model = None
                    if self.vosk_model is not None:
                        del self.vosk_model
                        self.vosk_model = None

                    self.current_backend = None

                    # load the (new) model
                    self.whisper_model = whispercpp.Whisper.from_pretrained(self.config['whisper']["model_name"],
                                                                            basedir=self.config['whisper']['base_dir'])

                    self.current_backend = 'whisper'
                    self.last_whisper_model_name = self.config['whisper']['model_name']

                self.whisper_model.params.language = self.config['whisper']['language']
                self.whisper_model.params.translate = self.config['whisper']['translate']
            else:  # whispercpp is not installed
                self.log.error("Backend is set to 'whisper', but whispercpp is not installed (pip install whispercpp)")

        if self.config['backend'] == 'vosk':
            if VOSK_INSTALLED:
                # if the current backend is not vosk, or the model has changed
                if self.current_backend != 'vosk' or self.last_vosk_model_path != self.config['vosk']['model_path']:
                    # delete the old model
                    if self.whisper_model is not None:
                        del self.whisper_model
                    if self.vosk_model is not None:
                        del self.vosk_model

                    self.current_backend = None

                    # make sure the model is actually there
                    if os.path.isdir(self.config['vosk']['model_path']):
                        self.vosk_model = vosk.Model(self.config['vosk']['model_path'])

                        self.current_backend = 'vosk'
                        self.last_vosk_model_path = self.config['vosk']['model_path']
                    else:  # the model file does not exist
                        self.log.error(F"Vosk model not found at {self.config['vosk']['model_path']}")
            else:  # vosk is not installed
                self.log.error("Backend is set to 'vosk', but vosk is not installed (pip install vosk)")

    async def pre_start(self) -> None:
        """
        Called before the handlers are initialized
        :return:
        """
        # Make Config call self.on_config_update whenever the config is updated.
        self.config.set_on_update(self.on_config_update)
        # Load the config. This will call self.on_config_update, which will load the model.
        self.config.load_and_update()

    async def stop(self) -> None:
        # delete the models to free up RAM
        if self.whisper_model:
            del self.whisper_model
            self.whisper_model = None
        if self.vosk_model:
            del self.vosk_model
            self.vosk_model = None
        self.current_backend = None

    @command.passive("", msgtypes=(MessageType.AUDIO,))
    async def transcribe_audio_message(self, evt: MessageEvent, match: Tuple[str]) -> None:
        """
        Replies to all audio messages with their transcription.
        """
        # Make sure that the message type is audio
        if evt.content.msgtype != MessageType.AUDIO:
            return

        content: MediaMessageEventContent = evt.content
        self.log.debug(F"Message received. MimeType: {content.info.mimetype}")

        if content.url:  # content.url exists. File is not encrypted
            data = await download_unencrypted_media(content.url, evt.client)
        elif content.file:  # content.file exists. File IS encrypted
            data = await download_encrypted_media(content.file, evt.client)
        else:  # shouldn't happen
            self.log.warning("A message with AUDIO message type received, but it does not contain a file.")
            return

        if shutil.which("ffmpeg") is None:
            self.log.error("FFmpeg must be on PATH")
            return

        if self.config['backend'] == 'whisper' and WHISPER_INSTALLED:
            # transcribe using whisper
            transc = await transcribe_audio_whisper(data, self.whisper_model, content.info.mimetype, self.log)
        elif self.config['backend'] == 'vosk' and VOSK_INSTALLED:
            # transcribe using vosk
            transc = await transcribe_audio_vosk(data, self.vosk_model, content.info.mimetype, self.log)
        else:
            self.log.warning("An audio message was received, but no valid backend is configured")
            return

        self.log.debug(F"Message transcribed: {transc}")
        # send transcription as reply
        await evt.reply(transc)
        self.log.debug("Reply sent")

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
