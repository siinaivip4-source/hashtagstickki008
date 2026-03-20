import streamlit as st
import pandas as pd
from PIL import Image as PILImage
import time
from transformers import CLIPProcessor, CLIPModel
import torch
import os
import re
import base64
import json
import uuid
import zipfile
import io
import extra_streamlit_components as stx
import firebase_admin
from firebase_admin import credentials, firestore

# ===== PAGE CONFIGURATION =====
st.set_page_config(
    page_title="AI Pro ZIP Batch Hashtag", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 0. HỆ THỐNG BẢO MẬT (FIREBASE + COOKIE) =====
cookie_manager = stx.CookieManager()

@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            key_dict = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        except Exception:
            st.error("⚠️ Lỗi cấu hình Firebase Secrets!")
            st.stop()
    return firestore.client()

db = init_firebase()

def check_license_key():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 CỬU VÂN SƠN - BẢO MẬT</h2>", unsafe_allow_html=True)
            client_cookie_id = cookie_manager.get(cookie="SIIN_DEVICE_ID")
            if not client_cookie_id:
                client_cookie_id = str(uuid.uuid4())
                cookie_manager.set("SIIN_DEVICE_ID", client_cookie_id, max_age=31536000)
            
            st.info(f"💻 Mã trình duyệt: `{str(client_cookie_id)[:8]}-...`")
            entered_key = st.text_input("🔑 Nhập License Key:", type="password")
            
            if st.button("🔓 Mở Khóa Hệ Thống", use_container_width=True, type="primary"):
                key_ref = db.collection("keys").document(entered_key.strip())
                key_doc = key_ref.get()
                if key_doc.exists:
                    key_data = key_doc.to_dict()
                    saved_id = key_data.get("device_id", "")
                    if saved_id == "" or saved_id == client_cookie_id:
                        key_ref.update({"device_id": client_cookie_id})
                        st.session_state["authenticated"] = True
                        st.session_state["user_name"] = key_data.get("owner_name", "VIP")
                        st.rerun()
                    else: st.error("🚫 Key đã bị trói với thiết bị khác!")
                else: st.error("❌ Key không tồn tại!")
        st.stop()

check_license_key()

# ===== 1. CSS HACK: XANH HÓA TẤT CẢ ACTION BUTTONS =====
st.markdown("""
    <style>
    div.stButton > button[kind="primary"], 
    div.stDownloadButton > button {
        background-color: #28a745 !important;
        color: white !important;
        border-color: #28a745 !important;
        width: 100%;
    }
    div.stButton > button[kind="primary"]:hover, 
    div.stDownloadButton > button:hover {
        background-color: #218838 !important;
        border-color: #1e7e34 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ===== 2. DATA HIERARCHY & UTILS =====
OBJECT_HIERARCHY = {
    'Action': {'Communicate': ['Talk', 'Shakehead', 'Shakehand', 'Think', 'Shout', 'Tease', 'Sing', 'Refuse', 'Agree'],
               'Lifeaction': ['Eat', 'Sleep', 'Wakeup', 'Cook', 'Study', 'Work', 'Relax'],
               'Physicalaction': ['Walk', 'Run', 'Jump', 'Dance', 'Clap', 'Shake', 'Punch', 'Racing', 'Beg', 'Pray', 'Twerk', 'Chuck', 'Slap'],
               'Reaction': ['Laugh', 'Cry', 'Surprised', 'Shy', 'Crazy', 'Sulk']},
    'Animal': {'Bear': [], 'Bird': [], 'Capibara': [], 'Cat': [], 'Cockroach': [], 'Dog': [], 'Dragon': [], 'Duck': [], 'Fox': [], 'Frog': [], 'Monkey': [], 'Panda': [], 'Phoenix': [], 'Rabbit': [], 'Shark': [], 'Tasmania': [], 'Tiger': [], 'Turtle': []},
    'Body': {'Brain': [], 'Cheek': [], 'Eyes': [], 'Hand': [], 'Lips': []},
    'Celebrate': {'Birthday': [], 'Graduationday': [], 'Valentine': [], 'Wedding': []},
    'Cuisine': {'Drink': [], 'Food': [], 'Fruit': ['Banana', 'Strawberry', 'Berry', 'Peach']},
    'Culture': {'America': [], 'Brazil': [], 'Buddha': [], 'Chile': [], 'Cross': [], 'God': [], 'Hindi': [], 'Hindugods': [], 'India': [], 'Indonesia': [], 'Mexico': [], 'Religion': [], 'Tamil': [], 'Telugu': [], 'Traditional': [], 'Vietnam': []},
    'Emoji': {'Ghost': []},
    'Emotion': {'Negative': ['Sad', 'Angry', 'Scared', 'Worry', 'Disgust', 'Cold', 'Boring', 'Sick', 'Dizzy'],
                'Positive': ['Happy', 'Shock', 'Wow']},
    'Entertainment': {'Anime': ['Demonslayer', 'Dragonball', 'Onepiece', 'Attackontitan', 'Darlinginthefranxx', 'Jujutsukaisen', 'Bleach', 'Deathnote', 'Nagatoro', 'Spyxfamily'],
                      'Cartoon': ['Flork', 'Dumpling', 'Stitch', 'Pentolquby', 'Bubududu', 'Natra', 'Frozen', 'Brownandcony', 'Thesecretlifeofpets', 'Nailoong', 'Spongebobsquarepants'],
                      'Film': ['Actor', 'Actress', 'Joker', 'Ironman', 'Spiderman', 'Kamenrider', 'Marvel', 'Strangerthings', 'Starwars', 'Gameofthrones'],
                      'Influencer': [], 'KPOP': ['BTS', 'Blackpink', 'Twice', 'Straykids', 'Newjeans'],
                      'Singer': ['Cardi B', 'Taylor Swift', 'Arianagrande']},
    'Game': {'Amongus': [], 'Fortnite': [], 'Freefire': [], 'Leagueoflegends': [], 'Mario': [], 'Pubg': []},
    'Holiday': {'Aprilfool': [], 'Carnival': [], 'Christmas': [], 'Coachella': [], 'Diwali': [], 'Easter': [], 'Eidalfitr': [], 'Halloween': [], 'Holi': [], 'Independenceday': [], 'Memorialday': [], 'Midautumn': [], 'Navratri': [], 'Newyear': [], 'Oktoberfest': [], 'Rakshabandhan': [], 'Ramadan': [], 'Thanksgiving': [], 'Womensday': []},
    'Love': {'Couple': [], 'Crush': [], 'Cuddle': [], 'Heart': [], 'Kiss': [], 'Passion': []},
    'Nature': {'Autumn': [], 'Cloud': [], 'Flower': [], 'Mushroom': [], 'Spring': [], 'Summer': [], 'Sun': [], 'Winter': []},
    'Other': {'Brainrot': [], 'Family': [], 'Ghost': [], 'Girlwithapearlearring': [], 'Landmark': [], 'Logo': [], 'Monalisa': [], 'Money': [], 'Statueofliberty': [], 'Toilet': [], 'Travel': [], 'Vampire': []},
    'Quote': {'Flirt': ['Youarebeautiful', 'Youaremine', 'Yourock', 'Iloveyou', 'Imissyou', 'Ilikeyou'],
              'Greetings': ['Goodmorning', 'Goodevening', 'Goodnight', 'Goodbye', 'Thankyou', 'Sorry', 'Godblessyou', 'Staypositive'],
              'Motivation': ['Nopainnogain', 'Levelup', 'Beyourself', 'Nevergiveup', 'Calmdown'],
              'Satire': ['Idontcare', 'Idontknow', 'Notmyfault', 'Getalife', 'Mindyourbusiness', 'Chillout', 'Nothanks', 'Goaway', 'Donttalktome'],
              'Slang': []},
    'Sport': {'Americanfootball': [], 'Baseball': [], 'Basketball': [], 'Cricket': [], 'F1racing': [], 'Football': ['Flamengo', 'Corinthians', 'Messi', 'Neymar', 'Ronaldo', 'UEFA', 'FIFA', 'Worldcup'], 'Hockey': []},
    'Vehicle': {'Bike': [], 'Car': [], 'Skateboard': []}
}

STYLES = ['None', 'Meme', 'Funny', 'Cute', 'Hot', 'Slay', 'Lowkey', 'Highkey', 'Savage', '2D', '3D', 'Anime', 'Romance', 'Cool']
OBJECT_L1_OPTIONS = ["None"] + [k for k in OBJECT_HIERARCHY.keys() if k not in ['Action', 'Emotion']]

def get_flat_options(root_key):
    opts = ["None"]
    for l2, l3_list in OBJECT_HIERARCHY[root_key].items():
        if not l3_list: opts.append(l2)
        else: opts.extend(l3_list)
    return opts

ACTION_OPTIONS = get_flat_options('Action')
EMOTION_OPTIONS = get_flat_options('Emotion')

# --- Helper Functions ---
def natural_keys(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def detect_type_from_bytes(img_bytes, file_name):
    """Xác nhận định dạng Gif hay Image từ dữ liệu Bytes"""
    ext = file_name.lower().split('.')[-1]
    if ext == 'gif': return 'Gif'
    try:
        img = PILImage.open(io.BytesIO(img_bytes))
        if getattr(img, "is_animated", False): return 'Gif'
    except: pass
    return 'Image'

def render_base64_img(bytes_data, file_name):
    b64 = base64.b64encode(bytes_data).decode("utf-8")
    ext = file_name.split('.')[-1].lower()
    mime = "image/webp" if ext == "webp" else ("image/gif" if ext == "gif" else f"image/{ext}")
    st.markdown(f'<img src="data:{mime};base64,{b64}" style="width:100%; border-radius:8px;"/>', unsafe_allow_html=True)

# ===== 3. AI MODEL SETUP =====
MODEL_ID = "openai/clip-vit-large-patch14"

@st.cache_resource(show_spinner="Loading AI Model...")
def load_clip_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        processor = CLIPProcessor.from_pretrained(MODEL_ID)
        model = CLIPModel.from_pretrained(MODEL_ID).to(device)
        return processor, model, device
    except Exception: return None, None, "cpu"

@st.cache_data
def get_separated_vocabularies():
    obj_labels = []
    for l1 in [k for k in OBJECT_L1_OPTIONS if k != "None"]:
        for l2_key, l3_list in OBJECT_HIERARCHY[l1].items():
            if not l3_list: obj_labels.append(l2_key)
            else: obj_labels.extend(l3_list)
    return sorted(list(set(obj_labels))), sorted([a for a in ACTION_OPTIONS if a != "None"]), sorted([e for e in EMOTION_OPTIONS if e != "None"])

def run_classification(image, labels, processor, model, device):
    inputs = processor(text=labels, images=image, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)
    return labels[probs.argmax().item()]

@st.cache_data
def get_ai_prediction_from_bytes(img_bytes):
    processor, model, device = st.session_state['ai_model']
    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
    v_obj, v_act, v_emo = get_separated_vocabularies()
    
    s_obj = run_classification(img, v_obj, processor, model, device)
    s_act = run_classification(img, v_act, processor, model, device)
    s_emo = run_classification(img, v_emo, processor, model, device)
    
    valid_styles = [s for s in STYLES if s != "None"]
    inputs = processor(text=valid_styles, images=img, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        probs = model(**inputs).logits_per_image.softmax(dim=1)[0]
    top2 = torch.topk(probs, 2).indices.tolist()
    return s_obj, s_act, s_emo, valid_styles[top2[0]], valid_styles[top2[1]]

def get_object_hierarchy_path(leaf):
    if leaf in ["Other", "None"]: return "None", None, None
    for l1 in [k for k in OBJECT_L1_OPTIONS if k != "None"]:
        for l2, l3_list in OBJECT_HIERARCHY[l1].items():
            if not l3_list and leaf == l2: return l1, l2, None
            if leaf in l3_list: return l1, l2, leaf
    return "None", None, None

# --- UI Dialog ---
@st.dialog("🖼️ Xem toàn bộ thư mục")
def show_preview_zip(zip_buffer, files_to_show):
    st.markdown(f"**Hiển thị {len(files_to_show)} tệp trong thư mục**")
    cols = st.columns(4)
    with zipfile.ZipFile(zip_buffer) as z_dialog:
        for i, f_path in enumerate(files_to_show):
            with z_dialog.open(f_path) as f:
                img_bytes_dialog = f.read()
                with cols[i % 4]:
                    st.caption(os.path.basename(f_path))
                    render_base64_img(img_bytes_dialog, f_path)

# ===== 4. MAIN UI =====
st.title("🔥 AI Pro Multi-Folder ZIP Hashtag Generator")
st.markdown(f"👤 **User:** `{st.session_state.get('user_name')}` | 🛠️ **Mode:** Batch ZIP (Web Optimized)")

with st.sidebar:
    if st.button("🔄 Refresh Page"): st.rerun()
    if st.button("🚪 Logout"): 
        st.session_state["authenticated"] = False
        st.rerun()
    proc, mod, dev = load_clip_model()
    st.session_state['ai_model'] = (proc, mod, dev)
    st.success(f"AI: **{dev.upper()}**")

zip_file = st.file_uploader("Upload file .ZIP chứa các Folder Sticker:", type=["zip"])

if zip_file:
    zip_bytes_io = io.BytesIO(zip_file.getvalue())
    with zipfile.ZipFile(zip_bytes_io) as z:
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
        all_files = sorted([m for m in z.namelist() if m.lower().endswith(valid_exts) and not m.startswith('__MACOSX')], key=natural_keys)
        groups = {}
        for f in all_files:
            folder = os.path.dirname(f) or "Root"
            if folder not in groups: groups[folder] = []
            groups[folder].append(f)
        st.success(f"📦 Tìm thấy {len(groups)} Folders và {len(all_files)} tệp.")

        folder_configs = {}
        for f_name, f_files in groups.items():
            with st.expander(f"📂 Thư mục: {f_name} ({len(f_files)} stickers)", expanded=False):
                col_img, col_cfg = st.columns([1, 4])
                with z.open(f_files[0]) as first:
                    img_bytes = first.read()
                    with col_img:
                        render_base64_img(img_bytes, f_files[0])
                        if st.button(f"👁️ View All", key=f"btn_{f_name}", use_container_width=True):
                            show_preview_zip(zip_bytes_io, f_files)
                with col_cfg:
                    s_obj, s_act, s_emo, s_s1, s_s2 = get_ai_prediction_from_bytes(img_bytes)
                    def_l1, def_l2, def_l3 = get_object_hierarchy_path(s_obj)
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.caption("🎯 Object Hierarchy")
                        idx_l1 = OBJECT_L1_OPTIONS.index(def_l1) if def_l1 in OBJECT_L1_OPTIONS else 0
                        sel_l1 = st.selectbox("L1 Category", OBJECT_L1_OPTIONS, index=idx_l1, key=f"l1_{f_name}")
                        l2_opts = ["None"] + list(OBJECT_HIERARCHY[sel_l1].keys()) if sel_l1 != "None" else ["None"]
                        idx_l2 = l2_opts.index(def_l2) if (def_l2 in l2_opts) else 0
                        sel_l2 = st.selectbox("L2 Subject", l2_opts, index=idx_l2, key=f"l2_{f_name}")
                        l3_opts = ["None"] + OBJECT_HIERARCHY[sel_l1][sel_l2] if (sel_l1 != "None" and sel_l2 != "None") else ["None"]
                        if len(l3_opts) > 1:
                            idx_l3 = l3_opts.index(def_l3) if (def_l3 in l3_opts) else 0
                            sel_l3 = st.selectbox("L3 Detail", l3_opts, index=idx_l3, key=f"l3_{f_name}")
                        else: sel_l3 = "None"
                        final_obj = sel_l3 if sel_l3 != "None" else (sel_l2 if sel_l2 != "None" else sel_l1)
                    with c2:
                        st.caption("🎭 Action & Emotion")
                        idx_act = ACTION_OPTIONS.index(s_act) if s_act in ACTION_OPTIONS else 0
                        sel_act = st.selectbox("Action", ACTION_OPTIONS, index=idx_act, key=f"act_{f_name}")
                        idx_emo = EMOTION_OPTIONS.index(s_emo) if s_emo in EMOTION_OPTIONS else 0
                        sel_emo = st.selectbox("Emotion", EMOTION_OPTIONS, index=idx_emo, key=f"emo_{f_name}")
                    with c3:
                        st.caption("🎨 Styles")
                        idx_s1 = STYLES.index(s_s1) if s_s1 in STYLES else 0
                        sel_s1 = st.selectbox("Style 1", STYLES, index=idx_s1, key=f"s1_{f_name}")
                        s2_opts = [s for s in STYLES if s != sel_s1 or s == "None"]
                        idx_s2 = s2_opts.index(s_s2) if s_s2 in s2_opts else 0
                        sel_s2 = st.selectbox("Style 2", s2_opts, index=idx_s2, key=f"s2_{f_name}")
                    folder_configs[f_name] = {
                        "obj": final_obj, "act": sel_act, "emo": sel_emo, 
                        "s1": sel_s1, "s2": sel_s2, "files": f_files
                    }

        st.divider()
        if st.button("🚀 Export All Folders to CSV", type="primary", use_container_width=True):
            results = []
            # Mở lại zip để kiểm tra định dạng từng tệp khi xuất
            with zipfile.ZipFile(zip_bytes_io) as z_final:
                for f_name, cfg in folder_configs.items():
                    folder_hashtag = f_name.split('/')[-1].replace(" ", "")
                    for file_path in cfg["files"]:
                        with z_final.open(file_path) as current_f:
                            file_bytes = current_f.read()
                            
                        fname = os.path.basename(file_path)
                        # ĐỊNH DẠNG ĐÃ TRỞ LẠI:
                        m_type = detect_type_from_bytes(file_bytes, fname)
                        
                        tags = [folder_hashtag, cfg["obj"], cfg["act"], cfg["emo"], m_type, cfg["s1"], cfg["s2"]]
                        hashtag_str = " ".join([f"#{t}" for t in tags if t and t != "None"])
                        
                        results.append({
                            "Folder": f_name, 
                            "File Name": fname, 
                            "Object": cfg["obj"] if cfg["obj"] != "None" else "",
                            "Action": cfg["act"] if cfg["act"] != "None" else "",
                            "Emotion": cfg["emo"] if cfg["emo"] != "None" else "",
                            "Type": m_type,
                            "Style1": cfg["s1"] if cfg["s1"] != "None" else "",
                            "Style2": cfg["s2"] if cfg["s2"] != "None" else "",
                            "Hashtags": hashtag_str
                        })
            
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            st.download_button(
                label="📥 Download Final CSV",
                data=df.to_csv(index=False).encode('utf-8-sig'),
                file_name="hashtags_batch_full.csv",
                mime="text/csv"
            )
