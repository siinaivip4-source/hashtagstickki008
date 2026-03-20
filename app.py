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
st.set_page_config(page_title="AI Pro ZIP Batch Hashtag", page_icon="🚀", layout="wide")

# ===== 0. BẢO MẬT FIREBASE & COOKIE (Giữ nguyên phong độ) =====
cookie_manager = stx.CookieManager()

@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            key_dict = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        except:
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
            client_id = cookie_manager.get(cookie="SIIN_DEVICE_ID")
            if not client_id:
                client_id = str(uuid.uuid4())
                cookie_manager.set("SIIN_DEVICE_ID", client_id, max_age=31536000)
            st.info(f"💻 Mã trình duyệt: `{str(client_id)[:8]}...`")
            entered_key = st.text_input("🔑 Nhập License Key:", type="password")
            if st.button("🔓 Mở Khóa", use_container_width=True, type="primary"):
                key_ref = db.collection("keys").document(entered_key.strip())
                key_doc = key_ref.get()
                if key_doc.exists:
                    key_data = key_doc.to_dict()
                    if key_data.get("device_id", "") in ["", client_id]:
                        key_ref.update({"device_id": client_id})
                        st.session_state["authenticated"] = True
                        st.session_state["user_name"] = key_data.get("owner_name", "VIP")
                        st.rerun()
                    else: st.error("🚫 Key đã dùng trên máy khác!")
                else: st.error("❌ Key không tồn tại!")
        st.stop()

check_license_key()

# ===== 1. AI & LOGIC XỬ LÝ ZIP =====
MODEL_ID = "openai/clip-vit-large-patch14"

@st.cache_resource
def load_clip_model():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        proc = CLIPProcessor.from_pretrained(MODEL_ID)
        mod = CLIPModel.from_pretrained(MODEL_ID).to(dev)
        return proc, mod, dev
    except: return None, None, "cpu"

@st.cache_data
def get_vocabs():
    # (Dữ liệu Dictionary rút gọn để tiết kiệm không gian, huynh giữ nguyên bản cũ nhé)
    obj_l = ["Cat", "Dog", "Anime", "Food", "Car"] # Ví dụ rút gọn
    act_l = ["Laugh", "Run", "Sleep", "Talk"]
    emo_l = ["Happy", "Sad", "Angry"]
    return obj_l, act_l, emo_l

def run_ai(image, labels, proc, mod, dev):
    inputs = proc(text=labels, images=image, return_tensors="pt", padding=True).to(dev)
    with torch.no_grad():
        probs = mod(**inputs).logits_per_image.softmax(dim=1)
    return labels[probs.argmax().item()]

# Hàm soi ảnh từ ZIP
def analyze_zip_member(zip_file, member_path, processor, model, device, vocabs):
    with zip_file.open(member_path) as f:
        img = PILImage.open(io.BytesIO(f.read())).convert("RGB")
        obj_l, act_l, emo_l = vocabs
        s_obj = run_classification(img, obj_l, processor, model, device) # Giả định hàm run_classification có sẵn
        # ... logic dự đoán tương tự bản cũ
        return s_obj, "None", "None", "None", "None" 

# ===== MAIN UI =====
st.title("🔥 AI Pro Multi-Folder ZIP Generator")
user_name = st.session_state.get("user_name")
st.markdown(f"👤 **User:** `{user_name}` | 🛠️ **Mode:** Batch ZIP Processing")

with st.sidebar:
    if st.button("🔄 Refresh"): st.rerun()
    proc, mod, dev = load_clip_model()
    st.session_state['ai_model'] = (proc, mod, dev)
    st.success(f"AI: {dev.upper()}")

# --- STEP 1: UPLOAD ZIP ---
st.subheader("1. Tải lên tệp ZIP (Chứa nhiều Folder con)")
zip_upload = st.file_uploader("Chọn file .ZIP của bạn:", type=["zip"])

if zip_upload:
    with zipfile.ZipFile(zip_upload) as z:
        # Lọc danh sách file ảnh trong ZIP và nhóm theo Folder
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
        all_members = [m for m in z.namelist() if m.lower().endswith(valid_exts) and not m.startswith('__MACOSX')]
        
        folder_groups = {}
        for m in all_members:
            folder_name = os.path.dirname(m) or "Root"
            if folder_name not in folder_groups: folder_groups[folder_name] = []
            folder_groups[folder_name].append(m)
            
        st.success(f"📦 Đã tìm thấy {len(folder_groups)} thư mục trong file ZIP!")

        # --- STEP 2: CONFIG CHO TỪNG FOLDER ---
        st.subheader("2. Cấu hình Hashtag cho từng Folder")
        final_configs = {}
        
        for f_name, f_files in folder_groups.items():
            with st.expander(f"📂 Folder: {f_name} ({len(f_files)} ảnh)", expanded=False):
                col_pre, col_sel = st.columns([1, 3])
                
                # Hiển thị ảnh đầu tiên làm mẫu
                with z.open(f_files[0]) as first_f:
                    img_data = first_f.read()
                    with col_pre:
                        st.image(img_data, use_container_width=True)
                
                with col_sel:
                    # Chỗ này huynh dán các Selectbox (L1, L2, Action, Emotion, Style) 
                    # giống hệt logic cũ của muội, nhưng key phải có thêm f_name
                    # Ví dụ: st.selectbox(..., key=f"l1_{f_name}")
                    c1, c2 = st.columns(2)
                    sel_obj = c1.text_input("Đối tượng chính:", value="Auto", key=f"obj_{f_name}")
                    sel_style = c2.selectbox("Style:", ["None", "Meme", "Cute"], key=f"sty_{f_name}")
                    
                    final_configs[f_name] = {"obj": sel_obj, "sty": sel_style, "files": f_files}

        # --- STEP 3: BATCH EXPORT ---
        st.divider()
        if st.button("🚀 Export All Folders", type="primary", use_container_width=True):
            all_results = []
            for f_name, cfg in final_configs.items():
                tag_folder = f_name.split('/')[-1].replace(" ", "")
                for file_path in cfg["files"]:
                    fname = file_path.split('/')[-1]
                    tags = f"#{tag_folder} #{cfg['obj']} #{cfg['sty']}".replace("#None", "").replace("#Auto", "#AI_Pending")
                    all_results.append({"Folder": f_name, "File": fname, "Hashtags": tags})
            
            df = pd.DataFrame(all_results)
            st.dataframe(df, use_container_width=True)
            st.download_button("📥 Download Toàn Bộ CSV", df.to_csv(index=False).encode('utf-8-sig'), "batch_hashtags.csv")
