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
import firebase_admin
from firebase_admin import credentials, firestore
from streamlit_google_auth import Authenticate

# ===== PAGE CONFIGURATION =====
st.set_page_config(
    page_title="AI Pro Batch Hashtag Generator", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== TẠO FILE GOOGLE AUTH ẢO TỪ SECRETS =====
if not os.path.exists("google_credentials.json"):
    try:
        # Lấy nội dung từ Streamlit Secrets
        google_creds = json.loads(st.secrets["google_auth_json"])
        # Ghi ra một file ảo trên server
        with open("google_credentials.json", "w") as f:
            json.dump(google_creds, f)
    except Exception as e:
        st.error("⚠️ Chưa cấu hình biến 'google_auth_json' trong Streamlit Secrets!")
        st.stop()

# ===== 0. CẤU HÌNH GOOGLE AUTH =====
authenticator = Authenticate(
    secret_credentials_path='google_credentials.json',
    cookie_name='ai_pro_hashtag_cookie',
    cookie_key='chuoi_ma_hoa_bi_mat_cua_cau',
    # QUAN TRỌNG: Sửa link dưới đây thành link app Streamlit thật của cậu
    redirect_uri='https://hashtagstickki008.streamlit.app', 
)

# ... (Giữ nguyên phần code Firebase và phần Lõi ở dưới) ...

# ===== 1. KHỞI TẠO FIREBASE (Dùng để check Whitelist Email) =====
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            key_dict = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error("⚠️ Lỗi cấu hình Firebase Secrets. Vui lòng kiểm tra lại file secrets.toml.")
            st.stop()
    return firestore.client()

db = init_firebase()

# ===== 2. HỆ THỐNG KIỂM DUYỆT ĐĂNG NHẬP (GMAIL) =====
def check_gmail_login():
    # Kiểm tra trạng thái session từ cookie Google
    authenticator.check_authentification()

    if not st.session_state.get('connected'):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 CỬU VÂN SƠN - HỆ THỐNG NỘI BỘ</h2>", unsafe_allow_html=True)
            st.caption("Vui lòng đăng nhập bằng tài khoản Gmail đã được cấp quyền.")
            
            # Render nút Login của Google
            authenticator.login()
            
        st.stop() # Cắt luồng chạy nếu chưa đăng nhập thành công
    
    else:
        # Lấy thông tin user sau khi Google trả về
        user_info = st.session_state.get('user_info', {})
        user_email = user_info.get('email')
        user_name = user_info.get('name', 'Khách VIP')
        
        # --- BƯỚC KIỂM DUYỆT BẰNG FIREBASE ---
        # Tìm trong collection "allowed_users" xem có email này không
        user_ref = db.collection("allowed_users").document(user_email)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            st.error(f"❌ Tài khoản {user_email} chưa được cấp quyền truy cập hệ thống!")
            # Render nút đăng xuất để user có thể thoát và thử mail khác
            authenticator.logout()
            st.stop()
        else:
            # Lấy data từ Firebase (có thể thêm tên, role, status chặn...)
            user_data = user_doc.to_dict()
            is_active = user_data.get("is_active", True) 
            
            if not is_active:
                st.error(f"🚫 Tài khoản {user_email} đã bị tạm khóa bởi quản trị viên!")
                authenticator.logout()
                st.stop()

            # Nếu hợp lệ qua hết các bài test
            st.session_state["authenticated"] = True
            st.session_state["user_name"] = user_name
            st.session_state["user_email"] = user_email

check_gmail_login()

# =========================================================================
# TỪ ĐÂY TRỞ XUỐNG LÀ LÕI TOOL CHÍNH (Chỉ chạy khi Email hợp lệ)
# =========================================================================

user_name = st.session_state.get("user_name", "Khách")
user_email = st.session_state.get("user_email", "")

st.markdown("""
    <style>
    div.stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        border-color: #28a745 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838 !important;
        border-color: #1e7e34 !important;
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

MODEL_ID = "openai/clip-vit-large-patch14"

@st.cache_resource(show_spinner=f"Loading Heavy AI Model ({MODEL_ID}) into GPU... Please wait.")
def load_clip_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        processor = CLIPProcessor.from_pretrained(MODEL_ID)
        model = CLIPModel.from_pretrained(MODEL_ID).to(device)
        return processor, model, device
    except Exception as e:
        return None, None, "cpu"

@st.cache_data
def get_separated_vocabularies():
    obj_labels = []
    for l1 in [k for k in OBJECT_L1_OPTIONS if k != "None"]:
        for l2_key, l3_list in OBJECT_HIERARCHY[l1].items():
            if not l3_list: obj_labels.append(l2_key)
            else: obj_labels.extend(l3_list)
    if not obj_labels: obj_labels.append("Other")
    return sorted(list(set(obj_labels))), sorted([a for a in ACTION_OPTIONS if a != "None"]), sorted([e for e in EMOTION_OPTIONS if e != "None"])

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

def natural_keys(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def detect_media_type_local(file_path):
    ext = file_path.split('.')[-1].lower()
    if ext == 'gif': return 'Gif'
    try:
        img = PILImage.open(file_path)
        if getattr(img, "is_animated", False): return 'Gif'
    except Exception: pass
    return 'Image'

def run_triple_classification(file_path, vocabs, processor, model, device):
    try:
        image = PILImage.open(file_path).convert("RGB")
        def classify(labels):
            if not labels: return "None"
            inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = model(**inputs)
                probs = outputs.logits_per_image.softmax(dim=1)
            return labels[probs.argmax().item()]
        
        best_obj = classify(vocabs['Object'])
        best_act = classify(vocabs['Action'])
        best_emo = classify(vocabs['Emotion'])
        return best_obj, best_act, best_emo
    except Exception:
        return "None", "None", "None"

def run_style_classification(file_path, styles_list, processor, model, device):
    try:
        valid_styles = [s for s in styles_list if s != "None"]
        image = PILImage.open(file_path).convert("RGB")
        inputs = processor(text=valid_styles, images=image, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0]
        
        top2_idx = torch.topk(probs, 2).indices.tolist()
        return valid_styles[top2_idx[0]], valid_styles[top2_idx[1]]
    except Exception:
        return "None", "None"

@st.cache_data
def get_cached_ai_predictions(file_path):
    processor, model, device = st.session_state['ai_model']
    if not processor: return "None", "None", "None", "Image", "None", "None"
    
    vocabs = {'Object': st.session_state['v_obj'], 'Action': st.session_state['v_act'], 'Emotion': st.session_state['v_emo']}
    s_obj, s_act, s_emo = run_triple_classification(file_path, vocabs, processor, model, device)
    s_type = detect_media_type_local(file_path)
    s_style1, s_style2 = run_style_classification(file_path, STYLES, processor, model, device)
    
    return s_obj, s_act, s_emo, s_type, s_style1, s_style2

def get_object_hierarchy_path(leaf_node):
    if leaf_node == "Other" or leaf_node == "None": return "None", None, None
    for l1 in [k for k in OBJECT_L1_OPTIONS if k != "None"]:
        for l2, l3_list in OBJECT_HIERARCHY[l1].items():
            if not l3_list and leaf_node == l2:
                return l1, l2, None
            if leaf_node in l3_list:
                return l1, l2, leaf_node
    return "None", None, None

@st.dialog("🖼️ Full Folder Preview")
def show_folder_images_dialog(folder_name, file_paths):
    st.markdown(f"**Viewing all {len(file_paths)} images in '{folder_name}'**")
    cols = st.columns(4)
    for i, file_path in enumerate(file_paths):
        try:
            cols[i % 4].caption(os.path.basename(file_path))
            with open(file_path, "rb") as img_file:
                b64_str = base64.b64encode(img_file.read()).decode("utf-8")
            ext = file_path.split('.')[-1].lower()
            mime_type = "image/webp" if ext == "webp" else ("image/gif" if ext == "gif" else f"image/{ext}")
            html_img = f'<img src="data:{mime_type};base64,{b64_str}" style="width:100%; border-radius:8px;" />'
            cols[i % 4].markdown(html_img, unsafe_allow_html=True)
        except Exception:
            cols[i % 4].write("*(Format error)*")

st.title("🔥 AI Pro Batch Hashtag Generator")
st.markdown(f"**👤 Xin chào `{user_name}` ({user_email})** | Powered by `ViT-Large-Patch14` on **GPU**.")

with st.sidebar:
    st.subheader("Bảng Điều Khiển")
    if st.button("🔄 Làm Mới Hệ Thống", use_container_width=True):
        st.rerun()
        
    # Nút đăng xuất của thư viện Google Auth
    authenticator.logout()
        
    st.divider()
    st.subheader("System Status")
    processor, model, device = load_clip_model()
    if processor and model:
        if device == "cuda":
            st.success(f"🚀 AI Loaded on: **GPU (CUDA)**")
        else:
            st.warning(f"⚠️ AI Loaded on: **CPU** (Slow! Please install CUDA)")
            
        st.session_state['ai_model'] = (processor, model, device)
        v_obj, v_act, v_emo = get_separated_vocabularies()
        st.session_state['v_obj'] = v_obj
        st.session_state['v_act'] = v_act
        st.session_state['v_emo'] = v_emo
    else:
        st.error("AI Model failed to load.")
        st.session_state['ai_model'] = (None, None, "cpu")

st.subheader("1. AI Folder Configuration")
root_dir = st.text_input("Parent Directory Path (e.g., D:\\My_Stickers):")

folders_to_process = {}
folder_configs = {}

if root_dir and os.path.isdir(root_dir):
    subdirs = sorted([f.path for f in os.scandir(root_dir) if f.is_dir()], key=lambda x: natural_keys(os.path.basename(x)))
    if not subdirs: subdirs = [root_dir] 
        
    st.success(f"Detected {len(subdirs)} folder(s). Generating AI predictions...")
    
    for folder_path in subdirs:
        valid_files = [f for f in os.listdir(folder_path) if f.lower().endswith(VALID_EXTENSIONS)]
        valid_files.sort(key=natural_keys) 
        
        if valid_files:
            folder_name = os.path.basename(folder_path)
            folders_to_process[folder_name] = [os.path.join(folder_path, f) for f in valid_files]
            first_img_path = os.path.join(folder_path, valid_files[0])
            
            with st.container(border=True):
                col_img, col_cfg = st.columns([1, 4])
                
                with col_img:
                    try:
                        with open(first_img_path, "rb") as f:
                            b64_first = base64.b64encode(f.read()).decode("utf-8")
                        first_ext = first_img_path.split('.')[-1].lower()
                        first_mime = "image/webp" if first_ext == "webp" else ("image/gif" if first_ext == "gif" else f"image/{first_ext}")
                        
                        st.markdown(f'<img src="data:{first_mime};base64,{b64_first}" style="width:100%; border-radius:8px;"/>', unsafe_allow_html=True)
                    except Exception as e:
                        st.write("*(Preview error)*")
                        
                    if st.button(f"👁️ View All ({len(valid_files)})", key=f"btn_{folder_name}", use_container_width=True):
                        show_folder_images_dialog(folder_name, folders_to_process[folder_name])
                        
                with col_cfg:
                    st.markdown(f"**📂 Folder: {folder_name}**")
                    
                    s_obj, s_act, s_emo, s_type, s_s1, s_s2 = get_cached_ai_predictions(first_img_path)
                    def_l1, def_l2, def_l3 = get_object_hierarchy_path(s_obj)
                    
                    cfg1, cfg2, cfg3 = st.columns(3)
                    
                    with cfg1:
                        st.caption("🎯 Object Hierarchy")
                        idx_l1 = OBJECT_L1_OPTIONS.index(def_l1) if def_l1 in OBJECT_L1_OPTIONS else 0
                        sel_l1 = st.selectbox("L1 (Category)", options=OBJECT_L1_OPTIONS, index=idx_l1, key=f"l1_{folder_name}")
                        
                        if sel_l1 and sel_l1 != "None":
                            l2_opts = ["None"] + list(OBJECT_HIERARCHY[sel_l1].keys())
                            idx_l2 = l2_opts.index(def_l2) if def_l2 in l2_opts else 0
                            sel_l2 = st.selectbox("L2 (Subject)", options=l2_opts, index=idx_l2, key=f"l2_{folder_name}")
                            
                            if sel_l2 and sel_l2 != "None":
                                l3_opts = ["None"] + OBJECT_HIERARCHY[sel_l1][sel_l2] if OBJECT_HIERARCHY[sel_l1][sel_l2] else []
                                if len(l3_opts) > 1:
                                    idx_l3 = l3_opts.index(def_l3) if def_l3 in l3_opts else 0
                                    sel_l3 = st.selectbox("L3 (Detail)", options=l3_opts, index=idx_l3, key=f"l3_{folder_name}")
                                else:
                                    sel_l3 = None
                            else:
                                sel_l3 = None
                        else:
                            sel_l2 = "None"
                            sel_l3 = None
                            
                        final_obj = sel_l3 if sel_l3 and sel_l3 != "None" else (sel_l2 if sel_l2 and sel_l2 != "None" else sel_l1)

                    with cfg2:
                        st.caption("🎭 Action & Emotion")
                        idx_act = ACTION_OPTIONS.index(s_act) if s_act in ACTION_OPTIONS else 0
                        sel_act = st.selectbox("Action", options=ACTION_OPTIONS, index=idx_act, key=f"act_{folder_name}")
                        
                        idx_emo = EMOTION_OPTIONS.index(s_emo) if s_emo in EMOTION_OPTIONS else 0
                        sel_emo = st.selectbox("Emotion", options=EMOTION_OPTIONS, index=idx_emo, key=f"emo_{folder_name}")

                    with cfg3:
                        st.caption("🎨 Styles")
                        idx_s1 = STYLES.index(s_s1) if s_s1 in STYLES else 0
                        sel_s1 = st.selectbox("Style 1", options=STYLES, index=idx_s1, key=f"s1_{folder_name}")
                        
                        s2_opts = [s for s in STYLES if s != sel_s1 or s == "None"]
                        idx_s2 = s2_opts.index(s_s2) if s_s2 in s2_opts else 0
                        sel_s2 = st.selectbox("Style 2", options=s2_opts, index=idx_s2, key=f"s2_{folder_name}")
                        
                    folder_configs[folder_name] = {
                        "obj": final_obj,
                        "act": sel_act if sel_act != "None" else "None",
                        "emo": sel_emo if sel_emo != "None" else "None",
                        "s1": str(sel_s1) if sel_s1 else "None",
                        "s2": str(sel_s2) if sel_s2 else "None"
                    }
                
    if not folders_to_process: st.error("No valid image files found.")
elif root_dir:
    st.error("Invalid path.")

st.divider()

st.subheader("2. Batch Export")
st.info("The configuration set above will be applied to all natural-sorted files in their respective folders.")

if folders_to_process:
    total_files_to_process = sum(len(files) for files in folders_to_process.values())
    
    if st.button(f"🚀 Export Tags for {total_files_to_process} Files", type="primary", use_container_width=True):
        
        my_bar = st.progress(0, text="Assembling final data...")
        results = []
        current_file_idx = 0
        
        for folder_name, file_paths in folders_to_process.items():
            f_obj = folder_configs[folder_name]["obj"]
            f_act = folder_configs[folder_name]["act"]
            f_emo = folder_configs[folder_name]["emo"]
            f_s1 = folder_configs[folder_name]["s1"]
            f_s2 = folder_configs[folder_name]["s2"]
            
            folder_hashtag = folder_name.replace(" ", "")
            
            for file_path in file_paths:
                file_basename = os.path.basename(file_path)
                auto_type = detect_media_type_local(file_path)
                
                tags = [folder_hashtag, f_obj, f_act, f_emo, auto_type, f_s1, f_s2]
                valid_tags = [f"#{str(t).strip()}" for t in tags if t and str(t).strip() and str(t).strip() != "None"]
                hashtag_str = " ".join(valid_tags)
                
                results.append({
                    "Folder Name": folder_name,
                    "File Name": file_basename,
                    "Object": f_obj if f_obj != "None" else "",
                    "Action": f_act if f_act != "None" else "",
                    "Emotion": f_emo if f_emo != "None" else "",
                    "Type": auto_type,
                    "Style1": f_s1 if f_s1 != "None" else "",
                    "Style2": f_s2 if f_s2 != "None" else "",
                    "Generated Hashtags": hashtag_str
                })
                current_file_idx += 1
                my_bar.progress(current_file_idx / total_files_to_process, text=f"Processing {folder_name}...")
                
        my_bar.empty()
        st.success(f"🎉 Successfully exported data for {total_files_to_process} files!")
        
        df_results = pd.DataFrame(results)
        st.dataframe(df_results, use_container_width=True, hide_index=True)
        
        csv_data = convert_df_to_csv(df_results)
        st.download_button(
            label="📥 Download Results (CSV)",
            data=csv_data,
            file_name="ai_pro_hashtags.csv",
            mime="text/csv",
            type="primary"
        )
