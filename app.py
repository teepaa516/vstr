import streamlit as st
import pandas as pd
import json
import random
import time
import os
from datetime import datetime

# ------------------------
# Tiedostot
# ------------------------
PACKAGES_FILE = "packages.json"
HIGHSCORES_FILE = "highscores.json"
PACKAGE_SIZE = 20

# ------------------------
# Apufunktiot
# ------------------------
def load_words(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    expected = {"suomi", "italia", "epäsäännöllinen"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"CSV:stä puuttuu sarakkeita: {', '.join(missing)}")
    for col in expected:
        df[col] = df[col].astype(str).fillna("").str.strip()
    return df

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_packages(words, size=PACKAGE_SIZE):
    shuffled = words.sample(frac=1, random_state=42).reset_index(drop=True)
    return {
        f"paketti_{i+1}": shuffled.iloc[i*size:(i+1)*size].index.tolist()
        for i in range((len(shuffled) + size - 1) // size)
    }

def check_answer(user_answer, correct_answer):
    alts = [a.strip().lower() for a in correct_answer.split(";")]
    return user_answer.strip().lower() in alts

def record_highscore(highscores, key, correct, total, duration):
    ts = datetime.now().isoformat(timespec="seconds")
    percent = round(100 * correct / total, 1) if total else 0
    best = highscores.get(key)
    if not best or correct > best["correct"]:
        highscores[key] = {
            "correct": correct,
            "total": total,
            "percent": percent,
            "duration": duration,
            "timestamp": ts
        }
        save_json(HIGHSCORES_FILE, highscores)

# ------------------------
# UI
# ------------------------
st.set_page_config(page_title="Italian–Suomi verbivisa", layout="centered")
st.title("📖 Italian–Suomi verbivisa")

# Sanalistan valinta
csv_files = [f for f in os.listdir() if f.endswith(".csv")]
selected_csv = st.selectbox("Valitse sanalista", csv_files)

words = load_words(selected_csv)

# Ladataan paketit ja ennätykset
packages = load_json(PACKAGES_FILE, {})
highscores = load_json(HIGHSCORES_FILE, {})

if selected_csv not in packages:
    packages[selected_csv] = create_packages(words)
    save_json(PACKAGES_FILE, packages)

st.write(f"📂 Käytössä lista: **{selected_csv}**")

if st.button("Jaa paketit uudelleen"):
    packages[selected_csv] = create_packages(words)
    save_json(PACKAGES_FILE, packages)
    st.success("Paketit jaettu uudelleen!")

# Välilehdet
tab_list, tab_quiz, tab_scores = st.tabs(["📂 Paketit", "🎮 Visa", "🏆 Ennätykset"])

# ------------------------
# Pakettien listaus
# ------------------------
with tab_list:
    for name, idxs in packages[selected_csv].items():
        st.subheader(name)
        st.table(words.loc[idxs, ["italia", "suomi", "epäsäännöllinen"]])

# ------------------------
# Visa
# ------------------------
with tab_quiz:
    if "quiz" not in st.session_state:
        st.session_state.quiz = {}
    state = st.session_state.quiz

    package = st.selectbox("Paketti", ["kaikki"] + list(packages[selected_csv].keys()))
    mode = st.radio("Tila", ["Eka kierros", "Kunnes kaikki oikein"])
    direction = st.radio("Suunta", ["it → fi", "fi → it"])
    filter_type = st.radio("Sanajoukko", ["kaikki", "vain epäsäännölliset", "vain säännölliset"])

    if st.button("Aloita visa"):
        if package == "kaikki":
            idxs = sum(packages[selected_csv].values(), [])
        else:
            idxs = packages[selected_csv][package]
        df = words.loc[idxs]
        if filter_type != "kaikki":
            df = df[df["epäsäännöllinen"].str.lower().eq("x") if filter_type == "vain epäsäännölliset" else df["epäsäännöllinen"].str.lower().ne("x")]
        qlist = df.sample(frac=1).to_dict("records")
        state.update({
            "questions": qlist,
            "remaining": qlist.copy(),
            "done": [],
            "qkey": 0,
            "correct_first": 0,
            "start_time": time.time(),
            "package": package,
            "mode": mode,
            "direction": direction,
            "finished": False
        })

    if state.get("remaining") and not state.get("finished"):
        q = state["remaining"][0]
        ask, ans = ("italia", "suomi") if direction == "it → fi" else ("suomi", "italia")
        st.subheader(f"Sana: {q[ask]}")

        with st.form(key=f"form_{state['qkey']}"):
            user_answer = st.text_input(
                "Vastauksesi:",
                key=f"answer_{state['qkey']}",
                autofocus=True
            )
            submitted = st.form_submit_button("Tarkista")

        if submitted:
            if check_answer(user_answer, q[ans]):
                st.success("✓ Oikein!")
                if q not in state["done"]:
                    state["correct_first"] += 1
                state["remaining"].pop(0)
                state["done"].append(q)
            else:
                st.error(f"✗ Väärin. Oikea vastaus: {q[ans]}")
                if mode == "Kunnes kaikki oikein":
                    state["remaining"].append(state["remaining"].pop(0))
                else:
                    state["remaining"].pop(0)
                    state["done"].append(q)
            state["qkey"] += 1

        progress = len(state["done"]) / (len(state["done"]) + len(state["remaining"]))
        st.progress(progress)
        st.metric("Eka kierros oikein", f"{state['correct_first']}/{len(state['done'])+len(state['remaining'])}")

    elif state.get("finished") or (state.get("questions") and not state.get("remaining")):
        duration = int(time.time() - state["start_time"])
        total = len(state["questions"])
        correct = state["correct_first"]
        st.success(f"Visa valmis! Eka kierros oikein {correct}/{total} ({100*correct/total:.1f}%) ajassa {duration} s.")
        key = f"{selected_csv}|{direction}|{state['package']}"
        record_highscore(highscores, key, correct, total, duration)
        state["finished"] = True

# ------------------------
# Ennätykset
# ------------------------
with tab_scores:
    if highscores:
        df = pd.DataFrame([
            {"Avain": k, **v} for k, v in highscores.items()
        ])
        st.dataframe(df)

        reset = st.selectbox("Valitse nollattava avain (tai Tyhjennä kaikki)", ["Tyhjennä kaikki"] + list(highscores.keys()))
        if st.button("Nollaa"):
            if reset == "Tyhjennä kaikki":
                highscores.clear()
            else:
                highscores.pop(reset, None)
            save_json(HIGHSCORES_FILE, highscores)
            st.experimental_rerun()
    else:
        st.info("Ei ennätyksiä vielä.")
