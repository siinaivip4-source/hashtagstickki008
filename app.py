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
import extra_streamlit_components as stx
import firebase_admin
from firebase_admin import credentials, firestore

# ===== PAGE CONFIGURATION =====
st.set_page_config(
    page_title="AI Pro Batch Hashtag Generator", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 0. HỆ THỐNG BẢO MẬT (FIREBASE + COOKIE) =====
# Khởi tạo trực tiếp không cache để tránh lỗi Widget Warning trên Streamlit mới
cookie_manager = stx.CookieManager()

@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            # Đọc JSON từ Secrets của Streamlit Cloud
            key_dict = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error("⚠️ Lỗi cấu hình Firebase. Hãy kiểm tra lại Tab Secrets trên Streamlit Cloud!")
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
            
            # Lấy hoặc tạo Cookie ID để trói thiết bị
            client_cookie_id = cookie_manager.get(cookie="SIIN_DEVICE_ID")
            if not client_cookie_id:
                client_cookie_id = str(uuid.uuid4())
                cookie_manager.set("SIIN_DEVICE_ID", client_cookie_id, max_age=31536000)
            
            st.info(f"💻 Mã trình duyệt: `{str(client_cookie_id)[:8]}...`")
            entered_key = st.text_input("🔑 Nhập License Key của bạn:", type="password")
            
            if st.button("🔓 Mở Khóa Hệ Thống", use_container_width=True, type="primary"):
                if not entered_key:
                    st.warning("Vui lòng nhập Key!")
                    st.stop()
                
                key_ref = db.collection("keys").document(entered_key.strip())
                key_doc = key_ref.get()
                
                if not key_doc.exists:
                    st.error("❌ Key không tồn tại hoặc đã bị thu hồi!")
                else:
                    key_data = key_doc.to_dict()
                    saved_device_id = key_data.get("device_id", "")
                    owner_name = key_data.get("owner_name", "Khách VIP")
                    
                    if saved_device_id == "":
                        key_ref.update({"device_id": client_cookie_id})
                        st.success(f"🎉 Chào mừng {owner_name}! Key đã được khóa vào trình duyệt này.")
                        st.session_state["authenticated"] = True
                        st.session_state["user_name"] = owner_name
                        time.sleep(1.5); st.rerun()
                    elif saved_device_id == client_cookie_id:
                        st.success(f"🎉 Xác thực thành công! Xin chào {owner_name}.")
                        st.session_state["authenticated"] = True
                        st.session_state["user_name"] = owner_name
                        time.sleep(1); st.rerun()
                    else:
                        st.error("🚫 Key này đã được sử dụng trên máy khác. Không thể chia sẻ!")
        st.stop()

check_license_key()

# ===== 1. CẤU HÌNH DỮ LIỆU & CSS =====
st.markdown("""
    <style>
    div.stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        border-color: #28a745 !important;
    }
    </style>
""", unsafe_allow_html=True)

TYPES = ['Gif', 'Image']
STYLES = ['None', 'Meme', 'Funny', 'Cute', 'Hot', 'Slay', 'Lowkey', 'Highkey', 'Savage', '2D', '3D', 'Anime', 'Romance', 'Cool']

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

OBJECT_L1_OPTIONS = ["None"] + [k for k in OBJECT_HIERARCHY.keys() if k not in ['Action', 'Emotion']]

def get_flat_options(root_key):
    opts = ["None"]
    for l2, l3_list in OBJECT_HIERARCHY[root_key].items():
        if not l3_list: opts.append(l2)
        else: opts.extend(l3_list)
    return opts

ACTION_OPTIONS = get_flat_options('Action')
EMOTION_OPTIONS = get_flat_options('Emotion')

# ===== 2. AI MODEL SETUP =====
MODEL_ID = "openai/clip-vit-large-patch14"

@st.cache_resource(show_spinner="Loading AI Model...")
def load_clip_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        processor = CLIPProcessor.from_pretrained(MODEL_ID)
        model = CLIPModel.from_pretrained(MODEL_ID).to(device)
        return processor, model, device
    except: return None, None, "cpu"

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
def get_ai_prediction_from_bytes(file_bytes):
    processor, model, device = st.session_state['ai_model']
    img = PILImage.open(file_bytes).convert("RGB")
    
    obj_l, act_l, emo_l = st.session_state['vocabs']
    s_obj = run_classification(img, obj_l, processor, model, device)
    s_act = run_classification(img, act_l, processor, model, device)
    s_emo = run_classification(img, emo_l, processor, model, device)
    
    # Style
    valid_styles = [s for s in STYLES if s != "None"]
    inputs = processor(text=valid_styles, images=img, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
    top2 = torch.topk(probs, 2).indices.tolist()
    
    return s_obj, s_act, s_emo, valid_styles[top2[0]], valid_styles[top2[1]]

def get_object_hierarchy_path(leaf):
    if leaf in ["Other", "None"]: return "None", None, None
    for l1 in [k for k in OBJECT_L1_OPTIONS if k != "None"]:
        for l2, l3_list in OBJECT_HIERARCHY[l1].items():
            if not l3_list and leaf == l2: return l1, l2, None
            if leaf in l3_list: return l1, l2, leaf
    return "None", None, None

def render_base64_media(file_obj):
    b64 = base64.b64encode(file_obj.getvalue()).decode("utf-8")
    ext = file_obj.name.split('.')[-1].lower()
    mime = f"image/{ext}" if ext != 'webp' else "image/webp"
    st.markdown(f'<img src="data:{mime};base64,{b64}" style="width:100%; border-radius:8px;"/>', unsafe_allow_html=True)

@st.dialog("🖼️ Preview Group")
def show_preview(files):
    cols = st.columns(4)
    for i, f in enumerate(files):
        with cols[i % 4]:
            st.caption(f.name)
            render_base64_media(f)

# ===== MAIN UI =====
st.title("🔥 AI Pro Batch Hashtag Generator")
st.markdown(f"👤 **User:** `{st.session_state.get('user_name')}` | Powered by `ViT-Large-Patch14`")

with st.sidebar:
    if st.button("🔄 Refresh Page", use_container_width=True): st.rerun()
    if st.button("🚪 Logout", use_container_width=True): 
        st.session_state["authenticated"] = False
        st.rerun()
    
    proc, mod, dev = load_clip_model()
    st.session_state['ai_model'] = (proc, mod, dev)
    v_obj, v_act, v_emo = get_separated_vocabularies()
    st.session_state['vocabs'] = (v_obj, v_act, v_emo)
    st.success(f"AI Loaded on: **{dev.upper()}**")

# --- 1. CONFIGURATION ---
st.subheader("1. AI Folder Configuration")
batch_name = st.text_input("📝 Folder/Batch Name (Hashtag):", value="My_Collection")
uploaded_files = st.file_uploader("Upload Images/GIFs:", type=["png", "jpg", "jpeg", "webp", "gif"], accept_multiple_files=True)

if uploaded_files:
    with st.container(border=True):
        col_img, col_cfg = st.columns([1, 4])
        with col_img:
            render_base64_media(uploaded_files[0])
            if st.button(f"👁️ View All ({len(uploaded_files)})", use_container_width=True):
                show_preview(uploaded_files)
        
        with col_cfg:
            # AI soi file đầu tiên
            s_obj, s_act, s_emo, s_s1, s_s2 = get_ai_prediction_from_bytes(uploaded_files[0])
            def_l1, def_l2, def_l3 = get_object_hierarchy_path(s_obj)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                idx_l1 = OBJECT_L1_OPTIONS.index(def_l1) if def_l1 in OBJECT_L1_OPTIONS else 0
                sel_l1 = st.selectbox("L1 Category", OBJECT_L1_OPTIONS, index=idx_l1)
                
                l2_opts = ["None"] + list(OBJECT_HIERARCHY[sel_l1].keys()) if sel_l1 != "None" else ["None"]
                idx_l2 = l2_opts.index(def_l2) if def_l2 in l2_opts else 0
                sel_l2 = st.selectbox("L2 Subject", l2_opts, index=idx_l2)
                
                l3_opts = ["None"] + OBJECT_HIERARCHY[sel_l1][sel_l2] if (sel_l1 != "None" and sel_l2 != "None") else ["None"]
                sel_l3 = st.selectbox("L3 Detail", l3_opts) if len(l3_opts) > 1 else "None"
                
                final_obj = sel_l3 if sel_l3 != "None" else (sel_l2 if sel_l2 != "None" else sel_l1)

            with c2:
                idx_act = ACTION_OPTIONS.index(s_act) if s_act in ACTION_OPTIONS else 0
                sel_act = st.selectbox("Action", ACTION_OPTIONS, index=idx_act)
                idx_emo = EMOTION_OPTIONS.index(s_emo) if s_emo in EMOTION_OPTIONS else 0
                sel_emo = st.selectbox("Emotion", EMOTION_OPTIONS, index=idx_emo)

            with c3:
                idx_s1 = STYLES.index(s_s1) if s_s1 in STYLES else 0
                sel_s1 = st.selectbox("Style 1", STYLES, index=idx_s1)
                sel_s2 = st.selectbox("Style 2", [s for s in STYLES if s != sel_s1 or s == "None"])

    # --- 2. EXPORT ---
    st.divider()
    if st.button(f"🚀 Export {len(uploaded_files)} Files", type="primary", use_container_width=True):
        results = []
        folder_tag = batch_name.replace(" ", "")
        for f in uploaded_files:
            m_type = "Gif" if f.name.lower().endswith('gif') else "Image"
            tags = [folder_tag, final_obj, sel_act, sel_emo, m_type, sel_s1, sel_s2]
            hashtag_str = " ".join([f"#{t}" for t in tags if t and t != "None"])
            
            results.append({
                "File": f.name, "Hashtags": hashtag_str, 
                "Object": final_obj if final_obj != "None" else "",
                "Action": sel_act if sel_act != "None" else "",
                "Emotion": sel_emo if sel_emo != "None" else ""
            })
        
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8-sig'), "hashtags.csv", "text/csv", type="primary")
