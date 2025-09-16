import pandas as pd
import json
import os
import random
from typing import Dict, List

CSV_FILE = "verbit.csv"
PACKAGES_FILE = "packages.json"
HIGHSCORES_FILE = "highscores.json"
PACKAGE_SIZE = 20

# --------------------
# Sanat
# --------------------
def load_words(csv_file: str = CSV_FILE) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    expected = {"suomi", "italia", "epäsäännöllinen"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"CSV:stä puuttuu sarakkeita: {', '.join(missing)}")
    for col in ["suomi", "italia", "epäsäännöllinen"]:
        df[col] = df[col].astype(str).fillna("").str.strip()
    return df

# --------------------
# Paketinhallinta
# --------------------
def load_packages(words: pd.DataFrame, package_size: int = PACKAGE_SIZE):
    if os.path.exists(PACKAGES_FILE):
        with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
            packages = json.load(f)
        total = sum(len(p) for p in packages.values())
        return packages if total == len(words) else None
    return None


def save_packages(packages: Dict[str, List[int]]):
    with open(PACKAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(packages, f, ensure_ascii=False, indent=2)


def create_packages(words: pd.DataFrame, package_size: int = PACKAGE_SIZE):
    indices = list(range(len(words)))
    random.shuffle(indices)
    packages = {}
    for i in range(0, len(indices), package_size):
        p_id = f"paketti_{i // package_size + 1}"
        packages[p_id] = indices[i : i + package_size]
    save_packages(packages)
    return packages

# --------------------
# Ennätysten hallinta
# --------------------
def _load_all_highscores():
    """Lataa kaikki ennätykset kaikille listoille."""
    if os.path.exists(HIGHSCORES_FILE):
        with open(HIGHSCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_all_highscores(all_scores):
    with open(HIGHSCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(all_scores, f, ensure_ascii=False, indent=2)

def load_highscores():
    """Palauta vain nykyisen listan ennätykset."""
    all_scores = _load_all_highscores()
    return all_scores.get(CSV_FILE, {})

def save_highscores(scores):
    """Tallenna vain nykyisen listan ennätykset."""
    all_scores = _load_all_highscores()
    all_scores[CSV_FILE] = scores
    _save_all_highscores(all_scores)

def reset_highscore(package_key: str | None = None):
    all_scores = _load_all_highscores()
    scores = all_scores.get(CSV_FILE, {})
    if package_key:
        scores.pop(package_key, None)
    else:
        scores = {}
    all_scores[CSV_FILE] = scores
    _save_all_highscores(all_scores)
    return scores
