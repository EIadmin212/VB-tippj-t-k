import streamlit as st
import json
import datetime
import os
import hashlib
import pandas as pd
import requests
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------
# BEÁLLÍTÁSOK
# ---------------------------------------------------------
st.set_page_config(page_title="VB Tippjáték 2026", page_icon="⚽", layout="wide")

API_KEY = "61523fa2549e43399c32d65544a160bb"
DATA_FILE = "tippjatek_2026_admin_adatok.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

default_data = {
    "meccsek": {}, 
    "jatekosok": {
        "Admin": {
            "pw_hash": hash_password("admin123"),
            "tippek": {}, "bonusz_gyoztes": "", "bonusz_golkiraly": ""
        }
    }, 
    "regisztralt_nevek": ["Admin"], 
    "torna_gyoztese": "", 
    "torna_golkiralya": "",
    "last_api_update": "2000-01-01 00:00:00"
}

# ---------------------------------------------------------
# ADATBÁZIS ÉS LOGIKA FÜGGVÉNYEK
# ---------------------------------------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "regisztralt_nevek" not in data:
                data["regisztralt_nevek"] = list(data["jatekosok"].keys())
            if "torna_gyoztese" not in data: data["torna_gyoztese"] = ""
            if "torna_golkiralya" not in data: data["torna_golkiralya"] = ""
            if "last_api_update" not in data: data["last_api_update"] = "2000-01-01 00:00:00"
            return data
    return default_data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def calculate_points(tipp_h, tipp_v, teny_h, teny_v):
    if teny_h is None or teny_v is None or tipp_h is None or tipp_v is None:
        return 0
    if tipp_h == teny_h and tipp_v == teny_v:
        return 3
    tipp_kim = "H" if tipp_h > tipp_v else "V" if tipp_v > tipp_h else "D"
    teny_kim = "H" if teny_h > teny_v else "V" if teny_v > teny_h else "D"
    if tipp_kim == teny_kim:
        return 1
    return 0

def torna_elkezdodott(data):
    if not data["meccsek"]: return False 
    legkorabbi_kezdes = None
    for m_id, m in data["meccsek"].items():
        try:
            dt = datetime.datetime.strptime(m["kezdes"], "%Y-%m-%d %H:%M")
            if legkorabbi_kezdes is None or dt < legkorabbi_kezdes:
                legkorabbi_kezdes = dt
        except ValueError:
            continue
    if legkorabbi_kezdes and datetime.datetime.now() > legkorabbi_kezdes:
        return True
    return False

def feldolgoz_meccsek_api(matches_data, data):
    """Közös funkció az API válasz feldolgozására és az időzóna javítására (+2 óra)"""
    for m in matches_data:
        m_id = str(m["id"])
        hazai = m.get("homeTeam", {}).get("name") or "TBD"
        vendeg = m.get("awayTeam", {}).get("name") or "TBD"
        
        # Időzóna javítása: UTC-ből Közép-európai idő (+2 óra hozzáadása)
        dt = datetime.datetime.strptime(m["utcDate"], "%Y-%m-%dT%H:%M:%SZ")
        dt_local = dt + datetime.timedelta(hours=2)
        kezdes_str = dt_local.strftime("%Y-%m-%d %H:%M")
        
        score = m.get("score", {}).get("fullTime", {})
        
        if m_id not in data["meccsek"]:
            data["meccsek"][m_id] = {
                "hazai": hazai, "vendeg": vendeg, "kezdes": kezdes_str, 
                "eredmeny_hazai": score.get("home"), "eredmeny_vendeg": score.get("away")
            }
        else:
            data["meccsek"][m_id]["hazai"] = hazai
            data["meccsek"][m_id]["vendeg"] = vendeg
            data["meccsek"][m_id]["kezdes"] = kezdes_str # Frissíti a helyes időpontra
            if score.get("home") is not None:
                data["meccsek"][m_id]["eredmeny_hazai"] = score.get("home")
                data["meccsek"][m_id]["eredmeny_vendeg"] = score.get("away")
    return data

def frissit_api_okosan(data):
    if not API_KEY.strip(): return False
    most = datetime.datetime.now()
    utolso_frissites = datetime.datetime.strptime(data["last_api_update"], "%Y-%m-%d %H:%M:%S")
    
    if (most - utolso_frissites).total_seconds() >= 60:
        try:
            response = requests.get("https://api.football-data.org/v4/competitions/WC/matches", headers={"X-Auth-Token": API_KEY})
            if response.status_code == 200:
                matches_data = response.json().get("matches", [])
                data = feldolgoz_meccsek_api(matches_data, data)
                
                data["last_api_update"] = most.strftime("%Y-%m-%d %H:%M:%S")
                save_data(data)
                return True
        except Exception:
            pass
    return False

if 'user' not in st.session_state:
    st.session_state['user'] = None

data = load_data()

# ---------------------------------------------------------
# UI: BELÉPTETÉS ÉS REGISZTRÁCIÓ
# ---------------------------------------------------------
if st.session_state['user'] is None:
    st.title("⚽ Világbajnokság Tippjáték 2026")
    st.markdown("### Lépj be a tippek leadásához!")
    
    tab_login, tab_reg = st.tabs(["🔑 Bejelentkezés", "📝 Regisztráció"])
    
    with tab_login:
       
        with st.form("login_form"):
            login_user = st.text_input("Felhasználónév")
            login_pw = st.text_input("Jelszó", type="password")
            submitted = st.form_submit_button("Belépés")
            if submitted:
                if login_user in data["jatekosok"]:
                    if data["jatekosok"][login_user]["pw_hash"] == hash_password(login_pw):
                        st.session_state['user'] = login_user
                        st.rerun()
                    else:
                        st.error("Hibás jelszó!")
                else:
                    st.error("Nincs ilyen regisztrált felhasználó!")

    with tab_reg:
        with st.form("reg_form"):
            reg_user = st.text_input("Új Felhasználónév")
            reg_pw = st.text_input("Új Jelszó", type="password")
            reg_submitted = st.form_submit_button("Regisztráció")
            if reg_submitted:
                if reg_user.lower() == "admin" or reg_user in data["jatekosok"]:
                    st.error("Ez a név már foglalt!")
                elif not reg_user or not reg_pw:
                    st.error("Minden mezőt ki kell tölteni!")
                else:
                    data["regisztralt_nevek"].append(reg_user)
                    data["jatekosok"][reg_user] = {
                        "pw_hash": hash_password(reg_pw),
                        "tippek": {}, "bonusz_gyoztes": "", "bonusz_golkiraly": ""
                    }
                    save_data(data)
                    st.success("Sikeres regisztráció! Most már bejelentkezhetsz.")

# ---------------------------------------------------------
# UI: FŐ ALKALMAZÁS (BELÉPVE)
# ---------------------------------------------------------
else:
    # ⏱️ AUTOMATIKUS FRISSÍTÉS (60 mp)
    st_autorefresh(interval=60000, key="api_refresh")
    
    if frissit_api_okosan(data):
        st.toast('🔄 Eredmények frissítve az API-ból!', icon='⚽')
    
    active_user = st.session_state['user']
    
    # Felső sáv
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(f"⚽ VB Tippjáték - Üdv, {active_user}! 🏆")
        
        utolso_friss = data.get('last_api_update', '2000-01-01 00:00:00')
        ha_nincs = "Még nem történt letöltés" if "2000" in utolso_friss else utolso_friss
        st.caption(f"🔄 **Eredmények utoljára szinkronizálva:** {ha_nincs}")
        
    with col2:
        if st.button("🚪 Kijelentkezés"):
            st.session_state['user'] = None
            st.rerun()
            
    tab_sajat, tab_rivalisok, tab_ranglista, tab_admin = st.tabs([
        "📝 Saját Tippjeim", "👀 Riválisok Tippjei", "📊 Ranglista", "⚙️ Admin & Vezérlés"
    ])
    
    # --- 1. FÜL: SAJÁT TIPPEK ---
    with tab_sajat:
        st.header("Saját tippek leadása")
        elkezdodott = torna_elkezdodott(data)
        
        st.subheader("🏆 Bónusz kérdések (10 - 10 pont)")
        if elkezdodott:
            st.warning("🔒 A torna már elkezdődött, a bónusz tippek lezárultak!")
            st.info(f"**Győztes tipped:** {data['jatekosok'][active_user].get('bonusz_gyoztes', '-')}")
            st.info(f"**Gólkirály tipped:** {data['jatekosok'][active_user].get('bonusz_golkiraly', '-')}")
        else:
            st.success("🟢 A bónusz tippek a torna kezdetéig módosíthatók.")
            with st.form("bonusz_form"):
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    b_gyoztes = st.text_input("Ki nyeri a VB-t?", value=data["jatekosok"][active_user].get("bonusz_gyoztes", ""))
                with col_b2:
                    b_golkiraly = st.text_input("Ki lesz a gólkirály?", value=data["jatekosok"][active_user].get("bonusz_golkiraly", ""))
                
                if st.form_submit_button("Bónuszok Mentése"):
                    data["jatekosok"][active_user]["bonusz_gyoztes"] = b_gyoztes.strip()
                    data["jatekosok"][active_user]["bonusz_golkiraly"] = b_golkiraly.strip()
                    save_data(data)
                    st.success("Bónusz tippek rögzítve!")
                    st.rerun()
                    
        st.divider()
        st.subheader("⚽ Meccsek Tippelése")
        
        if not data["meccsek"]:
            st.info("Még nincsenek meccsek a rendszerben. Várjuk a sorsolást!")
        else:
            tippelheto_meccsek = {
                m_id: f"{m['hazai']} - {m['vendeg']} ({m['kezdes']})" 
                for m_id, m in data["meccsek"].items() 
                if m["eredmeny_hazai"] is None
            }
            
            if tippelheto_meccsek:
                # 🛠️ JAVÍTÁS: A selectbox kikerült az űrlapból, így a váltás azonnal frissíti a mezőket!
                valasztott_meccs = st.selectbox("Válassz meccset a tippeléshez:", options=list(tippelheto_meccsek.keys()), format_func=lambda x: tippelheto_meccsek[x])
                
                elozo_h, elozo_v = 0, 0
                if valasztott_meccs in data["jatekosok"][active_user]["tippek"]:
                    elozo_h = data["jatekosok"][active_user]["tippek"][valasztott_meccs]["hazai"]
                    elozo_v = data["jatekosok"][active_user]["tippek"][valasztott_meccs]["vendeg"]

                with st.form("tipp_form"):
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        tipp_h = st.number_input("Hazai gólok:", min_value=0, max_value=20, value=elozo_h, step=1)
                    with col_t2:
                        tipp_v = st.number_input("Vendég gólok:", min_value=0, max_value=20, value=elozo_v, step=1)
                        
                    if st.form_submit_button("Tipp Leadása"):
                        data["jatekosok"][active_user]["tippek"][valasztott_meccs] = {"hazai": tipp_h, "vendeg": tipp_v}
                        save_data(data)
                        st.success("Tipp sikeresen rögzítve!")
                        st.rerun()
            else:
                st.info("Minden meccs lejátszva, nincs több tippelési lehetőség!")

            st.markdown("#### Leadott Tippjeid Áttekintése")
            tipp_lista = []
            for m_id, m in data["meccsek"].items():
                sajat = data["jatekosok"][active_user]["tippek"].get(m_id)
                tipp_str = f"{sajat['hazai']} - {sajat['vendeg']}" if sajat else "-"
                teny_str = f"{m['eredmeny_hazai']} - {m['eredmeny_vendeg']}" if m['eredmeny_hazai'] is not None else "Várakozás"
                
                pont = ""
                if sajat and m['eredmeny_hazai'] is not None:
                    pont = calculate_points(sajat['hazai'], sajat['vendeg'], m['eredmeny_hazai'], m['eredmeny_vendeg'])
                
                tipp_lista.append({
                    "Meccs": f"{m['hazai']} - {m['vendeg']}",
                    "Kezdés": m['kezdes'],
                    "Tipped": tipp_str,
                    "Eredmény": teny_str,
                    "Pont": pont
                })
            st.dataframe(pd.DataFrame(tipp_lista), use_container_width=True)

    # --- 2. FÜL: RIVÁLISOK TIPPJEI ---
    with tab_rivalisok:
        st.header("👀 Riválisok Tippjei (Csak Lezárt Meccsek)")
        st.write("Itt csak azután láthatod a többiek tippjeit, ha a meccs már véget ért (került be eredmény).")
        
        lezart_meccsek = {
            m_id: f"{m['hazai']} - {m['vendeg']} (Eredmény: {m['eredmeny_hazai']}-{m['eredmeny_vendeg']})" 
            for m_id, m in data["meccsek"].items() 
            if m["eredmeny_hazai"] is not None
        }
        
        if not lezart_meccsek:
            st.info("Még nincs lejátszott meccs. Várjuk a kezdősípszót!")
        else:
            valasztott_lezart = st.selectbox("Válassz egy lejátszott meccset:", options=list(lezart_meccsek.keys()), format_func=lambda x: lezart_meccsek[x])
            m_teny = data["meccsek"][valasztott_lezart]
            
            rival_data = []
            for jatekos, j_data in data["jatekosok"].items():
                tipp_str = "Nem tippelt"
                pont = 0
                if valasztott_lezart in j_data["tippek"]:
                    t = j_data["tippek"][valasztott_lezart]
                    tipp_str = f"{t['hazai']} - {t['vendeg']}"
                    pont = calculate_points(t['hazai'], t['vendeg'], m_teny['eredmeny_hazai'], m_teny['eredmeny_vendeg'])
                rival_data.append({"Játékos": jatekos, "Tippje": tipp_str, "Kapott Pont": pont})
                
            st.dataframe(pd.DataFrame(rival_data).sort_values(by="Kapott Pont", ascending=False), use_container_width=True)

    # --- 3. FÜL: RANGLISTA ÉS BÓNUSZOK ---
    with tab_ranglista:
        st.header("📊 Bajnoki Tabella")
        
        valos_gyoztes = str(data.get("torna_gyoztese") or "").strip().lower()
        valos_golkiraly = str(data.get("torna_golkiralya") or "").strip().lower()
        torna_vege = bool(valos_gyoztes)
        
        eredmenyek = []
        for jatekos, j_data in data["jatekosok"].items():
            meccs_pont = 0
            bonusz_pont = 0
            
            for m_id, tipp in j_data["tippek"].items():
                m_teny = data["meccsek"].get(m_id)
                if m_teny: 
                    meccs_pont += calculate_points(tipp["hazai"], tipp["vendeg"], m_teny["eredmeny_hazai"], m_teny["eredmeny_vendeg"])
            
            j_gyoztes = str(j_data.get("bonusz_gyoztes") or "").strip()
            j_golkiraly = str(j_data.get("bonusz_golkiraly") or "").strip()
            
            if torna_vege and j_gyoztes.lower() == valos_gyoztes: bonusz_pont += 10
            if torna_vege and j_golkiraly.lower() == valos_golkiraly: bonusz_pont += 10
            
            megjelenitett_gyoztes = j_gyoztes if torna_vege or jatekos == active_user else "*** Titkos ***"
            megjelenitett_golkiraly = j_golkiraly if torna_vege or jatekos == active_user else "*** Titkos ***"
                
            ossz_pont = meccs_pont + bonusz_pont
            eredmenyek.append({
                "Játékos": jatekos, 
                "Tipp Győztes": megjelenitett_gyoztes, 
                "Tipp Gólkirály": megjelenitett_golkiraly,
                "Meccs Pont": meccs_pont, 
                "Bónusz Pont": bonusz_pont, 
                "Összesen": ossz_pont
            })
            
        df_ranglista = pd.DataFrame(eredmenyek).sort_values(by="Összesen", ascending=False).reset_index(drop=True)
        df_ranglista.index = df_ranglista.index + 1
        
        st.dataframe(df_ranglista, use_container_width=True)

    # --- 4. FÜL: ADMIN ÉS EREDMÉNYEK (CSAK ADMIN LÁTHATJA) ---
    with tab_admin:
        if active_user == "Admin":
            st.header("⚙️ Adminisztrációs Vezérlőpult")
            st.info("Itt tudod menedzselni a meccseket, a bónuszokat, a felhasználókat és a biztonsági mentéseket.")
            
            st.subheader("👥 Regisztrált Játékosok")
            regisztraltak = data.get("regisztralt_nevek", [])
            st.write(f"Összesen {len(regisztraltak)} játékos van a rendszerben.")
            st.code(", ".join(regisztraltak))
            st.divider()

            st.subheader("💾 Adatbázis Biztonsági Mentés (Export / Import)")
            col_exp, col_imp = st.columns(2)
            
            with col_exp:
                st.markdown("#### Adatok Letöltése (Export)")
                st.write("Mentsd le a teljes adatbázist a saját gépedre biztonsági másolatként!")
                json_string = json.dumps(data, indent=4, ensure_ascii=False)
                st.download_button(
                    label="⬇️ Adatbázis Letöltése (.json)",
                    file_name=f"tippjatek_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    data=json_string
                )

            with col_imp:
                st.markdown("#### Adatok Visszatöltése (Import)")
                st.warning("⚠️ **Figyelem:** Az importálás felülírja a jelenlegi adatokat (a jelszavakat és a tippeket is)!")
                uploaded_file = st.file_uploader("Válassz ki egy korábbi mentést (.json)", type="json")
                
                if uploaded_file is not None:
                    if st.button("🚨 Biztosan felülírom az adatbázist!"):
                        try:
                            uj_adat = json.loads(uploaded_file.getvalue().decode("utf-8"))
                            if "jatekosok" in uj_adat and "meccsek" in uj_adat:
                                save_data(uj_adat)
                                st.success("Adatbázis sikeresen frissítve! Kérlek, frissítsd az oldalt (F5).")
                            else:
                                st.error("A feltöltött fájl nem érvényes tippjáték adatbázis!")
                        except Exception as e:
                            st.error(f"Hiba a beolvasás során: {e}")
                            
            st.divider()
            
            st.subheader("🌍 Kézi API Szinkronizáció")
            if st.button("Meccsek lekérése azonnal"):
                response = requests.get("https://api.football-data.org/v4/competitions/WC/matches", headers={"X-Auth-Token": API_KEY})
                if response.status_code == 200:
                    data = feldolgoz_meccsek_api(response.json().get("matches", []), data)
                    data["last_api_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_data(data)
                    st.success("Meccsek sikeresen szinkronizálva!")
                    st.rerun()
                else:
                    st.error(f"API Hiba: {response.status_code}")

            st.divider()
            st.subheader("🛠️ Kézi Eredmény Megadás (Bírói pult)")
            aktiv_meccsek = {m_id: f"{m['hazai']} - {m['vendeg']} ({m['kezdes']})" for m_id, m in data["meccsek"].items()}
            
            if aktiv_meccsek:
                # 🛠️ JAVÍTÁS ITT IS: A selectbox kikerült az űrlapból
                admin_meccs = st.selectbox("Válaszd ki a meccset:", options=list(aktiv_meccsek.keys()), format_func=lambda x: aktiv_meccsek[x])
                with st.form("manual_result_form"):
                    col_a1, col_a2 = st.columns(2)
                    with col_a1:
                        admin_h = st.number_input("Tényleges Hazai gól:", min_value=0, max_value=20, step=1)
                    with col_a2:
                        admin_v = st.number_input("Tényleges Vendég gól:", min_value=0, max_value=20, step=1)
                        
                    if st.form_submit_button("Lefújás & Eredmény Rögzítése"):
                        data["meccsek"][admin_meccs]["eredmeny_hazai"] = admin_h
                        data["meccsek"][admin_meccs]["eredmeny_vendeg"] = admin_v
                        save_data(data)
                        st.success("Eredmény rögzítve! A meccs lezárult, a tippek publikussá váltak.")
                        st.rerun()
            else:
                st.warning("Nincs aktív meccs az adatbázisban.")

            st.divider()
            st.subheader("🏁 Torna Végeredménye (Bónuszok Kiosztásához)")
            with st.form("tournament_end_form"):
                col_v1, col_v2 = st.columns(2)
                with col_v1:
                    veg_gyoztes = st.text_input("Valós Győztes:", value=data.get("torna_gyoztese", ""))
                with col_v2:
                    veg_golkiraly = st.text_input("Valós Gólkirály:", value=data.get("torna_golkiralya", ""))
                
                if st.form_submit_button("Aranylabda Átadása (Bónuszok Kiosztása)"):
                    data["torna_gyoztese"] = veg_gyoztes.strip()
                    data["torna_golkiralya"] = veg_golkiraly.strip()
                    save_data(data)
                    st.success("A torna végeredménye rögzítve! Bónuszok kiosztva, titkos tippek leleplezve.")
                    st.rerun()
        else:
            st.error("⛔ Nincs jogosultságod megtekinteni ezt az oldalt! Ezt a felületet kizárólag az Adminisztrátor érheti el.")
