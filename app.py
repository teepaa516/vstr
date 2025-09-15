import streamlit as st
import streamlit.components.v1 as components
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

# Muista aiempi valinta sessionissa
prev_sel = st.session_state.get("selected_csv")
default_index = csv_files.index(prev_sel) if prev_sel in csv_files else 0
selected_csv = st.selectbox("Valitse sanalista", csv_files, index=default_index, key="selected_csv")

# Nollaa käynnissä oleva visa, jos lista vaihtui
if st.session_state.get("selected_csv_prev") != selected_csv:
    st.session_state.quiz_state = None
    st.session_state.selected_csv_prev = selected_csv

# Päivitä utilsin polut valinnan mukaan
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
TAB_LABELS = ["📂 Pakettilista", "🎮 Visa", "📊 Tulos", "🏆 Ennätykset"]
if "quiz_state" not in st.session_state:
    st.session_state.quiz_state = None

tab1, tab2, tab3, tab4 = st.tabs(TAB_LABELS)

# --------------------
# TAB 1: Pakettilista
# --------------------
with tab1:
    st.header("Pakettien sisältö")
    if packages:
        total_words = len(words)
        num_packages = len(packages)
        st.caption(f"📦 {total_words} sanaa, {num_packages} pakettia (paketin koko {utils.PACKAGE_SIZE})")
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

        colA, colB = st.columns([1,1])
        with colA:
            start = st.button("Aloita visa", type="primary")
        with colB:
            if st.button("Nollaa käynnissä oleva visa"):
                st.session_state.quiz_state = None
                st.rerun()

        if start:
            if package_choice == "kaikki":
                indices = [i for ids in packages.values() for i in ids]
            else:
                indices = list(packages[package_choice])

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

                # --- Juokseva eka kierros oikein -laskuri ---
                first_correct_preview = state["first_correct"]
                if state.get("await_next") and state.get("last_feedback", {}).get("is_correct") and state["ptr"] < state["first_total"]:
                    first_correct_preview += 1
                pct_preview = round(100 * first_correct_preview / max(1, state["first_total"]), 1)
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.metric("Eka kierros oikein", f"{first_correct_preview}/{state['first_total']}", f"{pct_preview}%")
                with c2:
                    st.caption("Ensimmäisen kierroksen tulos päivittyy reaaliajassa.")

                # Kysymys
                if state["direction"] == "it → fi":
                    question, answer = row["italia"], row["suomi"]
                else:
                    question, answer = row["suomi"], row["italia"]

                st.subheader(f"Sana: **{question}**")

                # --- Palautenäkymä ---
                if state.get("await_next"):
                    fb = state.get("last_feedback", {})
                    if fb.get("is_correct"):
                        st.success("✓ Oikein!")
                    else:
                        st.error(f"✗ Väärin. Oikea vastaus: {fb.get('answer')}")

                    with st.form(key=f"nextform_{state['qkey']}"):
                        st.text_input("Paina Enter jatkaaksesi", value="", key=f"continue_{state['qkey']}")
                        go_next = st.form_submit_button("Seuraava")

                    components.html(
                        """
                        <script>
                        const t = setInterval(() => {
                          const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                          if (inputs.length) {
                            inputs[inputs.length - 1].focus();
                            clearInterval(t);
                          }
                        }, 50);
                        </script>
                        """,
                        height=0,
                    )

                    if go_next:
                        if fb.get("is_correct") and state["ptr"] < state["first_total"]:
                            state["first_correct"] += 1
                        if (not fb.get("is_correct")) and state["mode"] == "Kunnes kaikki oikein":
                            state["indices"].append(fb.get("current_index"))

                        state["ptr"] += 1
                        state["qkey"] += 1
                        state["await_next"] = False
                        state["last_feedback"] = None
                        if state["ptr"] >= len(state["indices"]):
                            state["done"] = True
                        st.rerun()

                # --- Vastauslomake ---
                else:
                    with st.form(key=f"form_{state['qkey']}"):
                        user_answer = st.text_input("Vastauksesi:")
                        submitted = st.form_submit_button("Tarkista")

                    components.html(
                        """
                        <script>
                        const t = setInterval(() => {
                          const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                          if (inputs.length) {
                            inputs[inputs.length - 1].focus();
                            clearInterval(t);
                          }
                        }, 50);
                        </script>
                        """,
                        height=0,
                    )

                    if submitted:
                        correct_set = [a.strip().lower() for a in str(answer).split(";")]
                        is_correct = user_answer.strip().lower() in correct_set
                        state["last_feedback"] = {
                            "is_correct": is_correct,
                            "answer": answer,
                            "user": user_answer,
                            "current_index": current_index,
                        }
                        state["await_next"] = True
                        st.rerun()

# --------------------
# TAB 3: Tulos
# --------------------
with tab3:
    st.header("Tulokset")
    state = st.session_state.get("quiz_state")
    if state and state["done"]:
        from datetime import datetime as _dt
        start = _dt.fromisoformat(state.get("start_time")) if state.get("start_time") else None
        end = _dt.now()
        duration = (end - start).seconds if start else None
        avg_time = round(duration / state["first_total"], 1) if duration and state["first_total"] else None

        first_total = max(1, state["first_total"])
        first_correct = state["first_correct"]
        pct = round(100 * first_correct / first_total, 1)

        if state["package"] == "kaikki":
            st.info(f"Eka kierros yhteensä: **{first_correct}/{first_total} ({pct}%)**")
            st.caption("Koonti ei tallennu ennätyksiin.")
        else:
            st.success(f"Eka kierros oikein: **{first_correct}/{first_total} ({pct}%)**")
            if not state.get("saved", False):
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
    else:
        st.info("Pelaa visa ja palaa tähän nähdäksesi tuloksen.")

# --------------------
# TAB 4: Ennätykset
# --------------------
with tab4:
    st.header("Ennätykset")
    st.caption(f"📄 Tämä näkymä käyttää tiedostoa: **{utils.HIGHSCORES_FILE}** (lista: **{selected_csv}**)")

    scores = utils.load_highscores()
    valid_keys = set(packages.keys()) if packages else set()
    filtered_scores = {}
    for k, v in scores.items():
        try:
            _, pkg_name, _ = [s.strip() for s in k.split("|", maxsplit=2)]
        except Exception:
            pkg_name = None
        if (not valid_keys) or (pkg_name in valid_keys):
            filtered_scores[k] = v

    if not filtered_scores:
        st.info("Ei ennätyksiä tälle sanalistalle vielä.")
    else:
        rows = []
        for k, v in sorted(filtered_scores.items(), key=lambda x: x[0]):
            rows.append({
                "Avain": k,
                "Oikein": v.get("oikein"),
                "Yhteensä": v.get("yhteensä"),
                "%": v.get("prosentti"),
                "Kesto (s)": v.get("kesto_s"),
                "Aikaleima": v.get("aikaleima"),
            })
        st.dataframe(rows, use_container_width=True)

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            reset_target = st.selectbox("Valitse nollattava avain (tai Tyhjennä kaikki)",
                                        ["—"] + sorted(filtered_scores.keys()) + ["Tyhjennä kaikki"])
        with col2:
            if st.button("Nollaa"):
                if "Tyhjennä kaikki" in reset_target:
                    utils.reset_highscore()
                    st.success("Kaikki ennätykset tälle sanalistalle nollattu.")
                    st.session_state.quiz_state = None
                    st.rerun()
                elif reset_target != "—":
                    utils.reset_highscore(reset_target)
                    st.success("Valittu ennätys nollattu.")
                    st.session_state.quiz_state = None
                    st.rerun()
        with col3:
            if st.button("Poista highscores-tiedosto"):
                try:
                    os.remove(utils.HIGHSCORES_FILE)
                    st.success(f"Poistettu: {utils.HIGHSCORES_FILE}")
                except FileNotFoundError:
                    st.info("Tiedostoa ei ollut valmiiksi.")
                st.session_state.quiz_state = None
                st.rerun()
