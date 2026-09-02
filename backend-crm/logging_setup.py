import logging


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # httpx loga "HTTP Request: ..." em INFO para cada chamada externa
    # (UazAPI, OpenAI, backend-core) — com o root em INFO isso inunda os
    # logs de produção. Mantém WARNING+ para não perder erros de rede.
    logging.getLogger("httpx").setLevel(logging.WARNING)
