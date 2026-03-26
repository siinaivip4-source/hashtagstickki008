import streamlit as st
import pandas as pd
from PIL import Image as PILImage
import time
from transformers import CLIPProcessor, CLIPModel
import torch
import os
import re
import base64

# ===== PAGE CONFIGURATION =====
st.set_page_config(
    page_title="AI Pro Batch Hashtag Generator", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 1. HỆ THỐNG ĐĂNG NHẬP NỘI BỘ =====
def check_password():
    """Trả về True nếu người dùng nhập đúng mật khẩu từ st.secrets."""
    def password_entered():
        if (
            st.session_state["username"] in st.secrets["passwords"]
            and st.session_state["password"]
            == st.secrets["passwords"][st.session_state["username"]]
        ):
            st.session_state["password_correct"] = True
            st.session_state["user_name"] = st.session_state["username"]
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 CỬU VÂN SƠN - HỆ THỐNG NỘI BỘ</h2>", unsafe_allow_html=True)
            st.text_input("👤 Tài khoản", key="username")
            st.text_input("🔑 Mật khẩu", type="password", key="password")
            st.button("Đăng nhập", on_click=password_entered, type="primary", use_container_width=True)
        return False
    elif not st.session_state["password_correct"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 CỬU VÂN SƠN - HỆ THỐNG NỘI BỘ</h2>", unsafe_allow_html=True)
            st.text_input("👤 Tài khoản", key="username")
            st.text_input("🔑 Mật khẩu", type="password", key="password")
            st.button("Đăng nhập", on_click=password_entered, type="primary", use_container_width=True)
            st.error("❌ Tài khoản hoặc mật khẩu không chính xác!")
        return False
    return True

if not check_password():
    st.stop()

# =========================================================================
# LÕI TOOL CHÍNH
# =========================================================================

user_name = st.session_state.get("user_name", "Thành viên")

# CSS cho giao diện
st.markdown("""
    <style>
    div.stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        border-color: #28a745 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Từ điển dữ liệu (Giữ nguyên từ appl7.py) ---
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

VALID_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
OBJECT_L1_OPTIONS = ["None"] + [k for k in OBJECT_HIERARCHY.keys() if k not in ['Action', 'Emotion']]

def get_flat_options(root_key):
    opts = ["None"]
    for l2, l3_list in OBJECT_HIERARCHY[root_key].items():
        if not l3_list: opts.append(l2)
        else: opts.extend(l3_list)
    return opts

ACTION_OPTIONS = get_flat_options('Action')
EMOTION_OPTIONS = get_flat_options('Emotion')

# --- Các hàm xử lý AI & File ---
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

def natural_keys(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def detect_media_type_local(file_path):
    if file_path.lower().endswith('.gif'): return 'Gif'
    try:
        img = PILImage.open(file_path)
        if getattr(img, "is_animated", False): return 'Gif'
    except: pass
    return 'Image'

def run_triple_classification(file_path, vocabs, processor, model, device):
    try:
        image = PILImage.open(file_path).convert("RGB")
        def classify(labels):
            inputs = processor(text=labels, images=image, return_tensors="pt", padding=True).to(device)
            with torch.no_grad():
                outputs = model(**inputs)
                probs = outputs.logits_per_image.softmax(dim=1)
            return labels[probs.argmax().item()]
        return classify(vocabs['Object']), classify(vocabs['Action']), classify(vocabs['Emotion'])
    except: return "None", "None", "None"

def run_style_classification(file_path, styles_list, processor, model, device):
    try:
        valid_styles = [s for s in styles_list if s != "None"]
        image = PILImage.open(file_path).convert("RGB")
        inputs = processor(text=valid_styles, images=image, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0]
        top2 = torch.topk(probs, 2).indices.tolist()
        return valid_styles[top2[0]], valid_styles[top2[1]]
    except: return "None", "None"

@st.cache_data
def get_cached_ai_predictions(file_path):
    processor, model, device = st.session_state['ai_model']
    vocabs = {'Object': st.session_state['v_obj'], 'Action': st.session_state['v_act'], 'Emotion': st.session_state['v_emo']}
    s_obj, s_act, s_emo = run_triple_classification(file_path, vocabs, processor, model, device)
    s_type = detect_media_type_local(file_path)
    s_s1, s_s2 = run_style_classification(file_path, STYLES, processor, model, device)
    return s_obj, s_act, s_emo, s_type, s_s1, s_s2

def get_object_hierarchy_path(leaf_node):
    if leaf_node in ["Other", "None"]: return "None", None, None
    for l1 in [k for k in OBJECT_L1_OPTIONS if k != "None"]:
        for l2, l3_list in OBJECT_HIERARCHY[l1].items():
            if not l3_list and leaf_node == l2: return l1, l2, None
            if leaf_node in l3_list: return l1, l2, leaf_node
    return "None", None, None

@st.dialog("🖼️ Full Folder Preview")
def show_folder_images_dialog(folder_name, file_paths):
    st.markdown(f"**Viewing: {folder_name}**")
    cols = st.columns(4)
    for i, path in enumerate(file_paths):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        ext = path.split('.')[-1].lower()
        mime = f"image/{ext}" if ext != 'webp' else "image/webp"
        cols[i % 4].markdown(f'<img src="data:{mime};base64,{b64}" style="width:100%; border-radius:5px;"/>', unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔄 Làm Mới", use_container_width=True):
            st.rerun()
    with col_b2:
        if st.button("🚪 Đăng Xuất", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()
    
    st.divider()
    processor, model, device = load_clip_model()
    if processor:
        st.success(f"🚀 AI Ready: {device.upper()}")
        st.session_state['ai_model'] = (processor, model, device)
        v_obj, v_act, v_emo = get_separated_vocabularies()
        st.session_state['v_obj'], st.session_state['v_act'], st.session_state['v_emo'] = v_obj, v_act, v_emo

# --- Main UI ---
st.title("🔥 AI Pro Batch Hashtag Generator")
st.caption(f"Đăng nhập bởi: {user_name}")

root_dir = st.text_input("Nhập đường dẫn thư mục cha (ví dụ D:\\Stickers):")

folders_to_process = {}
folder_configs = {}

if root_dir and os.path.isdir(root_dir):
    subdirs = sorted([f.path for f in os.scandir(root_dir) if f.is_dir()], key=lambda x: natural_keys(os.path.basename(x)))
    if not subdirs: subdirs = [root_dir]

    for folder_path in subdirs:
        valid_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(VALID_EXTENSIONS)], key=natural_keys)
        if valid_files:
            folder_name = os.path.basename(folder_path)
            folders_to_process[folder_name] = [os.path.join(folder_path, f) for f in valid_files]
            
            with st.container(border=True):
                c_img, c_cfg = st.columns([1, 4])
                first_img = folders_to_process[folder_name][0]
                
                with c_img:
                    with open(first_img, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    st.markdown(f'<img src="data:image/png;base64,{b64}" style="width:100%; border-radius:8px;"/>', unsafe_allow_html=True)
                    if st.button(f"👁️ View ({len(valid_files)})", key=f"v_{folder_name}"):
                        show_folder_images_dialog(folder_name, folders_to_process[folder_name])
                
                with c_cfg:
                    st.markdown(f"**📂 Folder: {folder_name}**")
                    s_obj, s_act, s_emo, s_type, s_s1, s_s2 = get_cached_ai_predictions(first_img)
                    def_l1, def_l2, def_l3 = get_object_hierarchy_path(s_obj)
                    
                    g1, g2, g3 = st.columns(3)
                    with g1:
                        sel_l1 = st.selectbox("Category (L1)", OBJECT_L1_OPTIONS, index=OBJECT_L1_OPTIONS.index(def_l1) if def_l1 in OBJECT_L1_OPTIONS else 0, key=f"l1_{folder_name}")
                        l2_opts = ["None"] + list(OBJECT_HIERARCHY[sel_l1].keys()) if sel_l1 != "None" else ["None"]
                        sel_l2 = st.selectbox("Subject (L2)", l2_opts, index=l2_opts.index(def_l2) if def_l2 in l2_opts else 0, key=f"l2_{folder_name}")
                    with g2:
                        sel_act = st.selectbox("Action", ACTION_OPTIONS, index=ACTION_OPTIONS.index(s_act) if s_act in ACTION_OPTIONS else 0, key=f"a_{folder_name}")
                        sel_emo = st.selectbox("Emotion", EMOTION_OPTIONS, index=EMOTION_OPTIONS.index(s_emo) if s_emo in EMOTION_OPTIONS else 0, key=f"e_{folder_name}")
                    with g3:
                        sel_s1 = st.selectbox("Style 1", STYLES, index=STYLES.index(s_s1) if s_s1 in STYLES else 0, key=f"s1_{folder_name}")
                        sel_s2 = st.selectbox("Style 2", STYLES, index=STYLES.index(s_s2) if s_s2 in STYLES else 0, key=f"s2_{folder_name}")
                    
                    folder_configs[folder_name] = {"obj": sel_l2 if sel_l2 != "None" else sel_l1, "act": sel_act, "emo": sel_emo, "s1": sel_s1, "s2": sel_s2}

if folders_to_process:
    st.divider()
    if st.button(f"🚀 Xuất Hashtag cho {sum(len(v) for v in folders_to_process.values())} file", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        results = []
        all_paths = [(fn, fp) for fn, fpaths in folders_to_process.items() for fp in fpaths]
        
        for idx, (f_name, f_path) in enumerate(all_paths):
            cfg = folder_configs[f_name]
            h_folder = f"#{f_name.replace(' ', '')}"
            m_type = detect_media_type_local(f_path)
            tags = [h_folder] + [f"#{cfg[k]}" for k in ["obj", "act", "emo", "s1", "s2"] if cfg[k] != "None"] + [f"#{m_type}"]
            results.append({"Folder": f_name, "File": os.path.basename(f_path), "Hashtags": " ".join(tags)})
            progress_bar.progress((idx + 1) / len(all_paths))
            
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Tải CSV", df.to_csv(index=False).encode('utf-8-sig'), "hashtags.csv", "text/csv")
