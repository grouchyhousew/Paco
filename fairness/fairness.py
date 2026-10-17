"""
fairness.py — Provably Fair для раунда игры "Мины" (и потенциально других
игр с локальным RNG), по схеме commit-reveal:

1. В момент старта раунда генерируется:
   - bomb positions — криптографически случайный набор позиций мин
     (secrets.SystemRandom, не обычный random)
   - binary_map — строка из 0/1 длиной TOTAL_CELLS, "1" = мина, "0" = пусто
   - salt — случайная строка (соль), нужна только затем, чтобы по одному
     публичному хэшу нельзя было перебором подобрать саму карту мин
   - result_string = f"{binary_map}_{salt}"
   - hash = sha256(result_string)  — вот это и есть публичный "коммит"

2. Игроку сразу показывается только hash — до конца раунда карта мин
   математически зафиксирована, но не раскрыта, и оператор не может её
   задним числом поменять (любое изменение result_string меняет hash).

3. После окончания раунда (проигрыш/победа/кэшаут) result_string
   раскрывается полностью и остаётся доступным по кнопке "Честность" у
   результата — можно взять этот result_string, посчитать от него sha256
   самому (например на любом сайте с SHA-256) и свериться с hash, который
   был показан ДО игры.
"""

import hashlib
import secrets
import string

_ALPHABET = string.ascii_letters + string.digits


def _generate_salt(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def generate_mines_commit(total_cells: int, bomb_count: int) -> dict:
    """Генерирует один раунд Мин: позиции бомб + публичный хэш-коммит."""
    positions = secrets.SystemRandom().sample(range(total_cells), bomb_count)
    bomb_set = set(positions)

    binary_map = "".join("1" if i in bomb_set else "0" for i in range(total_cells))
    salt = _generate_salt()
    result_string = f"{binary_map}_{salt}"
    commit_hash = hashlib.sha256(result_string.encode()).hexdigest()

    return {
        "positions": positions,
        "binary_map": binary_map,
        "salt": salt,
        "result_string": result_string,
        "hash": commit_hash,
    }


def generate_tower_commit(max_layers: int, cells_per_layer: int, bomb_count: int) -> dict:
    """
    Генерирует один раунд Башни: мины фиксируются сразу для ВСЕХ слоёв
    (как и было раньше — на каждом этаже своя, заранее известная расстановка),
    но теперь через secrets, и всё сразу склеивается в одну binary_map,
    слой за слоем, для того же commit-reveal, что и в Минах.
    """
    mine_positions = []
    binary_rows = []
    for _ in range(max_layers):
        positions = secrets.SystemRandom().sample(range(cells_per_layer), min(bomb_count, cells_per_layer))
        mine_positions.append(positions)
        binary_rows.append("".join("1" if col in positions else "0" for col in range(cells_per_layer)))

    binary_map = "".join(binary_rows)
    salt = _generate_salt()
    result_string = f"{binary_map}_{salt}"
    commit_hash = hashlib.sha256(result_string.encode()).hexdigest()

    return {
        "mine_positions": mine_positions,
        "binary_map": binary_map,
        "salt": salt,
        "result_string": result_string,
        "hash": commit_hash,
    }


def verify(result_string: str, expected_hash: str) -> bool:
    """Пересчитывает hash от result_string и сверяет с ожидаемым — то же самое,
    что игрок делает вручную на стороннем sha256-калькуляторе."""
    return hashlib.sha256(result_string.encode()).hexdigest() == expected_hash
