from typing import Callable

from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper


class Config(BaseProxyConfig):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize on_update
        self.on_update = None

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("backend")  # Set backend. Either vosk or whisper
        helper.copy_dict("whisper", override_existing_map=False)  # Whisper specific config
        helper.copy_dict("vosk", override_existing_map=False)  # Vosk specific config

        # If on_update is set, call it
        if self.on_update is not None:
            self.on_update()

    def set_on_update(self, on_update: Callable[[], None]) -> None:
        """
        Set a callable that will be called whenever the config is updated (including for the first time).
        Should be called before `load_and_update()`
        """
        self.on_update = on_update
