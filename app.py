import streamlit as st
import random
from datetime import datetime
import utils
import glob
import os

st.set_page_config(page_title="Italian–Suomi verbivisa", layout="wide")
st.title("📖 Italian–Suomi verbivisa")

# --------------------
# Valitse sanalista
# --------------------
csv_files = glob.glob("*.csv")
if not csv_files:
    st.error("Kansiosta ei löytynyt yhtään CSV-tiedostoa.")
    st.stop()

selected_csv = st.selectbox("Valitse sanalista", csv_files, index=0)

# päivitä utilsin tiedostopolut
utils.CSV_FILE = selected_csv
base = os.path.splitext(selected_csv)[0]
utils.PACKAGES_FILE = f"{base}_packages.json"
utils.HIGHSCORES_FILE = f"{base}_highscores.json"

st.write(f"📂 Käytössä lista: **{selected_csv}**")

# --------------------
# Ladataan sanat ja paketit
# --------------------
try:
    words = utils.load_words()
except Exception as e:
    st.error(f"Virhe sanalistan latauksessa: {e}")
    st.stop()

packages = utils.load_packages(words)
if packages is None:
    st.warning("Paketteja ei löytynyt tai sanalistan pituus muuttunut.")
    if st.button("Jaa paketit uudelleen", type="primary"):
        packages = utils.create_packages(words)
        st.success("Uusi pakettijako luotu.")
else:
    if st.button("Jaa paketit uudelleen"):
        packages = utils.create_packages(words)
        st.success("Uusi pakettijako luotu.")

# --------------------
# Välilehdet ja tila
# --------------------
scores = utils.load_highscores()
TAB_LABELS = ["📂 Pakettilista", "🎮 Visa", "🏆 Ennätykset"]
if "quiz_state" not in st.session_state:
    st.session_state.quiz_state = None

tab1, tab2, tab3 = st.tabs(TAB_LABELS)

# --------------------
# TAB 1: Pakettilista
# --------------------
with tab1:
    st.header("Pakettien sisältö")
    if packages:
        total_words = len(words)
        num_packages = len(packages)
        st.caption(
            f"📦 {total_words} sanaa, {num_packages} pakettia (paketin koko {utils.PACKAGE_SIZE})"
        )
        for p_id, idxs in packages.items():
            st.subheader(f"{p_id} — {len(idxs)} sanaa")
            st.table(words.iloc[idxs][["suomi", "italia", "epäsäännöllinen"]])
    else:
        st.info("Paina \"Jaa paketit uudelleen\" luodaksesi paketit.")

# --------------------
# TAB 2: Visa
# --------------------
with tab2:
    st.header("Visa")
    if not packages:
        st.info("Luo paketit ensin.")
    else:
        direction = st.radio("Suunta", ["it → fi", "fi → it"], horizontal=True)
        wordset = st.radio("Sanajoukko", ["kaikki", "epäsäännölliset", "säännölliset"], horizontal=True)
        mode = st.radio("Tila", ["Eka kierros", "Kunnes kaikki oikein"], horizontal=True)
        package_choice = st.selectbox("Paketti", ["kaikki"] + list(packages.keys()))

        start_col1, start_col2 = st.columns([1, 1])
        with start_col1:
            start = st.button("Aloita visa", type="primary")
        with start_col2:
            if st.button("Nollaa käynnissä oleva visa"):
                st.session_state.quiz_state = None
                st.rerun()

        if start:
            if package_choice == "kaikki":
                indices = [i for ids in packages.values() for i in ids]
            else:
                indices = list(packages[package_choice])

            # Suodata sanajoukko
            if wordset == "epäsäännölliset":
                indices = [i for i in indices if str(words.iloc[i]["epäsäännöllinen"]).lower() == "x"]
            elif wordset == "säännölliset":
                indices = [i for i in indices if str(words.iloc[i]["epäsäännöllinen"]).lower() != "x"]

            random.shuffle(indices)
            st.session_state.quiz_state = {
                "indices": indices,
                "ptr": 0,
                "mode": mode,
                "direction": direction,
                "package": package_choice,
                "wordset": wordset,
                "first_total": len(indices),
                "first_correct": 0,
                "done": False,
                "qkey": 0,
                "start_time": datetime.now().isoformat(timespec="seconds"),
                "await_next": False,
                "last_feedback": None,
                "saved": False,
            }

        state = st.session_state.quiz_state
        if state and not state["done"]:
            if not state["indices"]:
                st.warning("Valitussa yhdistelmässä ei ole sanoja.")
            else:
                current_index = state["indices"][state["ptr"]]
                row = words.iloc[current_index]

                # Edistymispalkki
                progress = state["ptr"] + 1
                total_qs = len(state["indices"])
                st.progress(progress / total_qs, text=f"Kysymys {progress}/{total_qs}")

                # --- Juokseva "Oikein tähän mennessä" -laskuri ---
                answered_so_far = min(state["ptr"], state["first_total"])
                if state.get("await_next", False):
                    answered_so_far = min(answered_so_far + 1, state["first_total"])

                first_correct_preview = state["first_correct"]
                if state.get("await_next", False):
                    fb = state.get("last_feedback")
                    if fb and fb.get("is_correct"):
                        first_correct_preview += 1

                pct_preview = round(100 * first_correct_preview / max(1, answered_so_far), 1)

                st.metric(
                    "Oikein tähän mennessä",
                    f"{first_correct_preview}/{answered_so_far}",
                    f"{pct_preview}%"
                )

                # Kysymys
                if state["direction"] == "it → fi":
                    question, answer = row["italia"], row["suomi"]
                else:
                    question, answer = row["suomi"], row["italia"]

                st.subheader(f"Sana: **{question}**")

                if not state.get("await_next", False):
                    with st.form(key=f"form_{state['qkey']}"):
                        user_answer = st.text_input("Vastauksesi:", key=f"answer_{state['qkey']}", autofocus=True)
                        submitted = st.form_submit_button("Tarkista")

                    if submitted:
                        correct_set = [a.strip().lower() for a in str(answer).split(";")]
                        is_correct = user_answer.strip().lower() in correct_set

                        state["last_feedback"] = {"is_correct": is_correct, "answer": answer}
                        state["await_next"] = True
                        st.rerun()
                else:
                    fb = state["last_feedback"]
                    if fb["is_correct"]:
                        st.success("✓ Oikein!")
                        if state["ptr"] < state["first_total"]:
                            state["first_correct"] += 1
                    else:
                        st.error(f"✗ Väärin. Oikea vastaus: {fb['answer']}")
                        if state["mode"] == "Kunnes kaikki oikein":
                            state["indices"].append(current_index)

                    with st.form(key=f"next_{state['qkey']}"):
                        st.write("Paina Enter jatkaaksesi")
                        _ = st.text_input("(Enter = Seuraava)", key=f"dummy_{state['qkey']}", label_visibility="collapsed")
                        next_pressed = st.form_submit_button("Seuraava")

                    if next_pressed:
                        state["ptr"] += 1
                        state["qkey"] += 1
                        state["await_next"] = False
                        state["last_feedback"] = None
                        if state["ptr"] >= len(state["indices"]):
                            state["done"] = True
                        st.rerun()

        # --- Visa valmis → näytetään lopputulos ---
        if state and state["done"]:
            first_total = max(1, state["first_total"])
            first_correct = state["first_correct"]
            pct = round(100 * first_correct / first_total, 1)

            # kesto ja keskimääräinen vastausaika
            from datetime import datetime as _dt
            start = _dt.fromisoformat(state.get("start_time")) if state.get("start_time") else None
            end = _dt.now()
            duration = (end - start).seconds if start else None
            avg_time = round(duration / first_total, 1) if duration else None

            msg = f"Visa päättyi! Eka kierros oikein: {first_correct}/{first_total} ({pct}%)"
            if duration:
                msg += f" — kesto {duration} s"
            if avg_time:
                msg += f" — keskimäärin {avg_time} s/sana"
            st.success(msg)

            if state["package"] != "kaikki" and not state.get("saved", False):
                key = f"{state['direction']} | {state['package']} | {state['wordset']}"
                scores = utils.load_highscores()
                prev = scores.get(key)
                now = {
                    "oikein": first_correct,
                    "yhteensä": first_total,
                    "prosentti": pct,
                    "aikaleima": datetime.now().isoformat(timespec="seconds"),
                    "kesto_s": duration if duration else None,
                }
                if (not prev) or (first_correct > prev.get("oikein", -1)):
                    scores[key] = now
                    utils.save_highscores(scores)
                    st.write("Ennätys tallennettu.")
                else:
                    st.caption("Ei ylittänyt aiempaa ennätystä → ei tallennettu.")
                state["saved"] = True

            # Uusi peli -nappi
            if st.button("🔄 Uusi peli", type="primary"):
                st.session_state.quiz_state = None
                st.rerun()

# --------------------
# TAB 3: Ennätykset
# --------------------
with tab3:
    st.header("Ennätykset")
    scores = utils.load_highscores()
    if not scores:
        st.info("Ei ennätyksiä vielä.")
    else:
        rows = []
        for k, v in sorted(scores.items(), key=lambda x: x[0]):
            rows.append({
                "Avain": k,
                "Oikein": v.get("oikein"),
                "Yhteensä": v.get("yhteensä"),
                "%": v.get("prosentti"),
                "Kesto (s)": v.get("kesto_s"),
                "Aikaleima": v.get("aikaleima"),
            })
        st.dataframe(rows, use_container_width=True)

        col1, col2 = st.columns([2, 1])
        with col1:
            reset_target = st.selectbox(
                "Valitse nollattava avain (tai Tyhjennä kaikki)",
                ["—"] + list(scores.keys()) + ["Tyhjennä kaikki"],
            )
        with col2:
            if st.button("Nollaa"):
                if reset_target == "Tyhjennä kaikki":
                    utils.reset_highscore()
                    st.success("Kaikki ennätykset nollattu.")
                    st.session_state.quiz_state = None
                    st.rerun()
                elif reset_target != "—":
                    utils.reset_highscore(reset_target)
                    st.success("Valittu ennätys nollattu.")
                    st.session_state.quiz_state = None
                    st.rerun()
