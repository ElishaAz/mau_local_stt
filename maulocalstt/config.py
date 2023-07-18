from typing import Callable

from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper


class Config(BaseProxyConfig):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_update = None

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("backend")
        helper.copy_dict("whisper", override_existing_map=False)
        helper.copy_dict("vosk", override_existing_map=False)

        if self.on_update is not None:
            self.on_update()

    def set_on_update(self, on_update: Callable[[], None]):
        self.on_update = on_update
