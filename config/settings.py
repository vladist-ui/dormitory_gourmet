from dataclasses import dataclass
from environs import Env


@dataclass
class DbConfig:
    creds_file: str


@dataclass
class TgBot:
    token: str
    admin_ids: list[int]


@dataclass
class Config:
    tg_bot: TgBot
    db: DbConfig


def load_config(path: str = None) -> Config:
    env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot(
            token=env.str("BOT_TOKEN"), admin_ids=list(map(int, env.list("ADMINS")))
        ),
        db=DbConfig(creds_file=env.str("CREDS_FILE", "creds.json")),
    )
